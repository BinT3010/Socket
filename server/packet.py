import struct
from checksum import calculate_checksum, verify_checksum

# Định dạng header:
# H = unsigned short (2 bytes)
# B = unsigned char (1 byte)
# B = unsigned char (1 byte)
# H = unsigned short (2 bytes)

HEADER_FORMAT = "!HBBH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


class Packet:
    # Loại gói tin
    DATA = 0
    ACK = 1

    def __init__(self, packet_type, seq, data=b''):
        self.packet_type = packet_type
        self.seq = seq
        self.data = data

    def to_bytes(self):
        # Độ dài dữ liệu
        length = len(self.data)

        # Tạo header với checksum = 0 để tính checksum
        header = struct.pack(
            HEADER_FORMAT,
            0,
            self.packet_type,
            self.seq,
            length
        )

        # Tính checksum trên header + data
        checksum = calculate_checksum(header + self.data)

        # Tạo lại header với checksum thật
        header = struct.pack(
            HEADER_FORMAT,
            checksum,
            self.packet_type,
            self.seq,
            length
        )

        return header + self.data
    
    @staticmethod
    def from_bytes(raw_data):
        if len(raw_data) < HEADER_SIZE:
            raise ValueError(
                f"Packet quá ngắn: nhận {len(raw_data)} bytes, "
                f"cần ít nhất {HEADER_SIZE} bytes"
            )

        checksum, packet_type, seq, length = struct.unpack(
            HEADER_FORMAT,
            raw_data[:HEADER_SIZE]
        )

        # Kiểm tra packet có đủ phần data theo length không
        if len(raw_data) < HEADER_SIZE + length:
            raise ValueError(
                f"Packet không đầy đủ: header={HEADER_SIZE}, "
                f"data cần={length}, nhận={len(raw_data) - HEADER_SIZE}"
            )

        data = raw_data[HEADER_SIZE:HEADER_SIZE + length]

        packet = Packet(packet_type, seq, data)

        header = struct.pack(
            HEADER_FORMAT,
            0,
            packet_type,
            seq,
            length
        )

        if not verify_checksum(header + data, checksum):
            raise ValueError("Checksum không hợp lệ!")

        return packet