from __future__ import annotations

import base64
import json
from datetime import datetime

try:
    from Crypto.Cipher import AES
except ImportError as exc:  # pragma: no cover - exercised only when dependency is missing
    raise RuntimeError("pycryptodome is required. Install dependencies from python/requirements.txt.") from exc

from .time_utils import get_zoned_date_key


IV = b"ZZWBKJ_ZHIHUAWEI"
BLOCK_SIZE = 16


def build_daily_aes_key(date: datetime | None = None, time_zone: str = "Asia/Shanghai") -> str:
    base = get_zoned_date_key(date, time_zone)
    return f"{base}{base[::-1]}"


def _pad(data: bytes) -> bytes:
    pad_len = BLOCK_SIZE - (len(data) % BLOCK_SIZE)
    return data + bytes([pad_len]) * pad_len


def _unpad(data: bytes) -> bytes:
    pad_len = data[-1]
    if pad_len < 1 or pad_len > BLOCK_SIZE:
        raise ValueError("Invalid PKCS7 padding")
    return data[:-pad_len]


def encrypt_payload(payload: dict, date: datetime | None = None, time_zone: str = "Asia/Shanghai") -> str:
    key = build_daily_aes_key(date, time_zone).encode("utf-8")
    plain = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    cipher = AES.new(key, AES.MODE_CBC, iv=IV)
    encrypted = cipher.encrypt(_pad(plain))
    return base64.b64encode(encrypted).decode("ascii")


def decrypt_payload(cipher_text: str, date: datetime | None = None, time_zone: str = "Asia/Shanghai") -> str:
    key = build_daily_aes_key(date, time_zone).encode("utf-8")
    cipher = AES.new(key, AES.MODE_CBC, iv=IV)
    decrypted = cipher.decrypt(base64.b64decode(cipher_text))
    return _unpad(decrypted).decode("utf-8")
