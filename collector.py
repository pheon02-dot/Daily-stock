#!/usr/bin/env python3
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


SYMBOLS = {
    "sp500": ("^GSPC", "S&P 500", "US indices"),
    "nasdaq": ("^IXIC", "Nasdaq Composite", "US indices"),
    "dow": ("^DJI", "Dow Jones", "US indices"),
    "russell2000": ("^RUT", "Russell 2000", "US indices"),
    "sox": ("^SOX", "Philadelphia Semiconductor Index", "US indices"),
    "stoxx600": ("^STOXX", "STOXX Europe 600", "Europe"),
    "eurostoxx50": ("^STOXX50E", "EURO STOXX 50", "Europe"),
    "dax": ("^GDAXI", "DAX", "Europe"),
    "ftse100": ("^FTSE", "FTSE 100", "Europe"),
    "cac40": ("^FCHI", "CAC 40", "Europe"),
    "us10y": ("^TNX", "US 10Y yield", "Rates & volatility"),
    "vix": ("^VIX", "VIX", "Rates & volatility"),
    "dxy": ("DX-Y.NYB", "US Dollar Index", "FX"),
    "usdjpy": ("JPY=X", "USD/JPY", "FX"),
    "usdkrw": ("KRW=X", "USD/KRW", "FX"),
    "wti": ("CL=F", "WTI crude", "Commodities"),
    "gold": ("GC=F", "Gold", "Commodities"),
    "silver": ("SI=F", "Silver", "Commodities"),
    "bitcoin": ("BTC-USD", "Bitcoin", "Crypto"),
}

OUT = Path("public")
DATA_DIR = OUT / "data"
CHART_DIR = OUT / "charts"


def fetch_chart(symbol, interval, range_):
    encoded = quote(symbol, safe="")
    last_error = None
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        url = f"https://{host}/v8/finance/chart/{encoded}?interval={interval}&range={range_}&events=history"
        for attempt in range(3):
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0 market-briefing/1.0"})
                with urlopen(req, timeout=25) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                result = payload.get("chart", {}).get("result")
                if result:
                    return result[0], url
                last_error = payload.get("chart", {}).get("error") or "empty result"
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Yahoo chart request failed: {last_error}")


def parse_series(result, symbol=None):
    timestamps = result.get("timestamp") or []
    quote_data = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote_data.get("close") or []
    points = []
    for ts, close in zip(timestamps, closes):
        if close is None or not math.isfinite(close):
            continue
        value = float(close)
        # Yahoo's ^TNX has historically used either yield-percent or yield*10
        # conventions. Store an actual percentage yield in both cases.
        if symbol == "^TNX" and value > 20:
            value /= 10
        points.append({"timestamp": int(ts), "value": round(value, 8)})
    return points


def quote_summary(meta, daily):
    # The chartPreviousClose field can refer to the session before the whole
    # requested range. Use the final two daily observations for true 1-day moves.
    latest = daily[-1]["value"] if daily else meta.get("regularMarketPrice")
    previous = daily[-2]["value"] if len(daily) > 1 else (meta.get("previousClose") or meta.get("chartPreviousClose"))
    if latest is None or previous in (None, 0):
        return {"latest": latest, "previous": previous, "change": None, "change_percent": None}
    change = float(latest) - float(previous)
    return {
        "latest": round(float(latest), 8),
        "previous": round(float(previous), 8),
        "change": round(change, 8),
        "change_percent": round(change / float(previous) * 100, 4),
    }


def normalized(points, mode):
    if not points:
        return []
    base = points[0]["value"]
    if base == 0:
        return []
    if mode == "percent":
        return [(p["timestamp"], (p["value"] / base - 1) * 100) for p in points]
    return [(p["timestamp"], p["value"] / base * 100) for p in points]


def plot_group(data, keys, period, title, filename):
    mode = "percent" if period == "intraday_5m" else "index"
    fig, ax = plt.subplots(figsize=(12, 5.5), dpi=150)
    plotted = 0
    for key in keys:
        item = data.get("assets", {}).get(key, {})
        points = item.get(period) or []
        series = normalized(points, mode)
        if not series:
            continue
        xs = [datetime.fromtimestamp(ts, tz=timezone.utc) for ts, _ in series]
        ys = [v for _, v in series]
        ax.plot(xs, ys, linewidth=1.7, label=item["name"])
        plotted += 1
    if not plotted:
        plt.close(fig)
        return None
    ax.set_title(title, loc="left", weight="bold")
    ax.set_ylabel("Change from first point (%)" if mode == "percent" else "First close = 100")
    ax.grid(alpha=0.22)
    ax.legend(frameon=False, ncol=min(plotted, 3))
    fig.autofmt_xdate()
    fig.tight_layout()
    path = CHART_DIR / filename
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def write_index(data, charts):
    rows = []
    for item in data["assets"].values():
        q = item.get("quote", {})
        cp = q.get("change_percent")
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                item["name"], q.get("latest", "-"), q.get("change", "-"),
                "-" if cp is None else f"{cp:+.2f}%"
            )
        )
    images = "\n".join(f'<h2>{name}</h2><img src="{path.replace("public/", "")}" alt="{name}">' for name, path in charts.items())
    html = f"""<!doctype html><html lang='ko'><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Daily Stock Market Data</title>
<style>body{{font-family:system-ui;margin:24px;max-width:1100px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:8px;border-bottom:1px solid #ddd;text-align:right}}td:first-child,th:first-child{{text-align:left}}img{{width:100%;height:auto;border:1px solid #eee;border-radius:8px}}small{{color:#666}}</style>
<h1>Daily Stock Market Data</h1><small>Updated {data['generated_at']}</small>
<table><thead><tr><th>Asset</th><th>Latest</th><th>Change</th><th>Change %</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
{images}</html>"""
    (OUT / "index.html").write_text(html, encoding="utf-8")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    data = {"generated_at": datetime.now(timezone.utc).isoformat(), "source": "Yahoo Finance chart v8", "assets": {}, "errors": {}}
    for key, (symbol, name, group) in SYMBOLS.items():
        try:
            intra_result, intra_url = fetch_chart(symbol, "5m", "1d")
            daily_result, daily_url = fetch_chart(symbol, "1d", "3mo")
            intraday = parse_series(intra_result, symbol)
            daily = parse_series(daily_result, symbol)
            meta = daily_result.get("meta") or intra_result.get("meta") or {}
            data["assets"][key] = {
                "symbol": symbol, "name": name, "group": group,
                "currency": meta.get("currency"), "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
                "timezone": meta.get("exchangeTimezoneName"), "quote": quote_summary(meta, daily),
                "intraday_5m": intraday, "daily_3mo": daily,
                "source_urls": {"intraday": intra_url, "daily": daily_url},
            }
        except Exception as exc:
            data["errors"][key] = str(exc)

    groups = {
        "US indices": ["sp500", "nasdaq", "dow", "russell2000", "sox"],
        "Europe": ["stoxx600", "eurostoxx50", "dax", "ftse100", "cac40"],
        "Rates & volatility": ["us10y", "vix"],
        "FX": ["dxy", "usdjpy", "usdkrw"],
        "Commodities": ["wti", "gold", "silver"],
        "Crypto": ["bitcoin"],
    }
    charts = {}
    for group, keys in groups.items():
        slug = group.lower().replace(" & ", "-").replace(" ", "-")
        for period, suffix, label in (("intraday_5m", "5m", "latest session, 5-minute"), ("daily_3mo", "3mo", "3 months, daily")):
            name = f"{group} — {label}"
            path = plot_group(data, keys, period, name, f"{slug}-{suffix}.png")
            if path:
                charts[name] = path
    data["charts"] = {k: v.replace("public/", "") for k, v in charts.items()}
    (DATA_DIR / "market_data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_index(data, charts)
    print(f"Collected {len(data['assets'])} assets; errors={len(data['errors'])}")
    if not data["assets"]:
        raise SystemExit("No market data collected")


if __name__ == "__main__":
    main()
