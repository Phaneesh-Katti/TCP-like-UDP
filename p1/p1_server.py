import socket
import time
import json
import argparse
import os

# Constants
MSS = 1400  # Maximum Segment Size
WINDOW_SIZE = 5  # Number of packets in flight
DUP_ACK_THRESHOLD = 3  # Threshold for duplicate ACKs to trigger fast recovery
FILE_PATH = "input.txt"  # Example file path

# RTT estimation parameters
ALPHA = 0.125
BETA = 0.25
INITIAL_TIMEOUT = 1.0  # Initial timeout before RTT measurements
EstimatedRTT = INITIAL_TIMEOUT  # Initialize EstimatedRTT with a default value
DevRTT = 0.0  # Initialize deviation RTT

def send_file(server_ip, server_port, enable_fast_recovery):
    global EstimatedRTT, DevRTT

    # Initialize UDP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((server_ip, server_port))

    print(f"Server listening on {server_ip}:{server_port}")

    client_address = None
    file_path = FILE_PATH  # Predefined file name

    try:
        # Determine the number of packets needed
        file_size = os.path.getsize(file_path)
        expected_packets_count = (file_size + MSS - 1) // MSS  # Round up division

        with open(file_path, 'rb') as file:
            seq_num = 0
            window_base = 0
            unacked_packets = {}
            last_ack_received = -1
            TimeoutInterval = INITIAL_TIMEOUT
            duplicate_ack_count = 0  # Initialize duplicate ACK counter

            # Wait for client connection
            while client_address is None:
                print("Waiting for client connection...")
                data, client_address = server_socket.recvfrom(1024)  # Receive initial connection request
                print(f"Connection established with client {client_address}")

            # Now we can start sending packets
            while True:
                # Window-based sending logic
                while len(unacked_packets) < WINDOW_SIZE and seq_num < window_base + WINDOW_SIZE:
                    chunk = file.read(MSS)
                    if not chunk:
                        break  # End of file

                    # Create and send the packet
                    packet = create_packet(seq_num, chunk)
                    server_socket.sendto(packet, client_address)
                    unacked_packets[seq_num] = (packet, time.time())  # Track sent packets with timestamp
                    print(f"Sent packet {seq_num}")
                    seq_num += 1

                if not unacked_packets and not chunk:
                    # If there are no unacknowledged packets and we reached EOF, break the loop
                    break

                # Wait for ACKs and retransmit if needed
                try:
                    server_socket.settimeout(TimeoutInterval)  # Use the current timeout interval
                    ack_packet, _ = server_socket.recvfrom(1024)

                    print(f"Received ACK packet: {ack_packet.decode()}")  # Log received ACK packet

                    # Validate that the ACK packet is JSON
                    ack_seq_num = get_seq_no_from_ack_pkt(ack_packet)

                    if ack_seq_num in unacked_packets:
                        # Acknowledge received ACKs
                        print(f"Received ACK for packet {ack_seq_num}")
                        send_time = unacked_packets[ack_seq_num][1]
                        SampleRTT = time.time() - send_time
                        print(f"SampleRTT for packet {ack_seq_num}: {SampleRTT:.4f} seconds")

                        # Update EstimatedRTT and DevRTT
                        EstimatedRTT = (1 - ALPHA) * EstimatedRTT + ALPHA * SampleRTT
                        DevRTT = (1 - BETA) * DevRTT + BETA * abs(SampleRTT - EstimatedRTT)
                        TimeoutInterval = EstimatedRTT + 4 * DevRTT
                        print(f"Updated TimeoutInterval: {TimeoutInterval:.4f} seconds")

                        # Update state
                        del unacked_packets[ack_seq_num]  # Remove acknowledged packet

                        # Slide window forward if necessary
                        if ack_seq_num > last_ack_received:
                            last_ack_received = ack_seq_num
                            # Update window base
                            window_base = ack_seq_num
                            duplicate_ack_count = 0  # Reset duplicate ACK count

                    else:
                        # Duplicate ACK received
                        duplicate_ack_count += 1
                        print(f"Duplicate ACK received for packet {ack_seq_num}, count={duplicate_ack_count}")

                        # Check for fast recovery condition
                        if enable_fast_recovery and duplicate_ack_count >= DUP_ACK_THRESHOLD:
                            print("Entering fast recovery mode")
                            fast_recovery(server_socket, client_address, unacked_packets)

                except socket.timeout:
                    # Timeout handling: retransmit all unacknowledged packets
                    print("Timeout occurred, retransmitting unacknowledged packets")
                    retransmit_unacked_packets(server_socket, client_address, unacked_packets)
                    # for seq in list(unacked_packets.keys()):
                    #     print(f"Retransmitting packet {seq}")
                    #     server_socket.sendto(unacked_packets[seq][0], client_address)

            # After all packets are sent and acknowledged
            end_packet = json.dumps({'seq_num': -1, 'data': ''}).encode()
            server_socket.sendto(end_packet, client_address)
            print("Sent END signal to client")

    except Exception as e:
        print(f"An error occurred: {e}")  # Handle any exceptions that occur in the try block
    finally:
        server_socket.close()  # Ensure the socket is closed when done
        print("Server socket closed.")



def create_packet(seq_num, data):
    """
    Create a packet with the sequence number and data.
    """
    packet = {
        'seq_num': seq_num,
        'data': data.decode('latin1')  # Convert bytes to a string for serialization
    }
    return json.dumps(packet).encode()

def get_seq_no_from_ack_pkt(ack_packet):
    """
    Extract sequence number from the ACK packet.
    """
    ack = json.loads(ack_packet.decode())
    return ack['ack_seq']

def retransmit_unacked_packets(server_socket, client_address, unacked_packets):
    """
    Retransmit all unacknowledged packets.
    """
    for seq_num, (packet, _) in unacked_packets.items():
        print(f"Retransmitting packet {seq_num}")
        server_socket.sendto(packet, client_address)

def fast_recovery(server_socket, client_address, unacked_packets):
    """
    Retransmit the earliest unacknowledged packet (fast recovery).
    """
    earliest_unacked_seq_num = min(unacked_packets.keys())
    print(f"Fast recovery: retransmitting packet {earliest_unacked_seq_num}")
    packet, _ = unacked_packets[earliest_unacked_seq_num]
    server_socket.sendto(packet, client_address)

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Reliable file transfer server over UDP.')
parser.add_argument('server_ip', help='IP address of the server')
parser.add_argument('server_port', type=int, help='Port number of the server')
parser.add_argument('fast_recovery', type=int, help='Enable fast recovery (1 for True, 0 for False)')

args = parser.parse_args()

# Run the server
send_file(args.server_ip, args.server_port, args.fast_recovery == 1)
