"""Salary tool functions returning human-readable result strings."""

from __future__ import annotations

import data


def _format_amount(amount: float) -> str:
    """Format amount with thousands separators."""
    if amount == int(amount):
        return f"{int(amount):,}"
    return f"{amount:,.2f}"


def _period_label(period: str | None) -> str:
    """Human-readable period label."""
    if period is None:
        return "all time"
    return period


def tool_register_worker(
    full_name: str,
    job_started_date: str,
    birthdate: str,
    fixed_salary: float,
) -> str:
    """Register a new worker. Returns human-readable result."""
    try:
        worker = data.register_worker(
            full_name, job_started_date, birthdate, fixed_salary
        )
        return (
            f"Registered {worker['full_name']} with fixed salary "
            f"{_format_amount(worker['fixed_salary'])} (started {job_started_date}). "
            f"Final salary: {_format_amount(worker['final_salary'])}."
        )
    except ValueError as exc:
        return str(exc)


def tool_update_worker(worker: str, **fields) -> str:
    """Update worker profile fields. Returns human-readable result."""
    try:
        updated = data.update_worker(worker, **fields)
        return f"Updated {updated['full_name']}'s profile."
    except ValueError as exc:
        return str(exc)


def tool_add_bonus(worker: str, amount: float, note: str = "") -> str:
    """Add bonus for a worker. Returns human-readable result."""
    try:
        record = data.add_bonus(worker, amount, note)
        breakdown = data.calculate_net_salary(record)
        return (
            f"Added bonus {_format_amount(amount)} to {record['full_name']}. "
            f"Net payable (all time): {_format_amount(breakdown['net_payable'])}."
        )
    except ValueError as exc:
        return str(exc)


def tool_add_penalty(worker: str, amount: float, note: str = "") -> str:
    """Add penalty for a worker. Returns human-readable result."""
    try:
        record = data.add_penalty(worker, amount, note)
        final = record.get("final_salary", data.calculate_net_salary(record)["net_payable"])
        return (
            f"Added penalty {_format_amount(amount)} for {record['full_name']}. "
            f"Final salary: {_format_amount(final)}."
        )
    except ValueError as exc:
        return str(exc)


def tool_delete_worker(worker: str) -> str:
    """Delete a worker. Returns human-readable result."""
    try:
        key = data.resolve_worker_key(worker)
        record = data.get_worker(key)
        if record is None:
            return f"Worker not found: {worker}"
        name = record["full_name"]
        data.delete_worker(key)
        return f"Removed {name} from the worker list."
    except ValueError as exc:
        return str(exc)


def tool_add_advance(worker: str, amount: float, note: str = "") -> str:
    """Add advance for a worker. Returns human-readable result."""
    try:
        record = data.add_advance(worker, amount, note)
        breakdown = data.calculate_net_salary(record)
        return (
            f"Recorded advance {_format_amount(amount)} for {record['full_name']}. "
            f"Net payable (all time): {_format_amount(breakdown['net_payable'])}."
        )
    except ValueError as exc:
        return str(exc)


def tool_record_payout(worker: str, amount: float, period: str | None = None) -> str:
    """Record salary payout. Returns human-readable result."""
    try:
        record = data.record_payout(worker, amount, period)
        breakdown = data.calculate_net_salary(record)
        period_text = _period_label(period)
        return (
            f"Recorded payout {_format_amount(amount)} for {record['full_name']} "
            f"({period_text}). Net payable (all time): "
            f"{_format_amount(breakdown['net_payable'])}."
        )
    except ValueError as exc:
        return str(exc)


def tool_calculate_salary(worker: str, period: str | None = None) -> str:
    """Calculate net salary breakdown. Returns human-readable result."""
    try:
        key = data.resolve_worker_key(worker)
        record = data.get_worker(key)
        if record is None:
            return f"Worker not found: {worker}"
        breakdown = data.calculate_net_salary(record, period=period)
        period_text = _period_label(period)
        return (
            f"{record['full_name']} — {period_text}: "
            f"fixed {_format_amount(breakdown['fixed_salary'])} + "
            f"bonuses {_format_amount(breakdown['total_bonuses'])} − "
            f"advances {_format_amount(breakdown['total_advances'])} − "
            f"penalties {_format_amount(breakdown['total_penalties'])} − "
            f"paid {_format_amount(breakdown['total_payouts'])} = "
            f"net payable {_format_amount(breakdown['net_payable'])}."
        )
    except ValueError as exc:
        return str(exc)


def tool_get_worker(worker: str) -> str:
    """Get worker profile summary. Returns human-readable result."""
    try:
        key = data.resolve_worker_key(worker)
        record = data.get_worker(key)
        if record is None:
            return f"Worker not found: {worker}"
        final = record.get("final_salary", data.calculate_net_salary(record)["net_payable"])
        return (
            f"{record['full_name']}: started {record['job_started_date']}, "
            f"birthdate {record['birthdate']}, "
            f"fixed salary {_format_amount(record['fixed_salary'])}, "
            f"final salary {_format_amount(final)}."
        )
    except ValueError as exc:
        return str(exc)


def _worker_balances() -> list[tuple[str, float]]:
    """Return (full_name, net_payable) for each worker."""
    workers = data.list_workers()
    rows: list[tuple[str, float]] = []
    for key, worker in workers.items():
        final = worker.get(
            "final_salary",
            data.calculate_net_salary({"key": key, **worker})["net_payable"],
        )
        rows.append((worker["full_name"], final))
    return rows


def tool_list_workers(language: str = "en") -> str:
    """List all workers with count and net payable balances."""
    rows = _worker_balances()
    if not rows:
        empty = {
            "en": "No workers registered yet.",
            "ru": "Пока нет зарегистрированных работников.",
            "uz": "Hozircha ro'yxatdan o'tgan ishchi yo'q.",
        }
        return empty.get(language, empty["en"])

    count = len(rows)
    if language == "uz":
        lines = [f"Jami ishchilar soni: {count}", ""]
        for index, (name, final) in enumerate(rows, start=1):
            lines.append(f"{index}. {name} — {_format_amount(final)}")
        return "\n".join(lines)

    if language == "ru":
        lines = [f"Всего работников: {count}", ""]
        for index, (name, final) in enumerate(rows, start=1):
            lines.append(f"{index}. {name} — {_format_amount(final)}")
        return "\n".join(lines)

    parts = [f"{name} ({_format_amount(final)})" for name, final in rows]
    return f"Workers ({count}): " + ", ".join(parts)


def tool_list() -> str:
    """List all workers and net payable balances."""
    return tool_list_workers("en")


def tool_history(worker: str) -> str:
    """Get last 10 transactions for a worker."""
    try:
        key = data.resolve_worker_key(worker)
        record = data.get_worker(key)
        if record is None:
            return f"Worker not found: {worker}"
        history = data.get_history(key, limit=10)
        if not history:
            return f"No history for {record['full_name']}."
        lines = [
            f"- {h['action']}: {h['details']} ({h['timestamp']})" for h in history
        ]
        return f"History for {record['full_name']}:\n" + "\n".join(lines)
    except ValueError as exc:
        return str(exc)
