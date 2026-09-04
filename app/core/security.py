import os
import hmac
import hashlib
import json
import base64
import time
from typing import Optional, Dict, Any
from app.core.config import settings

# Constantes de seguridad
PBKDF2_ITERATIONS = 100_000
SALT_BYTES = 16
DEFAULT_TOKEN_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 días

def get_password_hash(password: str) -> str:
    """Genera un hash seguro con PBKDF2-HMAC-SHA256 y salt aleatorio."""
    salt = os.urandom(SALT_BYTES)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        PBKDF2_ITERATIONS
    )
    # Formato: pbkdf2_sha256$iterations$salt_hex$key_hex
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña en texto plano coincide con el hash almacenado."""
    if not hashed_password:
        return False
    
    # Compatibilidad con contraseñas planas iniciales
    if not hashed_password.startswith("pbkdf2_sha256$"):
        return plain_password == hashed_password
    
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4:
            return False
        
        _, iterations_str, salt_hex, expected_key_hex = parts
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(expected_key_hex)
        
        candidate_key = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt,
            iterations
        )
        return hmac.compare_digest(candidate_key, expected_key)
    except Exception:
        return False

def create_access_token(data: Dict[str, Any], expires_in: int = DEFAULT_TOKEN_EXPIRY_SECONDS) -> str:
    """Genera un token de sesión firmado criptográficamente con HMAC-SHA256."""
    payload = data.copy()
    now = int(time.time())
    payload["iat"] = now
    payload["exp"] = now + expires_in
    
    # Serializar payload a base64url
    payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode('utf-8').rstrip('=')
    
    # Firmar con la clave secreta
    signature = hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')
    
    return f"{payload_b64}.{sig_b64}"

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodifica y verifica la firma y expiración de un token de acceso."""
    if not token or "." not in token:
        return None
    
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        
        # Verificar firma en tiempo constante
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode('utf-8'),
            payload_b64.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Padding base64
        padded_sig = sig_b64 + "=" * (-len(sig_b64) % 4)
        received_sig = base64.urlsafe_b64decode(padded_sig.encode('utf-8'))
        
        if not hmac.compare_digest(received_sig, expected_sig):
            return None
        
        # Decodificar payload
        padded_payload = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(padded_payload.encode('utf-8')).decode('utf-8')
        payload = json.loads(payload_json)
        
        # Verificar expiración
        exp = payload.get("exp")
        if exp and int(time.time()) > exp:
            return None
        
        return payload
    except Exception:
        return None
