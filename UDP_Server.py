import socket
import time
import json
import datetime

MAX_OFFLINE_INTERVAL_SECONDS = 10  # Time after which offline clients are removed
UNMATCH_BUFFER_SECONDS = 10  # Time before a match is removed if inactive
UDP_SERVER_PORT = 12000  # Port for UDP tracker server
SERVER_REFRESH_RATE_SECONDS = 4  # Interval to refresh server state

def send_message(TCP_connection_socket, msg_type, msg_content):
    """Generic function to send messages over TCP."""
    msg = {
        "message_type": msg_type,
        "message": msg_content
    }
    TCP_connection_socket.send(json.dumps(msg).encode())

def send_Standby(UDP_socket, server_address):
    """Announce peer’s availability to tracker (UDP)."""
    msg = {
        "message_type": "STANDBY",
        "message_content": "Please wait till we get a receiver"
    }
    UDP_socket.sendto(json.dumps(msg).encode(), server_address)
    
def send_ack(TCP_connection_socket):
    """Send acknowledgment message."""
    send_message(TCP_connection_socket,
                 "ACK",
                 "Connection established.")

def send_available(UDP_socket, server_address, file_name, tcp_port, folder):
    """Announce peer’s availability to tracker (UDP)."""
    msg = {
        "message_type": "AVAILABLE",
        "peer_type": "CS",  # Indicating this peer is a content seeder
        "file_id": file_name,
        "port": tcp_port,
        "path": str(folder)
    }
    UDP_socket.sendto(json.dumps(msg).encode(), server_address)

def send_ping(UDP_socket, peers):
    """Send a PING message via UDP to all active peers."""
    msg = json.dumps({"message_type": "PING"})
    
    for peer_key, peer_data in peers.items():
        peer_address = (peer_data["ip"], peer_data["port"])
        UDP_socket.sendto(msg.encode(), peer_address)
        print(f"Sent PING to {peer_address}")


def send_file_transfer(TCP_connection_socket, file_path):
    """Send file transfer initiation and handle chunked transfer."""
    if file_path.exists():
        with open(file_path, "rb") as file:
            while chunk := file.read(1024):  # Read file in 1024-byte chunks
                TCP_connection_socket.send(chunk)
        print("File transfer completed.")
    else:
        send_message(TCP_connection_socket, "ERROR", "File Not Found")

def remove_offline_clients(log, max_offline_interval_seconds):
    """Remove offline clients that exceeded allowed offline duration."""
    clients_to_delete = [ip_port for ip_port in log if time.time() - log[ip_port]["last_seen"] > max_offline_interval_seconds]
    for ip_port in clients_to_delete:
        del log[ip_port]  # Use del to safely remove item

def remove_match(matches, matches_to_remove, key_to_remove, unmatch_buffer_seconds, i):
    """Remove a match if its duration exceeds the unmatch buffer time."""
    if time.time() - matches[key_to_remove]["match_made_time"] > unmatch_buffer_seconds:
        del matches[key_to_remove]
        matches_to_remove.pop(i)
        print("Match removed")

def remove_queued_matches(matches, matches_to_remove, unmatch_buffer_seconds):
    """Remove expired queued matches."""
    if matches_to_remove:
        for i, match in enumerate(matches_to_remove):
            seeder_ip_port = create_custom_key(match["ip"], match["port"])
            leecher_ip_port = create_custom_key(match["other_ip"], match["other_port"])
            key_to_remove = f"{seeder_ip_port}_{leecher_ip_port}"
            remove_match(matches, matches_to_remove, key_to_remove, unmatch_buffer_seconds, i)

def get_ip_and_port(ip_port_key):
    """Extract IP and port from custom key format."""
    ip, port = ip_port_key.split("_")
    return ip, int(port)

def create_custom_key(ip, port):
    """Create a unique key using IP and port for tracking clients."""
    return f"{ip}_{port}"

def write_log(log, data, address):
    """Write peer connection details to log."""
    custom_key = create_custom_key(address[0], address[1])
    Seeder_files = data["file_id"]
    log[custom_key] = {
        "id": data["type_of_peer"],
        "ip": address[0],
        "port": address[1],
        "file_id": data["file_id"],
        "last_seen": time.time()
    }


def check_file(files, file):
    return file in files

def main():
    UDP_server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    UDP_server_socket.bind(('', UDP_SERVER_PORT))
    UDP_server_socket.settimeout(SERVER_REFRESH_RATE_SECONDS)
    print("Tracker is online.")

    log_seeders = {}
    log_leechers = {}
    matches = {}
    matches_to_remove = []
    
    try:
        while True:
            try:
                message, message_source_address = UDP_server_socket.recvfrom(2048)
                data = json.loads(message.decode())

                if data["message_type"] == "DISCOVER_PEER":
                    if data["type_of_peer"] in ["S", "CS"]:
                        write_log(log_seeders, data, message_source_address)
                        Seeder_files = data["file_id"]
                    elif data["type_of_peer"] == "L":
                        write_log(log_leechers, data, message_source_address)
                        

                elif data["message_type"] == "REMOVE_MATCH":
                    data.update({"other_ip": message_source_address[0], "other_port": message_source_address[1]})
                    matches_to_remove.append(data)
                elif data["message_type"] == "AVAILABLE":
                        custom_key = create_custom_key(message_source_address[0], message_source_address[1])
    
                        if data["type_of_peer"] in ["S", "CS"]:
                            if custom_key in log_seeders:
                                log_seeders[custom_key]["last_seen"] = time.time()
                                

                            elif data["type_of_peer"] == "L":
                                if custom_key in log_leechers:
                                    log_leechers[custom_key]["last_seen"] = time.time()
                                                       

            except socket.timeout:
                remove_offline_clients(log_seeders, MAX_OFFLINE_INTERVAL_SECONDS)
                remove_offline_clients(log_leechers, MAX_OFFLINE_INTERVAL_SECONDS)
                remove_queued_matches(matches, matches_to_remove, UNMATCH_BUFFER_SECONDS)
                print(f"Seeders online: {len(log_seeders)} Leechers online: {len(log_leechers)} @ [{datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S')}]")

                
                # Match leechers with seeders
                if log_leechers and log_seeders:
                    for leecher_ip_port, leecher_data in log_leechers.items():
                        for seeder_ip_port, seeder_data in log_seeders.items():
                            search_key = f"{seeder_ip_port}_{leecher_ip_port}"
                            if leecher_data["file_id"] in Seeder_files and search_key not in matches:
                                print("FOUND A MATCH!")
                                matches[search_key] = {"match_made_time": time.time()}
                                seeder_data["message_type"] = "MATCH_FOUND"
                                leecher_data["message_type"] = "MATCH_FOUND"
                                UDP_server_socket.sendto(json.dumps(seeder_data).encode(), get_ip_and_port(leecher_ip_port))
                                UDP_server_socket.sendto(json.dumps(leecher_data).encode(), get_ip_and_port(seeder_ip_port))
                send_ping(UDP_server_socket, log_seeders)
                send_ping(UDP_server_socket, log_leechers)

    except KeyboardInterrupt:
        print("KeyboardInterrupt. Closing UDP socket.")
        UDP_server_socket.close()
        exit()

if __name__ == "__main__":
    main()
