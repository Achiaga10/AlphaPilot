from datetime import UTC, date, datetime

from alphapilot.market.session import CompletedDailySessionPolicy


def policy_at(value: datetime) -> CompletedDailySessionPolicy:
    return CompletedDailySessionPolicy(now_provider=lambda: value)


def test_current_open_session_is_not_complete() -> None:
    policy = policy_at(datetime(2026, 8, 26, 18, 0, tzinfo=UTC))  # 14:00 New York

    assert policy.completed_through() == date(2026, 8, 25)
    assert policy.is_complete(date(2026, 8, 25)) is True
    assert policy.is_complete(date(2026, 8, 26)) is False


def test_current_session_is_complete_after_conservative_close_boundary() -> None:
    policy = policy_at(datetime(2026, 8, 26, 20, 16, tzinfo=UTC))  # 16:16 New York

    assert policy.completed_through() == date(2026, 8, 26)
    assert policy.is_complete(date(2026, 8, 26)) is True
