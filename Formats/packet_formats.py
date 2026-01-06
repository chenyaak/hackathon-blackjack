"""
Global constants for the Blackjack client-server protocol.
All protocol-related magic numbers are defined here
to avoid hard-coded values in the codebase.
"""

# ===== Protocol =====

MAGIC_COOKIE = 0xabcddcba

# Message types
OFFER_TYPE   = 0x2
REQUEST_TYPE = 0x3
PAYLOAD_TYPE = 0x4


# ===== Network =====

# UDP port that clients listen on for offers (hardcoded by assignment)
CLIENT_UDP_PORT = 13122


# ===== Game Results (server -> client) =====

ROUND_ONGOING = 0x0
ROUND_TIE     = 0x1
ROUND_LOSS    = 0x2
ROUND_WIN     = 0x3


# ===== Card Suits =====

HEART   = 0
DIAMOND = 1
CLUB    = 2
SPADE   = 3


# ===== Player Decisions =====

HIT   = b"Hittt"   # must be exactly 5 bytes
STAND = b"Stand"   # must be exactly 5 bytes
