"""Salary tool functions returning human-readable result strings."""

from __future__ import annotations

from datetime import date, datetime

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


def _date_label(for_date: str | None) -> str:
    return f" for {for_date}" if for_date else ""


def tool_add_bonus(
    worker: str, amount: float, note: str = "", *, for_date: str | None = None
) -> str:
    """Add bonus for a worker. Returns human-readable result."""
    try:
        record = data.add_bonus(worker, amount, note, for_date=for_date)
        breakdown = data.calculate_net_salary(record)
        return (
            f"Added bonus {_format_amount(amount)} to {record['full_name']}"
            f"{_date_label(for_date)}. "
            f"Net payable (all time): {_format_amount(breakdown['net_payable'])}."
        )
    except ValueError as exc:
        return str(exc)


def tool_add_penalty(
    worker: str, amount: float, note: str = "", *, for_date: str | None = None
) -> str:
    """Add penalty for a worker. Returns human-readable result."""
    try:
        record = data.add_penalty(worker, amount, note, for_date=for_date)
        final = record.get("final_salary", data.calculate_net_salary(record)["net_payable"])
        return (
            f"Added penalty {_format_amount(amount)} for {record['full_name']}"
            f"{_date_label(for_date)}. "
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


def tool_add_advance(
    worker: str, amount: float, note: str = "", *, for_date: str | None = None
) -> str:
    """Add advance for a worker. Returns human-readable result."""
    try:
        record = data.add_advance(worker, amount, note, for_date=for_date)
        breakdown = data.calculate_net_salary(record)
        return (
            f"Recorded advance {_format_amount(amount)} for {record['full_name']}"
            f"{_date_label(for_date)}. "
            f"Net payable (all time): {_format_amount(breakdown['net_payable'])}."
        )
    except ValueError as exc:
        return str(exc)


def tool_record_payout(
    worker: str,
    amount: float,
    period: str | None = None,
    *,
    for_date: str | None = None,
) -> str:
    """Record salary payout. Returns human-readable result."""
    try:
        record = data.record_payout(worker, amount, period, for_date=for_date)
        breakdown = data.calculate_net_salary(record)
        when = for_date or _period_label(period)
        return (
            f"Recorded payout {_format_amount(amount)} for {record['full_name']} "
            f"({when}). Net payable (all time): "
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


_LIST_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "name": "Name",
        "age": "Age",
        "salary": "Salary",
        "header": "Workers",
        "empty": "No workers registered yet.",
    },
    "uz": {
        "name": "Ism",
        "age": "Yosh",
        "salary": "Maosh",
        "header": "Ishchilar",
        "empty": "Hozircha ro'yxatdan o'tgan ishchi yo'q.",
    },
    "ru": {
        "name": "Имя",
        "age": "Возраст",
        "salary": "Зарплата",
        "header": "Работники",
        "empty": "Пока нет зарегистрированных работников.",
    },
}


def _age_from_birthdate(birthdate: str) -> int | None:
    """Compute age in years from YYYY-MM-DD birthdate."""
    try:
        born = datetime.strptime(birthdate, "%Y-%m-%d").date()
    except ValueError:
        return None
    today = date.today()
    age = today.year - born.year
    if (today.month, today.day) < (born.month, born.day):
        age -= 1
    return age


def _worker_net_payable(key: str, worker: dict) -> float:
    return worker.get(
        "final_salary",
        data.calculate_net_salary({"key": key, **worker})["net_payable"],
    )


def _format_worker_card(key: str, worker: dict, labels: dict[str, str]) -> str:
    """Format one worker entry for the list view."""
    age = _age_from_birthdate(worker.get("birthdate", ""))
    age_str = str(age) if age is not None else "—"
    salary = _format_amount(_worker_net_payable(key, worker))
    return (
        f"{labels['name']}: {worker['full_name']}\n"
        f"{labels['age']}: {age_str}\n"
        f"{labels['salary']}: {salary}"
    )


def tool_list_workers(language: str = "en") -> str:
    """List all workers with name, age, and net salary per card."""
    labels = _LIST_LABELS.get(language, _LIST_LABELS["en"])
    workers = data.list_workers()
    if not workers:
        return labels["empty"]

    cards = [
        _format_worker_card(key, worker, labels)
        for key, worker in sorted(
            workers.items(), key=lambda item: item[1]["full_name"].lower()
        )
    ]
    header = f"{labels['header']} ({len(cards)})"
    return header + "\n\n" + "\n\n------\n\n".join(cards)


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
