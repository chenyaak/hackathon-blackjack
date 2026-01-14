"""
Blackjack Hackathon Client (UDP offer listener + TCP gameplay)

Flow:
1) Listen on UDP port 13122 for OFFER packets
2) Connect to server via TCP
3) Send REQUEST (rounds + team name)
4) Play rounds using PAYLOAD messages
5) Close TCP and go back to step 1 (run forever)
"""

import socket
import sys

from Formats.packet_formats import (
    CLIENT_UDP_PORT,
    HIT,
    STAND,
    ROUND_ONGOING,
    ROUND_WIN,
)
from protocolClient import (
    ProtocolError,
    decode_offer,
    encode_request,
    decode_payload_server,
    encode_payload_decision,
)


# -----------------------------
# TCP helper: recv exactly N bytes
# -----------------------------

# read tcp message
def recv_exact(sock: socket.socket, n: int) -> bytes:
    """Receive exactly n bytes from a TCP socket, or raise if connection closes."""
    chunks = []  # if bytes received in pieces, save it in chunks
    received = 0
    while received < n:
        try:
            chunk = sock.recv(n - received)  # wait for more data, read n-received bytes from received data
        except socket.timeout as e:
            raise TimeoutError(f"Timed out while waiting for {n} bytes from server.") from e

        if not chunk:
            raise ConnectionError("Server closed the TCP connection.")
        chunks.append(chunk)
        received += len(chunk)
    return b"".join(chunks)  # return all data received


# -----------------------------
# UDP: listen for server offers
# -----------------------------
def listen_for_offer(timeout_sec: float = 1.0) -> tuple[str, int, str]:
    """
    Blocks until a valid OFFER is received.
    Returns: (server_ip, tcp_port, server_name)
    """
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # create UDP socket with IPv4 protocol

    # Allow 2 clients to same port
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Listen on the required UDP port for offers.
    udp_sock.bind(("", CLIENT_UDP_PORT))

    udp_sock.settimeout(timeout_sec)  # set timeout

    print(f"Client started, listening for offer requests...")

    # run loop until a valid offer received
    while True:
        try:
            data, addr = udp_sock.recvfrom(1024)  # addr = (ip, port)
            server_ip = addr[0]
        except socket.timeout:
            # No offer arrived within timeout_sec; keep waiting
            continue

        try:
            tcp_port, server_name = decode_offer(data)  # decode message
            print(f"Received offer from {server_ip}")
            udp_sock.close()  # client received offer, can close UDP connection
            return server_ip, tcp_port, server_name
        except ProtocolError:
            # Not a valid offer (wrong cookie/type/length) -> ignore
            continue


# -----------------------------
# TCP: connect + request
# -----------------------------

def connect_tcp(server_ip: str, tcp_port: int, timeout_sec: float = 5.0) -> socket.socket:
    """Connect to the server over TCP."""
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # create TCP socket with IPv4 protocol
    tcp_sock.settimeout(timeout_sec)  # set timeout
    tcp_sock.connect((server_ip, tcp_port))  # # Connect to the server using the IP and TCP port received in the OFFER
    return tcp_sock


def send_request(tcp_sock: socket.socket, num_rounds: int, team_name: str) -> None:
    """Send REQUEST packet to server."""
    req = encode_request(num_rounds, team_name)
    tcp_sock.sendall(req)  # Send REQUEST message over the established TCP connection


# -----------------------------
# Gameplay
# -----------------------------
def prompt_decision() -> bytes:
    """Ask the user Hit/Stand until valid, return HIT or STAND bytes."""
    while True:
        choice = input("Hit or Stand? ").strip().lower()

        if choice in ("hit", "h"):
            return HIT
        if choice in ("stand", "s"):
            return STAND

        print("Please type 'Hit' or 'Stand' (or h/s).")  # if user types invalid input


def play_session(tcp_sock: socket.socket, num_rounds: int) -> float:
    """
    Play num_rounds rounds on an open TCP socket.
    Returns win_rate (0..1).
    """
    wins = 0
    gameStarted = 0
    decision = STAND

    # According to our protocol implementation:
    # Server->Client payload length is 9 bytes: cookie(4) + type(1) + result(1) + rank(2) + suit(1)
    SERVER_PAYLOAD_LEN = 9

    for r in range(1, num_rounds + 1):
        print(f"\n--- Round {r}/{num_rounds} ---")

        while True:
            data = recv_exact(tcp_sock, SERVER_PAYLOAD_LEN)  # client read PAYLOAD TCP message from server
            result, rank, suit = decode_payload_server(data)

            print(f"Received card: rank={rank}, suit={suit} | result={result}")

            if result != ROUND_ONGOING:  # if game ended
                if result == ROUND_WIN:
                    wins += 1  # if player won, add it to his record
                break
            if gameStarted > 0 or decision == HIT:
                decision = prompt_decision()  # ask player to choose HIT or STAND
                tcp_sock.sendall(encode_payload_decision(decision))  # send PAYLOAD message with player's decision
            gameStarted += 1

    return (wins / num_rounds) if num_rounds > 0 else 0.0


# -----------------------------
# User input helpers
# -----------------------------

# ask player how many rounds he wants to play
def prompt_rounds() -> int:
    while True:
        rounds = input("How many rounds do you want to play? ").strip()
        try:
            n = int(rounds)
            if 1 <= n <= 255:  # 1 byte in the request format
                return n
            print("Please enter a number between 1 and 255.")
        except ValueError:
            print("Please enter a valid integer.")


# ask for player's team name
def prompt_team_name() -> str:
    while True:
        name = input("Enter your team name: ").strip()
        if name:
            return name
        print("Team name cannot be empty.")


# -----------------------------
# Main loop (runs forever)
# -----------------------------
def main() -> None:
    team_name = prompt_team_name()  # ask player for his team's name

    while True:
        try:
            num_rounds = prompt_rounds()  # ask player's for number of rounds

            server_ip, tcp_port, _server_name = listen_for_offer()  # listens for offers (UDP)

            tcp_sock = connect_tcp(server_ip, tcp_port)  # connect to server (TCP)
            try:
                send_request(tcp_sock, num_rounds, team_name)  # REQUEST message
                win_rate = play_session(tcp_sock, num_rounds)  # start game - receive player's win rate
                print(f"\nFinished playing {num_rounds} rounds, win rate: {win_rate:.2%}")
            finally:
                tcp_sock.close()  # game ended, close TCP connection

        except KeyboardInterrupt:
            print("\nClient exiting.")
            sys.exit(0)
        except (ConnectionError, OSError) as e:
            print(f"\nNetwork error: {e}")
            # loop continues


if __name__ == "__main__":
    main()
