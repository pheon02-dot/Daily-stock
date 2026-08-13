# Daily Stock Market Data

Free daily market-data collector for a ChatGPT Work morning briefing.

## What it collects

- US: S&P 500, Nasdaq, Dow, Russell 2000
- Europe: STOXX 600, EURO STOXX 50, DAX, FTSE 100, CAC 40
- Rates/volatility: US 10Y yield proxy, VIX
- FX: DXY, USD/JPY, USD/KRW
- Commodities: WTI, gold, silver
- Crypto: Bitcoin

For each available symbol the workflow stores:

- 5-minute intraday data (range=1d)
- 3-month daily data (range=3mo)
- latest value, previous close, absolute change, and percent change
- normalized comparison charts

## Outputs

- public/data/market_data.json
- public/charts/*.png
- public/index.html

## Schedule

GitHub Actions refreshes the data every day at 07:30 Asia/Seoul and can also be run manually from the Actions tab.

## Data source

Yahoo Finance's unofficial chart endpoint is used first. It may throttle or change without notice. Missing values are never interpolated.
