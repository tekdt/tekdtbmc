import hashlib
import base64
import struct
import os
from Crypto.PublicKey import RSA

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
    """Xuất Public Key sang định dạng Windows BCRYPT_RSAKEY_BLOB cho AutoIt"""
    # RSA-2048: e thường là 65537 (0x010001)
    e_int = key.e
    n_int = key.n
    
    e_bytes = e_int.to_bytes((e_int.bit_length() + 7) // 8, byteorder='big')
    n_bytes = n_int.to_bytes(256, byteorder='big') 

    # Magic 'RSA1' (0x31415352)
    header = struct.pack('<I I I I I I', 0x31415352, 2048, len(e_bytes), len(n_bytes), 0, 0)
    blob = header + e_bytes + n_bytes
    return base64.b64encode(blob).decode('utf-8')

# --- CHƯƠNG TRÌNH CHÍNH ---
print("--- CÔNG CỤ QUẢN LÝ KHÓA TEKDT BMC ---")
master_password = r"<Điền_khoá_mã_hoá_của_bạn_vào_đây>"

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
    autoit_blob = export_windows_rsa_blob(key_pair)

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