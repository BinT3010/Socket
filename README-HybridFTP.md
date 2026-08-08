# Hybrid FTP - Modules

Dự án **Hybrid FTP** theo đề bài môn **Internetworking Protocol**.
Đây là phần code tập trung vào các nhiệm vụ của **Sang**:

1. **PORT** phía client - mở port lắng nghe, gửi địa chỉ cho server.
2. **TYPE** - cho phép chọn ASCII hoặc Binary.
3. **Hash Verification** - tự tính SHA-256 trước khi STOR và sau khi RETR, so sánh với server.
4. **Test** tải lên/xuống file ảnh thật qua client.
5. **Test đa luồng** - đóng vai nhiều client kết nối đồng thờii.

---

## 📁 Cấu trúc thư mục

```
hybrid_ftp/
├── common/
│   ├── __init__.py
│   ├── protocol.py          # Định nghĩa gói tin UDP, PORT/PASV parser, ReplyCode
│   └── utils.py             # SHA-256, đọc file chunk
├── client/
│   ├── __init__.py
│   ├── control_channel.py   # Kênh điều khiển TCP
│   ├── data_channel.py      # Kênh dữ liệu UDP + Reliable Stop-and-Wait
│   ├── hash_verify.py       # Module kiểm tra hash (Task #3)
│   ├── transfer.py          # STOR/RETR + PORT/PASV setup + hash integration
│   ├── client.py            # Lớp client chính
│   └── cli.py               # Giao diện dòng lệnh tương tác
├── server/
│   ├── __init__.py
│   └── server.py            # Server test đơn giản (multi-threaded)
├── tests/
│   ├── __init__.py
│   ├── test_concurrent.py   # Script test đa luồng (Task #5)
│   └── test_image.jpg       # File ảnh test mẫu
├── README.md
└── requirements.txt
```

---

## 🚀 Cài đặt & Chạy

### 1. Yêu cầu
- Python 3.10+
- Không cần thư viện bên thứ ba (chỉ dùng thư viện chuẩn)

### 2. Chạy Server
```bash
cd hybrid_ftp
python -m server.server
```
Server sẽ lắng nghe tại `0.0.0.0:2121`.

### 3. Chạy Client (Interactive CLI)
```bash
python -m client.cli 127.0.0.1 2121
```

### 4. Các lệnh CLI chính

| Lệnh | Mô tả |
|------|-------|
| `connect <host> [port]` | Kết nối đến server |
| `login <user> <pass>` | Đăng nhập (demo: mật khẩu bất kỳ) |
| `type A` / `type I` | Chuyển ASCII / Binary |
| `port` | Bật chế độ Active (PORT) |
| `pasv` | Bật chế độ Passive (PASV) |
| `upload <local> [remote]` | Upload file + kiểm tra hash |
| `download <remote> <local>` | Download file + kiểm tra hash |
| `hash <filename>` | Lấy hash SHA-256 từ server |
| `ls` | Liệt kê thư mục |
| `quit` | Thoát |

---

## 🧪 Test các nhiệm vụ của Sang

### Task 1: PORT Mode
```
ftp> port
ftp> upload tests/test_image.jpg myphoto.jpg
```
Client tự động mở UDP port ngẫu nhiên, gửi lệnh `PORT h1,h2,h3,h4,p1,p2` cho server.

### Task 2: TYPE
```
ftp> type I
[Transfer] Type set to BINARY
ftp> type A
[Transfer] Type set to ASCII
```

### Task 3: Hash Verification
Khi chạy `upload` hoặc `download`, client tự động:
1. Tính SHA-256 **trước** khi gửi (STOR) hoặc **sau** khi nhận (RETR).
2. Gửi lệnh `HASH <filename>` đến server.
3. So sánh và in báo cáo:
```
============================================================
  HASH VERIFICATION REPORT - UPLOAD (STOR)
============================================================
  Local  SHA-256: e3b0c44298fc1c149afbf4c8996fb924...
  Server SHA-256: e3b0c44298fc1c149afbf4c8996fb924...
  Status: ✅ TOÀN VẸN (Integrity OK)
============================================================
```

### Task 4: Test file ảnh thật
File test mẫu: `tests/test_image.jpg` (đã tạo sẵn).
```bash
# Terminal 1
python -m server.server

# Terminal 2
python -m client.cli 127.0.0.1 2121
ftp> login sang 123
ftp> type I
ftp> upload tests/test_image.jpg
ftp> download test_image.jpg tests/downloaded.jpg
```

### Task 5: Test đa luồng (Concurrent Clients)
```bash
python tests/test_concurrent.py
```
Script này tạo **5 client đồng thờii**, mỗi client upload một file khác nhau.

---

## 🔧 Kiến trúc Reliable UDP (Stop-and-Wait)

```
Client                          Server
  | ---- UDP DATA (seq=0) ---->   |
  | <--- UDP ACK  (ack=0) -----   |
  | ---- UDP DATA (seq=1) ---->   |
  | <--- UDP ACK  (ack=1) -----   |
  | ---- UDP FIN  (seq=N) ---->   |
  | <--- UDP ACK  (ack=N) -----   |
```

- **Header UDP custom**: 12 bytes (seq 4B, ack 4B, len 2B, flags 1B, checksum 1B)
- **Timeout**: 2 giây, retry tối đa 5 lần.
- **Checksum**: Internet Checksum (RFC 1071).

---

## 📝 Ghi chú

- Server test này **chấp nhận mọi mật khẩu** để tiện demo.
- Chế độ `PORT` trong demo sử dụng IP local auto-detect.
- Nếu chạy client và server trên **2 máy khác nhau**, cần cấu hình IP public cho `PORT`.

---

## 👤 Tác giả module

**Sang** - PORT | TYPE | Hash Verify | Reliable UDP | Concurrent Test
