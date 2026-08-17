from decimal import Decimal


def calculate_sma(
    values: list[Decimal],
    period: int,
) -> Decimal | None:
    """Calculate the latest simple moving average."""

    if period <= 0:
        raise ValueError("period must be greater than zero")

    if len(values) < period:
        return None

    window = values[-period:]

    return sum(
        window,
        Decimal(0),
    ) / Decimal(period)


def calculate_ema_series(
    values: list[Decimal],
    period: int,
) -> list[Decimal]:
    """Calculate an EMA series using an SMA seed."""

    if period <= 0:
        raise ValueError("period must be greater than zero")

    if len(values) < period:
        return []

    multiplier = Decimal(2) / Decimal(period + 1)

    seed = sum(
        values[:period],
        Decimal(0),
    ) / Decimal(period)

    ema_values = [seed]

    for value in values[period:]:
        previous_ema = ema_values[-1]

        current_ema = (value - previous_ema) * multiplier + previous_ema

        ema_values.append(current_ema)

    return ema_values
