from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from typing import Any, Callable
from urllib.parse import parse_qs, urljoin, urlparse

try:
    import requests
except ImportError as exc:  # pragma: no cover - exercised only when dependency is missing
    raise RuntimeError("requests is required. Install dependencies from python/requirements.txt.") from exc

try:
    from Crypto.Cipher import AES
except ImportError as exc:  # pragma: no cover - exercised only when dependency is missing
    raise RuntimeError("pycryptodome is required. Install dependencies from python/requirements.txt.") from exc


AUTH_CHARS = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"
DEFAULT_USER_AGENT = "Mozilla/5.0"

EXECUTION_RE = re.compile(r'name="execution"\s+value="([^"]+)"')
PWD_SALT_RE = re.compile(r'id="pwdEncryptSalt"\s+value="([^"]+)"')
CONTEXT_PATH_RE = re.compile(r'var\s+contextPath\s*=\s*"([^"]+)"')
ERROR_TEXT_RE = re.compile(r'id="showErrorTip"[^>]*>(.*?)<')


@dataclass(frozen=True)
class DirectCasLoginResult:
    status: str
    message: str
    cas: str | None = None


def random_string(length: int) -> str:
    import random

    return "".join(random.choice(AUTH_CHARS) for _ in range(length))


def _pad(data: bytes) -> bytes:
    pad_len = 16 - (len(data) % 16)
    return data + bytes([pad_len]) * pad_len


def encrypt_authserver_password(
    password: str,
    salt: str,
    *,
    random_provider: Callable[[int], str] = random_string,
) -> str:
    iv = random_provider(16).encode("utf-8")
    plain_text = (random_provider(64) + password).encode("utf-8")
    cipher = AES.new(salt.encode("utf-8"), AES.MODE_CBC, iv=iv)
    import base64

    return base64.b64encode(cipher.encrypt(_pad(plain_text))).decode("ascii")


def extract_cas_value(raw_value: str) -> str:
    text = raw_value.strip()
    if not text:
        raise ValueError("CAS callback value cannot be empty")

    parsed = urlparse(text)
    candidates: list[str] = []
    if parsed.query:
        candidates.append(parsed.query)
    if parsed.fragment:
        fragment = parsed.fragment.lstrip("#")
        candidates.append(fragment)
        if "?" in fragment:
            candidates.append(fragment.split("?", 1)[1])
    if "cas=" in text and not candidates:
        candidates.append(text)

    for candidate in candidates:
        values = parse_qs(candidate.lstrip("#?")).get("cas")
        if values and values[0]:
            return values[0]

    if parsed.scheme or "=" in text or "?" in text or "#" in text:
        raise ValueError("Could not parse cas from the provided callback URL")
    return text


def _extract_hidden_value(pattern: re.Pattern[str], html: str, label: str) -> str:
    match = pattern.search(html)
    if not match:
        raise ValueError(f"Could not find {label} on the CAS login page")
    return match.group(1)


def _extract_context_path(html: str, login_url: str) -> str:
    match = CONTEXT_PATH_RE.search(html)
    if match:
        return match.group(1)

    parsed = urlparse(login_url)
    parts = [part for part in parsed.path.split("/") if part]
    if parts:
        return f"/{parts[0]}"
    return "/authserver"


def _extract_error_message(html: str) -> str | None:
    match = ERROR_TEXT_RE.search(html)
    if not match:
        return None
    text = re.sub(r"<[^>]+>", "", match.group(1))
    text = unescape(text).strip()
    return text or None


def direct_cas_login(
    *,
    cas_entry_url: str,
    username: str,
    password: str,
    session: requests.Session | None = None,
    timeout: float = 20.0,
    random_provider: Callable[[int], str] = random_string,
) -> DirectCasLoginResult:
    client = session or requests.Session()
    login_page = client.get(cas_entry_url, allow_redirects=True, timeout=timeout, headers={"User-Agent": DEFAULT_USER_AGENT})
    login_url = login_page.url
    execution = _extract_hidden_value(EXECUTION_RE, login_page.text, "execution")
    pwd_salt = _extract_hidden_value(PWD_SALT_RE, login_page.text, "pwdEncryptSalt")
    context_path = _extract_context_path(login_page.text, login_url)

    captcha_url = urljoin(login_url, f"{context_path.rstrip('/')}/checkNeedCaptcha.htl")
    captcha_response = client.get(
        captcha_url,
        params={"username": username},
        timeout=timeout,
        headers={"X-Requested-With": "XMLHttpRequest", "User-Agent": DEFAULT_USER_AGENT},
    )
    captcha_payload = captcha_response.json()
    if bool(captcha_payload.get("isNeed")):
        return DirectCasLoginResult(
            status="captcha_required",
            message="CAS currently requires captcha/slider verification; use browser-assisted login instead.",
        )

    encrypted_password = encrypt_authserver_password(password, pwd_salt, random_provider=random_provider)
    form = {
        "username": username,
        "password": encrypted_password,
        "_eventId": "submit",
        "cllt": "userNameLogin",
        "dllt": "generalLogin",
        "lt": "",
        "execution": execution,
        "rmShown": "1",
    }
    final_response = client.post(
        login_url,
        data=form,
        allow_redirects=True,
        timeout=timeout,
        headers={"Referer": login_url, "User-Agent": DEFAULT_USER_AGENT},
    )

    try:
        cas = extract_cas_value(final_response.url)
    except ValueError:
        message = _extract_error_message(final_response.text) or "CAS login failed; the callback URL did not contain a cas parameter."
        return DirectCasLoginResult(status="auth_failed", message=message)

    return DirectCasLoginResult(status="success", message="CAS login succeeded", cas=cas)
