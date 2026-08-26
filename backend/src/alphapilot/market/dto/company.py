from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True, frozen=True)
class CompanyMetadata:
    ticker: str
    name: str
    exchange: str
    sector: str | None = None
    industry: str | None = None
    market_cap: Decimal | None = None
