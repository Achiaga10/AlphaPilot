from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class IndexConstituentData:
    ticker: str
    name: str
    exchange: str
    sector: str
    industry: str
