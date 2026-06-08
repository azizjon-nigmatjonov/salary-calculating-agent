"""JSON-backed salary storage and payroll calculations."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

import config

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PERIOD_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def _now_iso() -> str:
    """Return current local time in ISO format."""
    return datetime.now().isoformat(timespec="seconds")


def _validate_date(value: str, field_name: str) -> None:
    """Validate YYYY-MM-DD date string."""
    if not DATE_PATTERN.match(value):
        raise ValueError(f"{field_name} must be YYYY-MM-DD, got {value!r}")
    datetime.strptime(value, "%Y-%m-%d")


def _validate_period(value: str) -> None:
    """Validate YYYY-MM period string."""
    if not PERIOD_PATTERN.match(value):
        raise ValueError(f"period must be YYYY-MM, got {value!r}")
    datetime.strptime(value + "-01", "%Y-%m-%d")


def _validate_positive_amount(amount: float, field_name: str) -> None:
    """Ensure amount is a positive number."""
    if amount <= 0:
        raise ValueError(f"{field_name} must be positive, got {amount}")


def _timestamp_in_period(timestamp: str, period: str) -> bool:
    """Return True if ISO timestamp falls within YYYY-MM period."""
    try:
        dt = datetime.fromisoformat(timestamp)
    except ValueError:
        return False
    return dt.strftime("%Y-%m") == period


def _sum_entries(entries: list[dict[str, Any]], period: str | None) -> float:
    """Sum entry amounts, optionally filtered by period."""
    total = 0.0
    for entry in entries:
        if period is None or _timestamp_in_period(entry["timestamp"], period):
            total += float(entry["amount"])
    return total


def _sum_payouts(payouts: list[dict[str, Any]], period: str | None) -> float:
    """Sum payout amounts, optionally filtered by period."""
    total = 0.0
    for entry in payouts:
        if period is None:
            total += float(entry["amount"])
        elif entry.get("period") == period or _timestamp_in_period(
            entry["timestamp"], period
        ):
            total += float(entry["amount"])
    return total


def _append_history(worker: dict[str, Any], action: str, details: str) -> None:
    """Append an audit entry to worker history."""
    worker.setdefault("history", []).append(
        {"action": action, "details": details, "timestamp": _now_iso()}
    )


def _sync_final_salary(worker: dict[str, Any]) -> None:
    """Update stored final_salary from current ledger (all-time net payable)."""
    worker["final_salary"] = calculate_net_salary(worker)["net_payable"]


def load_db() -> dict[str, Any]:
    """Load database from JSON file, creating empty structure if missing."""
    try:
        with open(config.DB_FILE, encoding="utf-8") as f:
            db = json.load(f)
    except FileNotFoundError:
        db = {"workers": {}}
        save_db(db)
        return db

    if "workers" not in db:
        db["workers"] = {}

    migrated = False
    for worker in db["workers"].values():
        if "penalties" not in worker:
            worker["penalties"] = []
            migrated = True
        if "final_salary" not in worker:
            _sync_final_salary(worker)
            migrated = True
    if migrated:
        save_db(db)

    return db


def save_db(db: dict[str, Any]) -> None:
    """Persist database to JSON file."""
    with open(config.DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def normalize_worker_key(full_name: str) -> str:
    """Convert full name to lowercase slug key."""
    slug = full_name.strip().lower()
    slug = re.sub(r"[^\w\s]", "", slug, flags=re.UNICODE)
    slug = re.sub(r"\s+", "_", slug)
    return slug


def resolve_worker_key(name_or_key: str) -> str:
    """
    Resolve a worker slug or partial name to a canonical key.

    Raises ValueError if not found or ambiguous.
    """
    query = name_or_key.strip().lower()
    db = load_db()
    workers = db["workers"]

    if query in workers:
        return query

    matches: list[str] = []
    for key, worker in workers.items():
        full_name = worker.get("full_name", "").lower()
        if query == full_name or query in full_name or query in key:
            matches.append(key)

    if not matches:
        raise ValueError(f"Worker not found: {name_or_key!r}")
    if len(matches) > 1:
        names = ", ".join(workers[k]["full_name"] for k in matches)
        raise ValueError(f"Ambiguous worker {name_or_key!r}. Did you mean: {names}?")
    return matches[0]


def register_worker(
    full_name: str,
    job_started_date: str,
    birthdate: str,
    fixed_salary: float,
) -> dict[str, Any]:
    """Register a new worker. Raises ValueError on duplicate or invalid input."""
    _validate_date(job_started_date, "job_started_date")
    _validate_date(birthdate, "birthdate")
    _validate_positive_amount(float(fixed_salary), "fixed_salary")

    key = normalize_worker_key(full_name)
    db = load_db()

    if key in db["workers"]:
        raise ValueError(
            f"Worker {full_name!r} already exists. Use update to change profile."
        )

    worker: dict[str, Any] = {
        "full_name": full_name.strip(),
        "job_started_date": job_started_date,
        "birthdate": birthdate,
        "fixed_salary": float(fixed_salary),
        "bonuses": [],
        "advances": [],
        "penalties": [],
        "payouts": [],
        "history": [],
    }
    _append_history(
        worker,
        "register",
        f"Registered with fixed salary {fixed_salary:,.0f}",
    )
    _sync_final_salary(worker)
    db["workers"][key] = worker
    save_db(db)
    return {"key": key, **worker}


def get_worker(key: str) -> dict[str, Any] | None:
    """Get worker record by key, or None if not found."""
    db = load_db()
    worker = db["workers"].get(key)
    if worker is None:
        return None
    return {"key": key, **worker}


def list_workers() -> dict[str, Any]:
    """Return full workers dict from database."""
    return load_db()["workers"]


def update_worker(key: str, **fields: Any) -> dict[str, Any]:
    """Partially update worker profile fields."""
    resolved = resolve_worker_key(key)
    db = load_db()
    worker = db["workers"][resolved]

    allowed = {"full_name", "job_started_date", "birthdate", "fixed_salary"}
    updates: list[str] = []

    for field, value in fields.items():
        if field not in allowed or value is None:
            continue
        if field in ("job_started_date", "birthdate"):
            _validate_date(str(value), field)
        if field == "fixed_salary":
            _validate_positive_amount(float(value), "fixed_salary")
            value = float(value)
        if field == "full_name":
            value = str(value).strip()
        worker[field] = value
        updates.append(f"{field}={value}")

    if not updates:
        raise ValueError("No valid fields to update.")

    _append_history(worker, "update", ", ".join(updates))
    _sync_final_salary(worker)
    save_db(db)
    return {"key": resolved, **worker}


def add_bonus(key: str, amount: float, note: str = "") -> dict[str, Any]:
    """Add a bonus entry for a worker."""
    resolved = resolve_worker_key(key)
    _validate_positive_amount(float(amount), "amount")

    db = load_db()
    worker = db["workers"][resolved]
    entry = {"amount": float(amount), "note": note or "", "timestamp": _now_iso()}
    worker.setdefault("bonuses", []).append(entry)
    _append_history(worker, "add_bonus", f"+{amount:,.0f} ({note or 'no note'})")
    _sync_final_salary(worker)
    save_db(db)
    return {"key": resolved, **worker}


def add_penalty(key: str, amount: float, note: str = "") -> dict[str, Any]:
    """Add a penalty entry for a worker."""
    resolved = resolve_worker_key(key)
    _validate_positive_amount(float(amount), "amount")

    db = load_db()
    worker = db["workers"][resolved]
    entry = {"amount": float(amount), "note": note or "", "timestamp": _now_iso()}
    worker.setdefault("penalties", []).append(entry)
    _append_history(worker, "add_penalty", f"penalty {amount:,.0f} ({note or 'no note'})")
    _sync_final_salary(worker)
    save_db(db)
    return {"key": resolved, **worker}


def delete_worker(key: str) -> dict[str, Any]:
    """Remove a worker from the database."""
    resolved = resolve_worker_key(key)
    db = load_db()
    worker = db["workers"].pop(resolved)
    save_db(db)
    return {"key": resolved, **worker}


def add_advance(key: str, amount: float, note: str = "") -> dict[str, Any]:
    """Add an advance entry for a worker."""
    resolved = resolve_worker_key(key)
    _validate_positive_amount(float(amount), "amount")

    db = load_db()
    worker = db["workers"][resolved]
    entry = {"amount": float(amount), "note": note or "", "timestamp": _now_iso()}
    worker.setdefault("advances", []).append(entry)
    _append_history(worker, "add_advance", f"-{amount:,.0f} ({note or 'no note'})")
    _sync_final_salary(worker)
    save_db(db)
    return {"key": resolved, **worker}


def record_payout(key: str, amount: float, period: str | None = None) -> dict[str, Any]:
    """Record a salary payout for a worker."""
    resolved = resolve_worker_key(key)
    _validate_positive_amount(float(amount), "amount")
    if period is not None:
        _validate_period(period)

    db = load_db()
    worker = db["workers"][resolved]
    entry: dict[str, Any] = {
        "amount": float(amount),
        "timestamp": _now_iso(),
    }
    if period:
        entry["period"] = period
    worker.setdefault("payouts", []).append(entry)
    period_label = period or "unspecified period"
    _append_history(worker, "payout", f"paid {amount:,.0f} for {period_label}")
    _sync_final_salary(worker)
    save_db(db)
    return {"key": resolved, **worker}


def get_history(key: str, limit: int = 10) -> list[dict[str, Any]]:
    """Return last N history entries for a worker."""
    resolved = resolve_worker_key(key)
    db = load_db()
    history = db["workers"][resolved].get("history", [])
    return history[-limit:]


def calculate_net_salary(
    worker: dict[str, Any],
    *,
    period: str | None = None,
) -> dict[str, Any]:
    """
    Calculate net payable salary breakdown.

    net_payable = fixed_salary + bonuses - advances - penalties - payouts
    When period is set, bonuses/advances/penalties/payouts are filtered to that month.
    """
    if period is not None:
        _validate_period(period)

    fixed = float(worker["fixed_salary"])
    bonuses = _sum_entries(worker.get("bonuses", []), period)
    advances = _sum_entries(worker.get("advances", []), period)
    penalties = _sum_entries(worker.get("penalties", []), period)
    payouts = _sum_payouts(worker.get("payouts", []), period)
    net = fixed + bonuses - advances - penalties - payouts

    return {
        "fixed_salary": fixed,
        "total_bonuses": bonuses,
        "total_advances": advances,
        "total_penalties": penalties,
        "total_payouts": payouts,
        "net_payable": net,
        "period": period,
    }
