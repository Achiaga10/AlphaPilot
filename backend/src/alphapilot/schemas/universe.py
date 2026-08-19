from pydantic import BaseModel


class UniverseSyncResponse(BaseModel):
    status: str
    index_symbol: str
    active_count: int


class UniverseConstituentResponse(BaseModel):
    index_symbol: str
    ticker: str
    is_active: bool


class UniverseCompanySyncResponse(BaseModel):
    status: str
    index_symbol: str
    created_count: int
