import binascii
from Crypto.Cipher import AES
import hashlib

def decrypt_easy7s(encrypted_hex):
    print(f"Encrypted Hex: {encrypted_hex}")

    # Chuyển hex sang bytes
    data = binascii.unhexlify(encrypted_hex)
    print(f"Data (bytes): {data.hex()}") # Print as hex for readability

    # Tách IV (16 byte đầu) và ciphertext
    iv = data[:16]
    ciphertext = data[16:]
    print(f"IV: {iv.hex()}")
    print(f"Ciphertext: {ciphertext.hex()}")

    # Tạo key từ MD5 của "www.itiankong.net"
    key_str = "www.itiankong.net"
    key_md5 = hashlib.md5(key_str.encode('utf-16le')).digest()
    print(f"Key (MD5 of '{key_str}' encoded with utf-16le): {key_md5.hex()}")
    print(f"Key length: {len(key_md5)} bytes") # Check key length

    # Giải mã AES-256-CBC
    # WARNING: If original encryption was AES-256, this 16-byte key is too short!
    cipher = AES.new(key_md5, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(ciphertext)
    print(f"Decrypted (before padding removal): {decrypted.hex()}")
    print(f"Length of decrypted data: {len(decrypted)} bytes")

    # Loại bỏ padding PKCS#7
    # padding_length = decrypted[-1]
    print(f"Padding length (last byte of decrypted): {padding_length}")

    # Check if padding_length is plausible
    # if not (1 <= padding_length <= 16):
        # print("WARNING: Padding length seems implausible. This often indicates incorrect decryption.")
        # Consider returning the raw decrypted data or handling this case specifically
        # return decrypted.decode('latin1', errors='ignore') # Or another fallback

    # try:
        # # Attempt to decode after padding removal
        # return decrypted[:-padding_length].decode('utf-16le')
    # except UnicodeDecodeError as e:
        # print(f"UnicodeDecodeError during final decode: {e}")
        # print(f"Data attempting to decode (after padding removal): {decrypted[:-padding_length].hex()}")
        # You might want to return a raw byte string or raise a custom error here
        # depending on how you want to handle decryption failures.
        raise # Re-raise the error to stop execution and show the traceback

# Giải mã mật khẩu cho Lan.Intel.7z
encrypted_hex = "5A9C8E58DEFC135585EB85E04861F1D99CD7044D6556422239988F61658E450A9FA474FEF03A6D5215409F3334A61199D3F74E4C18A86E8B5EAFF97810D91AEE547F3FB168788C2BA5BC021676AF0AF00B07E99457CA3690148BAA024224A02C7D7D08AB3B54A13A42BD6788339BB51F5F18F1E824811B7681F376DEE0A99395005646B4B9A01981FAB53C8150EA2B6241CBE4E33E83C664CC4A4C0B919F7D744960CE435302468A2B80D77BD4B9D7506624F5326F716EF6402E1531F674318B4AF578C3E1F112B230466B090E796DCBC6BCCBBD40B3F9FBFA4EE670C94036189EB9E416F6F25AEFF1E3A15A1182743CE0BC5896F51C7E8AEE81993C624C6BF23B140A8ABD1EF07D6DD86FA66C89ED9108EC98CAE294882FCD03AF6890931FAE44550D17191B4A2C452D7CDB3E4CB515645C06DB906E3BD2136976FF17E36A010DFAF214073045F9A726F346317E7B1E02AFABF8E870AF3F599677E87433CA58C2D7220A6D6ACE2DE2C80A419232901E79C756495A193BC6FE5EBA23ABD601500DAEE5FE07CC2983304E74D7C31291F5C342389DC379A07D15ADF1A17E477CB7FEFF8120888441227382F233E597BEBFEF0EE6268E812B2EEBA734075B096637F358EAFBC04370BE869C92A17ED4DB9473863847DBA1A2AD0376E12754D2E23FBB38B8B4B69CD5867FC4A175B15A039E02C3CDCBA070D3CC02557F22AF892EDB70AA69E12D5A45B73275C43167E80767EEBF0CEE05D960937FAB63BAD8BCED97CD4DE028EF7067A63FB41CB539577A0FB73F17FC46BA68C638C36C73FD8C313E"
password = decrypt_easy7s(encrypted_hex)
print(f"Password for Lan.Intel.7z: {password}")