# import socket
# import time
#
# from Server.protocolServer import decode_request, ProtocolError
# from Server.protocolServer import encode_offer
#
# def udp_broadcast_offers(tcp_port: int, stop_event: threading.Event):
#     """
#     Broadcast offer every 1 second.
#     """
#     msg = encode_offer(tcp_port, TEAM_NAME)
#
#     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Create an IPv4( 192.168.1.10) UDP socket
#
#     # Enable broadcast mode on the socket
#     s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
#
#     # Loop until the server asks this thread to stop
#     while not stop_event.is_set():
#         try:
#             # Send the offer message to all clients on the local network
#             s.sendto(msg, ("<broadcast>", CLIENT_UDP_PORT))
#         except OSError:
#             pass
#
#         # to avoid busy waiting
#         time.sleep(1)
#
#     s.close()
#
# def main(): #שלדד !!!
#     """
#     Start the server:
#     - Open a TCP socket on an available port
#     - Broadcast UDP offers so clients can discover the server
#     - Keep running until manually stopped
#     """
#
#     # Create a TCP socket (IPv4, stream-based)
#     tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#
#     # Allow quick reuse of the address after server restart ??
#     tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#
#     # Bind to any available port chosen by the OS
#     tcp_sock.bind(("", 0))
#
#     # Start listening for incoming TCP connections
#     tcp_sock.listen()
#
#     # Retrieve the actual TCP port assigned by the OS
#     tcp_port = tcp_sock.getsockname()[1]
#
#     print(f"Server up. TCP port = {tcp_port}. Broadcasting offers...")
#
#     stop_event = threading.Event()
#
#     # Start a background thread to broadcast UDP offers
#     t = threading.Thread(
#         target=udp_broadcast_offers,
#         args=(tcp_port, stop_event),
#         daemon=True
#     )
#     t.start()
#
#     try:
#         # Keep the server running (TCP accept will be added later)
#         while True:
#             client_sock, addr = tcp_sock.accept()
#             print(f"Client connected from {addr}")
#             client_sock.close()
#     except KeyboardInterrupt:
#         # Handle manual server shutdown (Ctrl+C)
#         print("Shutting down server...")
#     finally:
#         # Stop the UDP broadcast thread and clean up
#         stop_event.set()
#         tcp_sock.close()


import socket
import threading
import time
import sys

# ייבוא מהקבצים הקיימים שלך
from Formats.packet_formats import CLIENT_UDP_PORT, TEAM_NAME, ROUND_ONGOING
from game import BlackjackGame
from protocolServer import (
    encode_offer,
    decode_request,
    decode_payload_decision,
    encode_payload_server,
    ProtocolError
)


def handle_client(client_sock, addr):
    """
    פונקציה המטפלת בלקוח ספציפי בת'רד נפרד.
    """
    print(f"[TCP] Connection accepted from {addr}")
    try:
        # 1. קבלת הודעת REQUEST (38 בתים)
        data = client_sock.recv(38)
        if not data:
            return

        num_rounds, team_name = decode_request(data)
        print(f"[GAME] Client '{team_name}' wants to play {num_rounds} rounds.")

        # 2. לולאת המשחק - ניהול הסיבובים
        for round_idx in range(1, num_rounds + 1):
            game = BlackjackGame()
            # התחלת סיבוב - מחלקת קלפים ראשונים
            game.start_round()

            # שליחת קלף שחקן 1
            p1_rank, p1_suit = game.player.cards[0]
            client_sock.sendall(encode_payload_server(ROUND_ONGOING, p1_rank, p1_suit))

            # שליחת קלף שחקן 2
            p2_rank, p2_suit = game.player.cards[1]
            client_sock.sendall(encode_payload_server(ROUND_ONGOING, p2_rank, p2_suit))

            # שליחת קלף דילר גלוי (הראשון)
            d1_rank, d1_suit = game.dealer.cards[0]
            client_sock.sendall(encode_payload_server(ROUND_ONGOING, d1_rank, d1_suit))

            # --- תור השחקן ---
            current_status = ROUND_ONGOING
            while current_status == ROUND_ONGOING:
                # המתנה להחלטת הלקוח (HIT/STAND) - 10 בתים
                decision_data = client_sock.recv(10)
                if not decision_data:
                    break

                decision = decode_payload_decision(decision_data)

                if decision == b'Hittt':
                    res, card = game.player_hit()
                    rank, suit = card
                    client_sock.sendall(encode_payload_server(res, rank, suit))
                    current_status = res
                else:  # STAND
                    res, dealer_cards = game.player_stand()
                    # אם השחקן עמד, הדילר מושך קלפים. נשלח אותם אחד אחד.
                    for i, d_card in enumerate(dealer_cards):
                        d_rank, d_suit = d_card
                        # רק הקלף האחרון שנשלח נושא את התוצאה הסופית (Win/Loss/Tie)
                        status = res if i == len(dealer_cards) - 1 else ROUND_ONGOING
                        client_sock.sendall(encode_payload_server(status, d_rank, d_suit))

                    # במקרה שהדילר לא משך אף קלף (היה לו כבר 17+)
                    if not dealer_cards:
                        # שולחים הודעת עדכון עם קלף הדילר השני שכבר היה לו, ועם התוצאה
                        d2_rank, d2_suit = game.dealer.cards[1]
                        client_sock.sendall(encode_payload_server(res, d2_rank, d2_suit))

                    current_status = res

            print(f"[GAME] Round {round_idx}/{num_rounds} for {team_name} finished.")

    except (ProtocolError, ConnectionResetError, socket.timeout) as e:
        print(f"[ERROR] Connection with {addr} closed: {e}")
    finally:
        client_sock.close()
        print(f"[TCP] Connection closed with {addr}")


def udp_broadcast_offers(tcp_port: int, stop_event: threading.Event):
    """
    שידור הודעות Offer ב-UDP כל שנייה.
    """
    msg = encode_offer(tcp_port, TEAM_NAME)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while not stop_event.is_set():
        try:
            s.sendto(msg, ("<broadcast>", CLIENT_UDP_PORT))
        except OSError:
            pass
        time.sleep(1)
    s.close()


def main():
    # יצירת Socket TCP
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        tcp_sock.bind(("", 0))  # הצמדה לפורט פנוי שהמערכת תבחר
        tcp_sock.listen(5)
        tcp_port = tcp_sock.getsockname()[1]
        print(f"Server started on TCP port {tcp_port}")
    except Exception as e:
        print(f"Failed to bind TCP socket: {e}")
        return

    stop_event = threading.Event()
    # הפעלת ת'רד השידורים
    broadcast_thread = threading.Thread(
        target=udp_broadcast_offers,
        args=(tcp_port, stop_event),
        daemon=True
    )
    broadcast_thread.start()

    print("Server is running. Press Ctrl+C to stop.")
    try:
        while True:
            # קבלת חיבורים חדשים
            client_sock, addr = tcp_sock.accept()
            # לכל לקוח נפתח ת'רד נפרד
            client_handler = threading.Thread(
                target=handle_client,
                args=(client_sock, addr),
                daemon=True
            )
            client_handler.start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        stop_event.set()
        tcp_sock.close()


if __name__ == "__main__":
    main()