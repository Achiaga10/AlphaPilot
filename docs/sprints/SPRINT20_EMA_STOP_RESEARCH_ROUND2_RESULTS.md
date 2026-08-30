# Sprint 20 EMA Loss-Control Research Round 2 Results

Protocol: [SPRINT20_EMA_STOP_RESEARCH_ROUND2_PROTOCOL.md](SPRINT20_EMA_STOP_RESEARCH_ROUND2_PROTOCOL.md). The candidate space and gates were frozen before results. All periods are previously observed research evidence, not untouched out-of-sample evidence.

## Development evidence

| Candidate | Return | CAGR | Max DD | Sharpe | Calmar | Turnover | Worst trade | P5 trade |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Control | 80.15% | 19.12% | 26.43% | 0.869 | 0.723 | 5,511.94% | -17.53% | -10.27% |
| ATR14 2.0× reference | 70.39% | 17.16% | 25.77% | 0.813 | 0.666 | 6,044.22% | -14.04% | -9.44% |
| Signal-day-low invalidation | 63.08% | 15.64% | 25.32% | 0.801 | 0.618 | 9,507.98% | -11.17% | -6.96% |

The structural signal-day-low arm improved drawdown and tails but increased turnover about 72.5%, above the frozen 25% ceiling, and was ineligible. The ATR2 reference retained about 89.8% of CAGR, 93.6% of Sharpe, and 92.1% of Calmar; improved drawdown by 0.66 points and worst-trade magnitude by about 19.9%; and increased turnover about 9.7%. It was the sole development qualifier.

## Reused / previously observed validation evidence

| Candidate | Final equity | Return | CAGR | Max DD | Sharpe | Calmar | Turnover | Top-5 positive P&L | 20-session recovery |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Control | $118,058.42 | 18.06% | 10.73% | 23.74% | 0.478 | 0.452 | 3,110.64% | 44.34% | N/A |
| ATR14 2.0× reference | $138,285.39 | 38.29% | 22.02% | 25.36% | 0.738 | 0.868 | 3,544.38% | 46.43% | 55.22% |

The reference passed CAGR, Sharpe, Calmar, concentration, turnover, and recovery gates. It failed the frozen maximum-drawdown gate: drawdown worsened by 1.62 percentage points versus the 1.5-point ceiling.

## Temporal folds

| Fold | Control return | ATR2 return | Control Sharpe | ATR2 Sharpe | Control DD | ATR2 DD |
|---|---:|---:|---:|---:|---:|---:|
| 2021-08-20–2022-12-31 | -10.35% | -8.39% | -0.394 | -0.316 | 21.18% | 19.07% |
| 2023-01-01–2024-12-31 | 97.60% | 80.67% | 1.401 | 1.334 | 25.95% | 24.48% |
| 2025-01-01–2026-08-20 | 18.06% | 38.29% | 0.478 | 0.738 | 23.74% | 25.36% |

The reference improved return, Sharpe, and drawdown in 2/3 folds. The configuration-identical reused-validation artifact is Fold 3.

## Decision

`NO_WINNER`. The hard reused-validation drawdown failure cannot be offset by other metrics or folds. There is no fallback, retuning, Round 3, automatic profile change, or EMA default change. Signal-day-low and ATR2 remain research evidence only; trailing stop and profit target remain `NONE`.

Limitations include current-constituent survivorship bias, `LEGACY_PARTIAL` snapshot provenance, daily-OHLC path ambiguity, fixed 5 bps-per-side costs, an imperfect SPY benchmark, and final-open mark-to-market handling.
