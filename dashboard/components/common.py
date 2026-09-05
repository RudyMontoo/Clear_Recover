"""Shared UI helpers: safety disclaimer, backend connection status, risk
intensity badges, and safe formatting. No business logic lives here --
only display helpers around data already returned by the API client.
"""

from __future__ import annotations

import html
import re

import streamlit as st

from dashboard.api_client import ClearRiskAPIClient, DashboardAPIError

GLOBAL_DISCLAIMER = (
    "Local synthetic-data demonstration only. This tool does not process payments, "
    "hold settlements, freeze funds, ban merchants, or make final fraud decisions."
)

# Short per-page reminder. The full statement above lives in the sidebar so
# it is always on screen without consuming the top of every page body.
PAGE_NOTICE = "Synthetic demo data · review recommendations only · not a final fraud decision."

BACKEND_START_COMMAND = "uvicorn app.main:app --reload"

INTENSITY_COLORS = {
    "low": "#1a7f37",
    "medium": "#9a6700",
    "high": "#cf222e",
}
INTENSITY_BACKGROUNDS = {
    "low": "#dafbe1",
    "medium": "#fff8c5",
    "high": "#ffebe9",
}


def inject_custom_css() -> None:
    """Local, inline CSS only -- no external stylesheet, font, or CDN
    request (see SECURITY.md: "built-in theming only, no external
    CSS/fonts/CDN"). Adds a light shadow to bordered containers so cards
    read as distinct surfaces instead of flat outlines, and tightens the
    default vertical rhythm between stacked sections."""
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] {
            box-shadow: 0 1px 3px rgba(11, 31, 58, 0.08);
        }
        div[data-testid="stMetric"] {
            background-color: var(--secondary-background-color);
            border-radius: 8px;
            padding: 0.75rem 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_disclaimer() -> None:
    """Full safety statement, rendered once in the sidebar so it stays on
    screen for the whole session without pushing page content down."""
    st.sidebar.warning(GLOBAL_DISCLAIMER, icon="⚠️")


def render_page_notice() -> None:
    """One-line reminder at the top of a page body."""
    st.caption(PAGE_NOTICE)


def render_connection_status(client: ClearRiskAPIClient) -> bool:
    """Quiet in the sidebar when healthy; loud in the page body only when
    broken. A working backend is the expected case and does not deserve a
    full-width alert on all five pages."""
    try:
        health = client.health()
        st.sidebar.caption(f"🟢 Backend connected · {health.get('data_mode', 'unknown')}")
        return True
    except DashboardAPIError as exc:
        st.sidebar.caption("🔴 Backend unavailable")
        st.error(
            f"Backend unavailable at {client.base_url} — start it with:\n\n`{BACKEND_START_COMMAND}`\n\n"
            f"({exc.message})",
            icon="🔌",
        )
        return False


_EMBEDDED_ENUM_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")


def humanize_embedded_enums(text: str | None) -> str:
    """Cleans up backend-generated prose (e.g. analyst_summary) that embeds a
    raw enum value mid-sentence, such as "Recommended action:
    ALLOW_WITH_MONITORING." -> "Recommended action: Allow with monitoring."
    Display-only -- this never touches the underlying case/API data, only
    what the dashboard prints. A plain-text heuristic (SNAKE_CASE token,
    2+ words), not a field-aware parser, so it is applied only to prose
    fields, not to raw identifiers like case IDs."""
    if not text:
        return text or ""
    return _EMBEDDED_ENUM_TOKEN_RE.sub(lambda m: humanize_enum(m.group(0)), text)


def humanize_enum(value: str | None) -> str:
    """Turns a backend enum string (SNAKE_CASE, e.g. "ALLOW_WITH_MONITORING",
    "REVIEW_CASE_CREATED") into a readable label ("Allow with monitoring",
    "Review case created"). Display-only -- the raw value is still what's
    sent to/compared against the API everywhere else."""
    if not value:
        return "—"
    return str(value).replace("_", " ").strip().capitalize()


STATUS_BADGE_COLORS = {
    "OPEN": ("#0550ae", "#ddf4ff"),
    "EVIDENCE_REQUESTED": ("#9a6700", "#fff8c5"),
    "EVIDENCE_SUBMITTED": ("#9a6700", "#fff8c5"),
    "UNDER_REVIEW": ("#0550ae", "#ddf4ff"),
    "RESOLVED": ("#1a7f37", "#dafbe1"),
    "ESCALATED": ("#cf222e", "#ffebe9"),
}


def status_badge(value: str | None) -> str:
    """Same visual language as intensity_badge, for case_status/recommendation
    values -- a colored pill with a human-readable label instead of a raw
    SNAKE_CASE string, HTML-escaped for the same reason intensity_badge is."""
    label = html.escape(humanize_enum(value))
    color, background = STATUS_BADGE_COLORS.get((value or "").upper(), ("#57606a", "#eaeef2"))
    return (
        f'<span style="background-color:{background}; color:{color}; '
        f'padding:2px 8px; border-radius:6px; font-weight:600; font-size:0.85em; white-space:nowrap;">{label}</span>'
    )


def render_status_badge(value: str | None) -> None:
    st.markdown(status_badge(value), unsafe_allow_html=True)


def intensity_badge(intensity: str | None) -> str:
    """Returns an HTML span with color AND text label -- never color alone.
    The label is HTML-escaped: the API types this field as a plain string,
    so nothing upstream structurally guarantees it stays within the known
    low/medium/high set."""
    label = html.escape((intensity or "unknown").strip())
    key = label.lower()
    color = INTENSITY_COLORS.get(key, "#57606a")
    background = INTENSITY_BACKGROUNDS.get(key, "#eaeef2")
    return (
        f'<span style="background-color:{background}; color:{color}; '
        f'padding:2px 8px; border-radius:6px; font-weight:600; font-size:0.85em;">{label}</span>'
    )


def render_intensity_badge(intensity: str | None) -> None:
    st.markdown(intensity_badge(intensity), unsafe_allow_html=True)


def format_timestamp(value: str | None) -> str:
    if not value:
        return "—"
    return str(value).replace("T", " ").split(".")[0]


def sla_display(case: dict) -> str:
    """One-line SLA status for a case, from the API's computed sla_* fields
    -- never computed client-side, and never a stand-in for a real
    notification (see docs/PHASE_2_REVIEW_SLA_DESIGN.md)."""
    if case.get("sla_hours") is None:
        return "N/A"
    if case.get("case_status") in ("RESOLVED", "ESCALATED"):
        return "Closed"
    if case.get("sla_breached"):
        hours_overdue = abs(case.get("hours_until_deadline") or 0)
        return f"⏰ Overdue by {hours_overdue:.1f}h"
    hours_remaining = case.get("hours_until_deadline")
    return f"{hours_remaining:.1f}h left" if hours_remaining is not None else "N/A"


def safe_get(data: dict, key: str, default="—"):
    value = data.get(key)
    return value if value not in (None, "") else default


def render_error(exc: DashboardAPIError) -> None:
    st.error(exc.message, icon="🚫")


NO_CASES_MESSAGE = "No cases exist yet. Seed demo cases first (see docs/UI_DEMO_GUIDE.md)."


def get_available_case_ids(client: ClearRiskAPIClient, limit: int = 100) -> list[str] | None:
    """Fetches case IDs for a page's case picker. Returns None (having
    already rendered the appropriate error/empty-state message) if the
    caller should stop rendering -- so every call site is just:

        available_case_ids = get_available_case_ids(client)
        if available_case_ids is None:
            return
    """
    try:
        cases_response = client.list_cases(limit=limit)
    except DashboardAPIError as exc:
        render_error(exc)
        return None

    available_case_ids = [item["case_id"] for item in cases_response.get("items", [])]
    if not available_case_ids:
        st.info(NO_CASES_MESSAGE)
        return None
    return available_case_ids
