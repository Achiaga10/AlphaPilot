from __future__ import annotations

import re
from typing import Any, cast

import httpx

from alphapilot.core.config import settings
from alphapilot.market.dto import IndexConstituentData
from alphapilot.market.providers.base import (
    IndexConstituentDetailsProvider,
    IndexConstituentsProvider,
)


class WikipediaIndexConstituentsProvider(
    IndexConstituentsProvider,
    IndexConstituentDetailsProvider,
):
    """S&P 500 constituents provider using the MediaWiki API."""

    API_URL = "https://en.wikipedia.org/w/api.php"

    SP500_INDEX_SYMBOL = "^GSPC"
    SP500_PAGE = "List of S&P 500 companies"

    SYMBOL_PATTERN = re.compile(
        r"\{\{(?:Nyse|Nasdaq)Symbol\|([^}|]+)",
        re.IGNORECASE,
    )

    async def get_index_constituents(
        self,
        index_symbol: str,
    ) -> list[str]:
        wikitext = await self._fetch_wikitext(
            index_symbol,
        )

        table = self._extract_constituents_table(
            wikitext,
        )

        tickers = sorted(
            {
                ticker.strip().upper()
                for ticker in self.SYMBOL_PATTERN.findall(table)
                if ticker.strip()
            }
        )

        if not tickers:
            raise RuntimeError(f"Wikipedia returned no constituents for {index_symbol}")

        return tickers

    async def get_index_constituent_details(
        self,
        index_symbol: str,
    ) -> list[IndexConstituentData]:
        wikitext = await self._fetch_wikitext(
            index_symbol,
        )

        table = self._extract_constituents_table(
            wikitext,
        )

        return self._parse_constituent_details(
            table,
        )

    async def _fetch_wikitext(
        self,
        index_symbol: str,
    ) -> str:
        normalized_symbol = index_symbol.strip().upper()

        if normalized_symbol != self.SP500_INDEX_SYMBOL:
            raise ValueError(f"Unsupported index symbol: {index_symbol}")

        if not settings.WIKIMEDIA_USER_AGENT:
            raise RuntimeError("WIKIMEDIA_USER_AGENT is not configured")

        headers = {
            "User-Agent": settings.WIKIMEDIA_USER_AGENT,
            "Api-User-Agent": settings.WIKIMEDIA_USER_AGENT,
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                timeout=20,
                headers=headers,
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    self.API_URL,
                    params={
                        "action": "parse",
                        "page": self.SP500_PAGE,
                        "prop": "wikitext",
                        "format": "json",
                        "formatversion": "2",
                    },
                )

                response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Wikipedia request failed with HTTP {exc.response.status_code}"
            ) from exc

        except httpx.HTTPError as exc:
            raise RuntimeError("Failed to fetch S&P 500 constituents from Wikipedia") from exc

        data = cast(
            dict[str, Any],
            response.json(),
        )

        return self._extract_wikitext(
            data,
        )

    @staticmethod
    def _extract_wikitext(
        data: dict[str, Any],
    ) -> str:
        parse_data = data.get("parse")

        if not isinstance(
            parse_data,
            dict,
        ):
            raise RuntimeError("Invalid MediaWiki response")

        wikitext = parse_data.get("wikitext")

        if isinstance(wikitext, str):
            return wikitext

        if isinstance(
            wikitext,
            dict,
        ):
            legacy_wikitext = wikitext.get("*")

            if isinstance(
                legacy_wikitext,
                str,
            ):
                return legacy_wikitext

        raise RuntimeError("MediaWiki response contains no wikitext")

    @staticmethod
    def _extract_constituents_table(
        wikitext: str,
    ) -> str:
        marker = 'id="constituents"'

        marker_position = wikitext.find(marker)

        if marker_position == -1:
            raise RuntimeError("S&P 500 constituents table was not found")

        table_start = wikitext.rfind(
            "{|",
            0,
            marker_position,
        )

        table_end = wikitext.find(
            "\n|}",
            marker_position,
        )

        if table_start == -1 or table_end == -1:
            raise RuntimeError("Unable to parse S&P 500 constituents table")

        return wikitext[table_start:table_end]

    @classmethod
    def _parse_constituent_details(
        cls,
        table: str,
    ) -> list[IndexConstituentData]:
        results: list[IndexConstituentData] = []

        rows = table.split("|-")

        for row in rows:
            symbol_match = re.search(
                r"\{\{(Nyse|Nasdaq)Symbol\|([^}|]+)",
                row,
                re.IGNORECASE,
            )

            if symbol_match is None:
                continue

            exchange_template = symbol_match.group(1).lower()

            ticker = symbol_match.group(2).strip().upper()

            fields = [
                field.strip()
                for field in row.split("\n")
                if (field.strip().startswith("|") and not field.strip().startswith("|}"))
            ]

            cleaned_fields = [cls._clean_wiki_value(field.lstrip("|").strip()) for field in fields]

            if len(cleaned_fields) < 4:
                continue

            name = cleaned_fields[1]
            sector = cleaned_fields[2]
            industry = cleaned_fields[3]

            exchange = "NYSE" if exchange_template == "nyse" else "NASDAQ"

            results.append(
                IndexConstituentData(
                    ticker=ticker,
                    name=name,
                    exchange=exchange,
                    sector=sector,
                    industry=industry,
                )
            )

        if not results:
            raise RuntimeError("Wikipedia returned no constituent details")

        return sorted(
            results,
            key=lambda item: item.ticker,
        )

    @staticmethod
    def _clean_wiki_value(
        value: str,
    ) -> str:
        value = re.sub(
            r"\[\[[^|\]]+\|([^\]]+)\]\]",
            r"\1",
            value,
        )

        value = re.sub(
            r"\[\[([^\]]+)\]\]",
            r"\1",
            value,
        )

        value = re.sub(
            r"<ref[^>]*>.*?</ref>",
            "",
            value,
            flags=re.DOTALL,
        )

        value = re.sub(
            r"<ref[^>]*/>",
            "",
            value,
        )

        return value.strip()
