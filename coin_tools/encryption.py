import os
from cryptography.fernet import Fernet

def get_encryption_key() -> bytes:
    """
    Retrieve the encryption key from an environment variable.
    Raises an error if not set.
    """
    key = os.environ.get('COINTOOLS_ENC_KEY')
    if not key:
        raise EnvironmentError("Environment variable COINTOOLS_ENC_KEY is required but not set.")
    return key.encode('utf-8')

def encrypt_data(data: bytes, override_key = None) -> bytes:
    """
    Encrypts bytes using Fernet symmetric encryption.
    """
    key = get_encryption_key() if not override_key else override_key
    f = Fernet(key)
    return f.encrypt(data)

def decrypt_data(encrypted_data: bytes) -> bytes:
    """
    Decrypts bytes using Fernet symmetric encryption.
    """
    key = get_encryption_key()
    f = Fernet(key)
    return f.decrypt(encrypted_data)
