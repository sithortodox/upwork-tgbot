import sys
sys.path.insert(0, '/app')

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import structlog

logger = structlog.get_logger()

class CryptoService:
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or os.getenv("ENCRYPTION_KEY", "default-secret-key-change-in-production")
        self._fernet = None
    
    def _get_fernet(self) -> Fernet:
        if self._fernet is None:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'upwork-bot-salt',
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self.secret_key.encode()))
            self._fernet = Fernet(key)
        return self._fernet
    
    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return None
        fernet = self._get_fernet()
        encrypted = fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return None
        fernet = self._get_fernet()
        encrypted = base64.urlsafe_b64decode(ciphertext.encode())
        decrypted = fernet.decrypt(encrypted)
        return decrypted.decode()

crypto_service = CryptoService()
