# Server/protocol.py

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

def check_cookie_and_type(data: bytes, expected_type: int):
    cookie, msg_type = struct.unpack("!IB", data[:5])
    if cookie != MAGIC_COOKIE:
        raise ProtocolError("Invalid magic cookie")
    if msg_type != expected_type:
        raise ProtocolError("Invalid message type")


def encode_name(text: str, length: int) -> bytes:
    raw = text.encode("utf-8")
    return raw[:length].ljust(length, b"\x00")


def decode_name(raw: bytes) -> str:
    return raw.rstrip(b"\x00").decode("utf-8")


# =====================
# Offer (UDP) — Server → Client
# =====================

def encode_offer(tcp_port: int, server_name: str) -> bytes:
    """
    Offer format:
    cookie (4B) | type (1B) | server port (2B) | server name (32B)
    """
    return struct.pack(
        "!IBH32s",
        MAGIC_COOKIE,  # I = 4 bytes
        OFFER_TYPE,  # B = 1 byte
        tcp_port,  # B = 1 byte
        encode_name(server_name, 32),  # 32 bytes
    )


# =====================
# Request (TCP) — Client → Server
# =====================

def decode_request(data: bytes):
    """
    Request format:
    cookie (4B) | type (1B) | num rounds (1B) | team name (32B)
    """
    if len(data) != 38:
        raise ProtocolError("Invalid request length")

    check_cookie_and_type(data, REQUEST_TYPE)

    _, _, num_rounds = struct.unpack("!IBB", data[:6])
    team_name = decode_name(data[6:38])

    return num_rounds, team_name


# =====================
# Payload — Client → Server
# =====================

def decode_payload_decision(data: bytes) -> bytes:
    """
    Payload from client:
    cookie (4B) | type (1B) | decision (5B)
    """
    if len(data) != 10:
        raise ProtocolError("Invalid payload length")

    check_cookie_and_type(data, PAYLOAD_TYPE)

    _, _, decision = struct.unpack("!IB5s", data)

    if decision not in (HIT, STAND):
        raise ProtocolError("Invalid player decision")

    return decision


# =====================
# Payload — Server → Client
# =====================

def encode_payload_server(result: int, rank: int = 0, suit: int = 0) -> bytes:
    """
    Payload to client:
    cookie (4B) | type (1B) | result (1B) | rank (2B) | suit (1B)
    """
    return struct.pack(
        "!IBBHB",
        MAGIC_COOKIE,
        PAYLOAD_TYPE,
        result,
        rank,
        suit,
    )
