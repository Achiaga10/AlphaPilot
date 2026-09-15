from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from alphapilot.api.routes.broker_alpaca import get_broker_sync_service
from alphapilot.broker.alpaca_read_only import AlpacaReadOnlyClient
from alphapilot.core.config import Settings
from alphapilot.database.models.broker_sync import (
    BrokerAccountSnapshot,
    BrokerExecution,
    BrokerExecutionMatchEvent,
    BrokerOrderObservation,
    BrokerPositionSnapshot,
    BrokerSyncRun,
)
from alphapilot.database.models.company import Company
from alphapilot.database.models.external_execution import ExternalExecutionCase
from alphapilot.database.models.forward_portfolio import ForwardOrder, ForwardPortfolio
from alphapilot.main import app
from alphapilot.schemas.external_execution import ExternalFillRequest
from alphapilot.services.broker_sync import (
    AlpacaBrokerSyncService,
    BrokerSyncNotConfiguredError,
)
from alphapilot.services.external_execution import ExternalExecutionService

SESSION = date(2026, 9, 15)
EXECUTED_AT = datetime(2026, 9, 15, 14, 35, tzinfo=UTC)


class FakeAlpaca:
    def __init__(
        self,
        *,
        orders: list[dict[str, object]] | None = None,
        activities: list[dict[str, object]] | None = None,
        fail: bool = False,
    ) -> None:
        self.orders = orders or []
        self.activities = activities or []
        self.fail = fail
        self.after_values: list[datetime] = []

    async def get_account(self) -> dict[str, object]:
        if self.fail:
            raise httpx.ConnectError("offline")
        return {
            "id": "account-id-not-returned-to-ui",
            "status": "ACTIVE",
            "currency": "USD",
            "cash": "9000.12",
            "equity": "10100.34",
            "buying_power": "18000.24",
        }

    async def get_positions(self) -> list[dict[str, object]]:
        return [
            {
                "symbol": "AAA",
                "side": "long",
                "qty": "100",
                "avg_entry_price": "100.25",
                "current_price": "101.50",
                "market_value": "10150",
                "unrealized_pl": "125",
            }
        ]

    async def get_orders(self, *, after: datetime) -> list[dict[str, object]]:
        self.after_values.append(after)
        return self.orders

    async def get_fill_activities(self, *, after: datetime) -> list[dict[str, object]]:
        self.after_values.append(after)
        return self.activities

    async def close(self) -> None:
        return None


def sync_settings(*, enabled: bool = True, configured: bool = True) -> Settings:
    return Settings(
        _env_file=None,
        ALPACA_SYNC_ENABLED=enabled,
        ALPACA_ENVIRONMENT="PAPER",
        ALPACA_API_KEY="test-key" if configured else "",
        ALPACA_SECRET_KEY="test-secret" if configured else "",
        ALPACA_SYNC_INTERVAL_SECONDS=300,
        ALPACA_SYNC_INITIAL_LOOKBACK_DAYS=14,
        ALPACA_SYNC_OVERLAP_MINUTES=10,
    )


def order_payload(*, status: str = "filled", filled_qty: str = "100") -> dict[str, object]:
    return {
        "id": "order-1",
        "client_order_id": "client-1",
        "symbol": "AAA",
        "side": "buy",
        "status": status,
        "type": "market",
        "qty": "100",
        "filled_qty": filled_qty,
        "filled_avg_price": "100.60" if filled_qty != "0" else None,
        "submitted_at": "2026-09-15T14:29:00Z",
        "updated_at": "2026-09-15T14:36:00Z",
    }


def fill_payload(
    activity_id: str, quantity: str, price: str, *, order_id: str = "order-1"
) -> dict[str, object]:
    return {
        "id": activity_id,
        "order_id": order_id,
        "symbol": "AAA",
        "side": "buy",
        "qty": quantity,
        "price": price,
        "transaction_time": EXECUTED_AT.isoformat(),
    }


async def seed_forward_action(
    session: AsyncSession, *, strategy: str = "micho-150-v1", ticker: str = "AAA"
) -> tuple[ForwardPortfolio, ExternalExecutionCase]:
    company = await session.scalar(select(Company).where(Company.ticker == ticker))
    if company is None:
        company = Company(ticker=ticker, name=ticker, exchange="NYSE")
        session.add(company)
        await session.flush()
    portfolio = ForwardPortfolio(
        strategy_id=strategy,
        strategy_version=1,
        execution_mode="VIRTUAL",
        broker_execution_mode="MANUAL_EXTERNAL",
        status="ACTIVE",
        forward_start_session=SESSION,
        initial_cash=Decimal("100000"),
        cash_balance=Decimal("100000"),
        equity=Decimal("100000"),
    )
    session.add(portfolio)
    await session.flush()
    order = ForwardOrder(
        portfolio_id=portfolio.id,
        company_id=company.id,
        ticker=ticker,
        side="ENTRY",
        status="FILLED",
        source_signal_session=date(2026, 9, 14),
        planned_execution_session=SESSION,
        actual_execution_session=SESSION,
        approved_allocation=Decimal("10000"),
        planned_shares=100,
        filled_shares=100,
        raw_fill_price=Decimal("100"),
        modeled_fill_price=Decimal("100.05"),
        friction_bps=Decimal("5"),
        friction_dollars=Decimal("5"),
        reason_code="BUY_APPROVED",
        strategy_id="micho-150-v1",
        strategy_version=1,
        loss_control_policy="SMA150_COMPLETED_CLOSE_EXIT",
        loss_control_boundary=Decimal("90"),
        evidence={},
    )
    session.add(order)
    await session.flush()
    case = ExternalExecutionCase(
        portfolio_id=portfolio.id,
        forward_order_id=order.id,
        broker="ALPACA",
        provenance="MANUAL_USER_RECORDED",
    )
    session.add(case)
    await session.commit()
    return portfolio, case


@pytest.mark.asyncio
async def test_sync_is_idempotent_get_only_and_canonical_broker_facts(
    db_session: AsyncSession,
) -> None:
    portfolio, case = await seed_forward_action(db_session)
    fake = FakeAlpaca(
        orders=[order_payload()],
        activities=[fill_payload("fill-1", "40", "100"), fill_payload("fill-2", "60", "101")],
    )
    service = AlpacaBrokerSyncService(
        db_session, config=sync_settings(), provider_factory=lambda: fake
    )
    for _ in range(10):
        result = await service.sync_now()
        assert result.status == "SUCCEEDED"
    assert await db_session.scalar(select(func.count()).select_from(BrokerExecution)) == 2
    assert await db_session.scalar(select(func.count()).select_from(BrokerOrderObservation)) == 1
    assert await db_session.scalar(select(func.count()).select_from(BrokerAccountSnapshot)) == 10
    assert await db_session.scalar(select(func.count()).select_from(BrokerPositionSnapshot)) == 10
    assert await db_session.scalar(select(func.count()).select_from(BrokerSyncRun)) == 10
    broker_fills = await service.executions()
    assert {item.match_state for item in broker_fills} == {"AUTO_MATCHED"}
    assert {item.external_case_id for item in broker_fills} == {case.id}
    action = await ExternalExecutionService(db_session).get_action(portfolio.id, case.id)
    assert action.canonical_execution_source == "ALPACA_READ_ONLY_SYNC"
    assert action.provenance == "ALPACA_READ_ONLY_SYNC"
    assert action.broker_match_state == "AUTO_MATCHED"
    assert action.status == "RECORDED"
    assert action.recorded_shares == 100
    assert action.weighted_fill_price == Decimal("100.60000000")
    assert action.recorded_fees is None
    assert action.fee_coverage_complete is False


@pytest.mark.asyncio
async def test_disabled_misconfigured_failure_and_last_good_snapshot_survive(
    db_session: AsyncSession,
) -> None:
    disabled = AlpacaBrokerSyncService(db_session, config=sync_settings(enabled=False))
    assert (await disabled.status()).status == "DISABLED"
    with pytest.raises(BrokerSyncNotConfiguredError):
        await disabled.sync_now()
    misconfigured = AlpacaBrokerSyncService(db_session, config=sync_settings(configured=False))
    assert (await misconfigured.status()).status == "MISCONFIGURED"
    with pytest.raises(BrokerSyncNotConfiguredError):
        await misconfigured.sync_now()

    good = FakeAlpaca(orders=[order_payload(status="canceled", filled_qty="0")])
    service = AlpacaBrokerSyncService(
        db_session, config=sync_settings(), provider_factory=lambda: good
    )
    assert (await service.sync_now()).status == "SUCCEEDED"
    account = await service.account()
    assert account is not None and account.equity == Decimal("10100.34000000")
    failing = AlpacaBrokerSyncService(
        db_session,
        config=sync_settings(),
        provider_factory=lambda: FakeAlpaca(fail=True),
    )
    failed = await failing.sync_now()
    assert failed.status == "FAILED"
    retained = await failing.account()
    assert retained is not None and retained.equity == account.equity
    assert failed.executions == 0


@pytest.mark.asyncio
async def test_manual_same_fact_uses_broker_and_different_fact_is_conflict(
    db_session: AsyncSession,
) -> None:
    portfolio, case = await seed_forward_action(db_session)
    external = ExternalExecutionService(
        db_session, now_provider=lambda: datetime(2026, 9, 15, 16, tzinfo=UTC)
    )
    await external.record_fill(
        portfolio.id,
        case.id,
        ExternalFillRequest(
            request_key="manual-fill-same",
            side="BUY",
            quantity=100,
            price=Decimal("100.60"),
            executed_at=EXECUTED_AT,
            fee=None,
            mark_complete=True,
        ),
    )
    fake = FakeAlpaca(
        orders=[order_payload()], activities=[fill_payload("same-fill", "100", "100.60")]
    )
    await AlpacaBrokerSyncService(
        db_session, config=sync_settings(), provider_factory=lambda: fake
    ).sync_now()
    same = await external.get_action(portfolio.id, case.id)
    assert same.canonical_execution_source == "ALPACA_READ_ONLY_SYNC"
    assert same.broker_match_state == "AUTO_MATCHED"
    assert len(same.fills) == 1 and len(same.broker_executions) == 1

    other_portfolio, other_case = await seed_forward_action(
        db_session, strategy="test-other-strategy", ticker="BBB"
    )
    await external.record_fill(
        other_portfolio.id,
        other_case.id,
        ExternalFillRequest(
            request_key="manual-fill-different",
            side="BUY",
            quantity=100,
            price=Decimal("100.60"),
            executed_at=EXECUTED_AT,
            fee=None,
            mark_complete=True,
        ),
    )
    different = FakeAlpaca(
        orders=[
            {
                **order_payload(),
                "id": "order-2",
                "client_order_id": "client-2",
                "symbol": "BBB",
            }
        ],
        activities=[
            {
                **fill_payload("different-fill", "99", "100.70", order_id="order-2"),
                "symbol": "BBB",
            }
        ],
    )
    await AlpacaBrokerSyncService(
        db_session, config=sync_settings(), provider_factory=lambda: different
    ).sync_now()
    conflict = await external.get_action(other_portfolio.id, other_case.id)
    assert conflict.broker_match_state == "CONFLICT"
    assert conflict.reconciliation_status == "BROKER_CONFLICT"
    assert conflict.recorded_shares == 99
    assert conflict.weighted_fill_price == Decimal("100.70000000")


@pytest.mark.asyncio
async def test_manual_link_unlink_ignore_are_audited_and_compatible(
    db_session: AsyncSession,
) -> None:
    _, case = await seed_forward_action(db_session)
    fake = FakeAlpaca(
        orders=[order_payload()],
        activities=[
            {
                **fill_payload("outside", "75", "103"),
                "transaction_time": "2026-09-12T14:35:00Z",
            }
        ],
    )
    service = AlpacaBrokerSyncService(
        db_session, config=sync_settings(), provider_factory=lambda: fake
    )
    await service.sync_now()
    execution = (await service.executions(unmatched_only=True))[0]
    assert execution.match_reason == "OUTSIDE_FORWARD_OR_EXECUTION_WINDOW"
    linked = await service.manual_match(
        execution.id, case.id, reason="Confirmed broker activity", request_key="match-0001"
    )
    assert linked.match_state == "MANUAL_MATCHED"
    unlinked = await service.unlink(
        execution.id, reason="Wrong Forward action", request_key="unlink-0001"
    )
    assert unlinked.match_state == "UNMATCHED" and unlinked.external_case_id is None
    ignored = await service.ignore(
        execution.id, reason="Unrelated discretionary trade", request_key="ignore-0001"
    )
    assert ignored.match_state == "IGNORED_EXTERNAL"
    assert await db_session.scalar(select(func.count()).select_from(BrokerExecutionMatchEvent)) == 3


@pytest.mark.asyncio
async def test_partial_order_stays_partial_and_ambiguous_match_stays_unlinked(
    db_session: AsyncSession,
) -> None:
    portfolio, case = await seed_forward_action(db_session)
    partial_provider = FakeAlpaca(
        orders=[order_payload(status="partially_filled", filled_qty="40")],
        activities=[fill_payload("partial-only", "40", "100")],
    )
    await AlpacaBrokerSyncService(
        db_session, config=sync_settings(), provider_factory=lambda: partial_provider
    ).sync_now()
    partial = await ExternalExecutionService(db_session).get_action(portfolio.id, case.id)
    assert partial.status == "PARTIALLY_RECORDED"
    assert partial.recorded_shares == 40

    await seed_forward_action(db_session, strategy="second-forward-candidate")
    ambiguous_provider = FakeAlpaca(
        orders=[{**order_payload(), "id": "ambiguous-order"}],
        activities=[fill_payload("ambiguous-fill", "100", "100.60", order_id="ambiguous-order")],
    )
    service = AlpacaBrokerSyncService(
        db_session, config=sync_settings(), provider_factory=lambda: ambiguous_provider
    )
    await service.sync_now()
    ambiguous = next(
        item
        for item in await service.executions(unmatched_only=True)
        if item.broker_activity_id == "ambiguous-fill"
    )
    assert ambiguous.match_state == "AMBIGUOUS"
    assert ambiguous.external_case_id is None


@pytest.mark.asyncio
async def test_distinct_broker_orders_for_one_forward_window_are_ambiguous(
    db_session: AsyncSession,
) -> None:
    await seed_forward_action(db_session)
    provider = FakeAlpaca(
        orders=[
            {**order_payload(), "id": "split-order-1"},
            {**order_payload(), "id": "split-order-2"},
        ],
        activities=[
            fill_payload("split-fill-1", "50", "100.50", order_id="split-order-1"),
            fill_payload("split-fill-2", "50", "100.70", order_id="split-order-2"),
        ],
    )
    service = AlpacaBrokerSyncService(
        db_session, config=sync_settings(), provider_factory=lambda: provider
    )
    await service.sync_now()

    executions = await service.executions(unmatched_only=True)
    assert len(executions) == 2
    assert {item.match_state for item in executions} == {"AMBIGUOUS"}
    assert {item.match_reason for item in executions} == {"MULTIPLE_BROKER_ORDER_GROUPS"}
    assert {item.external_case_id for item in executions} == {None}


@pytest.mark.asyncio
async def test_fractional_broker_quantity_remains_decimal_in_reconciliation(
    db_session: AsyncSession,
) -> None:
    portfolio, case = await seed_forward_action(db_session)
    provider = FakeAlpaca(
        orders=[order_payload(status="filled", filled_qty="40.50000000")],
        activities=[fill_payload("fractional-fill", "40.50000000", "100.25")],
    )
    await AlpacaBrokerSyncService(
        db_session, config=sync_settings(), provider_factory=lambda: provider
    ).sync_now()

    action = await ExternalExecutionService(db_session).get_action(portfolio.id, case.id)
    assert action.recorded_shares == Decimal("40.50000000")
    assert action.weighted_fill_price == Decimal("100.2500")
    assert action.share_variance_vs_virtual == Decimal("-59.50000000")
    assert action.reconciliation_status == "PRICE_AND_QUANTITY_DIVERGENCE"


@pytest.mark.asyncio
@pytest.mark.parametrize("broker_status", ["rejected", "canceled"])
async def test_nonfilled_terminal_order_is_observed_without_execution_evidence(
    db_session: AsyncSession,
    broker_status: str,
) -> None:
    portfolio, case = await seed_forward_action(db_session)
    provider = FakeAlpaca(
        orders=[order_payload(status=broker_status, filled_qty="0")],
        activities=[],
    )
    service = AlpacaBrokerSyncService(
        db_session, config=sync_settings(), provider_factory=lambda: provider
    )
    await service.sync_now()

    observed_orders = await service.orders()
    assert len(observed_orders) == 1
    assert observed_orders[0].status == broker_status.upper()
    assert await service.executions() == []
    action = await ExternalExecutionService(db_session).get_action(portfolio.id, case.id)
    assert action.recorded_shares == 0
    assert action.canonical_execution_source == "NONE"


@pytest.mark.asyncio
async def test_concurrent_sync_dedupes_and_does_not_mutate_forward(
    db_session: AsyncSession,
) -> None:
    portfolio, _ = await seed_forward_action(db_session)
    before = (
        portfolio.cash_balance,
        portfolio.equity,
        portfolio.realized_pnl,
        portfolio.revision,
    )
    portfolio_id = portfolio.id
    factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    fake = FakeAlpaca(
        orders=[order_payload()], activities=[fill_payload("concurrent", "100", "100.60")]
    )

    async def run() -> None:
        async with factory() as session:
            await AlpacaBrokerSyncService(
                session, config=sync_settings(), provider_factory=lambda: fake
            ).sync_now()

    await asyncio.gather(run(), run())
    assert await db_session.scalar(select(func.count()).select_from(BrokerExecution)) == 1
    db_session.expire_all()
    persisted = await db_session.get(ForwardPortfolio, portfolio_id)
    assert persisted is not None
    assert (
        persisted.cash_balance,
        persisted.equity,
        persisted.realized_pnl,
        persisted.revision,
    ) == before


@pytest.mark.asyncio
async def test_adapter_network_surface_uses_only_get() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        payload: object
        if request.url.path == "/v2/account":
            payload = {}
        else:
            payload = []
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://paper-api.alpaca.markets"
    )
    adapter = AlpacaReadOnlyClient(
        api_key="test", secret_key="test", environment="PAPER", client=client
    )
    await adapter.get_account()
    await adapter.get_positions()
    await adapter.get_orders(after=EXECUTED_AT)
    await adapter.get_fill_activities(after=EXECUTED_AT)
    assert methods == ["GET", "GET", "GET", "GET"]
    assert not any(
        hasattr(adapter, name)
        for name in ("submit_order", "cancel_order", "replace_order", "close_position")
    )
    await client.aclose()


@pytest.mark.asyncio
async def test_broker_read_api_and_confirmed_manual_reconciliation(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    _, case = await seed_forward_action(db_session)
    fake = FakeAlpaca(
        orders=[order_payload()],
        activities=[
            {
                **fill_payload("api-outside", "75", "103"),
                "transaction_time": "2026-09-12T14:35:00Z",
            }
        ],
    )
    service = AlpacaBrokerSyncService(
        db_session, config=sync_settings(), provider_factory=lambda: fake
    )
    app.dependency_overrides[get_broker_sync_service] = lambda: service
    try:
        status = await client.get("/api/v1/broker/alpaca/status")
        assert status.status_code == 200
        assert status.json()["environment"] == "PAPER"
        assert status.json()["provenance"] == "ALPACA_READ_ONLY_SYNC"
        synced = await client.post("/api/v1/broker/alpaca/sync")
        assert synced.status_code == 200 and synced.json()["status"] == "SUCCEEDED"
        for resource in ("account", "positions", "orders", "activity", "unmatched"):
            response = await client.get(f"/api/v1/broker/alpaca/{resource}")
            assert response.status_code == 200
        execution_id = (await client.get("/api/v1/broker/alpaca/unmatched")).json()[0]["id"]
        match_url = f"/api/v1/broker/alpaca/activity/{execution_id}/manual-match"
        request = {
            "confirmed": False,
            "external_case_id": str(case.id),
            "request_key": "api-match-0001",
            "reason": "User verified the activity",
        }
        assert (await client.post(match_url, json=request)).status_code == 422
        matched = await client.post(match_url, json={**request, "confirmed": True})
        assert matched.status_code == 200
        assert matched.json()["match_state"] == "MANUAL_MATCHED"
        unlink = await client.post(
            f"/api/v1/broker/alpaca/activity/{execution_id}/unlink",
            json={
                "confirmed": True,
                "request_key": "api-unlink-0001",
                "reason": "Correcting link",
            },
        )
        assert unlink.status_code == 200 and unlink.json()["match_state"] == "UNMATCHED"
        ignored = await client.post(
            f"/api/v1/broker/alpaca/activity/{execution_id}/ignore",
            json={
                "confirmed": True,
                "request_key": "api-ignore-0001",
                "reason": "Not a Forward trade",
            },
        )
        assert ignored.status_code == 200
        assert ignored.json()["match_state"] == "IGNORED_EXTERNAL"
    finally:
        app.dependency_overrides.pop(get_broker_sync_service, None)
