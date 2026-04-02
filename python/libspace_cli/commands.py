from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from .authserver import direct_cas_login, extract_cas_value
from .context import CommandContext, create_command_context
from .interfaces_catalog import build_interface_catalog, render_catalog_markdown, render_catalog_summary
from .member_seat import ACTIVE_SEAT_BOOKING_STATUSES, extract_active_seat_bookings, find_booking_by_id
from .reserve_service import execute_reserve_once, resolve_candidate_seats
from .result import is_success_response, is_token_expired_response
from .seat_selection import get_first_available_time_segment
from .time_utils import enforce_schedule_window, get_zoned_day_string, sleep_ms
from .tree import flatten_seat_tree


EARLY_WINDOW_SECONDS = 60
LATE_WINDOW_SECONDS = 60
CANCEL_VERIFICATION_DELAYS_MS = (0, 1000, 2000, 5000)


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_cas_url(base_url: str, cas_url: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", cas_url.lstrip("/"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_site_config(config_response: dict[str, Any]) -> dict[str, Any] | None:
    payload = config_response.get("data_decrypted")
    if not isinstance(payload, dict):
        return None
    nested = payload.get("config")
    return nested if isinstance(nested, dict) else payload


def _save_state_payload(
    ctx: CommandContext,
    state_key: str,
    status: str,
    detail: dict[str, Any] | None = None,
) -> None:
    payload = {"status": status, "at": _utc_timestamp()}
    if detail:
        payload.update(detail)
    ctx.state[state_key] = payload
    ctx.persist_state()


def _extract_token_payload(response: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    member = response.get("member")
    if isinstance(member, dict) and member.get("token"):
        return str(member["token"]), member

    data = response.get("data")
    if isinstance(data, dict) and data.get("token"):
        return str(data["token"]), data

    token = response.get("token")
    if token:
        return str(token), response
    return None, {}


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clear_cached_auth(ctx: CommandContext) -> None:
    ctx.state["token"] = None
    ctx.state["userInfo"] = None
    ctx.state["tokenSavedAt"] = None
    ctx.persist_state()
    ctx.api.set_token(None)


def _record_login_failure(
    ctx: CommandContext,
    *,
    status: str,
    message: str,
    login_mode: str,
    credential_source: str | None = None,
    response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "message": message,
        "loginMode": login_mode,
    }
    if credential_source:
        detail["credentialSource"] = credential_source
    if response is not None:
        detail["response"] = response
    _save_state_payload(ctx, "lastLogin", status, detail)
    return {
        "ok": False,
        "status": status,
        "message": message,
        "loginMode": login_mode,
        "credentialSource": credential_source,
        "response": response,
    }


def _record_login_success(
    ctx: CommandContext,
    *,
    token: str,
    user_info: dict[str, Any],
    login_mode: str,
    credential_source: str | None = None,
) -> dict[str, Any]:
    token_saved_at = _utc_timestamp()
    ctx.state["token"] = token
    ctx.state["userInfo"] = user_info
    ctx.state["tokenSavedAt"] = token_saved_at
    detail: dict[str, Any] = {
        "loginMode": login_mode,
        "userId": user_info.get("card") or user_info.get("username") or user_info.get("name") or "unknown",
    }
    if credential_source:
        detail["credentialSource"] = credential_source
    _save_state_payload(ctx, "lastLogin", "success", detail)
    ctx.api.set_token(token)
    return {
        "ok": True,
        "status": "success",
        "message": "Login succeeded and token was cached.",
        "loginMode": login_mode,
        "credentialSource": credential_source,
        "userId": detail["userId"],
    }


def _resolve_login_credentials(ctx: CommandContext, args: Any | None) -> tuple[str | None, str | None, str | None]:
    cli_username = _normalize_optional_string(getattr(args, "username", None)) if args is not None else None
    cli_password = _normalize_optional_string(getattr(args, "password", None)) if args is not None else None
    if cli_username or cli_password:
        if not (cli_username and cli_password):
            raise ValueError("Both --username and --password are required when overriding credentials from the CLI.")
        return "cli", cli_username, cli_password

    env_username = _normalize_optional_string(os.getenv("LIBSPACE_USERNAME"))
    env_password = _normalize_optional_string(os.getenv("LIBSPACE_PASSWORD"))
    if env_username or env_password:
        if not (env_username and env_password):
            raise ValueError("Both LIBSPACE_USERNAME and LIBSPACE_PASSWORD must be set together.")
        return "env", env_username, env_password

    if ctx.config.auth.username or ctx.config.auth.password:
        if not (ctx.config.auth.username and ctx.config.auth.password):
            raise ValueError("config.auth.username and config.auth.password must be set together.")
        return "config", ctx.config.auth.username, ctx.config.auth.password

    return None, None, None


def _exchange_cas_and_cache(
    ctx: CommandContext,
    *,
    raw_cas_value: str,
    login_mode: str,
    credential_source: str | None = None,
) -> dict[str, Any]:
    try:
        cas_value = extract_cas_value(raw_cas_value)
    except ValueError as exc:
        return _record_login_failure(
            ctx,
            status="api_error",
            message=str(exc),
            login_mode=login_mode,
            credential_source=credential_source,
        )

    try:
        response = ctx.api.exchange_cas_ticket(cas_value)
    except Exception as exc:  # pragma: no cover - network/runtime wrapper
        return _record_login_failure(
            ctx,
            status="api_error",
            message=f"Failed to exchange CAS ticket: {exc}",
            login_mode=login_mode,
            credential_source=credential_source,
        )

    token, user_info = _extract_token_payload(response)
    if not is_success_response(response) or not token:
        return _record_login_failure(
            ctx,
            status="api_error",
            message=response.get("msg", "Failed to exchange CAS ticket for a libspace token"),
            login_mode=login_mode,
            credential_source=credential_source,
            response=response,
        )

    return _record_login_success(
        ctx,
        token=token,
        user_info=user_info,
        login_mode=login_mode,
        credential_source=credential_source,
    )


def _perform_direct_login(
    ctx: CommandContext,
    *,
    username: str,
    password: str,
    credential_source: str,
) -> dict[str, Any]:
    try:
        config_response = ctx.api.get_index_config()
    except Exception as exc:  # pragma: no cover - network/runtime wrapper
        return _record_login_failure(
            ctx,
            status="api_error",
            message=f"Failed to fetch site config: {exc}",
            login_mode="direct",
            credential_source=credential_source,
        )

    if not is_success_response(config_response):
        return _record_login_failure(
            ctx,
            status="api_error",
            message=config_response.get("msg", "Failed to fetch site config"),
            login_mode="direct",
            credential_source=credential_source,
            response=config_response,
        )

    site_config = _extract_site_config(config_response)
    if site_config is None:
        return _record_login_failure(
            ctx,
            status="api_error",
            message="Failed to decode site config payload",
            login_mode="direct",
            credential_source=credential_source,
            response=config_response,
        )

    login_mode = str(site_config.get("login", "")).strip()
    cas_url = str(site_config.get("cas_url", "")).strip()
    if login_mode != "4" or not cas_url:
        return _record_login_failure(
            ctx,
            status="api_error",
            message=f"Current site is not using CAS login: login={login_mode!r}",
            login_mode="direct",
            credential_source=credential_source,
            response=site_config,
        )

    cas_entry_url = _resolve_cas_url(ctx.config.base_url, cas_url)
    try:
        direct_result = direct_cas_login(
            cas_entry_url=cas_entry_url,
            username=username,
            password=password,
        )
    except Exception as exc:  # pragma: no cover - network/runtime wrapper
        return _record_login_failure(
            ctx,
            status="api_error",
            message=f"Direct CAS login failed before ticket exchange: {exc}",
            login_mode="direct",
            credential_source=credential_source,
        )

    if direct_result.status == "captcha_required":
        return _record_login_failure(
            ctx,
            status="captcha_required",
            message=direct_result.message,
            login_mode="direct",
            credential_source=credential_source,
        )

    if direct_result.status != "success" or not direct_result.cas:
        return _record_login_failure(
            ctx,
            status="auth_failed",
            message=direct_result.message or "Unified authentication login failed",
            login_mode="direct",
            credential_source=credential_source,
        )

    return _exchange_cas_and_cache(
        ctx,
        raw_cas_value=direct_result.cas,
        login_mode="direct",
        credential_source=credential_source,
    )


def _perform_login(ctx: CommandContext, args: Any | None = None, *, allow_manual_cas: bool) -> dict[str, Any]:
    if allow_manual_cas and args is not None:
        raw_cas_value = _normalize_optional_string(getattr(args, "cas", None) or getattr(args, "url", None))
        if raw_cas_value:
            return _exchange_cas_and_cache(ctx, raw_cas_value=raw_cas_value, login_mode="manual_cas")

    try:
        credential_source, username, password = _resolve_login_credentials(ctx, args)
    except ValueError as exc:
        return _record_login_failure(
            ctx,
            status="api_error",
            message=str(exc),
            login_mode="direct",
        )

    if not username or not password:
        return _record_login_failure(
            ctx,
            status="api_error",
            message="No credentials available. Set python/config.json auth.username/auth.password or pass --username/--password.",
            login_mode="direct",
        )

    return _perform_direct_login(
        ctx,
        username=username,
        password=password,
        credential_source=credential_source or "config",
    )


def _ensure_authenticated(ctx: CommandContext) -> dict[str, Any]:
    if ctx.state.get("token"):
        try:
            my_info = ctx.api.get_my_info()
        except Exception as exc:  # pragma: no cover - network/runtime wrapper
            return {"ok": False, "reason": "validation_exception", "message": str(exc)}

        if is_success_response(my_info):
            return {"ok": True, "myInfo": my_info, "loginRefreshed": False}
        if not is_token_expired_response(my_info):
            return {"ok": False, "reason": "validation_failed", "response": my_info}

        ctx.logger.warn("Cached token was rejected by server; attempting automatic login")
        _clear_cached_auth(ctx)
    else:
        ctx.logger.info("No cached token found; attempting automatic login")

    login_result = _perform_login(ctx, allow_manual_cas=False)
    if not login_result["ok"]:
        return {"ok": False, "reason": "auto_login_failed", "login": login_result}

    try:
        my_info = ctx.api.get_my_info()
    except Exception as exc:  # pragma: no cover - network/runtime wrapper
        return {"ok": False, "reason": "post_login_validation_exception", "message": str(exc)}

    if is_success_response(my_info):
        return {"ok": True, "myInfo": my_info, "loginRefreshed": True}
    return {"ok": False, "reason": "post_login_validation_failed", "response": my_info}


def _describe_auth_failure(auth_result: dict[str, Any]) -> str:
    if auth_result.get("reason") == "auto_login_failed":
        login = auth_result.get("login") or {}
        return str(login.get("message") or login.get("status") or "Automatic login failed")
    if auth_result.get("message"):
        return str(auth_result["message"])
    response = auth_result.get("response")
    if isinstance(response, dict) and response.get("msg"):
        return str(response["msg"])
    return str(auth_result.get("reason") or "Authentication failed")


def _auth_failure_detail(auth_result: dict[str, Any]) -> dict[str, Any]:
    detail = {"reason": auth_result.get("reason")}
    if auth_result.get("reason") == "auto_login_failed":
        login = auth_result.get("login") or {}
        detail["loginStatus"] = login.get("status")
        detail["loginMessage"] = login.get("message")
        return detail
    if auth_result.get("message"):
        detail["message"] = auth_result.get("message")
    if auth_result.get("response") is not None:
        detail["response"] = auth_result.get("response")
    return detail


def _build_area_label(room: dict[str, Any]) -> str:
    return " / ".join(
        str(part).strip()
        for part in (room.get("areaName"), room.get("floorName"), room.get("roomName"))
        if str(part or "").strip()
    )


def login_command(args: Any) -> int:
    ctx = create_command_context("login")
    ctx.logger.info("Starting login flow")

    result = _perform_login(ctx, args=args, allow_manual_cas=True)
    if result["ok"]:
        ctx.logger.info("Login succeeded", {"userId": result.get("userId"), "loginMode": result.get("loginMode")})
        print(result["message"])
        return 0

    ctx.logger.error(
        "Login failed",
        {
            "status": result.get("status"),
            "loginMode": result.get("loginMode"),
            "credentialSource": result.get("credentialSource"),
        },
    )
    print(result["message"])
    return 1


def discover_command(args: Any) -> int:
    ctx = create_command_context("discover")
    target_date = str(getattr(args, "date", "") or "").strip() or get_zoned_day_string(None, ctx.config.time_zone)
    ctx.logger.info("Starting discover flow", {"targetDate": target_date})

    auth_result = _ensure_authenticated(ctx)
    if not auth_result["ok"]:
        detail = _auth_failure_detail(auth_result)
        ctx.logger.error("Authentication failed during discover", detail)
        print(_describe_auth_failure(auth_result))
        return 1

    tree_response = ctx.api.get_seat_tree(date=target_date)
    if not is_success_response(tree_response):
        ctx.logger.error("Failed to fetch seat tree", {"response": tree_response})
        print(tree_response.get("msg", "Failed to fetch the seat tree"))
        return 1

    output = {
        "generatedAt": _utc_timestamp(),
        "targetDate": target_date,
        "candidateTemplate": [],
        "areaPreferenceTemplate": [],
        "rooms": [],
    }

    valid_rooms = [room for room in flatten_seat_tree(tree_response.get("data")) if room.get("isValid") == 1]
    for room in valid_rooms:
        room_date_response = ctx.api.get_seat_date({"build_id": room["roomId"]})
        if not is_success_response(room_date_response):
            ctx.logger.warn("Skipping room because room-level date query failed", {"roomId": room["roomId"]})
            continue

        room_day = next((item for item in room_date_response.get("data", []) if item.get("day") == target_date), None)
        if not room_day:
            continue

        time_segment = get_first_available_time_segment(room_day)
        if not time_segment:
            continue

        seat_list_response = ctx.api.get_seat_list(
            room_id=room["roomId"],
            segment_id=time_segment["id"],
            day=room_day["day"],
            start_time=time_segment["start"],
            end_time=time_segment["end"],
        )
        if not is_success_response(seat_list_response):
            ctx.logger.warn("Skipping room because seat list query failed", {"roomId": room["roomId"]})
            continue

        available_seats = [
            {"seatId": seat.get("id"), "seatName": seat.get("name")}
            for seat in seat_list_response.get("data", [])
            if int(seat.get("status", 0) or 0) == 1
        ]
        room_record = {
            **room,
            "segmentId": time_segment["id"],
            "startTime": time_segment["start"],
            "endTime": time_segment["end"],
            "availableSeatCount": len(available_seats),
            "availableSeats": available_seats,
        }
        output["rooms"].append(room_record)

        if available_seats:
            seat_ids = [item["seatId"] for item in available_seats]
            output["candidateTemplate"].append({"roomId": room["roomId"], "seatIds": seat_ids})
            output["areaPreferenceTemplate"].append(
                {
                    "label": _build_area_label(room),
                    "roomId": room["roomId"],
                    "match": {
                        "areaName": room.get("areaName"),
                        "floorName": room.get("floorName"),
                        "roomName": room.get("roomName"),
                    },
                    "seatIds": seat_ids,
                }
            )

    output_path = ctx.paths.runtime_dir / f"discover-{target_date.replace('-', '')}.json"
    _write_json(output_path, output)
    ctx.logger.info("Discover result written", {"filePath": str(output_path), "roomCount": len(output["rooms"])})

    print(f"Wrote discover result to: {output_path}")
    print(f"Bookable rooms: {len(output['rooms'])}")
    for room in output["rooms"][:20]:
        sample = ", ".join(str(item["seatId"]) for item in room["availableSeats"][:10])
        print(
            f"{_build_area_label(room)} | roomId={room['roomId']} | "
            f"segment={room['segmentId']} | seats={sample}"
        )
    return 0


def reserve_once_command(args: Any) -> int:
    ctx = create_command_context("reserve-once")
    force = bool(getattr(args, "force", False))
    ctx.logger.info("Starting reserve-once flow", {"force": force})

    if not force:
        schedule = enforce_schedule_window(
            trigger_time=ctx.config.trigger_time,
            time_zone=ctx.config.time_zone,
            early_window_seconds=EARLY_WINDOW_SECONDS,
            late_window_seconds=LATE_WINDOW_SECONDS,
        )
        if not schedule.ok:
            _save_state_payload(ctx, "lastReserve", "schedule_miss", {"reason": schedule.reason})
            ctx.logger.warn("Execution skipped because schedule window was missed", {"reason": schedule.reason})
            print(f"Execution skipped: {schedule.reason}")
            return 1
        if schedule.delay_ms > 0:
            ctx.logger.info("Waiting until trigger time", {"delayMs": schedule.delay_ms})
            sleep_ms(schedule.delay_ms)

    auth_result = _ensure_authenticated(ctx)
    if not auth_result["ok"]:
        detail = _auth_failure_detail(auth_result)
        _save_state_payload(ctx, "lastReserve", "api_error", detail)
        ctx.logger.error("Authentication failed during reserve-once", detail)
        print(_describe_auth_failure(auth_result))
        return 1

    target_day = get_zoned_day_string(None, ctx.config.time_zone)
    tree_response = ctx.api.get_seat_tree(date=target_day)
    if not is_success_response(tree_response):
        _save_state_payload(ctx, "lastReserve", "api_error", {"reason": "seat_tree_failed", "response": tree_response})
        ctx.logger.error("Failed to fetch seat tree", {"response": tree_response})
        print(tree_response.get("msg", "Failed to fetch the seat tree"))
        return 1

    valid_rooms = [room for room in flatten_seat_tree(tree_response.get("data")) if room.get("isValid") == 1]
    if not valid_rooms:
        result = {
            "status": "no_available_seat",
            "detail": f"No valid rooms are available for {target_day}",
        }
        _save_state_payload(ctx, "lastReserve", result["status"], result)
        ctx.logger.warn("No valid rooms found in seat tree", {"targetDay": target_day})
        print(result["detail"])
        return 1

    candidate_seats = resolve_candidate_seats(
        selection_mode=ctx.config.selection_mode,
        candidate_seats=ctx.config.candidate_seats,
        area_preferences=ctx.config.area_preferences,
        valid_rooms=valid_rooms,
        logger=ctx.logger,
    )
    if not candidate_seats:
        result = {
            "status": "no_available_seat",
            "detail": "No configured room matched today's valid rooms",
            "selectionMode": ctx.config.selection_mode,
        }
        _save_state_payload(ctx, "lastReserve", result["status"], result)
        ctx.logger.warn("No candidate room remained after selection resolution", {"selectionMode": ctx.config.selection_mode})
        print(result["detail"])
        return 1

    reserve_result = execute_reserve_once(
        api=ctx.api,
        candidate_seats=candidate_seats,
        target_day=target_day,
        logger=ctx.logger,
    )

    if reserve_result["status"] == "success":
        _save_state_payload(
            ctx,
            "lastReserve",
            "success",
            {
                "roomId": reserve_result["roomId"],
                "seatId": reserve_result["seatId"],
                "seatName": reserve_result["seatName"],
                "segmentId": reserve_result["segmentId"],
                "day": reserve_result["day"],
            },
        )
        ctx.logger.info("Reservation succeeded", reserve_result)
        print(
            f"Reservation succeeded: roomId={reserve_result['roomId']}, "
            f"seatId={reserve_result['seatId']}, segment={reserve_result['segmentId']}"
        )
        return 0

    _save_state_payload(ctx, "lastReserve", reserve_result["status"], reserve_result)
    ctx.logger.warn("Reservation did not succeed", reserve_result)
    print(reserve_result.get("detail") or reserve_result.get("response", {}).get("msg") or reserve_result["status"])
    return 1


def _select_booking_for_cancel(response: dict[str, Any], reservation_id: Any | None) -> tuple[str, dict[str, Any] | None, list[dict[str, Any]]]:
    active_bookings = extract_active_seat_bookings(response)
    if reservation_id is not None:
        booking = find_booking_by_id(response, reservation_id)
        if booking is None or str(booking.get("status")) not in ACTIVE_SEAT_BOOKING_STATUSES:
            return "no_active_booking", None, active_bookings
        return "ok", booking, active_bookings

    if not active_bookings:
        return "no_active_booking", None, active_bookings
    if len(active_bookings) > 1:
        return "multiple_active_bookings", None, active_bookings
    return "ok", active_bookings[0], active_bookings


def _verify_cancel_result(ctx: CommandContext, reservation_id: Any) -> dict[str, Any]:
    last_observed: dict[str, Any] | None = None

    for delay_ms in CANCEL_VERIFICATION_DELAYS_MS:
        if delay_ms > 0:
            sleep_ms(delay_ms)

        response = ctx.api.get_member_seat(page=1, limit=100)
        if not is_success_response(response):
            ctx.logger.warn("Verification query failed after cancellation", {"response": response})
            last_observed = {"response": response}
            continue

        booking = find_booking_by_id(response, reservation_id)
        if booking is not None:
            last_observed = booking
            if str(booking.get("status")) not in ACTIVE_SEAT_BOOKING_STATUSES:
                return {
                    "status": "success",
                    "reservationId": reservation_id,
                    "bookingStatus": booking.get("status"),
                    "bookingStatusName": booking.get("statusName"),
                }
            continue

        active_bookings = extract_active_seat_bookings(response)
        if not active_bookings:
            return {
                "status": "success",
                "reservationId": reservation_id,
                "bookingStatus": None,
                "bookingStatusName": "not_listed",
            }

    return {
        "status": "verification_pending",
        "reservationId": reservation_id,
        "lastObserved": last_observed,
    }


def cancel_seat_command(args: Any) -> int:
    ctx = create_command_context("cancel-seat")
    ctx.logger.info("Starting cancel-seat flow")

    auth_result = _ensure_authenticated(ctx)
    if not auth_result["ok"]:
        detail = _auth_failure_detail(auth_result)
        _save_state_payload(ctx, "lastCancel", "api_error", detail)
        ctx.logger.error("Authentication failed during cancel-seat", detail)
        print(_describe_auth_failure(auth_result))
        return 1

    member_seat_response = ctx.api.get_member_seat(page=1, limit=100)
    if not is_success_response(member_seat_response):
        _save_state_payload(ctx, "lastCancel", "api_error", {"reason": "member_seat_failed", "response": member_seat_response})
        ctx.logger.error("Failed to query current seat bookings", {"response": member_seat_response})
        print(member_seat_response.get("msg", "Failed to query current seat bookings"))
        return 1

    reservation_id = getattr(args, "id", None)
    selection_status, booking, active_bookings = _select_booking_for_cancel(member_seat_response, reservation_id)
    if selection_status == "no_active_booking":
        _save_state_payload(ctx, "lastCancel", "no_active_booking", {})
        ctx.logger.warn("No active booking available for cancellation")
        print("No active seat booking was found.")
        return 1

    if selection_status == "multiple_active_bookings":
        detail = {
            "reason": "multiple_active_bookings",
            "activeReservationIds": [item.get("id") for item in active_bookings],
        }
        _save_state_payload(ctx, "lastCancel", "api_error", detail)
        ctx.logger.warn("Multiple active bookings found; explicit id is required", detail)
        print("Multiple active bookings were found. Re-run cancel-seat with --id <reservationId>.")
        for item in active_bookings:
            print(
                f"id={item.get('id')} | status={item.get('statusName') or item.get('status')} | "
                f"room={item.get('roomName') or item.get('spaceName') or '-'} | "
                f"seat={item.get('seatName') or item.get('seatNo') or item.get('seatNum') or '-'}"
            )
        return 1

    assert booking is not None
    cancel_response = ctx.api.cancel_space(reservation_id=booking.get("id"))
    if not is_success_response(cancel_response):
        detail = {
            "reason": "cancel_failed",
            "reservationId": booking.get("id"),
            "response": cancel_response,
        }
        _save_state_payload(ctx, "lastCancel", "api_error", detail)
        ctx.logger.error("Cancellation request failed", detail)
        print(cancel_response.get("msg", "Cancellation request failed"))
        return 1

    verification = _verify_cancel_result(ctx, booking.get("id"))
    detail = {
        "reservationId": booking.get("id"),
        "response": cancel_response,
    }
    detail.update({key: value for key, value in verification.items() if key != "status"})
    _save_state_payload(ctx, "lastCancel", verification["status"], detail)

    if verification["status"] == "success":
        ctx.logger.info("Cancellation verified", detail)
        print(
            f"Cancellation verified: id={booking.get('id')}, "
            f"status={verification.get('bookingStatusName') or verification.get('bookingStatus')}"
        )
        return 0

    ctx.logger.warn("Cancellation API succeeded but verification is still pending", detail)
    print("Cancellation request succeeded, but the booking list has not refreshed yet.")
    return 1


def interfaces_command(args: Any) -> int:
    records = build_interface_catalog()
    output = getattr(args, "output", None)
    requested_format = getattr(args, "format", None)
    fmt = requested_format

    if output and not fmt:
        fmt = "md" if Path(output).suffix.lower() == ".md" else "json"
    fmt = fmt or "md"

    rendered = json.dumps(records, ensure_ascii=False, indent=2) if fmt == "json" else render_catalog_markdown(records)

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        print(f"Exported {len(records)} endpoints to: {output_path}")
        return 0

    if requested_format in {"json", "md"}:
        print(rendered)
    else:
        print(render_catalog_summary(records))
    return 0
