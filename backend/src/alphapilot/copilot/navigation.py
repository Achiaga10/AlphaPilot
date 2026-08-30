from __future__ import annotations

from typing import Any

PRODUCT_NAVIGATION: dict[str, dict[str, Any]] = {
    "navigation.dashboard": {
        "route": "/",
        "page": "Dashboard",
        "purpose": "Research portfolio summary, cash, risk, and latest plan overview.",
    },
    "navigation.portfolio_plan": {
        "route": "/portfolio",
        "page": "Portfolio Plan",
        "purpose": (
            "Generate a backend plan, review decisions, manage the research portfolio, "
            "open Position Intelligence, and record manual paper validation."
        ),
    },
    "navigation.evaluate": {
        "route": "/evaluate",
        "page": "Evaluate Stock",
        "purpose": "Evaluate one ticker with the selected backend strategy profile.",
    },
    "navigation.settings": {
        "route": "/settings",
        "page": "Research Settings",
        "purpose": "Review frozen strategy and risk configuration.",
    },
    "navigation.data": {
        "route": "/admin/data",
        "page": "Data Management",
        "purpose": (
            "Run manual market-data synchronization and inspect scheduler and data freshness "
            "when research-admin tools are enabled."
        ),
    },
    "navigation.position_intelligence": {
        "route": "/portfolio",
        "page": "Position Intelligence",
        "purpose": (
            "Use Why this position? on a holding to inspect monitoring, exit guidance, and "
            "Paper Validation, or ask about the ticker in Ask AI."
        ),
    },
    "navigation.ask_ai": {
        "route": "all pages",
        "page": "Ask AI",
        "purpose": (
            "Open the bottom-right read-only assistant. AlphaPilot resolves product, portfolio, "
            "and explicitly named held-position questions internally."
        ),
    },
}


def navigation_facts() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "source": "product_navigation",
            "field": "navigation",
            "label": value["page"],
            "value": value,
        }
        for key, value in PRODUCT_NAVIGATION.items()
    }
