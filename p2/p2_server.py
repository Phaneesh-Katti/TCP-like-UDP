import socket
import time
import json
import argparse
import os

# Constants
MSS = 1400  # Maximum Segment Size
INITIAL_CWND = MSS  # Initial congestion window size
INITIAL_SSTHRESH = 65535  # Initial slow start threshold
INITIAL_RTO = 1.0  # Initial retransmission timeout
ALPHA = 0.125  # RTT smoothing factor
BETA = 0.25  # RTT deviation factor
MIN_RTO = 0.2  # Minimum RTO value
MAX_RTO = 60.0  # Maximum RTO value

class CongestionControl:
    def __init__(self):
        self.cwnd = INITIAL_CWND
        self.ssthresh = INITIAL_SSTHRESH
        self.duplicate_ack_count = 0
        self.in_fast_recovery = False
        self.last_sent_byte = 0
        self.last_acked_byte = 0
        self.rtt_estimator = RTTEstimator()
        self.unacked_packets = {}  # {seq_num: (packet_data, timestamp)}
        self.packets_in_flight = 0
        print(f"Initialized CongestionControl with cwnd={self.cwnd}, ssthresh={self.ssthresh}")

    def on_ack_received(self, ack_num):
        """Handle received ACK"""
        print(f"ACK received: {ack_num}")
        if ack_num <= self.last_acked_byte:
            print(f"Duplicate ACK detected (ACK: {ack_num}), increasing duplicate count")
            self.duplicate_ack_count += 1
            if self.duplicate_ack_count == 3:
                print(f"Triple duplicate ACK received, triggering fast retransmit")
                self.on_triple_duplicate_ack()
        else:
            print(f"New ACK received (ACK: {ack_num})")
            self.last_acked_byte = ack_num
            self.duplicate_ack_count = 0
            
            if self.in_fast_recovery:
                print(f"Exiting fast recovery mode")
                self.cwnd = self.ssthresh
                self.in_fast_recovery = False
            else:
                # Normal ACK processing
                if self.cwnd < self.ssthresh:
                    # Slow start
                    self.cwnd += MSS
                    print(f"Slow start: cwnd increased to {self.cwnd}")
                else:
                    # Congestion avoidance
                    increment = MSS * (MSS / self.cwnd)
                    self.cwnd += increment
                    print(f"Congestion avoidance: cwnd increased to {self.cwnd:.2f}")

    def on_triple_duplicate_ack(self):
        """Handle triple duplicate ACK"""
        print(f"Handling triple duplicate ACK: Reducing ssthresh and cwnd")
        self.ssthresh = max(self.cwnd // 2, 2 * MSS)
        self.cwnd = self.ssthresh + 3 * MSS
        self.in_fast_recovery = True
        print(f"ssthresh set to {self.ssthresh}, cwnd set to {self.cwnd}")

    def on_timeout(self):
        """Handle timeout"""
        print(f"Timeout detected: Reducing ssthresh and resetting cwnd")
        self.ssthresh = max(self.cwnd // 2, 2 * MSS)
        self.cwnd = MSS
        self.in_fast_recovery = False
        self.duplicate_ack_count = 0
        print(f"ssthresh set to {self.ssthresh}, cwnd reset to {self.cwnd}")

class RTTEstimator:
    def __init__(self):
        self.srtt = None
        self.rttvar = None
        self.rto = INITIAL_RTO
        print(f"RTTEstimator initialized with RTO={self.rto}")

    def update(self, measured_rtt):
        """Update RTT estimates"""
        print(f"RTT measured: {measured_rtt:.4f} seconds")
        if self.srtt is None:
            self.srtt = measured_rtt
            self.rttvar = measured_rtt / 2
        else:
            self.rttvar = (1 - BETA) * self.rttvar + BETA * abs(self.srtt - measured_rtt)
            self.srtt = (1 - ALPHA) * self.srtt + ALPHA * measured_rtt
        
        self.rto = self.srtt + 4 * self.rttvar
        self.rto = min(max(self.rto, MIN_RTO), MAX_RTO)
        print(f"Updated SRTT={self.srtt:.4f}, RTTVAR={self.rttvar:.4f}, RTO={self.rto:.4f}")

def send_file(server_ip, server_port):
    """Send file using TCP Reno-like congestion control"""
    print(f"Server starting on {server_ip}:{server_port}")
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((server_ip, server_port))
    print(f"Server listening on {server_ip}:{server_port}")
    
    cc = CongestionControl()
    file_path = "input.txt"
    
    try:
        # Wait for initial client connection
        print(f"Waiting for client connection...")
        data, client_address = server_socket.recvfrom(1024)
        print(f"Client connected from {client_address}")
        
        file_size = os.path.getsize(file_path)
        print(f"File to send: {file_path} ({file_size} bytes)")
        
        with open(file_path, 'rb') as file:
            while True:
                # Calculate available window
                available_window = min(cc.cwnd, INITIAL_SSTHRESH) - cc.packets_in_flight
                print(f"\nAvailable window: {available_window} bytes, cwnd={cc.cwnd}, in-flight={cc.packets_in_flight}")
                
                # Send data while window allows
                while available_window >= MSS and cc.last_sent_byte < file_size:
                    file.seek(cc.last_sent_byte)
                    data = file.read(min(MSS, available_window))
                    if not data:
                        break
                    
                    packet = create_packet(cc.last_sent_byte, data)
                    print(f"Sending packet with sequence number {cc.last_sent_byte} (size={len(data)})")
                    server_socket.sendto(packet, client_address)
                    
                    packet_size = len(data)
                    cc.unacked_packets[cc.last_sent_byte] = (data, time.time())
                    cc.last_sent_byte += packet_size
                    cc.packets_in_flight += packet_size
                    available_window -= packet_size
                
                # Handle ACKs and timeouts
                try:
                    server_socket.settimeout(cc.rtt_estimator.rto)
                    print(f"Waiting for ACK with timeout of {cc.rtt_estimator.rto} seconds...")
                    ack_packet, _ = server_socket.recvfrom(1024)
                    ack_data = parse_ack(ack_packet)
                    
                    if ack_data:
                        ack_num = ack_data['ack_num']
                        print(f"ACK received for sequence number {ack_num}")
                        
                        # Update RTT if possible
                        if ack_num in cc.unacked_packets:
                            send_time = cc.unacked_packets[ack_num][1]
                            rtt = time.time() - send_time
                            cc.rtt_estimator.update(rtt)
                        
                        # Process ACK
                        cc.on_ack_received(ack_num)
                        
                        # Remove acknowledged packets
                        keys_to_remove = [k for k in cc.unacked_packets.keys() if k <= ack_num]
                        for k in keys_to_remove:
                            packet_size = len(cc.unacked_packets[k][0])
                            cc.packets_in_flight -= packet_size
                            del cc.unacked_packets[k]
                            print(f"Packet with sequence number {k} acknowledged and removed from unacked list")
                
                except socket.timeout:
                    print("Timeout waiting for ACK, triggering timeout mechanism")
                    cc.on_timeout()
                    if cc.unacked_packets:
                        first_unacked = min(cc.unacked_packets.keys())
                        data = cc.unacked_packets[first_unacked][0]
                        print(f"Retransmitting packet with sequence number {first_unacked}")
                        packet = create_packet(first_unacked, data)
                        server_socket.sendto(packet, client_address)
                
                # Check if transfer is complete
                if not cc.unacked_packets and cc.last_sent_byte >= file_size:
                    print("All packets acknowledged, sending end marker")
                    end_packet = create_packet(-1, b'')
                    server_socket.sendto(end_packet, client_address)
                    break
    
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Closing server socket")
        server_socket.close()

def create_packet(seq_num, data):
    """Create packet with sequence number and data"""
    packet = {
        'seq_num': seq_num,
        'data': data.decode('latin1') if isinstance(data, bytes) else data
    }
    return json.dumps(packet).encode()

def parse_ack(ack_packet):
    """Parse acknowledgment packet"""
    try:
        return json.loads(ack_packet.decode())
    except json.JSONDecodeError:
        print("Error decoding ACK packet")
        return None

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description='TCP Reno-like UDP server')
#     parser.add_argument('server_ip', help='Server IP address')
#     parser.add_argument('server_port', type=int, help='Server port number')
    
#     args = parser.parse_args()
#     print(f"Starting TCP Reno-like UDP server")
#     send_file(args.server_ip, args.server_port)

parser = argparse.ArgumentParser(description='TCP Reno-like UDP server')
parser.add_argument('server_ip', help='Server IP address')
parser.add_argument('server_port', type=int, help='Server port number')

args = parser.parse_args()
print(f"Starting TCP Reno-like UDP server")
send_file(args.server_ip, args.server_port)

# import socket
# import time
# import json
# import argparse
# import os

# # Constants
# MSS = 1400  # Maximum Segment Size
# INITIAL_CWND = MSS  # Initial congestion window size
# INITIAL_SSTHRESH = 65535  # Initial slow start threshold
# INITIAL_RTO = 1.0  # Initial retransmission timeout
# ALPHA = 0.125  # RTT smoothing factor
# BETA = 0.25  # RTT deviation factor
# MIN_RTO = 0.2  # Minimum RTO value
# MAX_RTO = 60.0  # Maximum RTO value

# class CongestionControl:
#     def __init__(self):
#         self.cwnd = INITIAL_CWND
#         self.ssthresh = INITIAL_SSTHRESH
#         self.duplicate_ack_count = 0
#         self.in_fast_recovery = False
#         self.last_sent_byte = 0
#         self.last_acked_byte = 0
#         self.rtt_estimator = RTTEstimator()
#         self.unacked_packets = {}  # {seq_num: (packet_data, timestamp)}
#         self.packets_in_flight = 0
        
#     def on_ack_received(self, ack_num):
#         """Handle received ACK"""
#         if ack_num <= self.last_acked_byte:
#             self.duplicate_ack_count += 1
#             if self.duplicate_ack_count == 3:
#                 self.on_triple_duplicate_ack()
#         else:
#             # New ACK
#             self.last_acked_byte = ack_num
#             self.duplicate_ack_count = 0
            
#             if self.in_fast_recovery:
#                 # Exit fast recovery
#                 self.cwnd = self.ssthresh
#                 self.in_fast_recovery = False
#             else:
#                 # Normal ACK processing
#                 if self.cwnd < self.ssthresh:
#                     # Slow start
#                     self.cwnd += MSS
#                 else:
#                     # Congestion avoidance
#                     self.cwnd += MSS * (MSS / self.cwnd)
    
#     def on_triple_duplicate_ack(self):
#         """Handle triple duplicate ACK"""
#         self.ssthresh = max(self.cwnd // 2, 2 * MSS)
#         self.cwnd = self.ssthresh + 3 * MSS
#         self.in_fast_recovery = True
    
#     def on_timeout(self):
#         """Handle timeout"""
#         self.ssthresh = max(self.cwnd // 2, 2 * MSS)
#         self.cwnd = MSS
#         self.in_fast_recovery = False
#         self.duplicate_ack_count = 0

# class RTTEstimator:
#     def __init__(self):
#         self.srtt = None
#         self.rttvar = None
#         self.rto = INITIAL_RTO
    
#     def update(self, measured_rtt):
#         """Update RTT estimates"""
#         if self.srtt is None:
#             self.srtt = measured_rtt
#             self.rttvar = measured_rtt / 2
#         else:
#             self.rttvar = (1 - BETA) * self.rttvar + BETA * abs(self.srtt - measured_rtt)
#             self.srtt = (1 - ALPHA) * self.srtt + ALPHA * measured_rtt
        
#         self.rto = self.srtt + 4 * self.rttvar
#         self.rto = min(max(self.rto, MIN_RTO), MAX_RTO)

# def send_file(server_ip, server_port):
#     """Send file using TCP Reno-like congestion control"""
#     server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     server_socket.bind((server_ip, server_port))
#     print(f"Server listening on {server_ip}:{server_port}")
    
#     cc = CongestionControl()
#     file_path = "input.txt"
    
#     try:
#         # Wait for initial client connection
#         data, client_address = server_socket.recvfrom(1024)
#         print(f"Client connected from {client_address}")
        
#         file_size = os.path.getsize(file_path)
#         with open(file_path, 'rb') as file:
#             while True:
#                 # Calculate available window
#                 available_window = min(cc.cwnd, INITIAL_SSTHRESH) - cc.packets_in_flight
                
#                 # Send data while window allows
#                 while available_window >= MSS and cc.last_sent_byte < file_size:
#                     # Read and send data
#                     file.seek(cc.last_sent_byte)
#                     data = file.read(min(MSS, available_window))
#                     if not data:
#                         break
                    
#                     packet = create_packet(cc.last_sent_byte, data)
#                     server_socket.sendto(packet, client_address)
                    
#                     # Update state
#                     packet_size = len(data)
#                     cc.unacked_packets[cc.last_sent_byte] = (data, time.time())
#                     cc.last_sent_byte += packet_size
#                     cc.packets_in_flight += packet_size
#                     available_window -= packet_size
                
#                 # Handle ACKs and timeouts
#                 try:
#                     server_socket.settimeout(cc.rtt_estimator.rto)
#                     ack_packet, _ = server_socket.recvfrom(1024)
#                     ack_data = parse_ack(ack_packet)
                    
#                     if ack_data:
#                         ack_num = ack_data['ack_num']
#                         # Update RTT if possible
#                         if ack_num in cc.unacked_packets:
#                             send_time = cc.unacked_packets[ack_num][1]
#                             rtt = time.time() - send_time
#                             cc.rtt_estimator.update(rtt)
                        
#                         # Process ACK
#                         cc.on_ack_received(ack_num)
                        
#                         # Remove acknowledged packets
#                         keys_to_remove = [k for k in cc.unacked_packets.keys() if k <= ack_num]
#                         for k in keys_to_remove:
#                             packet_size = len(cc.unacked_packets[k][0])
#                             cc.packets_in_flight -= packet_size
#                             del cc.unacked_packets[k]
                
#                 except socket.timeout:
#                     cc.on_timeout()
#                     # Retransmit first unacked packet
#                     if cc.unacked_packets:
#                         first_unacked = min(cc.unacked_packets.keys())
#                         data = cc.unacked_packets[first_unacked][0]
#                         packet = create_packet(first_unacked, data)
#                         server_socket.sendto(packet, client_address)
                
#                 # Check if transfer is complete
#                 if not cc.unacked_packets and cc.last_sent_byte >= file_size:
#                     # Send end marker
#                     end_packet = create_packet(-1, b'')
#                     server_socket.sendto(end_packet, client_address)
#                     break
    
#     except Exception as e:
#         print(f"Error: {e}")
#     finally:
#         server_socket.close()

# def create_packet(seq_num, data):
#     """Create packet with sequence number and data"""
#     packet = {
#         'seq_num': seq_num,
#         'data': data.decode('latin1') if isinstance(data, bytes) else data
#     }
#     return json.dumps(packet).encode()

# def parse_ack(ack_packet):
#     """Parse acknowledgment packet"""
#     try:
#         return json.loads(ack_packet.decode())
#     except json.JSONDecodeError:
#         print("Error decoding ACK packet")
#         return None

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description='TCP Reno-like UDP server')
#     parser.add_argument('server_ip', help='Server IP address')
#     parser.add_argument('server_port', type=int, help='Server port number')
    
#     args = parser.parse_args()
#     send_file(args.server_ip, args.server_port)


# not sending end of file -1 sequence number for some reason
# import socket
# import time
# import json
# import argparse
# import os

# # Constants
# MSS = 1400  # Maximum Segment Size
# INITIAL_SSTHRESH = 64 * MSS  # Initial slow start threshold
# WINDOW_SIZE = 5  # Number of packets in flight (initial)
# DUP_ACK_THRESHOLD = 3  # Threshold for duplicate ACKs to trigger fast recovery
# FILE_PATH = "input.txt"  # Example file path

# # RTT estimation parameters
# ALPHA = 0.125
# BETA = 0.25
# INITIAL_TIMEOUT = 1.0  # Initial timeout before RTT measurements
# EstimatedRTT = INITIAL_TIMEOUT  # Initialize EstimatedRTT with a default value
# DevRTT = 0.0  # Initialize deviation RTT

# def send_file(server_ip, server_port, enable_fast_recovery):
#     global EstimatedRTT, DevRTT

#     # Initialize UDP socket
#     server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     server_socket.bind((server_ip, server_port))

#     print(f"Server listening on {server_ip}:{server_port}")

#     client_address = None
#     file_path = FILE_PATH  # Predefined file name

#     try:
#         # Determine the number of packets needed
#         file_size = os.path.getsize(file_path)
#         expected_packets_count = (file_size + MSS - 1) // MSS  # Round up division

#         with open(file_path, 'rb') as file:
#             seq_num = 0
#             window_base = 0
#             unacked_packets = {}
#             last_ack_received = -1
#             TimeoutInterval = INITIAL_TIMEOUT
#             duplicate_ack_count = 0  # Initialize duplicate ACK counter
#             cwnd = 1 * MSS  # Congestion window starts at 1 MSS
#             ssthresh = INITIAL_SSTHRESH

#             # Wait for client connection
#             while client_address is None:
#                 print("Waiting for client connection...")
#                 data, client_address = server_socket.recvfrom(1024)  # Receive initial connection request
#                 print(f"Connection established with client {client_address}")

#             # Now we can start sending packets
#             while True:
#                 # Window-based sending logic
#                 while len(unacked_packets) < cwnd / MSS and seq_num < expected_packets_count:
#                     chunk = file.read(MSS)
#                     if not chunk:
#                         break  # End of file

#                     # Create and send the packet
#                     packet = create_packet(seq_num, chunk)
#                     server_socket.sendto(packet, client_address)
#                     unacked_packets[seq_num] = (packet, time.time())  # Track sent packets with timestamp
#                     print(f"Sent packet {seq_num}")
#                     seq_num += 1

#                 if not unacked_packets and not chunk:
#                     # If there are no unacknowledged packets and we reached EOF, break the loop
#                     break

#                 # Wait for ACKs and retransmit if needed
#                 try:
#                     server_socket.settimeout(TimeoutInterval)  # Use the current timeout interval
#                     ack_packet, _ = server_socket.recvfrom(1024)

#                     print(f"Received ACK packet: {ack_packet.decode()}")  # Log received ACK packet

#                     # Validate that the ACK packet is JSON
#                     ack_seq_num = get_seq_no_from_ack_pkt(ack_packet)

#                     if ack_seq_num in unacked_packets:
#                         # Acknowledge received ACKs
#                         print(f"Received ACK for packet {ack_seq_num}")
#                         send_time = unacked_packets[ack_seq_num][1]
#                         SampleRTT = time.time() - send_time
#                         print(f"SampleRTT for packet {ack_seq_num}: {SampleRTT:.4f} seconds")

#                         # Update EstimatedRTT and DevRTT
#                         EstimatedRTT = (1 - ALPHA) * EstimatedRTT + ALPHA * SampleRTT
#                         DevRTT = (1 - BETA) * DevRTT + BETA * abs(SampleRTT - EstimatedRTT)
#                         TimeoutInterval = EstimatedRTT + 4 * DevRTT
#                         print(f"Updated TimeoutInterval: {TimeoutInterval:.4f} seconds")

#                         # Slide the window base
#                         del unacked_packets[ack_seq_num]
#                         window_base = ack_seq_num + 1
#                         last_ack_received = ack_seq_num

#                         # Handle slow start and congestion avoidance
#                         if cwnd < ssthresh:
#                             # Slow start
#                             cwnd += MSS
#                             print(f"Slow start: increased cwnd to {cwnd / MSS} MSS")
#                         else:
#                             # Congestion avoidance
#                             cwnd += MSS * (MSS / cwnd)
#                             print(f"Congestion avoidance: increased cwnd to {cwnd / MSS} MSS")

#                         duplicate_ack_count = 0  # Reset the duplicate ACK counter after receiving a new ACK

#                     elif ack_seq_num == last_ack_received:
#                         # Detect duplicate ACK
#                         duplicate_ack_count += 1
#                         print(f"Duplicate ACK detected: {duplicate_ack_count}")

#                         if duplicate_ack_count == DUP_ACK_THRESHOLD:
#                             # Fast retransmit and fast recovery
#                             print(f"Entering fast recovery. Reducing cwnd and retransmitting packet {window_base}")
#                             ssthresh = max(cwnd // 2, 1 * MSS)  # Halve the congestion window
#                             cwnd = ssthresh + 3 * MSS  # Fast recovery step
#                             retransmit_packet = unacked_packets[window_base][0]
#                             server_socket.sendto(retransmit_packet, client_address)
#                             print(f"Retransmitted packet {window_base}")
#                     else:
#                         print(f"Received unexpected ACK: {ack_seq_num}")

#                 except socket.timeout:
#                     # Timeout behavior: Retransmit all unacknowledged packets and reset cwnd
#                     print("Timeout: retransmitting all unacknowledged packets")
#                     ssthresh = max(cwnd // 2, 1 * MSS)
#                     cwnd = 1 * MSS  # Reset to slow start
#                     for seq, (pkt, _) in unacked_packets.items():
#                         server_socket.sendto(pkt, client_address)
#                         print(f"Retransmitted packet {seq}")

#             print("EOF reached, entering -1 send")
#             # Send a signal to the client that the transfer is complete
#             end_signal = json.dumps({'seq_num': -1, 'data': ''}).encode()
#             server_socket.sendto(end_signal, client_address)
#             print("File transfer complete. Sent END signal to client.")

#     except Exception as e:
#         print(f"Error: {e}")

# def create_packet(seq_num, chunk):
#     """
#     Create a packet with sequence number and chunk of data.
#     """
#     packet_data = json.dumps({'seq_num': seq_num, 'data': chunk.decode('latin1')})
#     return packet_data.encode()

# def get_seq_no_from_ack_pkt(ack_packet):
#     """
#     Extract the sequence number from an ACK packet.
#     """
#     try:
#         parsed_packet = json.loads(ack_packet.decode())
#         return parsed_packet['ack_seq']
#     except json.JSONDecodeError:
#         print("Received a malformed ACK packet")
#         return -1

# # Parse command-line arguments
# parser = argparse.ArgumentParser(description='Reliable file sender over UDP with TCP Reno congestion control.')
# parser.add_argument('server_ip', help='IP address of the server')
# parser.add_argument('server_port', type=int, help='Port number of the server')
# parser.add_argument('--fast-recovery', action='store_true', help='Enable fast recovery mode')

# args = parser.parse_args()

# # Run the server
# send_file(args.server_ip, args.server_port, args.fast_recovery)
