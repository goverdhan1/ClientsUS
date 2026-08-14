from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from . import state as state_mod
from .consent import SuppressionList
from .models import Lead


def select_batch(
    leads: list[Lead],
    suppression: SuppressionList,
    sent_log_path: Path,
    *,
    max_count: int,
    per_state_cap: int,
    cooldown_days: int,
) -> tuple[list[Lead], dict[str, int]]:
    """Pick who may be emailed this run, in file order.

    A lead is skipped if it is a duplicate, unsubscribed, contacted within the
    cooldown window, or its state already hit the per-state cap for this run.
    """
    seen: set[str] = set()
    per_state: dict[str, int] = defaultdict(int)
    chosen: list[Lead] = []
    skipped = {"duplicate": 0, "suppressed": 0, "cooldown": 0, "state_cap": 0, "over_max": 0}

    for lead in leads:
        if len(chosen) >= max_count:
            skipped["over_max"] += 1
            continue
        if not lead.email.strip():
            skipped["no_email"] = skipped.get("no_email", 0) + 1
            continue
        key = lead.normalized_email
        if key in seen:
            skipped["duplicate"] += 1
            continue
        seen.add(key)
        if suppression.is_suppressed(key):
            skipped["suppressed"] += 1
            continue
        if state_mod.recently_contacted(sent_log_path, key, cooldown_days):
            skipped["cooldown"] += 1
            continue
        if per_state[lead.state] >= per_state_cap:
            skipped["state_cap"] += 1
            continue
        per_state[lead.state] += 1
        chosen.append(lead)

    return chosen, skipped


def select_whatsapp_batch(
    leads: list[Lead],
    sent_log_path: Path,
    *,
    max_count: int,
    per_state_cap: int,
    cooldown_days: int,
) -> tuple[list[Lead], dict[str, int]]:
    """Pick leads eligible for WhatsApp this run (phone + whatsapp consent)."""
    seen: set[str] = set()
    per_state: dict[str, int] = defaultdict(int)
    chosen: list[Lead] = []
    skipped: dict[str, int] = defaultdict(int)

    for lead in leads:
        if len(chosen) >= max_count:
            skipped["over_max"] += 1
            continue
        if lead.validate_for_whatsapp():
            skipped["invalid"] += 1
            continue
        if not lead.phone.strip():
            skipped["no_phone"] += 1
            continue
        key = lead.phone.strip()
        if key in seen:
            skipped["duplicate"] += 1
            continue
        seen.add(key)
        if state_mod.recently_contacted_whatsapp(sent_log_path, key, cooldown_days):
            skipped["cooldown"] += 1
            continue
        if per_state[lead.state] >= per_state_cap:
            skipped["state_cap"] += 1
            continue
        per_state[lead.state] += 1
        chosen.append(lead)

    return chosen, dict(skipped)
