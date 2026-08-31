from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from alphapilot.copilot.context import CopilotContext
from alphapilot.copilot.intent import CopilotIntent, classify_question
from alphapilot.copilot.orchestrator import CopilotOrchestrator
from alphapilot.core.config import settings


class FailingProvider:
    name = "must-not-run"
    model = "must-not-run"

    async def available(self) -> bool:
        raise AssertionError("provider availability must not be checked")

    async def generate(self, **kwargs):
        raise AssertionError("deterministic facts must not call an LLM")


def _context() -> CopilotContext:
    values = {
        "position.ticker": "APA",
        "live.price": Decimal("39.80"),
        "live.high": Decimal("41.20"),
        "live.low": Decimal("39.50"),
        "live.timestamp": datetime.fromisoformat("2026-08-31T14:43:21+00:00"),
        "live.freshness": "LIVE",
        "live.completed_ema20": Decimal("41.00"),
        "live.provisional_ema20": Decimal("40.90"),
        "live.completed_ema50": Decimal("40.30"),
        "live.provisional_ema50": Decimal("40.20"),
        "live.completed_sma150": Decimal("38.50"),
        "live.provisional_sma150": Decimal("38.51"),
        "live.completed_atr14": Decimal("1.25"),
        "live.provisional_atr14": Decimal("1.30"),
        "live.distance_to_ema20_dollars": Decimal("-1.10"),
        "live.distance_to_ema20_pct": Decimal("-2.689"),
        "live.distance_to_ema50_dollars": Decimal("-0.40"),
        "live.distance_to_ema50_pct": Decimal("-0.995"),
        "live.live_status": "CRITICAL_ATTENTION",
        "live.live_reason": "LIVE_PRICE_BELOW_PROVISIONAL_EMA50",
        "live.projected_signal": "SELL",
        "live.projected_reason": "EMA50_BREAKDOWN",
        "live.projection_is_official": False,
        "live.confirmed_sell_required": False,
    }
    return CopilotContext(
        "POSITION",
        uuid4(),
        uuid4(),
        "APA",
        date(2026, 8, 28),
        {
            key: {
                "source": "test",
                "field": key,
                "label": key,
                "value": value,
            }
            for key, value in values.items()
        },
        (),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "intent", "expected"),
    [
        ("What is APA EMA20?", CopilotIntent.INDICATOR_VALUE, "$41.00"),
        ("What is APA EMA20 right now?", CopilotIntent.LIVE_POSITION_STATUS, "$40.90"),
        ("What is APA EMA50?", CopilotIntent.INDICATOR_VALUE, "$40.30"),
        ("What is APA SMA150?", CopilotIntent.INDICATOR_VALUE, "$38.50"),
        ("What is ATR14 for APA?", CopilotIntent.INDICATOR_VALUE, "$1.25"),
        ("What is APA trading at right now?", CopilotIntent.LIVE_PRICE, "$39.80"),
        ("What is APA current price?", CopilotIntent.LIVE_PRICE, "$39.80"),
        ("What is today's low for APA?", CopilotIntent.LIVE_PRICE, "$39.50"),
        ("Is APA below EMA20 right now?", CopilotIntent.LIVE_POSITION_STATUS, "below"),
        (
            "What happens if today's session closed at this price?",
            CopilotIntent.LIVE_STRATEGY_PROJECTION,
            "provisional and non-official",
        ),
        (
            "Should I sell APA now?",
            CopilotIntent.LIVE_STRATEGY_PROJECTION,
            "provisional and non-official",
        ),
    ],
)
async def test_live_exact_facts_never_call_llm(question, intent, expected) -> None:
    assert classify_question(question) == intent
    answer = await CopilotOrchestrator(None, FailingProvider())._answer(  # type: ignore[arg-type]
        _context(), question, intent=intent
    )
    assert expected in answer.answer
    assert answer.provider == "alphapilot"


@pytest.mark.asyncio
async def test_open_ended_explanation_is_typed_unavailable_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AI_GENERATIVE_EXPLANATIONS_ENABLED", False)
    answer = await CopilotOrchestrator(None, FailingProvider())._answer(  # type: ignore[arg-type]
        _context(), "Explain the broader market context", intent=CopilotIntent.EXPLANATION
    )
    assert answer.result_status == "GENERATIVE_EXPLANATION_UNAVAILABLE"
    assert "deterministic" in answer.answer
