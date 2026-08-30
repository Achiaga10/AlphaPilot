from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.copilot.intent import (
    PORTFOLIO_INTENTS,
    POSITION_INTENTS,
    CopilotIntent,
    classify_question,
)
from alphapilot.database.models.company import Company
from alphapilot.database.models.research_portfolio import ResearchPosition
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.research_portfolio import ResearchPortfolioRepository


class CopilotResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    ENTITY_ESTABLISHED = "ENTITY_ESTABLISHED"
    MULTIPLE_TICKERS = "MULTIPLE_TICKERS"
    UNKNOWN_TICKER = "UNKNOWN_TICKER"
    POSITION_NOT_HELD = "POSITION_NOT_HELD"


@dataclass(frozen=True, slots=True)
class ResolvedCopilotQuery:
    intent: CopilotIntent
    scope: str
    status: CopilotResolutionStatus
    ticker: str | None = None
    position_id: UUID | None = None
    answer: str | None = None


class CopilotQueryResolver:
    """Resolve read scope and portfolio entity without delegating identity to an LLM."""

    def __init__(self, session: AsyncSession) -> None:
        self.companies = CompanyRepository(session)
        self.portfolios = ResearchPortfolioRepository(session)

    _RESERVED_SYMBOLS = {"AI", "ATR", "BUY", "EMA", "HOLD", "SELL", "SMA", "STOP"}

    async def resolve(
        self,
        portfolio_id: UUID,
        question: str,
        *,
        active_ticker: str | None = None,
        pending_intent: str | None = None,
    ) -> ResolvedCopilotQuery:
        companies = await self.companies.list()
        positions = await self.portfolios.list_open_positions(portfolio_id)
        company_by_ticker = {item.ticker.upper(): item for item in companies}
        held_by_ticker = {item.ticker_at_entry.upper(): item for item in positions}
        explicit = self._explicit_tickers(question, companies, set(held_by_ticker))

        if len(explicit) > 1:
            return ResolvedCopilotQuery(
                CopilotIntent.GENERAL,
                "GENERAL",
                CopilotResolutionStatus.MULTIPLE_TICKERS,
                answer=(
                    "I can currently answer one position at a time. "
                    "Which ticker would you like to start with?"
                ),
            )

        intent = classify_question(question)
        if pending_intent and explicit and self._is_ticker_only(question, explicit[0]):
            try:
                candidate = CopilotIntent(pending_intent)
            except ValueError:
                candidate = intent
            if candidate in POSITION_INTENTS:
                intent = candidate

        if intent in {CopilotIntent.GLOSSARY, CopilotIntent.NAVIGATION}:
            return ResolvedCopilotQuery(intent, "GENERAL", CopilotResolutionStatus.RESOLVED)
        if intent in PORTFOLIO_INTENTS:
            return ResolvedCopilotQuery(intent, "PORTFOLIO", CopilotResolutionStatus.RESOLVED)

        ticker = explicit[0] if explicit else None
        if intent not in POSITION_INTENTS:
            if ticker:
                return await self._resolve_entity(ticker, company_by_ticker, held_by_ticker, intent)
            unknown = self._unknown_symbol(question, company_by_ticker)
            if unknown:
                return ResolvedCopilotQuery(
                    intent,
                    "GENERAL",
                    CopilotResolutionStatus.UNKNOWN_TICKER,
                    ticker=unknown,
                    answer=f"I couldn't identify {unknown} as a ticker in AlphaPilot.",
                )
            return ResolvedCopilotQuery(intent, "GENERAL", CopilotResolutionStatus.RESOLVED)

        ticker = ticker or (active_ticker.upper() if active_ticker else None)
        if ticker is None:
            unknown = self._unknown_symbol(question, company_by_ticker)
            if unknown:
                return ResolvedCopilotQuery(
                    intent,
                    "POSITION",
                    CopilotResolutionStatus.UNKNOWN_TICKER,
                    ticker=unknown,
                    answer=f"I couldn't identify {unknown} as a ticker in AlphaPilot.",
                )
            return ResolvedCopilotQuery(
                intent,
                "POSITION",
                CopilotResolutionStatus.CLARIFICATION_REQUIRED,
                answer="Which ticker do you mean?",
            )
        return await self._resolve_position(ticker, company_by_ticker, held_by_ticker, intent)

    async def _resolve_entity(
        self,
        ticker: str,
        companies: Mapping[str, Company],
        positions: Mapping[str, ResearchPosition],
        intent: CopilotIntent,
    ) -> ResolvedCopilotQuery:
        if ticker not in companies:
            return ResolvedCopilotQuery(
                intent,
                "GENERAL",
                CopilotResolutionStatus.UNKNOWN_TICKER,
                ticker=ticker,
                answer=f"I couldn't identify {ticker} as a ticker in AlphaPilot.",
            )
        if ticker not in positions:
            return ResolvedCopilotQuery(
                intent,
                "POSITION",
                CopilotResolutionStatus.POSITION_NOT_HELD,
                ticker=ticker,
                answer=(
                    f"You do not currently have an open {ticker} position "
                    "in this research portfolio."
                ),
            )
        position = positions[ticker]
        return ResolvedCopilotQuery(
            intent,
            "POSITION",
            CopilotResolutionStatus.ENTITY_ESTABLISHED,
            ticker,
            position.id,
            f"I'll use {ticker} for your next position question.",
        )

    async def _resolve_position(
        self,
        ticker: str,
        companies: Mapping[str, Company],
        positions: Mapping[str, ResearchPosition],
        intent: CopilotIntent,
    ) -> ResolvedCopilotQuery:
        if ticker not in companies:
            return ResolvedCopilotQuery(
                intent,
                "POSITION",
                CopilotResolutionStatus.UNKNOWN_TICKER,
                ticker=ticker,
                answer=f"I couldn't identify {ticker} as a ticker in AlphaPilot.",
            )
        position = positions.get(ticker)
        if position is None:
            return ResolvedCopilotQuery(
                intent,
                "POSITION",
                CopilotResolutionStatus.POSITION_NOT_HELD,
                ticker=ticker,
                answer=(
                    f"You do not currently have an open {ticker} position "
                    "in this research portfolio."
                ),
            )
        return ResolvedCopilotQuery(
            intent,
            "POSITION",
            CopilotResolutionStatus.RESOLVED,
            ticker,
            position.id,
        )

    @staticmethod
    def _explicit_tickers(
        question: str, companies: Sequence[Company], held_tickers: set[str]
    ) -> list[str]:
        matches: list[str] = []
        common_words = {"all", "are", "can", "for", "has", "open", "own", "the"}
        primary_names: dict[str, list[str]] = {}
        for company in companies:
            primary = company.name.split()[0].casefold().strip(".,")
            if len(primary) >= 4:
                primary_names.setdefault(primary, []).append(company.ticker.upper())
        for company in companies:
            ticker = company.ticker.upper()
            exact_symbol = re.search(
                rf"(?<![A-Za-z0-9]){re.escape(ticker)}(?![A-Za-z0-9])", question
            )
            held_lowercase_symbol = (
                ticker in held_tickers
                and len(ticker) >= 3
                and ticker.casefold() not in common_words
                and re.search(
                    rf"(?<![A-Za-z0-9]){re.escape(ticker)}(?![A-Za-z0-9])",
                    question,
                    re.I,
                )
            )
            if ticker not in CopilotQueryResolver._RESERVED_SYMBOLS and (
                exact_symbol or held_lowercase_symbol
            ):
                matches.append(ticker)
                continue
            name = company.name.strip()
            if len(name) >= 4 and re.search(rf"\b{re.escape(name)}\b", question, re.I):
                matches.append(ticker)
                continue
            primary = name.split()[0].casefold().strip(".,")
            if len(primary_names.get(primary, ())) == 1 and re.search(
                rf"\b{re.escape(primary)}\b", question, re.I
            ):
                matches.append(ticker)
        return sorted(set(matches))

    @staticmethod
    def _is_ticker_only(question: str, ticker: str) -> bool:
        return question.strip().strip("?.!, ").casefold() == ticker.casefold()

    @staticmethod
    def _unknown_symbol(question: str, known: Mapping[str, object]) -> str | None:
        reserved = CopilotQueryResolver._RESERVED_SYMBOLS | {"P&L"}
        candidates = re.findall(r"(?<![A-Za-z0-9])[A-Z][A-Z0-9.]{1,5}(?![A-Za-z0-9])", question)
        return next(
            (item for item in reversed(candidates) if item not in reserved and item not in known),
            None,
        )
