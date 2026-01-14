# # import socket
# # import time
# #
# # from Server.protocolServer import decode_request, ProtocolError
# # from Server.protocolServer import encode_offer
# #
# # def udp_broadcast_offers(tcp_port: int, stop_event: threading.Event):
# #     """
# #     Broadcast offer every 1 second.
# #     """
# #     msg = encode_offer(tcp_port, TEAM_NAME)
# #
# #     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Create an IPv4( 192.168.1.10) UDP socket
# #
# #     # Enable broadcast mode on the socket
# #     s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
# #
# #     # Loop until the server asks this thread to stop
# #     while not stop_event.is_set():
# #         try:
# #             # Send the offer message to all clients on the local network
# #             s.sendto(msg, ("<broadcast>", CLIENT_UDP_PORT))
# #         except OSError:
# #             pass
# #
# #         # to avoid busy waiting
# #         time.sleep(1)
# #
# #     s.close()
# #
# # def main(): #שלדד !!!
# #     """
# #     Start the server:
# #     - Open a TCP socket on an available port
# #     - Broadcast UDP offers so clients can discover the server
# #     - Keep running until manually stopped
# #     """
# #
# #     # Create a TCP socket (IPv4, stream-based)
# #     tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# #
# #     # Allow quick reuse of the address after server restart ??
# #     tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
# #
# #     # Bind to any available port chosen by the OS
# #     tcp_sock.bind(("", 0))
# #
# #     # Start listening for incoming TCP connections
# #     tcp_sock.listen()
# #
# #     # Retrieve the actual TCP port assigned by the OS
# #     tcp_port = tcp_sock.getsockname()[1]
# #
# #     print(f"Server up. TCP port = {tcp_port}. Broadcasting offers...")
# #
# #     stop_event = threading.Event()
# #
# #     # Start a background thread to broadcast UDP offers
# #     t = threading.Thread(
# #         target=udp_broadcast_offers,
# #         args=(tcp_port, stop_event),
# #         daemon=True
# #     )
# #     t.start()
# #
# #     try:
# #         # Keep the server running (TCP accept will be added later)
# #         while True:
# #             client_sock, addr = tcp_sock.accept()
# #             print(f"Client connected from {addr}")
# #             client_sock.close()
# #     except KeyboardInterrupt:
# #         # Handle manual server shutdown (Ctrl+C)
# #         print("Shutting down server...")
# #     finally:
# #         # Stop the UDP broadcast thread and clean up
# #         stop_event.set()
# #         tcp_sock.close()
#
#
# import socket
# import threading
# import time
# import sys
#
# # ייבוא מהקבצים הקיימים שלך
# from Formats.packet_formats import CLIENT_UDP_PORT, ROUND_ONGOING
# from game import BlackjackGame
# from protocolServer import (
#     encode_offer,
#     decode_request,
#     decode_payload_decision,
#     encode_payload_server,
#     ProtocolError
# )
#
#
# def handle_client(client_sock, addr):
#     """
#     פונקציה המטפלת בלקוח ספציפי בת'רד נפרד.
#     """
#     print(f"[TCP] Connection accepted from {addr}")
#     try:
#         # 1. קבלת הודעת REQUEST (38 בתים)
#         data = client_sock.recv(38)
#         if not data:
#             return
#
#         num_rounds, team_name = decode_request(data)
#         print(f"[GAME] Client '{team_name}' wants to play {num_rounds} rounds.")
#
#         # 2. לולאת המשחק - ניהול הסיבובים
#         for round_idx in range(1, num_rounds + 1):
#             game = BlackjackGame()
#             # התחלת סיבוב - מחלקת קלפים ראשונים
#             game.start_round()
#
#             # שליחת קלף שחקן 1
#             p1_rank, p1_suit = game.player.cards[0]
#             client_sock.sendall(encode_payload_server(ROUND_ONGOING, p1_rank, p1_suit))
#
#             # שליחת קלף שחקן 2
#             p2_rank, p2_suit = game.player.cards[1]
#             client_sock.sendall(encode_payload_server(ROUND_ONGOING, p2_rank, p2_suit))
#
#             # שליחת קלף דילר גלוי (הראשון)
#             d1_rank, d1_suit = game.dealer.cards[0]
#             client_sock.sendall(encode_payload_server(ROUND_ONGOING, d1_rank, d1_suit))
#
#             # --- תור השחקן ---
#             current_status = ROUND_ONGOING
#             while current_status == ROUND_ONGOING:
#                 # המתנה להחלטת הלקוח (HIT/STAND) - 10 בתים
#                 decision_data = client_sock.recv(10)
#                 if not decision_data:
#                     break
#
#                 decision = decode_payload_decision(decision_data)
#
#                 if decision == b'Hittt':
#                     res, card = game.player_hit()
#                     rank, suit = card
#                     client_sock.sendall(encode_payload_server(res, rank, suit))
#                     current_status = res
#                 else:  # STAND
#                     res, dealer_cards = game.player_stand()
#                     # אם השחקן עמד, הדילר מושך קלפים. נשלח אותם אחד אחד.
#                     for i, d_card in enumerate(dealer_cards):
#                         d_rank, d_suit = d_card
#                         # רק הקלף האחרון שנשלח נושא את התוצאה הסופית (Win/Loss/Tie)
#                         status = res if i == len(dealer_cards) - 1 else ROUND_ONGOING
#                         client_sock.sendall(encode_payload_server(status, d_rank, d_suit))
#
#                     # במקרה שהדילר לא משך אף קלף (היה לו כבר 17+)
#                     if not dealer_cards:
#                         # שולחים הודעת עדכון עם קלף הדילר השני שכבר היה לו, ועם התוצאה
#                         d2_rank, d2_suit = game.dealer.cards[1]
#                         client_sock.sendall(encode_payload_server(res, d2_rank, d2_suit))
#
#                     current_status = res
#
#             print(f"[GAME] Round {round_idx}/{num_rounds} for {team_name} finished.")
#
#     except (ProtocolError, ConnectionResetError, socket.timeout) as e:
#         print(f"[ERROR] Connection with {addr} closed: {e}")
#     finally:
#         client_sock.close()
#         print(f"[TCP] Connection closed with {addr}")
#
#
# def udp_broadcast_offers(tcp_port: int, stop_event: threading.Event):
#     """
#     שידור הודעות Offer ב-UDP כל שנייה.
#     """
#     msg = encode_offer(tcp_port, TEAM_NAME)
#     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
#
#     while not stop_event.is_set():
#         try:
#             s.sendto(msg, ("<broadcast>", CLIENT_UDP_PORT))
#         except OSError:
#             pass
#         time.sleep(1)
#     s.close()
#
#
# def main():
#     # יצירת Socket TCP
#     tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#
#     try:
#         tcp_sock.bind(("", 0))  # הצמדה לפורט פנוי שהמערכת תבחר
#         tcp_sock.listen(5)
#         tcp_port = tcp_sock.getsockname()[1]
#         print(f"Server started on TCP port {tcp_port}")
#     except Exception as e:
#         print(f"Failed to bind TCP socket: {e}")
#         return
#
#     stop_event = threading.Event()
#     # הפעלת ת'רד השידורים
#     broadcast_thread = threading.Thread(
#         target=udp_broadcast_offers,
#         args=(tcp_port, stop_event),
#         daemon=True
#     )
#     broadcast_thread.start()
#
#     print("Server is running. Press Ctrl+C to stop.")
#     try:
#         while True:
#             # קבלת חיבורים חדשים
#             client_sock, addr = tcp_sock.accept()
#             # לכל לקוח נפתח ת'רד נפרד
#             client_handler = threading.Thread(
#                 target=handle_client,
#                 args=(client_sock, addr),
#                 daemon=True
#             )
#             client_handler.start()
#     except KeyboardInterrupt:
#         print("\nShutting down server...")
#     finally:
#         stop_event.set()
#         tcp_sock.close()
#
#
# if __name__ == "__main__":
#     main()


# Server/server.py
"""
Blackjack Hackathon Server (UDP offers + TCP gameplay)

Responsibilities:
1) Broadcast OFFER packets via UDP every 1 second on port 13122
2) Accept TCP clients (port is included in OFFER)
3) For each client:
   - Read REQUEST (num rounds + team name)
   - Play N rounds using PAYLOAD messages (both directions)
   - Keep running forever
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
        s.connect(("8.8.8.8", 80))
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
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    offer = encode_offer(tcp_port, server_name)
    target = ("<broadcast>", CLIENT_UDP_PORT)

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
    game = BlackjackGame()
    game.start_round()

    # Initial reveal sequence (PDF: player gets 2 face-up; dealer shows 1 card)
    player_cards = list(game.player.cards)          # 2 cards
    dealer_up = game.dealer.cards[0]               # visible
    dealer_hidden = game.dealer.cards[1]           # hidden until dealer turn

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
