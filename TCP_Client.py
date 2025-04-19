import socket  # Library for network communication
import time  # Library for time-related functions
import json  # Library to handle JSON encoding and decoding
import datetime  # Library to work with dates and times
from pathlib import Path  # Library to work with file system paths
import hashlib
import math
# Constants to define server information and settings
server_name = "localhost"  # The server where we'll send messages (localhost for local testing)
UDP_SERVER_PORT = 12000  # The UDP port the server listens on
TCP_SERVER_PORT = 12500  # The TCP port for client-server communication
P2P_SERVER_PORT = 13000  # The port used for peer-to-peer communication
WAITING_TIME_SECONDS = 10  # Time to wait for responses (in seconds)
MAX_NUMBER_OF_CLIENTS_IN_QUEUE = 15  # Max clients allowed in TCP connection queue
CHUNK_SIZE = 4096

# Creating UDP and TCP sockets
UDP_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP socket for sending and receiving data
TCP_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP socket for reliable connection
local_ip = socket.gethostbyname(socket.gethostname())  # Getting the local IP address of the machine
server_address = (server_name, UDP_SERVER_PORT)  # Address of the server to communicate with
def create_seeder():
    global UDP_socket
    UDP_socket = UDP_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("\nConnected to Tracker as a seeder")
      # Reuses socket
def compute_chunk_checksum(chunk):
    """Generate SHA-256 checksum for a single chunk."""
    return hashlib.sha256(chunk).hexdigest()

def request_file(file):
    """
    Sends a request for a specific file to the server over TCP.
    The server will respond with the file data or an error message.
    """
    msg = {
        "message_type": "REQUEST_FILE",  # Type of message: Requesting a file
        "peer_id": local_ip,  # The IP address of the current client
        "requested_file": file  # Name or ID of the requested file
    }
    TCP_client_socket.send(json.dumps(msg).encode())  # Send the request as a JSON-encoded message
    modified_sentence = TCP_client_socket.recv(1024)  # Receive a response from the server
    return json.loads(modified_sentence.decode())  # Return the server's response after decoding it

def reconfigure():
    """
    Downloads the file by requesting each chunk one by one from the server.
    The file is saved on the disk as it's being downloaded.
    """
    global SAVE_PATH, total_chunks
    file_size = int(TCP_client_socket.recv(1024).decode())  
    total_chunks = math.ceil(file_size / CHUNK_SIZE)
    TCP_client_socket.sendall(str(total_chunks).encode())  # Acknowledge file size 
    
      # Make the SAVE_PATH and total_chunks variables accessible here
    with open(SAVE_PATH, "wb") as file:  # Open the file for writing in binary mode
        chunk_index = 0
        while (chunk_index <= total_chunks):  # Loop through each chunk of the file
            request_chunk(chunk_index)  # Request the chunk from the server
            chunk_packet = TCP_client_socket.recv(10240).decode()# Receive the chunk data
            
            
            chunk_packet = json.loads(chunk_packet)
            chunk_data = bytes.fromhex(chunk_packet["data"])
            if compute_chunk_checksum(chunk_data) != chunk_packet["checksum"]:
                print("There an issue")
                retransmit = {
                    "chunk_index": chunk_index,
                    "message_type": "RETRANSMIT",  # Convert binary to hex for JSON transmission
                }
                TCP_connection_socket.send(json.dumps(retransmit.encode()))
                continue
            perc = 100*chunk_index/total_chunks
            print(f"Download Progress : {perc:.2f}")
            ack_receive_chunk(chunk_index)  # Send acknowledgment that the chunk was received
            chunk_index += 1
            file.write(chunk_data)  # Write the received chunk to the file
    print(f"\nFile downloaded successfully: {SAVE_PATH}\n")  # Notify that the file has been successfully downloaded
    #TCP_client_socket.close()

def ack_receive_chunk(chunk_index):
    """
    Sends an acknowledgment back to the server to confirm that a chunk has been received.
    """
    msg = {
        "message_type": "ACK",  # Type of message: Acknowledgment
        "peer_id": local_ip,  # The IP address of the client
        "received_chunk": chunk_index  # The index of the chunk that was received
    }
    TCP_client_socket.send((json.dumps(msg)+ '\n').encode())  # Send the acknowledgment as a JSON-encoded message

def progression():
    """
    Sends the progress of the download to the server.
    """
    now = datetime.datetime.now().strftime('%H:%M')  # Get the current time
    msg = {"message_type": "PROGRESSION", "time_stamp": now}  # Create a progress message with the timestamp
    TCP_client_socket.send(json.dumps(msg).encode())  # Send the progress message to the server

def send_avaiable(peer_type):
    """Send an acknowledgment message."""
    now = datetime.datetime.now().strftime('%H:%M')
    msg = {
        "message_type": "AVAILABLE",  # Type of message (Acknowledgment)
        "time_stamp": now,  # Type of the message that is being acknowledged
        "type_of_peer" : peer_type
    }
    print("Sending ping to Tracker")
    UDP_socket.sendto(json.dumps(msg).encode(), server_address)

def request_chunk(chunk_index):
    """
    Sends a request for a specific chunk of the file to the server.
    """
    now = datetime.datetime.now().strftime('%H:%M')  # Get the current time
    msg = {"message_type": "REQUEST", 
           "time_stamp": now, 
           "chunk_index": chunk_index}  # Request message with chunk index
    TCP_client_socket.send(json.dumps(msg).encode())  # Send the chunk request to the server

def connect_to_TCP(seeder):
    """
    Establishes a TCP connection to another peer (seeder).
    """
    TCP_client_socket.connect((seeder, TCP_SERVER_PORT))  # Connect to the seeder peer
    now = datetime.datetime.now().strftime('%H:%M')
    msg = {
        "message_type": "CONNECT",  # Type of message: Connect
        "peer_id": local_ip,  # The IP address of the current client
        "time_stamp": now,  # Current timestamp
        "type_of_peer": "L"  # Peer type: L (Leecher)
    }
    TCP_client_socket.send(json.dumps(msg).encode())  # Send the connection request to the peer
    response = TCP_client_socket.recv(1024).decode()  # Expecting ACK or further message 2
    if "ACK" in response:
        return response  # Return the active connection
    else:
        TCP_client_socket.close()
        return None

def create_folder(client_name):
    """
    Creates a folder with the client's name to store the downloaded file.
    """
    folder = Path(client_name)  # Create a path object for the folder
    folder.mkdir(exist_ok=True)  # Create the folder if it doesn't exist
    return folder  # Return the folder path as a string

def connect_to_tracker(client_name, file_id,peer_id):
    """
    Sends a message to the tracker server to find peers for file sharing.
    """
    now = datetime.datetime.now().strftime('%H:%M')  # Get the current time
    msg = {
        "message_type": "DISCOVER_PEER",  # Type of message: Discover Peer
        "peer_id": local_ip,  # The IP address of the client
        "type_of_peer": peer_id,  # Peer type: L (Leecher)
        "time_stamp": now,  # Current timestamp
        "file_id": file_id,  # ID of the file to be downloaded
        "client_name": client_name  # Name of the client
    }
    UDP_socket.sendto(json.dumps(msg).encode(), server_address)  # Send the discovery message to the tracker server

def main():
    """
    The main function to run the client program, handling the peer-to-peer file sharing process.
    """
    global SAVE_PATH
    UDP_socket.settimeout(WAITING_TIME_SECONDS)

    client_name = input("Please enter your client name: \n")  # Prompt user for the client name
    file_id = input("Please enter the file ID to download: \n")  # Prompt user for the file ID to download
    
    SAVE_PATH = create_folder(client_name) / file_id
    peer_type = "L"

    try:
        connect_to_tracker(client_name, file_id,peer_type)
        print("Connection to Tracker established.")
        while True:  # Keep trying to find a peer
            try:
                message_from_UDP_server, UDP_server_address = UDP_socket.recvfrom(2048)  # Wait for a response from the server
                partner_peer_information = json.loads(message_from_UDP_server.decode())  # Parse the response
                message_type = partner_peer_information["message_type"]
                
                if message_type == "PING":
                    send_avaiable(peer_type)
                    continue
                elif message_type == "MATCH_FOUND":
                    if partner_peer_information["id"] == "CS":
                        # If the peer is a seeder (CS), connect to it and start the file download process
                        response = json.loads(connect_to_TCP(partner_peer_information["ip"]))
                        print(f"Connected to Peer with the {file_id}")# Messages 1 and 2 inside
                        if response["message_type"] == "ACK":
                            response = request_file(file_id)
                        
                        if response["message_type"] == "BEGIN":
                            print(f"Download of {file_id} begins\n")
                            reconfigure()  # Start downloading the file in chunks
                            print("Disconnected from peer.\n")
                            decision = input("Do you wish to be a seeder (Yes) or (No):\n")
                            if decision[0].upper() == "Y":
                                peer_type = "S"
                                
                                UDP_socket.close()
                                
                                create_seeder()
                                
                                connect_to_tracker(client_name, file_id,peer_type)
                            else:
                                print("Thank you for downloading on our server")

                elif partner_peer_information["id"] == "S":
                    # If the peer is a server (S), establish a P2P connection
                    TCP_client_socket.connect((partner_peer_information["ip"], P2P_SERVER_PORT))
                    TCP_client_socket.send("Hi fellow peer, I want a file.".encode())
                    TCP_client_socket.recv(1024).decode()

                elif partner_peer_information["id"] == "L":
                    # If the peer is another leecher (L), act as a server and share the file
                    TCP_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    TCP_server_socket.bind(("", P2P_SERVER_PORT))
                    TCP_server_socket.listen(MAX_NUMBER_OF_CLIENTS_IN_QUEUE)

                    while True:
                        TCP_connection_socket, _ = TCP_server_socket.accept()  # Accept incoming connection
                        TCP_connection_socket.recv(1024).decode()
                        TCP_connection_socket.send("Here is the file that you asked for".encode())  # Send file data
                        TCP_connection_socket.close()  # Close the connection after sending
                        TCP_server_socket.close()  # Close the server socket

            except socket.timeout:
                continue  # If timeout occurs, keep trying

    except KeyboardInterrupt:
        print("\nProgram interrupted. Closing connections and cleaning up.")
        UDP_socket.close()  # Close the UDP socket when the program is interrupted
        TCP_client_socket.close()  # Close the TCP client socket

if __name__ == "__main__":
    main()  # Run the main function when the script is executed
