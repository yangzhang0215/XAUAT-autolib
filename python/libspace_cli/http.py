from __future__ import annotations

import json
from datetime import datetime
from typing import Any

try:
    import requests
except ImportError as exc:  # pragma: no cover - exercised only when dependency is missing
    raise RuntimeError("requests is required. Install dependencies from python/requirements.txt.") from exc

from .crypto import encrypt_payload


class HttpError(RuntimeError):
    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.context = context or {}


class LibraryHttpClient:
    def __init__(
        self,
        *,
        base_url: str,
        lang: str,
        time_zone: str,
        token: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.lang = lang
        self.time_zone = time_zone
        self.token = token
        self.session = session or requests.Session()
        self.timeout = timeout

    def set_token(self, token: str | None) -> None:
        self.token = token

    def build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        normalized = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{normalized}"

    def _repair_mojibake(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._repair_mojibake(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._repair_mojibake(item) for item in value]
        if not isinstance(value, str) or not value:
            return value

        try:
            repaired = value.encode("gbk").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return value
        return repaired or value

    def post(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        *,
        encrypt: bool = False,
        include_authorization_in_body: bool = True,
        date: datetime | None = None,
    ) -> dict[str, Any]:
        url = self.build_url(path)
        headers = {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "lang": self.lang,
        }

        if self.token:
            headers["authorization"] = f"bearer{self.token}"

        payload = dict(data or {})
        if encrypt:
            body: dict[str, Any] = {"aesjson": encrypt_payload(payload, date=date, time_zone=self.time_zone)}
        else:
            body = payload

        if self.token and include_authorization_in_body:
            body["authorization"] = headers["authorization"]

        response = self.session.post(url, json=body, headers=headers, timeout=self.timeout)
        response.encoding = "utf-8"
        try:
            parsed = json.loads(response.content.decode("utf-8"))
        except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
            try:
                parsed = response.json()
            except ValueError as exc:
                raise HttpError(
                    f"Invalid JSON response from {path}",
                    context={"path": path, "status": response.status_code},
                ) from exc
        parsed = self._repair_mojibake(parsed)

        if not response.ok:
            raise HttpError(
                f"HTTP {response.status_code} for {path}",
                context={"path": path, "status": response.status_code, "payload": parsed},
            )

        return parsed
