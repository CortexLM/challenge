"""Secure credential transfer mechanism for TDX-verified challenges."""

import base64
import json
import secrets
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


@dataclass
class EncryptedCredentials:
    """Encrypted database credentials."""

    encrypted_data: bytes
    ephemeral_public_key: bytes
    nonce: bytes

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for JSON serialization."""
        return {
            "encrypted_data": base64.b64encode(self.encrypted_data).decode(),
            "ephemeral_public_key": base64.b64encode(self.ephemeral_public_key).decode(),
            "nonce": base64.b64encode(self.nonce).decode(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "EncryptedCredentials":
        """Create from dictionary."""
        return cls(
            encrypted_data=base64.b64decode(data["encrypted_data"]),
            ephemeral_public_key=base64.b64decode(data["ephemeral_public_key"]),
            nonce=base64.b64decode(data["nonce"]),
        )


class CredentialEncryption:
    """Handles secure encryption and decryption of database credentials."""

    def __init__(self):
        self.cipher = ChaCha20Poly1305

    def generate_key_pair(self) -> tuple[x25519.X25519PrivateKey, x25519.X25519PublicKey]:
        """Generate an X25519 key pair."""
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()
        return private_key, public_key

    def derive_shared_secret(
        self, private_key: x25519.X25519PrivateKey, peer_public_key: x25519.X25519PublicKey
    ) -> bytes:
        """Derive a shared secret using ECDH."""
        shared_key = private_key.exchange(peer_public_key)

        # Use HKDF to derive a proper encryption key
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"platform-credential-transfer-v1",
            info=b"credential-encryption",
        )
        return hkdf.derive(shared_key)

    def encrypt_credentials(
        self,
        credentials: dict[str, str],
        recipient_public_key: x25519.X25519PublicKey,
    ) -> EncryptedCredentials:
        """Encrypt database credentials for a specific recipient."""
        # Generate ephemeral key pair
        ephemeral_private, ephemeral_public = self.generate_key_pair()

        # Derive shared secret
        shared_secret = self.derive_shared_secret(ephemeral_private, recipient_public_key)

        # Create cipher
        cipher = self.cipher(shared_secret)

        # Generate nonce
        nonce = secrets.token_bytes(12)  # ChaCha20Poly1305 uses 96-bit nonces

        # Serialize credentials
        plaintext = json.dumps(credentials).encode()

        # Encrypt with associated data (the ephemeral public key)
        ephemeral_public_bytes = ephemeral_public.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )

        ciphertext = cipher.encrypt(nonce, plaintext, ephemeral_public_bytes)

        return EncryptedCredentials(
            encrypted_data=ciphertext,
            ephemeral_public_key=ephemeral_public_bytes,
            nonce=nonce,
        )

    def decrypt_credentials(
        self,
        encrypted: EncryptedCredentials,
        private_key: x25519.X25519PrivateKey,
    ) -> dict[str, str]:
        """Decrypt database credentials."""
        # Reconstruct ephemeral public key
        ephemeral_public = x25519.X25519PublicKey.from_public_bytes(encrypted.ephemeral_public_key)

        # Derive shared secret
        shared_secret = self.derive_shared_secret(private_key, ephemeral_public)

        # Create cipher
        cipher = self.cipher(shared_secret)

        # Decrypt with associated data
        plaintext = cipher.decrypt(
            encrypted.nonce,
            encrypted.encrypted_data,
            encrypted.ephemeral_public_key,
        )

        # Parse credentials
        return json.loads(plaintext.decode())


class ChallengeCredentialManager:
    """Manages credentials for a challenge."""

    def __init__(self):
        self.encryption = CredentialEncryption()
        self._private_key: x25519.X25519PrivateKey | None = None
        self._public_key: x25519.X25519PublicKey | None = None

    def initialize(self) -> str:
        """Initialize the credential manager and return the public key."""
        self._private_key, self._public_key = self.encryption.generate_key_pair()

        # Return public key as base64
        public_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        return base64.b64encode(public_bytes).decode()

    def decrypt_credentials(self, encrypted_data: dict[str, str]) -> dict[str, str]:
        """Decrypt credentials received from platform-api."""
        if not self._private_key:
            raise RuntimeError("Credential manager not initialized")

        encrypted = EncryptedCredentials.from_dict(encrypted_data)
        return self.encryption.decrypt_credentials(encrypted, self._private_key)

    def get_public_key_bytes(self) -> bytes:
        """Get the raw public key bytes."""
        if not self._public_key:
            raise RuntimeError("Credential manager not initialized")

        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
