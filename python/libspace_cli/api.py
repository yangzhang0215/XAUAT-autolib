from __future__ import annotations

import json
from typing import Any

from .crypto import decrypt_payload
from .http import LibraryHttpClient


class LibraryApi:
    def __init__(self, *, base_url: str, lang: str, time_zone: str, token: str | None = None) -> None:
        self.http = LibraryHttpClient(
            base_url=base_url,
            lang=lang,
            time_zone=time_zone,
            token=token,
        )

    def set_token(self, token: str | None) -> None:
        self.http.set_token(token)

    def get_index_config(self) -> dict[str, Any]:
        response = self.http.post("/api/index/config", {}, include_authorization_in_body=False)
        decrypted = response.get("data")
        if isinstance(decrypted, str):
            plain_text = decrypt_payload(decrypted, time_zone=self.http.time_zone)
            try:
                decrypted = json.loads(plain_text)
            except json.JSONDecodeError:
                decrypted = plain_text
        output = dict(response)
        output["data_decrypted"] = decrypted
        return output

    def exchange_cas_ticket(self, cas: str, open_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"cas": cas}
        if open_id:
            payload["open_id"] = open_id
        return self.http.post("/api/cas/user", payload, include_authorization_in_body=False)

    def get_my_info(self) -> dict[str, Any]:
        return self.http.post("/api/Member/my", {})

    def get_member_seat(self, *, page: int = 1, limit: int = 100) -> dict[str, Any]:
        return self.http.post("/api/Member/seat", {"page": page, "limit": limit})

    def cancel_space(self, *, reservation_id: Any) -> dict[str, Any]:
        return self.http.post("/api/Space/cancel", {"id": reservation_id})

    def get_seat_date(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.http.post("/api/Seat/date", payload or {})

    def get_seat_tree(self, *, date: str) -> dict[str, Any]:
        return self.http.post("/api/Seat/tree", {"date": date})

    def get_seat_list(
        self,
        *,
        room_id: Any,
        segment_id: Any,
        day: str,
        start_time: str,
        end_time: str,
        label_id: Any | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "area": room_id,
            "segment": segment_id,
            "day": day,
            "startTime": start_time,
            "endTime": end_time,
        }
        if label_id not in (None, ""):
            payload["label_id"] = label_id
        return self.http.post("/api/Seat/seat", payload)

    def confirm_seat(self, *, seat_id: Any, segment_id: Any) -> dict[str, Any]:
        return self.http.post(
            "/api/Seat/confirm",
            {"seat_id": seat_id, "segment": segment_id},
            encrypt=True,
        )

    def get_seminar_date(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.http.post("/api/Seminar/date", payload or {})

    def get_seminar_tree(self, *, date: str) -> dict[str, Any]:
        return self.http.post("/api/Seminar/tree", {"date": date})

    def get_seminar_detail(self, *, room_id: Any) -> dict[str, Any]:
        return self.http.post("/api/Seminar/detail", {"id": room_id})

    def get_seminar_schedule(self, *, room_id: Any, area_id: Any, day: str) -> dict[str, Any]:
        return self.http.post("/api/Seminar/seminar", {"room": room_id, "area": area_id, "day": day})

    def get_seminar_group(self, *, card: str) -> dict[str, Any]:
        return self.http.post("/api/Seminar/group", {"card": card})

    def submit_seminar(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.http.post("/api/Seminar/submit", payload)
