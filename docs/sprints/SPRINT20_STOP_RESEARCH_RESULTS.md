# Sprint 20 Protective-Stop Research Results

Protocol: [SPRINT20_STOP_RESEARCH_PROTOCOL.md](SPRINT20_STOP_RESEARCH_PROTOCOL.md). The protocol was frozen before any Sprint 20 result was observed. All runs used snapshot `5dd60f87-8947-4850-ba87-4a7df655528c`, RS20, COST_LOW (5 bps per side), $100,000, 10 positions, existing strategy rules/sizing, and mark-to-market final positions.

## Development

| Strategy | Stop | Return | CAGR | Max DD | Sharpe | Calmar | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|
| EMA | control | 80.15% | 19.12% | 26.43% | 0.869 | 0.723 | 5,511.94% |
| EMA | 2.0× ATR14 | 70.39% | 17.16% | 25.77% | 0.813 | 0.666 | 6,044.22% |
| EMA | 2.5× ATR14 | 53.88% | 13.67% | 27.69% | 0.684 | 0.493 | 5,519.54% |
| EMA | 3.0× ATR14 | 84.65% | 19.99% | 26.47% | 0.908 | 0.755 | 5,620.06% |
| Micho | control | 48.43% | 12.46% | 15.74% | 0.770 | 0.791 | 4,396.86% |
| Micho | 1.0× ATR14 | 53.58% | 13.60% | 17.83% | 0.912 | 0.763 | 5,252.44% |
| Micho | 1.5× ATR14 | 59.50% | 14.88% | 16.18% | 0.936 | 0.920 | 4,351.44% |
| Micho | 2.0× ATR14 | 50.51% | 12.92% | 18.78% | 0.824 | 0.688 | 4,170.25% |
| Micho | 2.5× ATR14 | 49.87% | 12.78% | 16.36% | 0.794 | 0.781 | 4,033.61% |

EMA 2.0× was the sole development-gate qualifier and was frozen. EMA 3.0× had attractive headline metrics but failed the declared ≥10% tail-loss-improvement gate; 2.5× failed CAGR retention. Micho 1.5× qualified and was frozen; the other Micho candidates failed drawdown and/or tail gates.

## Reused / previously observed validation evidence

| Strategy | Stop | Final equity | Return | CAGR | Max DD | Sharpe | Calmar | Trades | Turnover | Realized P&L | Final-open P&L | Top-5 positive P&L share | 20-session recovery |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EMA | control | $118,058.42 | 18.06% | 10.73% | 23.74% | 0.478 | 0.452 | 158 | 3,110.64% | $3,631.28 | $14,427.14 | 44.34% | N/A |
| EMA | 2.0× ATR14 | $138,285.39 | 38.29% | 22.02% | 25.36% | 0.738 | 0.868 | 169 | 3,544.38% | $19,081.15 | $19,204.24 | 46.43% | 55.22% |
| Micho | control | $128,508.10 | 28.51% | 16.65% | 11.44% | 1.228 | 1.456 | 103 | 1,769.06% | $4,767.91 | $23,740.19 | 65.25% | N/A |
| Micho | 1.5× ATR14 | $163,686.12 | 63.69% | 35.32% | 13.44% | 1.577 | 2.629 | 99 | 1,845.14% | $32,961.25 | $30,724.87 | 73.44% | 79.07% |

EMA fails because drawdown worsens 1.62 percentage points, above the frozen 1.5-point maximum. Micho fails because drawdown worsens 2.00 points, top-5 concentration worsens 8.19 points (limit 5), and 79.07% recovery exceeds the 65% ceiling. No gate was relaxed.

## Temporal folds

| Fold | Strategy | Control return | Stop return | Return better? | Control Sharpe | Stop Sharpe | Sharpe better? | Control DD | Stop DD | DD better? |
|---|---|---:|---:|---|---:|---:|---|---:|---:|---|
| 2021-08-20–2022-12-31 | EMA | -10.35% | -8.39% | Yes | -0.394 | -0.316 | Yes | 21.18% | 19.07% | Yes |
| 2023-01-01–2024-12-31 | EMA | 97.60% | 80.67% | No | 1.401 | 1.334 | No | 25.95% | 24.48% | Yes |
| 2025-01-01–2026-08-20 | EMA | 18.06% | 38.29% | Yes | 0.478 | 0.738 | Yes | 23.74% | 25.36% | No |
| 2021-08-20–2022-12-31 | Micho | 4.74% | 8.60% | Yes | 0.269 | 0.413 | Yes | 15.74% | 14.96% | Yes |
| 2023-01-01–2024-12-31 | Micho | 34.05% | 24.03% | No | 1.070 | 0.868 | No | 17.09% | 13.21% | Yes |
| 2025-01-01–2026-08-20 | Micho | 28.51% | 63.69% | Yes | 1.228 | 1.577 | Yes | 11.44% | 13.44% | No |

Both frozen candidates improve/equal return, Sharpe, and drawdown in 2/3 folds. The configuration-identical validation run is reused as fold 3. This directional result does not override failed hard validation gates.

## Decision

`NO_WINNER` for EMA and `NO_WINNER` for Micho. Existing profile stop defaults remain `NONE`; trailing and profit policies remain `NONE`; no migration or profile promotion is created. The studied stops remain research evidence only. Historical current-constituent membership creates survivorship bias, daily OHLC cannot resolve all intraday path ordering, costs are a fixed 5 bps per side, SPY is an imperfect benchmark, and final-open positions are marked rather than liquidated.
