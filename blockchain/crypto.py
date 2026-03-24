"""
Wrath of Cali Blockchain - Core Crypto Utilities
"""
import hashlib
import secrets
import json
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, asdict, field

# Simple base58 implementation
class SimpleBase58:
    """Simple base58-like encoding"""
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    
    @staticmethod
    def b58encode(data):
        if isinstance(data, str):
            data = data.encode()
        # Simple hex encoding for now
        return data.hex()
    
    @staticmethod
    def b58decode(data):
        if isinstance(data, str):
            return bytes.fromhex(data)
        return data

base58 = SimpleBase58()


def sha256(data: str) -> str:
    """Double SHA256 like Bitcoin"""
    return hashlib.sha256(hashlib.sha256(data.encode()).digest()).hexdigest()


def ripemd160(data: str) -> str:
    """RIPEMD160 hash"""
    h = hashlib.new('ripemd160')
    h.update(data.encode())
    return h.hexdigest()


def hash160(data: str) -> str:
    """Hash160: RIPEMD160(SHA256(x)) - Bitcoin address format"""
    sha = hashlib.sha256(data.encode()).digest()
    h = hashlib.new('ripemd160')
    h.update(sha)
    return h.hexdigest()


def generate_keypair() -> Tuple[str, str]:
    """Generate private/public key pair"""
    # Simplified - in production use proper EC
    private_key = secrets.token_hex(32)
    public_key = sha256(private_key)
    return private_key, public_key


def get_address(public_key: str) -> str:
    """Generate address from public key"""
    return base58.b58encode(hash160(public_key))


def sign(data: str, private_key: str) -> str:
    """Sign data with private key (simplified)"""
    return sha256(data + private_key)


def verify_signature(data: str, signature: str, public_key: str) -> bool:
    """Verify signature"""
    expected_sig = sha256(data + public_key)  # Simplified - use proper verification
    return signature == expected_sig


def encode_base58(data: str) -> str:
    """Encode to base58"""
    return base58.b58encode(data)


def decode_base58(data: str) -> str:
    """Decode from base58"""
    decoded = base58.b58decode(data)
    return decoded.decode() if isinstance(decoded, bytes) else decoded


class CryptoUtils:
    """Crypto utility class"""
    
    @staticmethod
    def hash(data: str) -> str:
        return sha256(data)
    
    @staticmethod
    def generate_address() -> Tuple[str, str, str]:
        priv, pub = generate_keypair()
        addr = get_address(pub)
        return addr, priv, pub
    
    @staticmethod
    def sign_transaction(tx_data: str, private_key: str) -> str:
        return sign(tx_data, private_key)


if __name__ == "__main__":
    # Test
    addr, priv, pub = CryptoUtils.generate_address()
    print(f"Address: {addr}")
    print(f"Private: {priv}")
    print(f"Public: {pub}")