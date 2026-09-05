"""Seeds the three fixed local-demo accounts used by Phase 2 authentication.

These are demo accounts only -- not real people -- same spirit as
merchant_demo_001 elsewhere in this codebase. See
docs/PHASE_2_AUTH_DESIGN.md. Passwords are randomly generated and printed
to the terminal once; nothing is written to any file.

Safe to re-run: if a username already exists, it is left untouched and
reported, not duplicated or reset.

Usage:
    python3 scripts/seed_demo_users.py
"""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.database import create_db_engine, init_db, make_session_factory, session_scope
from app.db.models import User
from app.services import auth_service

DEMO_CASE_PACKETS_PATH = Path(__file__).resolve().parent.parent / "demo_data" / "demo_case_packets.json"

# Which seeded demo case's merchant the demo merchant account should be able
# to log in as -- the one docs/UI_DEMO_GUIDE.md walks through for the
# Merchant Response page. `ml/generate_demo_cases.py` picks this scenario's
# merchant_id freshly from whatever synthetic dataset exists at generation
# time, so it is NOT a stable value across regenerations -- it must be read
# from the current demo_data/demo_case_packets.json, never hardcoded (a
# hardcoded value silently drifted out of sync with the real seeded cases
# once before, breaking the merchant-response demo flow entirely).
MERCHANT_DEMO_SCENARIO_KEY = "seasonal_sale_false_positive_candidate"
FALLBACK_MERCHANT_ID = "merchant_demo_0001"


def _resolve_demo_merchant_id() -> str:
    """Reads the current demo_data/demo_case_packets.json for the scenario
    merchant_demo should be able to act on. Falls back to a fixed ID (with a
    warning) if the file is missing or doesn't have the expected shape --
    seeding still proceeds rather than crashing, since a merchant login that
    happens to see zero cases is still safer than no login at all."""
    try:
        data = json.loads(DEMO_CASE_PACKETS_PATH.read_text())
        merchant_id = data[MERCHANT_DEMO_SCENARIO_KEY]["identification"]["merchant_id"]
        if isinstance(merchant_id, str) and merchant_id:
            return merchant_id
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        pass
    print(
        f"Warning: could not read merchant_id for '{MERCHANT_DEMO_SCENARIO_KEY}' from "
        f"{DEMO_CASE_PACKETS_PATH} -- falling back to {FALLBACK_MERCHANT_ID}. "
        "Run `python3 -m ml.generate_demo_cases` first if this looks wrong."
    )
    return FALLBACK_MERCHANT_ID


DEMO_ACCOUNTS = [
    {"username": "reviewer_demo", "role": "reviewer", "actor_id": "analyst_demo_001", "display_name": "Demo Reviewer", "merchant_id": None},
    {"username": "merchant_demo", "role": "merchant", "actor_id": "merchant_demo_actor_001", "display_name": "Demo Merchant", "merchant_id": _resolve_demo_merchant_id()},
    {"username": "riskmanager_demo", "role": "risk_manager", "actor_id": "riskmanager_demo_001", "display_name": "Demo Risk Manager", "merchant_id": None},
]


def seed() -> list[tuple[str, str, str]]:
    """Returns a list of (username, password, role) for accounts actually
    created this run -- an empty list for a username means it already
    existed and was left untouched."""
    engine = create_db_engine()
    init_db(engine)
    session_factory = make_session_factory(engine)

    created = []
    with session_scope(session_factory) as session:
        for account in DEMO_ACCOUNTS:
            existing = session.execute(select(User).where(User.username == account["username"])).scalar_one_or_none()
            if existing is not None:
                print(f"{account['username']}: already exists, left untouched.")
                continue

            password = secrets.token_urlsafe(9)
            auth_service.create_user(
                session,
                username=account["username"],
                password=password,
                role=account["role"],
                actor_id=account["actor_id"],
                display_name=account["display_name"],
                merchant_id=account["merchant_id"],
            )
            created.append((account["username"], password, account["role"]))

    return created


def main() -> None:
    created = seed()
    if not created:
        print("\nNo new accounts created (all demo usernames already existed).")
        return

    print("\nDemo account credentials (printed once, not stored anywhere else):")
    print("-" * 60)
    for username, password, role in created:
        print(f"  role={role:<12} username={username:<20} password={password}")
    print("-" * 60)
    print(
        "These are local-demo credentials only -- not production-grade "
        "auth. See docs/PHASE_2_AUTH_DESIGN.md and SECURITY.md."
    )


if __name__ == "__main__":
    main()
