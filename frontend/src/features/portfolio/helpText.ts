export const HELP_TEXT = {
  strategy:
    'EMA20 Pullback uses EMA20/EMA50 with the frozen HYBRID 2% exit. Micho uses mechanical SMA150 V1 with BOTH entry modes.',
  selection:
    'RS20 ranks BUY candidates by stock 20-trading-bar return minus SPY 20-trading-bar return. Higher scores get priority when capacity is constrained. Ticker ascending is an economically meaningless deterministic control.',
  sizing:
    'Equal slot is the broad research baseline. ATR risk uses the Sprint 10 risk budget. ATR volatility normalized uses inverse ATR percentage across the candidate group. Classifications depend on strategy; none is production-ready.',
  tickerScope:
    'Enter comma- or space-separated stored tickers. Blank evaluates the current active S&P 500 universe; current holdings are always included.',
  requestedDate:
    'The backend uses the newest stored SPY trading day on or before this requested date and evaluates all stock facts only through that analysis day.',
  rs20:
    'RS20 is stock 20-bar return minus SPY 20-bar return. Higher ranks first when BUY capacity is constrained. A negative score may still be selected; SELL and HOLD rows may be unscored.',
  modeledRisk:
    'Modeled risk is the sum of frozen entry risk proxies supplied for current positions. It can be incomplete for manually entered holdings.',
  availableRisk:
    'Available modeled risk is the configured portfolio-risk limit minus supplied current modeled risk. It may be overstated when existing entry-risk facts are unavailable.',
  constraints:
    'Backend-owned entry constraints cover whole shares, cash reserve, position weight, modeled portfolio risk, sector weight, and maximum positions. They do not guarantee realized risk.',
  opportunitiesOrder:
    'Approved BUY rows preserve backend candidate priority. Other decision views preserve backend response order and should not be read as a universal recommendation ranking.',
  universeOrder:
    'All evaluated tickers are displayed A-Z for lookup. Alphabetical order is not recommendation priority; BUY candidate rank is shown separately when available.',
} as const
