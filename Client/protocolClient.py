"""
Protocol encoding/decoding for the Blackjack game.
This file defines the exact packet formats shared by client and server.
"""

import struct
from Formats.packet_formats import (
    MAGIC_COOKIE,
    OFFER_TYPE,
    REQUEST_TYPE,
    PAYLOAD_TYPE,
    HIT,
    STAND,
    ROUND_ONGOING,
    ROUND_WIN,
    ROUND_LOSS,
    ROUND_TIE,
)


# =====================
# Exceptions
# =====================

class ProtocolError(Exception):
    pass


# =====================
# Helpers
# =====================


# check valid message (!B = 4 bytes) and its type (offer/ payload - as expected)
def check_cookie_and_type(data: bytes, expected_type: int):
    cookie, msg_type = struct.unpack("!IB", data[:5])
    if cookie != MAGIC_COOKIE:
        raise ProtocolError("Invalid magic cookie")
    if msg_type != expected_type:
        raise ProtocolError("Invalid message type")


# encode name (string) to bytes
def encode_name(text: str, length: int) -> bytes:
    raw = text.encode("utf-8")
    return raw[:length].ljust(length, b"\x00")


# decode name (bytes) to string
def decode_name(raw: bytes) -> str:
    return raw.rstrip(b"\x00").decode("utf-8")


# =====================
# Offer (UDP) — Server → Client
# =====================

# decode offer message
def decode_offer(data: bytes):
    """
    Offer format:
    cookie (4B) | type (1B) | server port (2B) | server name (32B) #total of 39 bytes
    """
    if len(data) != 39:
        raise ProtocolError("Invalid offer length")

    check_cookie_and_type(data, OFFER_TYPE)

    _, _, port = struct.unpack("!IBH",
                               data[:7])  # first 7 bytes: I=4 bytes (Magic cookie), B= 1 byte (type), H= 2 bytes (port)
    server_name = decode_name(data[7:39])  # last 32 bytes: Server's name

    return port, server_name


# =====================
# Request (TCP) — Client → Server
# =====================

# encode request message
def encode_request(num_rounds: int, team_name: str) -> bytes:
    """
    Request format:
    cookie (4B) | type (1B) | num rounds (1B) | team name (32B)
    """
    return struct.pack(
        "!IBB32s",
        MAGIC_COOKIE,  # I = 4 bytes
        REQUEST_TYPE,  # B = 1 byte
        num_rounds,  # B = 1 byte
        encode_name(team_name, 32),  # 32 bytes
    )


# =====================
# Payload — Client → Server
# =====================

# encode payload message - player chooses HIT or STAND
def encode_payload_decision(decision: bytes) -> bytes:
    """
    decision must be exactly b'Hittt' or b'Stand'
    """
    if decision not in (HIT, STAND):
        raise ValueError("Invalid player decision")

    return struct.pack(
        "!IB5s",
        MAGIC_COOKIE,  # I= 4 bytes
        PAYLOAD_TYPE,  # B = 1 byte
        decision,  # 5 bytes
    )


# decode payload message - round result and card value
def decode_payload_server(data: bytes):
    """
    Payload from server:
    cookie (4B) | type (1B) | result (1B) | rank (2B) | suit (1B) #total of 9 bytes
    """
    if len(data) != 9:
        raise ProtocolError("Invalid payload length")

    check_cookie_and_type(data, PAYLOAD_TYPE)

    _, _, result, rank, suit = struct.unpack("!IBBHB", data)

    return result, rank, suit
