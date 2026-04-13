from __future__ import annotations

from typing import Any


def flatten_seat_tree(area_data: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    rooms: list[dict[str, Any]] = []
    for area in area_data or []:
        for floor in area.get("children") or []:
            for room in floor.get("children") or []:
                rooms.append(
                    {
                        "areaId": area.get("id"),
                        "areaName": area.get("name"),
                        "floorId": floor.get("id"),
                        "floorName": floor.get("name"),
                        "roomId": room.get("id"),
                        "roomName": room.get("name"),
                        "totalCount": room.get("TotalCount", room.get("totalCount")),
                        "isValid": int(room.get("isValid", 0) or 0),
                        "tag": room.get("tag"),
                    }
                )
    return rooms


def flatten_seminar_tree(area_data: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    rooms: list[dict[str, Any]] = []
    for area in area_data or []:
        for floor in area.get("children") or []:
            for room in floor.get("children") or []:
                rooms.append(
                    {
                        "areaId": area.get("id"),
                        "areaName": area.get("name"),
                        "floorId": floor.get("id"),
                        "floorName": floor.get("name"),
                        "roomId": room.get("id"),
                        "roomName": room.get("name"),
                        "totalCount": room.get("TotalCount", room.get("totalCount")),
                        "isValid": int(room.get("isValid", 1) or 0),
                        "tag": room.get("tag"),
                        "upload": room.get("upload"),
                        "membercount": room.get("membercount"),
                    }
                )
    return rooms
