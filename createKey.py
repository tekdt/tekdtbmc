import hashlib
import base64
import struct
import os
from Crypto.PublicKey import RSA
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

class DeterministicRNG:
    def __init__(self, password):
        # Tạo hạt giống (seed) từ mật khẩu
        self.seed = hashlib.sha512(password.encode('utf-8')).digest()
        self.counter = 0

    def get_bytes(self, n):
        """Hàm này sẽ cung cấp n bytes dữ liệu dựa trên seed và counter hiện tại"""
        result = b""
        while len(result) < n:
            # Tạo hash mới dựa trên seed + counter
            hash_chunk = hashlib.sha512(self.seed + struct.pack(">Q", self.counter)).digest()
            result += hash_chunk
            self.counter += 1
        return result[:n]

def export_windows_rsa_blob(key):
    """Xuất RSA Public Key sang BCRYPT_RSAKEY_BLOB chuẩn Windows"""
    n = key.n
    e = key.e
    # RSA-2048: n phải luôn là 256 bytes
    n_bytes = n.to_bytes(256, 'big')
    # e thường là 65537 (0x010001), Windows yêu cầu độ dài thực tế (thường là 3 bytes)
    e_bytes = e.to_bytes((e.bit_length() + 7) // 8, 'big')

    # BCRYPT_RSAKEY_BLOB header
    # Magic: RSA1 (0x31415352)
    header = struct.pack('<6I', 
        0x31415352,  
        2048,        
        len(e_bytes),
        256,         # cbModulus cố định 256 cho RSA-2048
        0, 0         
    )
    blob = header + e_bytes + n_bytes
    return base64.b64encode(blob).decode('utf-8')

# --- CHƯƠNG TRÌNH CHÍNH ---
print("--- CÔNG CỤ QUẢN LÝ KHÓA TEKDT BMC ---")
master_password = r"<@INPUT_SECRET_KEY_HERE!>"

if not master_password:
    print("Mật khẩu không được để trống!")
    exit()

print("\n[*] Đang tính toán cặp khóa RSA-2048 định danh...")
print("[!] Quá trình này có thể mất từ 5-30 giây tùy vào tốc độ CPU...")

# Khởi tạo bộ sinh số định danh
rng = DeterministicRNG(master_password)

# Sinh khóa RSA (Sử dụng rng.get_bytes làm nguồn "ngẫu nhiên")
try:
    key_pair = RSA.generate(2048, randfunc=rng.get_bytes)
    
    # 1. Lưu Private Key (PEM)
    with open("private_key.pem", "wb") as f:
        f.write(key_pair.export_key('PEM'))

    # 2. Lưu Public Key (PEM)
    with open("public_key.pem", "wb") as f:
        f.write(key_pair.publickey().export_key('PEM'))

    # 3. Tạo chuỗi cho AutoIt
    autoit_blob = export_windows_rsa_blob(key_pair.publickey())

    print("-" * 60)
    print("THÀNH CÔNG!")
    print(f"[*] Đã tạo/khôi phục file: {os.path.abspath('private_key.pem')}")
    print(f"[*] Đã tạo/khôi phục file: {os.path.abspath('public_key.pem')}")
    print("-" * 60)
    print("Dán chuỗi này vào $g_sPublicKeyBase64 trong AutoIt:")
    print("\n" + autoit_blob + "\n")
    print("-" * 60)
    print("LƯU Ý: Nếu mất file, chỉ cần chạy lại với đúng mật khẩu này để khôi phục.")

except Exception as e:
    print(f"\n[!] Có lỗi xảy ra: {str(e)}")

input("\nNhấn Enter để thoát...")