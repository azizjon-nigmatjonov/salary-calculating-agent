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
            f"{_format_amount(worker['fixed_salary'])} (started {job_started_date})."
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
        breakdown = data.calculate_net_salary(record)
        return (
            f"{record['full_name']}: started {record['job_started_date']}, "
            f"birthdate {record['birthdate']}, "
            f"fixed salary {_format_amount(record['fixed_salary'])}, "
            f"net payable {_format_amount(breakdown['net_payable'])}."
        )
    except ValueError as exc:
        return str(exc)


def tool_list() -> str:
    """List all workers and net payable balances."""
    workers = data.list_workers()
    if not workers:
        return "No workers registered yet."

    parts: list[str] = []
    for key, worker in workers.items():
        record = {"key": key, **worker}
        net = data.calculate_net_salary(record)["net_payable"]
        parts.append(f"{worker['full_name']} ({_format_amount(net)})")
    return "Workers: " + ", ".join(parts)


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
