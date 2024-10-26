import socket
import argparse
import json

# Constants
MSS = 1400  # Maximum Segment Size
BUFFER_SIZE = MSS + 200  # Increased buffer size to accommodate larger packet size with headers

def receive_file(server_ip, server_port):
    """
    Receive the file from the server with reliability, handling packet loss
    and reordering.
    """
    # Initialize UDP socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(2)  # Set timeout for server response

    server_address = (server_ip, server_port)
    expected_seq_num = 0
    output_file_path = "received_file.txt"  # Default file name

    # Buffer to hold out-of-order packets
    packet_buffer = {}

    # Send initial connection request to server
    client_socket.sendto(b"START", server_address)

    with open(output_file_path, 'wb') as file:
        while True:
            try:
                # Receive the packet
                packet, _ = client_socket.recvfrom(BUFFER_SIZE)
                
                seq_num, data = parse_packet(packet)
                #print(f"Received packet: seq_num={seq_num}, data={data}")  # Log received packet details

                if seq_num == -1:  # Check for the END signal
                    print("Received END signal from server, file transfer complete")
                    break

                if seq_num == expected_seq_num:
                    # Write data to the file for the expected packet
                    file.write(data.encode('latin1'))  # Ensure data is written as bytes
                    print(f"Writing packet {seq_num} to file")  # Log the write action
                    
                    # Update expected seq number and send cumulative ACK for the received packet
                    send_ack(client_socket, server_address, seq_num)
                    expected_seq_num += 1
                    
                    # Check for any buffered packets that can now be written
                    while expected_seq_num in packet_buffer:
                        buffered_data = packet_buffer.pop(expected_seq_num)
                        file.write(buffered_data.encode('latin1'))  # Write buffered data to file
                        print(f"Writing buffered packet {expected_seq_num} to file")  # Log buffered write
                        send_ack(client_socket, server_address, expected_seq_num)
                        expected_seq_num += 1

                elif seq_num < expected_seq_num:
                    # Duplicate or old packet, send ACK again
                    print(f"Duplicate packet {seq_num} received. Sending ACK again.")
                    send_ack(client_socket, server_address, seq_num)
                else:
                    # Packet arrived out of order, store it in the buffer
                    print(f"Out-of-order packet {seq_num}, expected {expected_seq_num}, buffering it")
                    packet_buffer[seq_num] = data

            except socket.timeout:
                print("Timeout waiting for data")
            except ConnectionResetError:
                print("Connection reset by server. Exiting.")
                break


def parse_packet(packet):
    """
    Parse the packet to extract the sequence number and data.
    """
    try:
        parsed_packet = json.loads(packet.decode())
        seq_num = parsed_packet['seq_num']
        data = parsed_packet['data']
        return seq_num, data
    except json.JSONDecodeError:
        print("Received a non-JSON packet. Ignoring...")
        return -1, None  # Return a default value to indicate an error in parsing



def send_ack(client_socket, server_address, seq_num):
    """
    Send a cumulative acknowledgment for the received packet.
    """
    ack_packet = json.dumps({'ack_seq': seq_num}).encode()  # Format ACK as JSON
    client_socket.sendto(ack_packet, server_address)
    print(f"Sent cumulative ACK for packet {seq_num}")


# Parse command-line arguments
parser = argparse.ArgumentParser(description='Reliable file receiver over UDP.')
parser.add_argument('server_ip', help='IP address of the server')
parser.add_argument('server_port', type=int, help='Port number of the server')

args = parser.parse_args()

# Run the client
receive_file(args.server_ip, args.server_port)
