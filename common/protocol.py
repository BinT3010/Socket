"""
Hybrid FTP Protocol Definitions
Defines constants, packet formats, and helper functions for the custom UDP layer.
"""
import struct
import hashlib

# ---------------------------------------------------------------------------
# FTP Reply Codes
# ---------------------------------------------------------------------------
class ReplyCode:
    READY = "220"
    GOODBYE = "221"
    TRANSFER_COMPLETE = "226"
    LOGIN_SUCCESS = "230"
    USERNAME_OK = "331"
    PENDING_ACTION = "350"
    ACTION_OK = "250"
    PATH_CREATED = "257"
    CANT_OPEN_DATA = "425"
    ABORTED = "426"
    FILE_UNAVAILABLE = "450"
    SYNTAX_ERROR = "500"
    NOT_LOGGED_IN = "530"
    COMMAND_OK = "200"
    ENTERING_PASV = "227"
    OPENING_DATA = "150"

# ---------------------------------------------------------------------------
# Data Types
# ---------------------------------------------------------------------------
class DataType:
    ASCII = "A"
    BINARY = "I"

# ---------------------------------------------------------------------------
# Custom UDP Packet Format (Reliable Data Transfer)
# ---------------------------------------------------------------------------
#  0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                        Sequence Number                        |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                         ACK Number                            |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | Flags |     Payload Length      |          Checksum           |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                           Payload                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
# Flags:
#   bit 0: SYN - Synchronize / Start of transfer
#   bit 1: ACK - Acknowledgment
#   bit 2: FIN - Finish / End of transfer
#   bit 3: DATA - Data packet
#   bit 4: ERR - Error
# ---------------------------------------------------------------------------

UDP_HEADER_FORMAT = ">IIHBH"
UDP_HEADER_SIZE = struct.calcsize(UDP_HEADER_FORMAT)
UDP_MAX_PAYLOAD = 1024  # bytes per packet
UDP_PACKET_SIZE = UDP_HEADER_SIZE + UDP_MAX_PAYLOAD

class UDPPacket:
    FLAG_SYN = 0x01
    FLAG_ACK = 0x02
    FLAG_FIN = 0x04
    FLAG_DATA = 0x08
    FLAG_ERR = 0x10

    def __init__(self, seq=0, ack=0, flags=0, payload=b""):
        self.seq = seq
        self.ack = ack
        self.flags = flags
        self.payload = payload
        self.payload_len = len(payload)
        self.checksum = 0

    def compute_checksum(self):
        """Simple Internet Checksum (RFC 1071 style)."""
        data = struct.pack(UDP_HEADER_FORMAT, self.seq, self.ack, self.payload_len, self.flags, 0)
        data += self.payload
        if len(data) % 2:
            data += b"\x00"
        s = 0
        for i in range(0, len(data), 2):
            w = (data[i] << 8) + data[i + 1]
            s = (s + w) & 0xFFFF
            s = (s & 0xFFFF) + (s >> 16)
        return ~s & 0xFFFF

    def pack(self):
        self.checksum = self.compute_checksum()
        header = struct.pack(UDP_HEADER_FORMAT, self.seq, self.ack, self.payload_len, self.flags, self.checksum)
        return header + self.payload

    @classmethod
    def unpack(cls, data):
        if len(data) < UDP_HEADER_SIZE:
            return None
        seq, ack, payload_len, flags, checksum = struct.unpack(UDP_HEADER_FORMAT, data[:UDP_HEADER_SIZE])
        payload = data[UDP_HEADER_SIZE:UDP_HEADER_SIZE + payload_len]
        pkt = cls(seq, ack, flags, payload)
        pkt.checksum = checksum
        pkt.payload_len = payload_len
        return pkt

    def is_valid(self):
        return self.compute_checksum() == self.checksum

    def __repr__(self):
        flag_names = []
        if self.flags & self.FLAG_SYN: flag_names.append("SYN")
        if self.flags & self.FLAG_ACK: flag_names.append("ACK")
        if self.flags & self.FLAG_FIN: flag_names.append("FIN")
        if self.flags & self.FLAG_DATA: flag_names.append("DATA")
        if self.flags & self.FLAG_ERR: flag_names.append("ERR")
        return f"<UDPPacket seq={self.seq} ack={self.ack} flags={'|'.join(flag_names)} len={self.payload_len}>"


def format_port_cmd(ip: str, port: int) -> str:
    """Convert IP and port to FTP PORT command argument: h1,h2,h3,h4,p1,p2"""
    parts = ip.split(".")
    p1 = port // 256
    p2 = port % 256
    return ",".join(parts + [str(p1), str(p2)])


def parse_pasv_response(msg: str):
    """Parse PASV response to extract IP and port."""
    import re
    m = re.search(r"\((\d+,\d+,\d+,\d+,\d+,\d+)\)", msg)
    if not m:
        return None, None
    parts = list(map(int, m.group(1).split(",")))
    ip = ".".join(map(str, parts[:4]))
    port = parts[4] * 256 + parts[5]
    return ip, port
