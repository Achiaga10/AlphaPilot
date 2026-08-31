from __future__ import annotations

import re
from enum import StrEnum


class CopilotIntent(StrEnum):
    GLOSSARY = "GLOSSARY"
    DAILY_BRIEF = "DAILY_BRIEF"
    AVERAGE_COST = "AVERAGE_COST"
    QUANTITY = "QUANTITY"
    ENTRY_PRICE = "ENTRY_PRICE"
    CURRENT_PNL = "CURRENT_PNL"
    CURRENT_PRICE = "CURRENT_PRICE"
    MARKET_VALUE = "MARKET_VALUE"
    MONITORING_STATUS = "MONITORING_STATUS"
    STOP_OR_EXIT = "STOP_OR_EXIT"
    TRAILING_STOP = "TRAILING_STOP"
    PROFIT_TARGET = "PROFIT_TARGET"
    PORTFOLIO_VALUE = "PORTFOLIO_VALUE"
    PORTFOLIO_CASH = "PORTFOLIO_CASH"
    PORTFOLIO_POSITIONS = "PORTFOLIO_POSITIONS"
    PORTFOLIO_MONITORING = "PORTFOLIO_MONITORING"
    PAPER_VALIDATION = "PAPER_VALIDATION"
    NAVIGATION = "NAVIGATION"
    GENERAL = "GENERAL"
    EXPLANATION = "EXPLANATION"


def classify_question(question: str, *, general_scope: bool = False) -> CopilotIntent:
    normalized = question.casefold()
    if glossary_concept(question) is not None:
        return CopilotIntent.GLOSSARY
    if any(
        phrase in normalized
        for phrase in (
            "requires action today",
            "need action today",
            "look at today",
            "should i sell",
            "new opportunities",
            "opportunity actionable",
            "candidate actionable",
        )
    ):
        return CopilotIntent.DAILY_BRIEF
    if general_scope:
        return CopilotIntent.NAVIGATION
    if any(
        phrase in normalized
        for phrase in (
            "where do i",
            "how do i",
            "where can i",
            "what does attention mean",
            "data management",
            "sync market data",
        )
    ):
        return CopilotIntent.NAVIGATION
    if "portfolio value" in normalized or "total equity" in normalized:
        return CopilotIntent.PORTFOLIO_VALUE
    if "cash" in normalized and "position" not in normalized:
        return CopilotIntent.PORTFOLIO_CASH
    if any(phrase in normalized for phrase in ("how many positions", "positions do i own")):
        return CopilotIntent.PORTFOLIO_POSITIONS
    if "positions" in normalized and any(
        word in normalized for word in ("attention", "sell", "hold", "monitoring")
    ):
        return CopilotIntent.PORTFOLIO_MONITORING
    if any(word in normalized for word in ("why", "explain", "difference", "compare")):
        return CopilotIntent.EXPLANATION
    rules = (
        (
            CopilotIntent.AVERAGE_COST,
            (
                "average cost",
                "avg cost",
                "avarge cost",
                "cost basis per share",
                "\u05d4\u05e2\u05dc\u05d5\u05ea \u05d4\u05de\u05de\u05d5\u05e6\u05e2\u05ea",
                "\u05e2\u05dc\u05d5\u05ea \u05de\u05de\u05d5\u05e6\u05e2\u05ea",
                "\u05de\u05d7\u05d9\u05e8 \u05de\u05de\u05d5\u05e6\u05e2",
            ),
        ),
        (
            CopilotIntent.QUANTITY,
            ("quantity", "how many shares", "shares do i", "כמות", "כמה מניות"),
        ),
        (CopilotIntent.ENTRY_PRICE, ("entry price", "entry cost", "מחיר כניסה")),
        (CopilotIntent.CURRENT_PRICE, ("current price", "latest close", "מחיר נוכחי")),
        (CopilotIntent.MARKET_VALUE, ("market value", "position value", "שווי שוק")),
        (CopilotIntent.TRAILING_STOP, ("trailing stop", "סטופ נגרר")),
        (CopilotIntent.PROFIT_TARGET, ("profit target", "take profit", "יעד רווח")),
        (CopilotIntent.PAPER_VALIDATION, ("paper", "alpaca")),
        (
            CopilotIntent.STOP_OR_EXIT,
            ("stop", "sell", "exit", "loss control", "הגנה", "סטופ", "מכירה", "יציאה"),
        ),
        (CopilotIntent.CURRENT_PNL, ("p&l", "pnl", "profit", "loss", "רווח", "הפסד")),
        (CopilotIntent.MONITORING_STATUS, ("hold", "attention", "monitoring", "held", "מוחזק")),
    )
    for intent, needles in rules:
        if any(needle in normalized for needle in needles):
            return intent
    return CopilotIntent.GENERAL


_GLOSSARY_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("LOSS_CONTROL_BOUNDARY", ("loss-control boundary", "loss control boundary")),
    ("STRATEGY_EXIT_REFERENCE", ("strategy exit reference", "exit reference")),
    ("UNREALIZED_PNL", ("unrealized p&l", "unrealized pnl")),
    ("REALIZED_PNL", ("realized p&l", "realized pnl")),
    ("PROTECTIVE_STOP", ("protective stop",)),
    ("TRAILING_STOP", ("trailing stop",)),
    ("PROFIT_TARGET", ("profit target", "take profit")),
    ("AVERAGE_COST", ("average cost", "cost basis")),
    ("STOP_LOSS", ("stop loss", "stop-loss", "stop")),
    ("ATTENTION", ("attention",)),
    ("HOLD", ("hold",)),
    ("SELL", ("sell",)),
    ("EMA", ("ema",)),
    ("SMA", ("sma",)),
    ("ATR", ("atr",)),
)


def glossary_concept(question: str) -> str | None:
    """Return an AlphaPilot term only when the wording asks for its definition."""
    normalized = question.casefold().strip()
    if re.search(r"\b(my|our)\b", normalized):
        return None
    definition_wording = (
        re.search(r"\bwhat\s+(?:is|are)\b", normalized)
        or re.search(r"\bwhat\s+does\b.+\bmean\b", normalized)
        or re.search(r"\bdo\s+you\s+know\s+what\s+(?:is|a|an)\b", normalized)
        or re.search(r"\b(?:define|meaning of)\b", normalized)
    )
    if not definition_wording:
        return None
    for concept, aliases in _GLOSSARY_ALIASES:
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\d*\b", normalized):
                return concept
    return None


FACT_PREFIXES: dict[CopilotIntent, tuple[str, ...]] = {
    CopilotIntent.GLOSSARY: ("query.question",),
    CopilotIntent.AVERAGE_COST: ("position.ticker", "position.average_cost"),
    CopilotIntent.QUANTITY: ("position.ticker", "position.quantity"),
    CopilotIntent.ENTRY_PRICE: ("position.ticker", "position.entry_price"),
    CopilotIntent.CURRENT_PNL: (
        "position.ticker",
        "position.unrealized_pnl",
        "position.unrealized_pnl_pct",
        "guidance.completed_session",
    ),
    CopilotIntent.CURRENT_PRICE: (
        "position.ticker",
        "position.latest_completed_close",
        "guidance.completed_session",
    ),
    CopilotIntent.MARKET_VALUE: ("position.ticker", "position.market_value"),
    CopilotIntent.MONITORING_STATUS: (
        "position.ticker",
        "position.monitoring_status",
        "position.monitoring_reason",
    ),
    CopilotIntent.STOP_OR_EXIT: ("position.ticker", "guidance."),
    CopilotIntent.TRAILING_STOP: ("position.ticker", "guidance.trailing_stop"),
    CopilotIntent.PROFIT_TARGET: ("position.ticker", "guidance.profit_target"),
    CopilotIntent.PORTFOLIO_VALUE: ("portfolio.value",),
    CopilotIntent.PORTFOLIO_CASH: ("portfolio.cash",),
    CopilotIntent.PORTFOLIO_POSITIONS: ("portfolio.monitoring",),
    CopilotIntent.PORTFOLIO_MONITORING: ("portfolio.monitoring", "query.question"),
    CopilotIntent.PAPER_VALIDATION: ("position.ticker", "paper."),
    CopilotIntent.GENERAL: (
        "position.ticker",
        "position.profile",
        "position.monitoring_status",
        "position.monitoring_reason",
        "guidance.loss_control",
        "guidance.protective_stop",
    ),
    CopilotIntent.EXPLANATION: (
        "position.ticker",
        "position.profile",
        "position.monitoring_status",
        "position.monitoring_reason",
        "guidance.",
        "paper.",
    ),
}


DETERMINISTIC_INTENTS = frozenset(
    {
        CopilotIntent.GLOSSARY,
        CopilotIntent.AVERAGE_COST,
        CopilotIntent.QUANTITY,
        CopilotIntent.ENTRY_PRICE,
        CopilotIntent.CURRENT_PNL,
        CopilotIntent.CURRENT_PRICE,
        CopilotIntent.MARKET_VALUE,
        CopilotIntent.MONITORING_STATUS,
        CopilotIntent.STOP_OR_EXIT,
        CopilotIntent.TRAILING_STOP,
        CopilotIntent.PROFIT_TARGET,
        CopilotIntent.PORTFOLIO_VALUE,
        CopilotIntent.PORTFOLIO_CASH,
        CopilotIntent.PORTFOLIO_POSITIONS,
        CopilotIntent.PORTFOLIO_MONITORING,
    }
)


POSITION_INTENTS = frozenset(
    {
        CopilotIntent.AVERAGE_COST,
        CopilotIntent.QUANTITY,
        CopilotIntent.ENTRY_PRICE,
        CopilotIntent.CURRENT_PNL,
        CopilotIntent.CURRENT_PRICE,
        CopilotIntent.MARKET_VALUE,
        CopilotIntent.MONITORING_STATUS,
        CopilotIntent.STOP_OR_EXIT,
        CopilotIntent.TRAILING_STOP,
        CopilotIntent.PROFIT_TARGET,
        CopilotIntent.PAPER_VALIDATION,
        CopilotIntent.EXPLANATION,
    }
)

PORTFOLIO_INTENTS = frozenset(
    {
        CopilotIntent.PORTFOLIO_VALUE,
        CopilotIntent.PORTFOLIO_CASH,
        CopilotIntent.PORTFOLIO_POSITIONS,
        CopilotIntent.PORTFOLIO_MONITORING,
    }
)


def select_relevant_facts(
    facts: dict[str, dict[str, object]], intent: CopilotIntent
) -> dict[str, dict[str, object]]:
    prefixes = FACT_PREFIXES.get(intent)
    if prefixes is None:
        return facts
    return {
        key: value
        for key, value in facts.items()
        if any(key == prefix or key.startswith(prefix) for prefix in prefixes)
    }
