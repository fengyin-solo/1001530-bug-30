"""通信设备业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "comm"
REQUIRED_FIELDS = ["设备编号", "设备名称", "设备型号"]
OPTIONAL_FIELDS = ["所属站点", "安装日期", "上次检修日", "责任人"]
INFO_FIELDS = ["设备型号", "安装日期"]
STATUS_ORDER = ["待检修", "运行正常", "检修中", "已报废"]
TERMINAL_STATUS = "已报废"
PENDING_STATUSES = {"待检修", "检修中"}
ACTIONS = ["安排检修", "确认正常", "报废设备"]

# 流转顺序：检修在 待检修/运行正常 与 检修中 之间推进，报废是终点并归档，
# 已报废不接受任何动作，也不会再回到检修中或运行正常。
FLOW_RULES: dict[str, dict[str, str]] = {
    "待检修": {"安排检修": "检修中", "确认正常": "运行正常", "报废设备": "已报废"},
    "检修中": {"确认正常": "运行正常", "报废设备": "已报废"},
    "运行正常": {"安排检修": "检修中", "报废设备": "已报废"},
    "已报废": {},
}


def _normalize(entry: dict[str, Any]) -> dict[str, Any]:
    """把状态、待办与资料标记对齐到同一份数据，列表、详情、统计卡都走这里。"""
    status = str(entry.get("status") or STATUS_ORDER[0])
    if status not in STATUS_ORDER:
        status = STATUS_ORDER[0]
    entry["status"] = status
    entry["设备状态"] = status
    entry["pending"] = status in PENDING_STATUSES
    missing = [field for field in INFO_FIELDS if not str(entry.get(field) or "").strip()]
    entry["incomplete"] = bool(missing)
    entry["缺失字段"] = missing
    entry["abnormal"] = bool(missing)
    return entry


class CommService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [_normalize(row) for row in store.rows(MODULE)]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("设备编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return _normalize(entry) if entry is not None else None

    def get_stats(self) -> list[dict[str, Any]]:
        """统计卡只算在册设备：已报废归档的不参与在运统计。"""
        rows = [_normalize(row) for row in store.rows(MODULE)]
        return [
            {"label": "在册通信设备", "value": len(rows)},
            {"label": "待检修设备", "value": sum(1 for row in rows if row["status"] == "待检修")},
            {"label": "检修中设备", "value": sum(1 for row in rows if row["status"] == "检修中")},
            {"label": "资料待补全", "value": sum(1 for row in rows if row["incomplete"])},
        ]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": store.next_id(MODULE)}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS + OPTIONAL_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        rows.append(entry)
        return _normalize(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"通信设备 {entry_id} 不存在或已归档"
        if action not in ACTIONS:
            return None, f"动作「{action}」不属于通信设备可执行范围"
        current = str(entry.get("status") or STATUS_ORDER[0])
        if current == TERMINAL_STATUS:
            return None, "通信设备已报废归档，不能再执行任何操作"
        target = FLOW_RULES.get(current, {}).get(action)
        if target is None:
            return None, f"当前状态「{current}」不允许执行「{action}」，请按检修与报废的流转顺序操作"
        entry["status"] = target
        _normalize(entry)
        if target == TERMINAL_STATUS:
            store.archive(MODULE, entry_id)
            return entry, "通信设备已报废并归档，不再参与在运统计"
        return entry, f"通信设备已{action}"
