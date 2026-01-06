import socket
import time

from Server.protocol import decode_request, ProtocolError
from Server.protocol import encode_offer

def udp_broadcast_offers(tcp_port: int, stop_event: threading.Event):
    """
    Broadcast offer every 1 second.
    """
    msg = encode_offer(tcp_port, TEAM_NAME)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Create an IPv4( 192.168.1.10) UDP socket

    # Enable broadcast mode on the socket
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # Loop until the server asks this thread to stop
    while not stop_event.is_set():
        try:
            # Send the offer message to all clients on the local network
            s.sendto(msg, ("<broadcast>", CLIENT_UDP_PORT))
        except OSError:
            pass

        # to avoid busy waiting
        time.sleep(1)

    s.close()

def main(): #שלדד !!!
    """
    Start the server:
    - Open a TCP socket on an available port
    - Broadcast UDP offers so clients can discover the server
    - Keep running until manually stopped
    """

    # Create a TCP socket (IPv4, stream-based)
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Allow quick reuse of the address after server restart ??
    tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind to any available port chosen by the OS
    tcp_sock.bind(("", 0))

    # Start listening for incoming TCP connections
    tcp_sock.listen()

    # Retrieve the actual TCP port assigned by the OS
    tcp_port = tcp_sock.getsockname()[1]

    print(f"Server up. TCP port = {tcp_port}. Broadcasting offers...")

    stop_event = threading.Event()

    # Start a background thread to broadcast UDP offers
    t = threading.Thread(
        target=udp_broadcast_offers,
        args=(tcp_port, stop_event),
        daemon=True
    )
    t.start()

    try:
        # Keep the server running (TCP accept will be added later)
        while True:
            client_sock, addr = tcp_sock.accept()
            print(f"Client connected from {addr}")
            client_sock.close()
    except KeyboardInterrupt:
        # Handle manual server shutdown (Ctrl+C)
        print("Shutting down server...")
    finally:
        # Stop the UDP broadcast thread and clean up
        stop_event.set()
        tcp_sock.close()
