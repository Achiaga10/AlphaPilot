from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from alphapilot.copilot.intent import CopilotIntent, glossary_concept


@dataclass(frozen=True, slots=True)
class DirectAnswer:
    answer: str
    fact_ids: tuple[str, ...]
    fact_available: bool = True


def render_direct_answer(intent: CopilotIntent, facts: dict[str, dict[str, Any]]) -> DirectAnswer:
    if intent == CopilotIntent.GLOSSARY:
        return _glossary_answer(str(_value(facts, "query.question") or ""))
    if intent == CopilotIntent.PORTFOLIO_VALUE:
        return _money_fact(
            facts,
            "portfolio.value",
            "Your current research portfolio value is {value}.",
            "Portfolio value is unavailable.",
        )
    if intent == CopilotIntent.PORTFOLIO_CASH:
        return _money_fact(
            facts,
            "portfolio.cash",
            "Your current research portfolio cash is {value}.",
            "Portfolio cash is unavailable.",
        )
    if intent == CopilotIntent.PORTFOLIO_POSITIONS:
        positions = _value(facts, "portfolio.monitoring")
        if not isinstance(positions, list):
            return DirectAnswer("Open-position count is unavailable.", (), False)
        return DirectAnswer(
            f"You currently have {len(positions)} open research positions.",
            ("portfolio.monitoring",),
        )
    if intent == CopilotIntent.PORTFOLIO_MONITORING:
        positions = _value(facts, "portfolio.monitoring")
        if not isinstance(positions, list):
            return DirectAnswer("Portfolio monitoring is unavailable.", (), False)
        requested = next(
            (
                status
                for status in ("ATTENTION", "SELL", "HOLD")
                if status.casefold() in str(_value(facts, "query.question") or "").casefold()
            ),
            None,
        )
        matched = [str(item.get("ticker")) for item in positions if item.get("status") == requested]
        if requested is None:
            answer = "Portfolio monitoring is available for each open position."
        elif matched:
            answer = f"Positions currently marked {requested}: {', '.join(matched)}."
        else:
            answer = f"No open positions are currently marked {requested}."
        return DirectAnswer(answer, ("portfolio.monitoring",))
    if intent == CopilotIntent.PAPER_ANALYTICS:
        summary = _value(facts, "paper_analytics.summary")
        if isinstance(summary, dict):
            paper_pnl = _decimal(summary.get("gross_realized_pnl")) or Decimal("0")
            win_rate = _decimal(summary.get("win_rate_percent"))
            rate = f"{win_rate}%" if win_rate is not None else "unavailable (no closed trades)"
            return DirectAnswer(
                f"Forward Paper Evidence has {summary.get('open_trade_count', 0)} open and "
                f"{summary.get('closed_trade_count', 0)} closed trades. Gross realized Paper "
                f"P&L is {_signed_money(paper_pnl)}; closed-trade win rate is {rate}. Evidence "
                f"maturity is {summary.get('evidence_maturity', 'NO_DATA')}.",
                ("paper_analytics.summary",),
            )
        paper_id = next((key for key in facts if key.startswith("paper.")), None)
        paper = _value(facts, paper_id) if paper_id else None
        if isinstance(paper, dict):
            paper_symbol = str(_value(facts, "position.ticker") or "this position")
            return DirectAnswer(
                f"The {paper_symbol} Forward Paper record is {paper.get('status')}. Planned entry "
                f"was {paper.get('reference_entry_price')}; actual fill was "
                f"{paper.get('actual_entry_price')}; entry slippage was "
                f"{paper.get('entry_slippage_percent')}%; quantity adherence was "
                f"{paper.get('quantity_adherence_percent')}%. Gross Paper P&L is "
                f"{paper.get('paper_gross_pnl')}.",
                tuple(item for item in ("position.ticker", paper_id) if item),
            )
        return DirectAnswer("Forward Paper evidence is unavailable.", (), False)
    ticker = _value(facts, "position.ticker")
    symbol = str(ticker) if ticker else "this position"
    if intent == CopilotIntent.INDICATOR_VALUE:
        return _indicator_answer(facts, symbol)
    if intent == CopilotIntent.LIVE_PRICE:
        return _live_price_answer(facts, symbol)
    if intent == CopilotIntent.LIVE_POSITION_STATUS:
        return _live_status_answer(facts, symbol)
    if intent == CopilotIntent.LIVE_STRATEGY_PROJECTION:
        return _live_projection_answer(facts, symbol)
    if intent == CopilotIntent.AVERAGE_COST:
        return _money_fact(
            facts,
            "position.average_cost",
            f"Your average cost for {symbol} is {{value}} per share.",
            f"Average cost is unavailable for {symbol}.",
        )
    if intent == CopilotIntent.QUANTITY:
        value = _value(facts, "position.quantity")
        return _fact(
            value is not None,
            f"You own {value} shares of {symbol}." if value is not None else "",
            f"Quantity is unavailable for {symbol}.",
            facts,
            "position.quantity",
        )
    if intent == CopilotIntent.ENTRY_PRICE:
        return _money_fact(
            facts,
            "position.entry_price",
            f"Your entry price for {symbol} is {{value}} per share.",
            f"Entry price is unavailable for {symbol}.",
        )
    if intent == CopilotIntent.CURRENT_PRICE:
        return _money_fact(
            facts,
            "position.latest_completed_close",
            f"The latest completed close for {symbol} is {{value}}.",
            f"A completed-session price is unavailable for {symbol}.",
        )
    if intent == CopilotIntent.MARKET_VALUE:
        return _money_fact(
            facts,
            "position.market_value",
            f"The current market value of your {symbol} position is {{value}}.",
            f"Market value is unavailable for {symbol}.",
        )
    if intent == CopilotIntent.CURRENT_PNL:
        pnl = _decimal(_value(facts, "position.unrealized_pnl"))
        pct = _decimal(_value(facts, "position.unrealized_pnl_pct"))
        if pnl is None:
            return _unavailable(f"Current unrealized P&L is unavailable for {symbol}.", facts)
        suffix = f" ({_signed(pct)}%)" if pct is not None else ""
        ids = ["position.ticker", "position.unrealized_pnl"]
        if pct is not None:
            ids.append("position.unrealized_pnl_pct")
        return DirectAnswer(
            f"Your current unrealized P&L for {symbol} is {_signed_money(pnl)}{suffix}.",
            tuple(item for item in ids if item in facts),
        )
    if intent == CopilotIntent.MONITORING_STATUS:
        status = _value(facts, "position.monitoring_status")
        reason = _value(facts, "position.monitoring_reason")
        if status is None:
            return _unavailable(f"Monitoring status is unavailable for {symbol}.", facts)
        explanation = f" ({reason})" if reason else ""
        return DirectAnswer(
            f"{symbol} is currently {status}{explanation}.",
            tuple(
                item
                for item in (
                    "position.ticker",
                    "position.monitoring_status",
                    "position.monitoring_reason",
                )
                if item in facts
            ),
        )
    if intent == CopilotIntent.TRAILING_STOP:
        return _policy_answer(facts, symbol, "guidance.trailing_stop", "trailing stop")
    if intent == CopilotIntent.PROFIT_TARGET:
        return _policy_answer(facts, symbol, "guidance.profit_target", "profit target")
    if intent == CopilotIntent.STOP_OR_EXIT:
        return _loss_control_answer(facts, symbol)
    raise ValueError(f"intent {intent} is not deterministic")


_GLOSSARY: dict[str, str] = {
    "STOP_LOSS": (
        "A stop loss is a predefined loss-control rule used to exit a trade when it moves "
        "against you. In AlphaPilot, loss control can be an approved protective stop or a "
        "strategy-defined boundary. For example, Micho uses a completed daily close below "
        "SMA150; that is not an intraday broker stop order."
    ),
    "PROTECTIVE_STOP": (
        "A protective stop is an approved numeric loss-control boundary for a position; "
        "it is distinct from a completed-close strategy exit unless explicitly documented."
    ),
    "TRAILING_STOP": (
        "A trailing stop is a loss-control boundary that moves with favorable price "
        "movement under a predefined rule; AlphaPilot does not imply one is active unless "
        "the position facts say so."
    ),
    "PROFIT_TARGET": (
        "A profit target is a predefined price or rule for taking gains; AlphaPilot does "
        "not imply one is active unless the strategy or position facts specify it."
    ),
    "AVERAGE_COST": (
        "Average cost, or cost basis per share, is the position's total acquisition cost "
        "divided by its shares under the portfolio's accounting records."
    ),
    "UNREALIZED_PNL": (
        "Unrealized P&L is the gain or loss on an open position based on its current "
        "marked value versus cost basis."
    ),
    "REALIZED_PNL": (
        "Realized P&L is the gain or loss recognized by completed sales relative to the "
        "associated cost basis."
    ),
    "EMA": (
        "EMA means exponential moving average, which weights recent prices more heavily; "
        "a suffix such as EMA50 identifies the number of trading bars."
    ),
    "SMA": (
        "SMA means simple moving average, the arithmetic mean of prices over a fixed "
        "number of trading bars; SMA150 uses 150 bars."
    ),
    "ATR": (
        "ATR means Average True Range, a volatility measure based on recent true ranges; "
        "AlphaPilot's risk research uses deterministic completed-bar inputs."
    ),
    "HOLD": (
        "HOLD means the current strategy and monitoring rules do not call for a SELL "
        "action on the latest completed evidence."
    ),
    "ATTENTION": (
        "ATTENTION means a position warrants review under AlphaPilot's monitoring rules; "
        "it is not automatically a SELL instruction."
    ),
    "SELL": (
        "SELL means the strategy's deterministic exit condition is satisfied; it is a "
        "research decision, not a broker execution confirmation."
    ),
    "STRATEGY_EXIT_REFERENCE": (
        "A strategy exit reference is the indicator or price level used to evaluate a "
        "strategy exit on its documented timing semantics; it is not automatically a "
        "broker stop order."
    ),
    "LOSS_CONTROL_BOUNDARY": (
        "A loss-control boundary is an approved deterministic numeric rule that limits "
        "adverse exposure; its trigger timing must be stated explicitly."
    ),
}


def _glossary_answer(question: str) -> DirectAnswer:
    concept = glossary_concept(question)
    answer = _GLOSSARY.get(concept or "")
    if answer is None:
        return DirectAnswer("That AlphaPilot term is not available in the glossary.", (), False)
    return DirectAnswer(answer, ())


def render_navigation_answer(question: str, facts: dict[str, dict[str, Any]]) -> DirectAnswer:
    normalized = question.casefold()
    routes = (
        (("sync", "market data", "data management"), "navigation.data"),
        (("generate", "portfolio"), "navigation.portfolio_plan"),
        (("evaluate", "one stock"), "navigation.evaluate"),
        (("external position",), "navigation.portfolio_plan"),
        (("paper", "alpaca"), "navigation.position_intelligence"),
        (("attention",), "navigation.position_intelligence"),
    )
    fact_id = next(
        (identifier for words, identifier in routes if any(word in normalized for word in words)),
        "navigation.dashboard",
    )
    value = _value(facts, fact_id)
    if not isinstance(value, dict):
        return DirectAnswer("AlphaPilot product guidance is unavailable.", (), False)
    page = value.get("page", "the relevant page")
    route = value.get("route", "")
    purpose = value.get("purpose", "")
    return DirectAnswer(
        f"Open {page} from the left sidebar ({route}). {purpose}",
        (fact_id,),
    )


def _loss_control_answer(facts: dict[str, dict[str, Any]], symbol: str) -> DirectAnswer:
    loss = _value(facts, "guidance.loss_control")
    if isinstance(loss, dict) and loss.get("active") and loss.get("boundary") is not None:
        boundary = _money(loss["boundary"])
        policy = loss.get("policy", "loss-control policy")
        trigger = loss.get("trigger", "the documented trigger")
        broker = (
            "This is not an intraday broker stop order."
            if not loss.get("broker_stop_order")
            else ""
        )
        return DirectAnswer(
            f"Your current {symbol} loss-control boundary is {policy} at {boundary}. "
            f"{trigger} triggers SELL. {broker}".strip(),
            tuple(item for item in ("position.ticker", "guidance.loss_control") if item in facts),
        )
    references = [key for key in facts if key.startswith("guidance.reference.")]
    if references:
        reference = _value(facts, references[0])
        if isinstance(reference, dict) and reference.get("value") is not None:
            raw_type = reference.get("reference_type", "strategy exit")
            reference_type = getattr(raw_type, "value", str(raw_type))
            label = (
                "EMA50"
                if "EMA50" in reference_type
                else "EMA20"
                if "EMA20" in reference_type
                else "SMA150"
                if "SMA150" in reference_type
                else "strategy exit"
            )
            value = _money(reference["value"])
            return DirectAnswer(
                f"AlphaPilot has no approved protective loss-control policy for {symbol}. "
                f"The current hard {label} strategy-exit reference is {value}; "
                "it uses completed-close semantics and is not a broker stop order.",
                tuple(
                    item
                    for item in ("position.ticker", "guidance.loss_control", references[0])
                    if item in facts
                ),
            )
    return _unavailable(f"Loss-control guidance is unavailable for {symbol}.", facts)


def _policy_answer(
    facts: dict[str, dict[str, Any]], symbol: str, fact_id: str, label: str
) -> DirectAnswer:
    value = _value(facts, fact_id)
    if value is None or value == "UNAVAILABLE":
        return _unavailable(f"{label.title()} information is unavailable for {symbol}.", facts)
    if value == "NONE":
        return DirectAnswer(
            f"No. {symbol} does not currently have an active {label} policy.",
            tuple(item for item in ("position.ticker", fact_id) if item in facts),
        )
    return DirectAnswer(
        f"The active {label} policy for {symbol} is {value}.",
        tuple(item for item in ("position.ticker", fact_id) if item in facts),
    )


def _money_fact(
    facts: dict[str, dict[str, Any]], fact_id: str, template: str, unavailable: str
) -> DirectAnswer:
    value = _decimal(_value(facts, fact_id))
    if value is None:
        return _unavailable(unavailable, facts)
    return DirectAnswer(
        template.format(value=_money(value)),
        tuple(item for item in ("position.ticker", fact_id) if item in facts),
    )


def _fact(
    available: bool,
    answer: str,
    unavailable: str,
    facts: dict[str, dict[str, Any]],
    fact_id: str,
) -> DirectAnswer:
    if not available:
        return _unavailable(unavailable, facts)
    return DirectAnswer(
        answer, tuple(item for item in ("position.ticker", fact_id) if item in facts)
    )


def _unavailable(answer: str, facts: dict[str, dict[str, Any]]) -> DirectAnswer:
    return DirectAnswer(answer, ("position.ticker",) if "position.ticker" in facts else (), False)


def _value(facts: dict[str, dict[str, Any]], fact_id: str) -> Any:
    fact = facts.get(fact_id)
    return fact.get("value") if fact else None


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _money(value: Any) -> str:
    number = _decimal(value)
    return f"${number:,.2f}" if number is not None else "unavailable"


def _indicator_answer(facts: dict[str, dict[str, Any]], symbol: str) -> DirectAnswer:
    question = str(_value(facts, "query.question") or "").casefold()
    live = any(phrase in question for phrase in ("right now", "live", "current session"))
    if "ema" in question and "20" in question:
        name = "EMA20"
        field = "live.provisional_ema20" if live else "live.completed_ema20"
    elif "ema" in question and "50" in question:
        name = "EMA50"
        field = "live.provisional_ema50" if live else "live.completed_ema50"
    elif ("sma" in question or "moving average" in question) and "150" in question:
        name = "SMA150"
        field = "live.provisional_sma150" if live else "live.completed_sma150"
    else:
        name = "ATR14"
        field = "live.provisional_atr14" if live else "live.completed_atr14"
    value = _decimal(_value(facts, field))
    if value is None:
        return _unavailable(
            f"{name} is unavailable for {symbol}; refresh live market data first.", facts
        )
    qualifier = "provisional live" if live else "latest completed-session"
    return DirectAnswer(
        f"{symbol}'s {qualifier} {name} is {_money(value)}.",
        tuple(item for item in ("position.ticker", field) if item in facts),
    )


def _live_price_answer(facts: dict[str, dict[str, Any]], symbol: str) -> DirectAnswer:
    question = str(_value(facts, "query.question") or "").casefold()
    field = "live.high" if "high" in question else "live.low" if "low" in question else "live.price"
    label = (
        "current-session high"
        if field.endswith("high")
        else "current-session low"
        if field.endswith("low")
        else "live price"
    )
    value = _decimal(_value(facts, field))
    timestamp = _value(facts, "live.timestamp")
    freshness = _value(facts, "live.freshness")
    if value is None:
        return _unavailable(
            f"{label.title()} is unavailable for {symbol}; refresh live market data first.", facts
        )
    return DirectAnswer(
        f"{symbol}'s {label} is {_money(value)} as of {timestamp} ({freshness}).",
        tuple(
            item
            for item in ("position.ticker", field, "live.timestamp", "live.freshness")
            if item in facts
        ),
    )


def _live_status_answer(facts: dict[str, dict[str, Any]], symbol: str) -> DirectAnswer:
    question = str(_value(facts, "query.question") or "").casefold()
    price = _decimal(_value(facts, "live.price"))
    if "ema" in question and "20" in question:
        reference_field, distance_field, pct_field, label = (
            "live.provisional_ema20",
            "live.distance_to_ema20_dollars",
            "live.distance_to_ema20_pct",
            "provisional EMA20",
        )
    elif "ema" in question and "50" in question:
        reference_field, distance_field, pct_field, label = (
            "live.provisional_ema50",
            "live.distance_to_ema50_dollars",
            "live.distance_to_ema50_pct",
            "provisional EMA50",
        )
    else:
        status = _value(facts, "live.live_status")
        reason = _value(facts, "live.live_reason")
        if status is None:
            return _unavailable(f"Live status is unavailable for {symbol}; refresh first.", facts)
        return DirectAnswer(
            f"{symbol} is in {status}: {reason}. This is live monitoring, "
            "not a confirmed completed-session SELL.",
            tuple(
                item
                for item in ("position.ticker", "live.live_status", "live.live_reason")
                if item in facts
            ),
        )
    reference = _decimal(_value(facts, reference_field))
    distance = _decimal(_value(facts, distance_field))
    pct = _decimal(_value(facts, pct_field))
    if price is None or reference is None:
        return _unavailable(
            f"Live indicator status is unavailable for {symbol}; refresh first.", facts
        )
    relation = "below" if price < reference else "above or equal to"
    distance_text = (
        f" by {_money(abs(distance))} ({abs(pct):.2f}%)"
        if distance is not None and pct is not None
        else ""
    )
    return DirectAnswer(
        f"{symbol} is trading at {_money(price)}, {relation} its {label} of "
        f"{_money(reference)}{distance_text}. The frozen strategy has not confirmed "
        "a SELL from this incomplete session.",
        tuple(
            item
            for item in (
                "position.ticker",
                "live.price",
                reference_field,
                distance_field,
                pct_field,
            )
            if item in facts
        ),
    )


def _live_projection_answer(facts: dict[str, dict[str, Any]], symbol: str) -> DirectAnswer:
    signal = _value(facts, "live.projected_signal")
    reason = _value(facts, "live.projected_reason")
    confirmed = bool(_value(facts, "live.confirmed_sell_required"))
    if signal is None:
        return _unavailable(
            f"A live strategy projection is unavailable for {symbol}; refresh first.", facts
        )
    return DirectAnswer(
        f"If the current session closed now, {symbol}'s frozen strategy would project "
        f"{signal} ({reason}). This projection is provisional and non-official. "
        f"Confirmed completed-session SELL: {'YES' if confirmed else 'NO'}.",
        tuple(
            item
            for item in (
                "position.ticker",
                "live.projected_signal",
                "live.projected_reason",
                "live.confirmed_sell_required",
                "live.projection_is_official",
            )
            if item in facts
        ),
    )


def _signed(value: Decimal) -> str:
    return f"{value:+,.2f}"


def _signed_money(value: Decimal) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"
