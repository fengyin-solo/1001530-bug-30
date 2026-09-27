"""通信设备业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "comm"
REQUIRED_FIELDS = ["设备编号", "设备名称", "设备型号"]
OPTIONAL_FIELDS = ["所属站点", "安装日期", "上次检修日", "责任人"]
MARK_FIELDS = ["设备型号", "安装日期"]
STATUS_ORDER = ["待检修", "运行正常", "检修中", "已报废"]
ACTION_RULES = {"安排检修": "检修中", "确认正常": "运行正常", "报废设备": "已报废"}
NEGATIVE_ACTIONS = []
SCRAPPED = STATUS_ORDER[-1]


class CommService:
    def _sync_display(self, entry: dict[str, Any]) -> dict[str, Any]:
        """让展示字段与内部状态保持一致，并给缺项记录打上标记。"""
        entry["设备状态"] = entry.get("status")
        missing = [field for field in MARK_FIELDS if not str(entry.get(field) or "").strip()]
        entry["缺项标记"] = "、".join(missing)
        if missing:
            entry["abnormal"] = True
        return entry

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("设备编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._sync_display(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._sync_display(entry)

    def stats(self) -> list[dict[str, Any]]:
        """统计卡与列表共用同一份在册数据；已报废设备归档后不再参与在运统计。"""
        rows = [row for row in store.rows(MODULE) if row.get("status") != SCRAPPED]
        marked = sum(1 for row in rows if self._sync_display(row).get("缺项标记"))
        return [
            {"label": "在运通信设备", "value": len(rows)},
            {"label": "待检修设备", "value": sum(1 for row in rows if row.get("status") == "待检修")},
            {"label": "检修中设备", "value": sum(1 for row in rows if row.get("status") == "检修中")},
            {"label": "缺项待补设备", "value": marked},
        ]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS + OPTIONAL_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._sync_display(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"通信设备 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于通信设备可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        current = str(entry.get("status") or STATUS_ORDER[0])
        if current not in STATUS_ORDER:
            return None, f"当前状态「{current}」不在允许的状态序列里，请先修正数据"
        current_index = STATUS_ORDER.index(current)
        target_index = STATUS_ORDER.index(target)
        if target_index < current_index:
            flow = " → ".join(STATUS_ORDER)
            return None, f"通信设备当前为「{current}」，不能回退到「{target}」，状态须按 {flow} 顺序流转"
        if target_index == current_index:
            return self._sync_display(entry), f"通信设备已处于「{current}」，重复{action}不会改变状态"
        entry["status"] = target
        entry["pending"] = target != SCRAPPED
        if action in NEGATIVE_ACTIONS:
            entry["abnormal"] = True
        if target == SCRAPPED:
            store.archive(MODULE, entry_id)
            return self._sync_display(entry), "通信设备已报废并归档，不再参与在运统计"
        return self._sync_display(entry), f"通信设备已{action}"
