"""
Blackjack Hackathon Server (UDP offers + TCP gameplay)

Responsibilities (per PDF + shared protocol):
1) Broadcast OFFER packets via UDP every 1 second on port 13122
2) Accept TCP clients (port is included in OFFER)
3) For each client:
   - Read REQUEST (num rounds + team name)
   - Play N rounds using PAYLOAD messages (both directions)
   - Keep running forever

Uses:
- protocolServer.py for packet encode/decode
- game.py for Blackjack logic (deck/hand/winner)
- packet_formats.py for constants
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from typing import Optional

from Formats.packet_formats import CLIENT_UDP_PORT, ROUND_ONGOING, HIT, STAND
from protocolServer import (
    ProtocolError,
    encode_offer,
    decode_request,
    decode_payload_decision,
    encode_payload_server,
)
from game import BlackjackGame


# -----------------------------
# Networking helpers
# -----------------------------
def get_local_ip() -> str:
    """
    Best-effort local IP discovery (no hardcoded IPs).
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't actually send; used to pick the right interface.
        s.connect(("8.8.8.8", 80))  # google server - to find IP
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """
    Receive exactly n bytes from a TCP socket, or raise if connection closes / timeout.
    """
    chunks = []
    received = 0
    while received < n:
        chunk = sock.recv(n - received)
        if not chunk:
            raise ConnectionError("Client closed the TCP connection.")
        chunks.append(chunk)
        received += len(chunk)
    return b"".join(chunks)


def safe_drain_decisions(sock: socket.socket, attempts: int = 1) -> None:
    """
    Client implementation may send a decision after every ROUND_ONGOING payload it receives.
    During phases where the server doesn't *need* a decision (initial reveal / dealer reveal),
    we non-blockingly drain a few decisions so the TCP stream stays aligned.
    """
    prev_timeout = sock.gettimeout()
    try:
        sock.settimeout(0.01)
        for _ in range(attempts):
            try:
                data = recv_exact(sock, 10)  # client->server payload length
                _ = decode_payload_decision(data)  # validate & ignore
            except (TimeoutError, socket.timeout):
                break
            except (ProtocolError, ConnectionError):
                # If it's garbage/closed, just stop draining; caller will handle later.
                break
    finally:
        sock.settimeout(prev_timeout)


# -----------------------------
# UDP offer broadcaster
# -----------------------------
def offer_broadcaster(stop_event: threading.Event, tcp_port: int, server_name: str) -> None:
    """
    Broadcast OFFER once every second on UDP port 13122.
    """
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # broadcast
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # avoid bind

    offer = encode_offer(tcp_port, server_name)
    target = ("255.255.255.255", CLIENT_UDP_PORT)

    while not stop_event.is_set():
        try:
            udp.sendto(offer, target)
        except OSError:
            # Network hiccup; keep trying
            pass
        stop_event.wait(1.0)

    udp.close()


# -----------------------------
# Game flow (per-client)
# -----------------------------
def send_payload(sock: socket.socket, result: int, card: Optional[tuple[int, int]]) -> None:
    """
    Send server->client payload (9 bytes):
      cookie(4) | type(1) | result(1) | rank(2) | suit(1)
    """
    if card is None:
        rank, suit = 0, 0
    else:
        rank, suit = card
    sock.sendall(encode_payload_server(result=result, rank=rank, suit=suit))


def play_one_round(sock: socket.socket) -> None:
    """
    One blackjack round using BlackjackGame.
    We reveal:
    - Player 2 cards (one-by-one)
    - Dealer up-card
    Then:
    - Player decisions Hit/Stand
    - If Stand: reveal dealer hidden card + any dealer draws
    - Finally: send final result (with rank/suit = 0)
    """
    game = BlackjackGame()  # create game
    game.start_round()

    # Initial reveal sequence (PDF: player gets 2 face-up; dealer shows 1 card)
    player_cards = list(game.player.cards)  # 2 cards
    dealer_up = game.dealer.cards[0]  # visible
    dealer_hidden = game.dealer.cards[1]  # hidden until dealer turn

    # Reveal player cards (ongoing)
    for c in player_cards:
        send_payload(sock, ROUND_ONGOING, c)
        safe_drain_decisions(sock, attempts=1)

    # Reveal dealer up-card (ongoing)
    send_payload(sock, ROUND_ONGOING, dealer_up)
    safe_drain_decisions(sock, attempts=1)

    # Player turn
    while True:
        # Wait for decision
        data = recv_exact(sock, 10)
        decision = decode_payload_decision(data)

        if decision == HIT:
            result, card = game.player_hit()
            send_payload(sock, result, card)

            # If bust, round is over (result will be LOSS). Stop.
            if result != ROUND_ONGOING:
                return

        elif decision == STAND:
            # Dealer turn begins:
            # 1) reveal hidden card
            send_payload(sock, ROUND_ONGOING, dealer_hidden)
            safe_drain_decisions(sock, attempts=1)

            # 2) dealer draws until >=17 (game.player_stand does that)
            final_result, dealer_drawn = game.player_stand()

            for c in dealer_drawn:
                send_payload(sock, ROUND_ONGOING, c)
                safe_drain_decisions(sock, attempts=1)

            # 3) final result
            send_payload(sock, final_result, None)
            return

        else:
            # Should not happen (protocol validates), but keep safe:
            send_payload(sock, ROUND_ONGOING, None)


def handle_client(conn: socket.socket, addr: tuple[str, int]) -> None:
    """
    Serve one TCP client connection until it finishes its requested rounds or disconnects.
    """
    client_ip, client_port = addr
    conn.settimeout(30.0)

    try:
        # REQUEST is 38 bytes in our protocolServer.decode_request
        req = recv_exact(conn, 38)
        num_rounds, team_name = decode_request(req)

        print(f"Client connected from {client_ip}:{client_port} | team='{team_name}' | rounds={num_rounds}")

        for r in range(1, num_rounds + 1):
            print(f"[{team_name}] Round {r}/{num_rounds} start")
            play_one_round(conn)
            print(f"[{team_name}] Round {r}/{num_rounds} end")

        print(f"Client finished: {team_name} ({client_ip}:{client_port})")

    except (ConnectionError, TimeoutError, socket.timeout) as e:
        print(f"Client {client_ip}:{client_port} disconnected/timeout: {e}")
    except ProtocolError as e:
        print(f"Protocol error from {client_ip}:{client_port}: {e}")
    except Exception as e:
        print(f"Unexpected error with {client_ip}:{client_port}: {e}")
    finally:
        try:
            conn.close()
        except OSError:
            pass


# -----------------------------
# Main (runs forever)
# -----------------------------
def main() -> None:
    server_name = input("Enter server/team name: ").strip() or "BlackjackServer"

    # TCP server socket (pick any available port)
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # create TCP socket with IPv4 protocol
    tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # avoid bind
    tcp.bind(("", 0))  # any port
    tcp.listen()  # listen

    tcp_port = tcp.getsockname()[1]
    ip = get_local_ip()

    print(f"Server started, listening on IP address {ip} (TCP port {tcp_port})")

    # UDP offer broadcaster thread
    stop_event = threading.Event()
    t = threading.Thread(target=offer_broadcaster, args=(stop_event, tcp_port, server_name), daemon=True)
    t.start()

    try:
        while True:
            conn, addr = tcp.accept()  # conn = client's socket, addr = (IP, port)
            th = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            th.start()
    except KeyboardInterrupt:
        print("\nServer exiting.")
    finally:
        stop_event.set()
        try:
            tcp.close()
        except OSError:
            pass


if __name__ == "__main__":
    main()
