import socket
import argparse
import json
import time

# Constants
MSS = 1400  # Maximum Segment Size
BUFFER_SIZE = MSS + 200  # Buffer size for receiving packets

class CongestionControl:
    def __init__(self):
        self.rwnd = float('inf')  # Receive window (unlimited for this implementation)
        self.last_byte_received = -1
        self.out_of_order_packets = {}
        print("Initialized CongestionControl with unlimited receive window")

def receive_file(server_ip, server_port, output_file_path):
    """
    Receive file from server with reliability and flow control
    """
    print(f"\nInitializing client connecting to {server_ip}:{server_port}")
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(2)
    print("Socket created with 2 second timeout")
    
    server_address = (server_ip, server_port)
    cc = CongestionControl()
    
    print(f"Output will be written to: {output_file_path}")
    
    packet_buffer = {}
    expected_seq_num = 0
    
    # Initial connection
    print("Sending START signal to server...")
    client_socket.sendto(b"START", server_address)
    print("START signal sent")
    
    with open(output_file_path, 'wb') as file:
        print("Output file opened for writing")
        while True:
            try:
                print(f"\nWaiting for packet... (expecting sequence number {expected_seq_num})")
                packet, _ = client_socket.recvfrom(BUFFER_SIZE)
                packet_data = parse_packet(packet)
                
                if packet_data is None:
                    print("Received invalid packet, continuing...")
                    continue
                    
                seq_num = packet_data['seq_num']
                data = packet_data['data']
                print(f"Received packet with sequence number {seq_num}")
                
                if seq_num == -1:
                    print("\n=== File transfer complete ===")
                    break
                    
                # Handle in-order packet
                if seq_num == expected_seq_num:
                    print(f"In-order packet received (seq={seq_num})")
                    file.write(data.encode('latin1'))
                    print(f"Wrote {len(data)} bytes to file")
                    expected_seq_num += len(data)
                    
                    # Process any buffered in-order packets
                    while expected_seq_num in packet_buffer:
                        print(f"Processing buffered packet (seq={expected_seq_num})")
                        buffered_data = packet_buffer.pop(expected_seq_num)
                        file.write(buffered_data.encode('latin1'))
                        print(f"Wrote buffered data of {len(buffered_data)} bytes to file")
                        expected_seq_num += len(buffered_data)
                        
                    # Send cumulative ACK
                    print(f"Sending cumulative ACK for sequence number {expected_seq_num - 1}")
                    send_ack(client_socket, server_address, expected_seq_num - 1)
                    cc.last_byte_received = expected_seq_num - 1
                    
                # Handle out-of-order packet
                elif seq_num > expected_seq_num:
                    print(f"Out-of-order packet received (seq={seq_num}, expected={expected_seq_num})")
                    packet_buffer[seq_num] = data
                    print(f"Packet buffered. Current buffer size: {len(packet_buffer)} packets")
                    # Send duplicate ACK for the last in-order byte received
                    print(f"Sending duplicate ACK for last in-order byte {cc.last_byte_received}")
                    send_ack(client_socket, server_address, cc.last_byte_received)
                    
                # Handle duplicate packet
                else:
                    print(f"Duplicate or old packet received (seq={seq_num}, expected={expected_seq_num})")
                    # Send duplicate ACK
                    print(f"Sending duplicate ACK for sequence number {cc.last_byte_received}")
                    send_ack(client_socket, server_address, cc.last_byte_received)
                    
            except socket.timeout:
                print("\nTimeout occurred while waiting for data")
                # Send duplicate ACK on timeout
                if cc.last_byte_received >= 0:
                    print(f"Sending timeout-triggered duplicate ACK for sequence number {cc.last_byte_received}")
                    send_ack(client_socket, server_address, cc.last_byte_received)
            except Exception as e:
                print(f"\nError occurred: {e}")
                break
    
    print("\nClosing client socket")
    client_socket.close()
    print("Client socket closed")

def parse_packet(packet):
    """Parse received packet"""
    try:
        return json.loads(packet.decode())
    except json.JSONDecodeError:
        print("Error: Failed to decode packet as JSON")
        return None

def send_ack(client_socket, server_address, ack_num):
    """Send acknowledgment packet"""
    ack_packet = json.dumps({
        'ack_num': ack_num,
        'timestamp': time.time()
    }).encode()
    client_socket.sendto(ack_packet, server_address)
    print(f"Sent ACK packet: ack_num={ack_num}")

parser = argparse.ArgumentParser(description='TCP Reno-like UDP client')
parser.add_argument('server_ip', help='Server IP address')
parser.add_argument('server_port', type=int, help='Server port number')
parser.add_argument('--pref_outfile', type=str, default='received_file.txt', help='Output file path prefix')

args = parser.parse_args()
print(f"\n=== Starting TCP Reno-like UDP Client ===")
print(f"Server IP: {args.server_ip}")
print(f"Server Port: {args.server_port}")

# Construct the output file name based on the prefix
output_file_path = f"{args.pref_outfile}received_file.txt"
print(f"Output File: {output_file_path}")

receive_file(args.server_ip, args.server_port, output_file_path)

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description='TCP Reno-like UDP client')
#     parser.add_argument('server_ip', help='Server IP address')
#     parser.add_argument('server_port', type=int, help='Server port number')
#     parser.add_argument('--pref_outfile', type=str, default='received_file.txt', help='Output file path prefix')

#     args = parser.parse_args()
#     print(f"\n=== Starting TCP Reno-like UDP Client ===")
#     print(f"Server IP: {args.server_ip}")
#     print(f"Server Port: {args.server_port}")

#     # Construct the output file name based on the prefix
#     output_file_path = f"{args.pref_outfile}received_file.txt"
#     print(f"Output File: {output_file_path}")
    
#     receive_file(args.server_ip, args.server_port, output_file_path)



# code works properly but writes by default to received file txt need to update that
# import socket
# import argparse
# import json
# import time

# # Constants
# MSS = 1400  # Maximum Segment Size
# BUFFER_SIZE = MSS + 200  # Buffer size for receiving packets

# class CongestionControl:
#     def __init__(self):
#         self.rwnd = float('inf')  # Receive window (unlimited for this implementation)
#         self.last_byte_received = -1
#         self.out_of_order_packets = {}
#         print("Initialized CongestionControl with unlimited receive window")

# def receive_file(server_ip, server_port):
#     """
#     Receive file from server with reliability and flow control
#     """
#     print(f"\nInitializing client connecting to {server_ip}:{server_port}")
#     client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     client_socket.settimeout(2)
#     print("Socket created with 2 second timeout")
    
#     server_address = (server_ip, server_port)
#     cc = CongestionControl()
    
#     output_file_path = "received_file.txt"
#     print(f"Output will be written to: {output_file_path}")
    
#     packet_buffer = {}
#     expected_seq_num = 0
    
#     # Initial connection
#     print("Sending START signal to server...")
#     client_socket.sendto(b"START", server_address)
#     print("START signal sent")
    
#     with open(output_file_path, 'wb') as file:
#         print("Output file opened for writing")
#         while True:
#             try:
#                 print(f"\nWaiting for packet... (expecting sequence number {expected_seq_num})")
#                 packet, _ = client_socket.recvfrom(BUFFER_SIZE)
#                 packet_data = parse_packet(packet)
                
#                 if packet_data is None:
#                     print("Received invalid packet, continuing...")
#                     continue
                    
#                 seq_num = packet_data['seq_num']
#                 data = packet_data['data']
#                 print(f"Received packet with sequence number {seq_num}")
                
#                 if seq_num == -1:
#                     print("\n=== File transfer complete ===")
#                     break
                    
#                 # Handle in-order packet
#                 if seq_num == expected_seq_num:
#                     print(f"In-order packet received (seq={seq_num})")
#                     file.write(data.encode('latin1'))
#                     print(f"Wrote {len(data)} bytes to file")
#                     expected_seq_num += len(data)
                    
#                     # Process any buffered in-order packets
#                     while expected_seq_num in packet_buffer:
#                         print(f"Processing buffered packet (seq={expected_seq_num})")
#                         buffered_data = packet_buffer.pop(expected_seq_num)
#                         file.write(buffered_data.encode('latin1'))
#                         print(f"Wrote buffered data of {len(buffered_data)} bytes to file")
#                         expected_seq_num += len(buffered_data)
                        
#                     # Send cumulative ACK
#                     print(f"Sending cumulative ACK for sequence number {expected_seq_num - 1}")
#                     send_ack(client_socket, server_address, expected_seq_num - 1)
#                     cc.last_byte_received = expected_seq_num - 1
                    
#                 # Handle out-of-order packet
#                 elif seq_num > expected_seq_num:
#                     print(f"Out-of-order packet received (seq={seq_num}, expected={expected_seq_num})")
#                     packet_buffer[seq_num] = data
#                     print(f"Packet buffered. Current buffer size: {len(packet_buffer)} packets")
#                     # Send duplicate ACK for the last in-order byte received
#                     print(f"Sending duplicate ACK for last in-order byte {cc.last_byte_received}")
#                     send_ack(client_socket, server_address, cc.last_byte_received)
                    
#                 # Handle duplicate packet
#                 else:
#                     print(f"Duplicate or old packet received (seq={seq_num}, expected={expected_seq_num})")
#                     # Send duplicate ACK
#                     print(f"Sending duplicate ACK for sequence number {cc.last_byte_received}")
#                     send_ack(client_socket, server_address, cc.last_byte_received)
                    
#             except socket.timeout:
#                 print("\nTimeout occurred while waiting for data")
#                 # Send duplicate ACK on timeout
#                 if cc.last_byte_received >= 0:
#                     print(f"Sending timeout-triggered duplicate ACK for sequence number {cc.last_byte_received}")
#                     send_ack(client_socket, server_address, cc.last_byte_received)
#             except Exception as e:
#                 print(f"\nError occurred: {e}")
#                 break
    
#     print("\nClosing client socket")
#     client_socket.close()
#     print("Client socket closed")

# def parse_packet(packet):
#     """Parse received packet"""
#     try:
#         return json.loads(packet.decode())
#     except json.JSONDecodeError:
#         print("Error: Failed to decode packet as JSON")
#         return None

# def send_ack(client_socket, server_address, ack_num):
#     """Send acknowledgment packet"""
#     ack_packet = json.dumps({
#         'ack_num': ack_num,
#         'timestamp': time.time()
#     }).encode()
#     client_socket.sendto(ack_packet, server_address)
#     print(f"Sent ACK packet: ack_num={ack_num}")

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description='TCP Reno-like UDP client')
#     parser.add_argument('server_ip', help='Server IP address')
#     parser.add_argument('server_port', type=int, help='Server port number')
    
#     args = parser.parse_args()
#     print(f"\n=== Starting TCP Reno-like UDP Client ===")
#     print(f"Server IP: {args.server_ip}")
#     print(f"Server Port: {args.server_port}")
#     receive_file(args.server_ip, args.server_port)

# import socket
# import argparse
# import json
# import time

# # Constants
# MSS = 1400  # Maximum Segment Size
# BUFFER_SIZE = MSS + 200  # Buffer size for receiving packets

# class CongestionControl:
#     def __init__(self):
#         self.rwnd = float('inf')  # Receive window (unlimited for this implementation)
#         self.last_byte_received = -1
#         self.out_of_order_packets = {}

# def receive_file(server_ip, server_port):
#     """
#     Receive file from server with reliability and flow control
#     """
#     client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     client_socket.settimeout(2)
#     server_address = (server_ip, server_port)
#     cc = CongestionControl()
    
#     output_file_path = "received_file.txt"
#     packet_buffer = {}
#     expected_seq_num = 0
    
#     # Initial connection
#     client_socket.sendto(b"START", server_address)
    
#     with open(output_file_path, 'wb') as file:
#         while True:
#             try:
#                 packet, _ = client_socket.recvfrom(BUFFER_SIZE)
#                 packet_data = parse_packet(packet)
                
#                 if packet_data is None:
#                     continue
                    
#                 seq_num = packet_data['seq_num']
#                 data = packet_data['data']
                
#                 if seq_num == -1:  # End of transmission
#                     print("File transfer complete")
#                     break
                    
#                 # Handle in-order packet
#                 if seq_num == expected_seq_num:
#                     file.write(data.encode('latin1'))
#                     expected_seq_num += len(data)
                    
#                     # Process any buffered in-order packets
#                     while expected_seq_num in packet_buffer:
#                         buffered_data = packet_buffer.pop(expected_seq_num)
#                         file.write(buffered_data.encode('latin1'))
#                         expected_seq_num += len(buffered_data)
                        
#                     # Send cumulative ACK
#                     send_ack(client_socket, server_address, expected_seq_num - 1)
#                     cc.last_byte_received = expected_seq_num - 1
                    
#                 # Handle out-of-order packet
#                 elif seq_num > expected_seq_num:
#                     packet_buffer[seq_num] = data
#                     # Send duplicate ACK for the last in-order byte received
#                     send_ack(client_socket, server_address, cc.last_byte_received)
                    
#                 # Handle duplicate packet
#                 else:
#                     # Send duplicate ACK
#                     send_ack(client_socket, server_address, cc.last_byte_received)
                    
#             except socket.timeout:
#                 print("Timeout waiting for data")
#                 # Send duplicate ACK on timeout
#                 if cc.last_byte_received >= 0:
#                     send_ack(client_socket, server_address, cc.last_byte_received)
#             except Exception as e:
#                 print(f"Error: {e}")
#                 break
    
#     client_socket.close()

# def parse_packet(packet):
#     """Parse received packet"""
#     try:
#         return json.loads(packet.decode())
#     except json.JSONDecodeError:
#         print("Error decoding packet")
#         return None

# def send_ack(client_socket, server_address, ack_num):
#     """Send acknowledgment packet"""
#     ack_packet = json.dumps({
#         'ack_num': ack_num,
#         'timestamp': time.time()
#     }).encode()
#     client_socket.sendto(ack_packet, server_address)

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description='TCP Reno-like UDP client')
#     parser.add_argument('server_ip', help='Server IP address')
#     parser.add_argument('server_port', type=int, help='Server port number')
    
#     args = parser.parse_args()
#     receive_file(args.server_ip, args.server_port)

