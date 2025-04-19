import socket  # Library for network communication (TCP/UDP)
import time  # Library for time-related functions
import json  # Library for handling JSON encoding/decoding
import os  # Library for interacting with the operating system, like file manipulation
import datetime  # Library for handling date and time
from pathlib import Path  # For handling file paths
import hashlib
# Define server configuration variables
server_name = "localhost"  # Server IP address or hostname
MAX_NUMBER_OF_CLIENTS_IN_QUEUE = 15  # Max number of clients allowed to wait in the queue
UDP_SERVER_PORT = 12000  # Port for the UDP server
TCP_SERVER_PORT = 12500  # Port for the TCP server
WAITING_TIME_SECONDS = 5  # Timeout for waiting for connections in seconds
server_address = (server_name, UDP_SERVER_PORT)  # UDP server address tuple

# Initialize TCP and UDP sockets
TCP_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP socket for file transfer
UDP_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP socket for discovery

CHUNK_SIZE = 4096  # Size of file chunks to be sent over TCP
local_ip = "localhost"  # Local IP, modify if needed

# Enable address reuse for the TCP socket
TCP_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
def compute_chunk_checksum(chunk):
    """Generate SHA-256 checksum for a single chunk."""
    return hashlib.sha256(chunk).hexdigest()

def send_file_transfer(file):
    """Send a file transfer initiation message."""
    now = datetime.datetime.now().strftime('%H:%M')  # Get current time
    msg = {
        "message_type": "FILE_TRANSFER",  # Type of message
        "file_id": file,  # File ID to be transferred
        "time_stamp": now  # Current timestamp
    }
    TCP_connection_socket.send(json.dumps(msg).encode())  # Send the message as JSON over TCP

def connect_to_tracker(files):
    """Send a peer discovery message to the tracker server."""
    now = datetime.datetime.now().strftime('%H:%M')  # Get current time
    msg = {
        "message_type": "DISCOVER_PEER",  # Type of message (peer discovery)
        "type_of_peer": "CS",  # Peer type (CS = Seeder)
        "peer_id": local_ip,  # Local IP of the server
        "file_id": files,  # List of files available for transfer
        "time_stamp": now  # Current timestamp
    }
    UDP_socket.sendto(json.dumps(msg).encode(), server_address)  # Send the message as JSON over UDP

def send_ack(message_type):
    """Send an acknowledgment message."""
    msg = {
        "message_type": "ACK",  # Type of message (Acknowledgment)
        "requested_message_type": message_type  # Type of the message that is being acknowledged
    }
    TCP_connection_socket.send(json.dumps(msg).encode())  # Send the acknowledgment over TCP

def send_begin_download():
    """Send an acknowledgment message.""" 
    now = datetime.datetime.now().strftime('%H:%M')
    msg = {
        "message_type": "BEGIN",  # Type of message (Acknowledgment)
        "time_stamp": now  # Type of the message that is being acknowledged
    }
    TCP_connection_socket.send(json.dumps(msg).encode())  # Send the acknowledgment over TCP

def send_avaiable():
    """Send an acknowledgment message.""" 
    now = datetime.datetime.now().strftime('%H:%M') 
    msg = {
        "message_type": "AVAILABLE",  # Type of message (Acknowledgment)
        "time_stamp": now,  # Type of the message that is being acknowledged
        "type_of_peer": "CS"
    }
    UDP_socket.sendto(json.dumps(msg).encode(), server_address)

def send_error_404():
    """Send an error message for file not found.""" 
    msg = {
        "message_type": "ERROR",  # Type of message (Error)
        "error_code": 404,  # Error code for file not found
        "error_message": "File Not Found"  # Error message
    }
    TCP_connection_socket.send(json.dumps(msg).encode())  # Send the error message over TCP

def download(file_path):
    """Handles file chunk requests and sends the file to the client in chunks.""" 
    print(f"Preparing to download the file: {file_path}")
    file_size = os.path.getsize(file_path)  # Get the size of the file
    TCP_connection_socket.sendall(str(file_size).encode())  # Send file size first to the client message 5
    print(f"Sent file size of {file_size} bytes to client.")
    total_chunks = TCP_connection_socket.recv(1024)  # Wait for acknowledgment from client and recieve the total chunks
    print("Waiting for acknowledgment from client...")

    # Open the file and send it in chunks
    with open(file_path, "rb") as file:
        split = []
        while True:
            if len(split) > 1 and split[1] != '':
                request_id = json.loads(split[1])
            else:
                request_id = json.loads(TCP_connection_socket.recv(1024).decode())  # Receive chunk index request from client message 7
            if not request_id:
                break  # If no request or invalid request, break the loop
            if request_id == "ACK":
                continue
            chunk_index = request_id["chunk_index"]  # Get the requested chunk index
            file.seek(chunk_index * CHUNK_SIZE)  # Seek to the correct position in the file
            chunk_data = file.read(CHUNK_SIZE)  # Read the chunk data
            # Compute checksum for the chunk
            chunk_checksum = compute_chunk_checksum(chunk_data)

            # Send chunk + checksum to alllow it to send confirmation
            chunk_packet = {
                "chunk_index": chunk_index,
                "data": chunk_data.hex(),  # Convert binary to hex for JSON transmission
                "checksum": chunk_checksum
            }            
            print(f"Sending chunk {chunk_index} to client.")
            
            TCP_connection_socket.send(json.dumps(chunk_packet).encode())  # Send the chunk data to the client message 8
            ack = TCP_connection_socket.recv(1024).decode()
            split = ack.split('\n')
            ack = json.loads(split[0])
            
            ack = ack["message_type"]  # Wait for acknowledgment from client message 9
            
            
            while ack != "ACK":  # If acknowledgment is not received, retransmit the chunk
                print("Data corrupt resending")
                TCP_connection_socket.sendall(json.dumps(chunk_packet.encode()))  # Resend the chunk
                ack = TCP_connection_socket.recv(1024).decode()  # Wait for acknowledgment
                print(f"Resending chunk {chunk_index} to client.")

            print(f"Chunk {chunk_index} successfully acknowledged.")
            if chunk_index + 1 == total_chunks:  # This is the last chunk
                print("All chunks sent successfully. Closing connection.")
                TCP_connection_socket.close()
                break

    print("File transfer complete.")  # Print when the file transfer is complete

def main():
    global TCP_connection_socket
    """Main server function that listens for incoming client requests.""" 
    TCP_socket.bind(("127.0.0.1", TCP_SERVER_PORT))  # Bind explicitly to localhost
    TCP_socket.listen(MAX_NUMBER_OF_CLIENTS_IN_QUEUE)
    TCP_socket.settimeout(WAITING_TIME_SECONDS)
    UDP_socket.settimeout(WAITING_TIME_SECONDS)
    
    files = ["Tester.pdf","Billie_Eilish_-_lovely_(with_Khalid).mp3"]  # List of files available for transfer
    path = Path("Server")  # Path to the server directory containing files

    try:
        connect_to_tracker(files)
        print("Connection to Tracker established.")
        while True:
            try:
                message_from_UDP_server, _ = UDP_socket.recvfrom(1024)
                Tracker_information = json.loads(message_from_UDP_server.decode()) 
                message_type = Tracker_information.get("message_type")

                if message_type == "PING":
                    print("Received PING from tracker. Sending availability status.")
                    send_avaiable()
                    continue
                elif message_type == "MATCH_FOUND":
                    print("MATCH FOUND. Establishing connection with client...")
                    TCP_connection_socket, _ = TCP_socket.accept()
                    TCP_connection_socket.settimeout(10)
                    
                    message_from_TCP_server = TCP_connection_socket.recv(1024).decode()
                    if message_from_TCP_server:
                        msg = {"message_type": "ACK", "type_of_peer": "L"}
                        TCP_connection_socket.send(json.dumps(msg).encode())
                        print("Acknowledged client request.")
                        leecher_info = json.loads(TCP_connection_socket.recv(1024).decode())
                        if leecher_info.get("message_type") == "REQUEST_FILE":
                            msg = {"message_type": "BEGIN"}
                            TCP_connection_socket.send(json.dumps(msg).encode())                            
                            file = leecher_info.get("requested_file")
                            if file in files:
                                download(path / file)
                            else:
                                print(f"File '{file}' not found. Sending ERROR 404.")
                                send_error_404()
                    TCP_connection_socket.close()
                send_avaiable()
            except socket.timeout:
                continue
    except KeyboardInterrupt:
        print("Keyboard interrupt received. Closing sockets and exiting.")
        UDP_socket.close()
        exit()

if __name__ == "__main__":
    print("Server starting...")
    main()
