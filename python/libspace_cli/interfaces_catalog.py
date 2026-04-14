from __future__ import annotations

from collections import OrderedDict
from typing import Any


OBSERVED_ON = "2026-04-01"


GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Login and index",
        [
            ("GET", "/api/cas/cas"),
            ("POST", "/api/cas/user"),
            ("POST", "/api/index/config"),
            ("POST", "/api/index/lang"),
            ("POST", "/api/index/category"),
            ("POST", "/api/index/booking_rules"),
            ("POST", "/api/index/time"),
            ("POST", "/api/index/banner"),
            ("POST", "/api/index/notice"),
            ("POST", "/api/index/noticeDetail"),
            ("POST", "/api/index/subscribe"),
            ("POST", "/api/Captcha/verify"),
            ("POST", "/api/login/login"),
            ("POST", "/api/login/forget"),
            ("POST", "/api/login/resetpass"),
            ("POST", "/api/login/updateUserInfo"),
            ("POST", "/api/jwt/login"),
            ("POST", "/api/login/dingtalksns"),
            ("POST", "/api/login/wxlogin"),
            ("POST", "/api/login/wxwork"),
        ],
    ),
    (
        "Member",
        [
            ("POST", "/api/Member/lang"),
            ("POST", "/api/Member/my"),
            ("POST", "/api/Member/isQuickSelect"),
            ("POST", "/api/Member/removeOpenid"),
            ("POST", "/api/Member/reneges"),
            ("POST", "/api/Member/room"),
            ("POST", "/api/Member/seat"),
            ("POST", "/api/Member/seminar"),
            ("POST", "/api/member/invitations"),
        ],
    ),
    (
        "Seat reservation",
        [
            ("POST", "/api/Seat/date"),
            ("POST", "/api/Seat/tree"),
            ("POST", "/api/Seat/seat"),
            ("POST", "/api/Seat/confirm"),
            ("POST", "/api/Seat/change_seat"),
            ("POST", "/api/Seat/coordinate"),
            ("POST", "/api/Seat/qr_book_check"),
            ("POST", "/api/Seat/qr_change_seat"),
            ("POST", "/api/Seat/touch_qr_books"),
            ("POST", "/api/seat/label"),
            ("POST", "/api/seat/map"),
            ("POST", "/api/seat/qrcode"),
            ("POST", "/api/seat/qrcode_not_card"),
            ("POST", "/api/seat/xuzuoconfirm"),
        ],
    ),
    (
        "Room and entry",
        [
            ("POST", "/api/Room/list"),
            ("POST", "/api/Room/detail"),
            ("POST", "/api/Room/mylist"),
            ("POST", "/api/Space/cancel"),
            ("POST", "/api/Space/checkout"),
            ("POST", "/api/Space/leave"),
            ("POST", "/api/Space/signin"),
            ("POST", "/api/Enter/date"),
            ("POST", "/api/Enter/list"),
            ("POST", "/api/Enter/quantum"),
            ("POST", "/api/Enter/confirm"),
            ("POST", "/api/space/seminarCancel"),
        ],
    ),
    (
        "Seminar",
        [
            ("POST", "/api/Seminar/agree"),
            ("POST", "/api/Seminar/confirm"),
            ("POST", "/api/Seminar/date"),
            ("POST", "/api/Seminar/detail"),
            ("POST", "/api/Seminar/group"),
            ("POST", "/api/Seminar/roomCancel"),
            ("POST", "/api/Seminar/roomConfirm"),
            ("POST", "/api/Seminar/seminar"),
            ("POST", "/api/Seminar/submit"),
            ("POST", "/api/Seminar/tree"),
            ("POST", "/api/Seminar/v1seminar"),
            ("POST", "/api/seminar/should"),
            ("POST", "/reserve/seminar/signout"),
        ],
    ),
    (
        "Study area",
        [
            ("POST", "/api/Study/EntranceDetail"),
            ("POST", "/api/Study/EntranceLengthDetail"),
            ("POST", "/api/Study/StudyArea"),
            ("POST", "/api/Study/StudyAreaBook"),
            ("POST", "/api/Study/StudyAreaCancel"),
            ("POST", "/api/Study/StudyAreaDetail"),
            ("POST", "/api/Study/StudyAreaTree"),
            ("POST", "/api/Study/StudyBookDetail"),
            ("POST", "/api/Study/StudyBookRenegeDetail"),
            ("POST", "/api/Study/StudyOpenTime"),
            ("POST", "/api/Study/StudyOpenTimeCheck"),
            ("POST", "/api/Study/StudyOrder"),
            ("POST", "/api/Study/StudyOrderCheck"),
            ("POST", "/api/Study/libinfo"),
        ],
    ),
    (
        "Activity and extension",
        [
            ("POST", "/api/activity/apply"),
            ("POST", "/api/activity/detail"),
            ("POST", "/api/activity/list"),
            ("POST", "/api/activity/quit"),
            ("POST", "/reserve/activity/applying"),
            ("POST", "/reserve/activity/backState"),
            ("POST", "/reserve/activity/checkDateConflict"),
            ("POST", "/reserve/activity/comments"),
            ("POST", "/reserve/activity/confirm"),
            ("POST", "/reserve/activity/delDraft"),
            ("POST", "/reserve/activity/detail"),
            ("POST", "/reserve/activity/getAlertNotice"),
            ("POST", "/reserve/activity/getApplyTimeAndMd"),
            ("POST", "/reserve/activity/getSubmitField"),
            ("POST", "/reserve/activity/getdraftdetail"),
            ("POST", "/reserve/activity/like"),
            ("POST", "/reserve/activity/monitor"),
            ("POST", "/reserve/activity/mycancel"),
            ("POST", "/reserve/activity/mydetail"),
            ("POST", "/reserve/activity/mylist"),
            ("POST", "/reserve/activity/partake"),
            ("POST", "/reserve/activity/submit"),
            ("POST", "/reserve/activity/unconfirm"),
        ],
    ),
    (
        "Other reserved interfaces",
        [
            ("POST", "/reserve/index/index"),
            ("POST", "/reserve/index/detail"),
            ("POST", "/reserve/index/confirm"),
            ("POST", "/reserve/index/quickSelect"),
            ("POST", "/reserve/device/cancel"),
            ("POST", "/reserve/device/deviceInfoByTime"),
            ("POST", "/reserve/device/mylist"),
            ("POST", "/reserve/lostlocker/memberExtractBlackRecord"),
            ("POST", "/reserve/smartDevice/setLightBrightness"),
            ("POST", "/reserve/smartDevice/setLightStatus"),
            ("POST", "/reserve/smartDevice/setRelayStatus"),
            ("POST", "/api/Help/index"),
            ("POST", "/api/Help/detail"),
            ("POST", "/api/Upload/index"),
            ("POST", "/api/Upload/upload"),
            ("POST", "/api/upload/index"),
        ],
    ),
    (
        "CAS authserver",
        [
            ("GET", "https://authserver.xauat.edu.cn/authserver/login"),
            ("POST", "https://authserver.xauat.edu.cn/authserver/login"),
            ("GET", "https://authserver.xauat.edu.cn/authserver/checkNeedCaptcha.htl"),
        ],
    ),
]

PUBLIC_ENDPOINTS = {
    ("GET", "/api/cas/cas"),
    ("POST", "/api/cas/user"),
    ("POST", "/api/index/config"),
    ("POST", "/api/index/lang"),
    ("POST", "/api/index/category"),
    ("POST", "/api/index/booking_rules"),
    ("POST", "/api/index/time"),
    ("POST", "/api/index/banner"),
    ("POST", "/api/index/notice"),
    ("POST", "/api/index/noticeDetail"),
    ("POST", "/api/index/subscribe"),
    ("POST", "/api/Captcha/verify"),
    ("POST", "/api/login/login"),
    ("POST", "/api/login/forget"),
    ("POST", "/api/login/resetpass"),
    ("POST", "/api/login/updateUserInfo"),
    ("POST", "/api/jwt/login"),
    ("POST", "/api/login/dingtalksns"),
    ("POST", "/api/login/wxlogin"),
    ("POST", "/api/login/wxwork"),
    ("POST", "/api/Help/index"),
    ("POST", "/api/Help/detail"),
    ("GET", "https://authserver.xauat.edu.cn/authserver/login"),
    ("POST", "https://authserver.xauat.edu.cn/authserver/login"),
    ("GET", "https://authserver.xauat.edu.cn/authserver/checkNeedCaptcha.htl"),
}

ENCRYPTED_ENDPOINTS = {
    ("POST", "/api/Enter/confirm"),
    ("POST", "/api/Seat/confirm"),
    ("POST", "/api/Seat/touch_qr_books"),
    ("POST", "/api/Study/StudyOrder"),
    ("POST", "/api/login/forget"),
    ("POST", "/api/login/login"),
    ("POST", "/api/login/resetpass"),
    ("POST", "/api/login/updateUserInfo"),
    ("POST", "/api/seat/qrcode"),
    ("POST", "/api/seat/qrcode_not_card"),
    ("POST", "/api/seat/xuzuoconfirm"),
    ("POST", "/reserve/index/confirm"),
}

USED_BY_V1_ENDPOINTS = {
    ("GET", "/api/cas/cas"),
    ("POST", "/api/cas/user"),
    ("POST", "/api/index/config"),
    ("POST", "/api/Member/my"),
    ("POST", "/api/Member/seat"),
    ("POST", "/api/Space/cancel"),
    ("POST", "/api/Seat/date"),
    ("POST", "/api/Seat/tree"),
    ("POST", "/api/Seat/seat"),
    ("POST", "/api/Seat/confirm"),
    ("POST", "/api/Seminar/date"),
    ("POST", "/api/Seminar/detail"),
    ("POST", "/api/Seminar/group"),
    ("POST", "/api/Seminar/seminar"),
    ("POST", "/api/Seminar/tree"),
    ("POST", "/reserve/index/confirm"),
    ("GET", "https://authserver.xauat.edu.cn/authserver/login"),
    ("POST", "https://authserver.xauat.edu.cn/authserver/login"),
    ("GET", "https://authserver.xauat.edu.cn/authserver/checkNeedCaptcha.htl"),
}


def _make_record(method: str, path: str, module: str) -> dict[str, Any]:
    return {
        "path": path,
        "method": method,
        "module": module,
        "auth_required": (method, path) not in PUBLIC_ENDPOINTS,
        "encrypted_body": (method, path) in ENCRYPTED_ENDPOINTS,
        "used_by_v1": (method, path) in USED_BY_V1_ENDPOINTS,
        "observed_on": OBSERVED_ON,
    }


INTERFACE_CATALOG = [_make_record(method, path, module) for module, items in GROUPS for method, path in items]

if len(INTERFACE_CATALOG) != 124:
    raise RuntimeError(f"Unexpected interface catalog size: {len(INTERFACE_CATALOG)}")


def build_interface_catalog() -> list[dict[str, Any]]:
    return [dict(record) for record in INTERFACE_CATALOG]


def render_catalog_markdown(records: list[dict[str, Any]]) -> str:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for record in records:
        grouped.setdefault(record["module"], []).append(record)

    lines = [
        "# XAUAT Libspace Interface Catalog",
        "",
        f"- Observed on: {OBSERVED_ON}",
        f"- Total endpoints: {len(records)}",
        "",
    ]

    for module, items in grouped.items():
        lines.append(f"## {module} ({len(items)})")
        lines.append("")
        lines.append("| Path | Method | Auth | Encrypted | Used by v1 | Observed |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for item in items:
            lines.append(
                "| {path} | {method} | {auth} | {encrypted} | {used} | {observed} |".format(
                    path=item["path"],
                    method=item["method"],
                    auth="yes" if item["auth_required"] else "no",
                    encrypted="yes" if item["encrypted_body"] else "no",
                    used="yes" if item["used_by_v1"] else "no",
                    observed=item["observed_on"],
                )
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_catalog_summary(records: list[dict[str, Any]]) -> str:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for record in records:
        grouped.setdefault(record["module"], []).append(record)

    lines = [f"Total endpoints: {len(records)}", ""]
    for module, items in grouped.items():
        lines.append(f"[{module}] {len(items)}")
        for item in items:
            lines.append(
                f"  {item['method']} {item['path']} | auth={'yes' if item['auth_required'] else 'no'} | "
                f"encrypted={'yes' if item['encrypted_body'] else 'no'} | v1={'yes' if item['used_by_v1'] else 'no'}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
