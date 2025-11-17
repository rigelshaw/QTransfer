import hashlib
import secrets
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

class QuantumCrypto:
    @staticmethod
    def derive_aes_key(bb84_key_hex: str, salt: str, info: bytes = b"qtransfer-aes") -> bytes:
        """Derive AES key from BB84 key using HKDF-SHA256"""
        bb84_key_bytes = bytes.fromhex(bb84_key_hex)
        
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # 32 bytes = 256-bit key
            salt=salt.encode(),
            info=info
        )
        derived_key = hkdf.derive(bb84_key_bytes)
        return derived_key
    
    @staticmethod
    def encrypt_chunk(data: bytes, key: bytes, nonce: bytes) -> bytes:
        """Encrypt data chunk with AES-GCM"""
        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce))
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(data) + encryptor.finalize()
        return encryptor.tag + encrypted_data
    
    @staticmethod
    def decrypt_chunk(encrypted_data: bytes, key: bytes, nonce: bytes) -> bytes:
        """Decrypt data chunk with AES-GCM"""
        tag = encrypted_data[:16]
        ciphertext = encrypted_data[16:]
        
        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag))
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    @staticmethod
    def generate_key_fingerprint(key: bytes) -> str:
        """Generate a human-readable key fingerprint"""
        return hashlib.sha256(key).hexdigest()[:16]
    
    @staticmethod
    def generate_nonce() -> bytes:
        """Generate a 12-byte nonce for AES-GCM"""
        return secrets.token_bytes(12)
