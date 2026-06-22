"""FinAlly Market Data Simulator Demo.

Run with:  uv run market_data_demo.py

Displays a live-updating terminal dashboard of simulated stock prices
using the GBM simulator and Rich library. Runs until Ctrl+C.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque

from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.market.cache import PriceCache
from app.market.seed_prices import SEED_PRICES, TICKER_PARAMS
from app.market.simulator import SimulatorDataSource

SPARK_CHARS = "▁▂▃▄▅▆▇█"

TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]

# Sector tags shown next to ticker names
SECTOR: dict[str, str] = {
    "AAPL": "tech", "GOOGL": "tech", "MSFT": "tech",
    "AMZN": "tech", "META": "tech", "NVDA": "tech", "NFLX": "tech",
    "JPM": "fin", "V": "fin",
    "TSLA": "—",
}
SECTOR_COLOR: dict[str, str] = {"tech": "cyan", "fin": "yellow", "—": "bright_black"}


def sparkline(values: list[float]) -> str:
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    spread = hi - lo
    if spread == 0:
        return SPARK_CHARS[3] * len(values)
    n = len(SPARK_CHARS) - 1
    return "".join(SPARK_CHARS[int((v - lo) / spread * n)] for v in values)


def fmt(price: float) -> str:
    return f"{price:,.2f}" if price >= 1000 else f"{price:.2f}"


def direction_style(direction: str) -> tuple[str, str]:
    """Returns (color, arrow_markup)."""
    if direction == "up":
        return "green", "[bold green]▲[/]"
    if direction == "down":
        return "red", "[bold red]▼[/]"
    return "bright_black", "[bright_black]─[/]"


def build_table(
    cache: PriceCache,
    history: dict[str, deque],
    session_opens: dict[str, float],
    tick_count: int,
) -> Table:
    table = Table(
        expand=True,
        border_style="bright_black",
        header_style="bold bright_white",
        pad_edge=False,
        padding=(0, 1),
        show_edge=True,
    )
    table.add_column("Ticker", width=7, no_wrap=True)
    table.add_column("Sector", width=5, no_wrap=True)
    table.add_column("Price", justify="right", width=10, no_wrap=True)
    table.add_column("Tick Δ", justify="right", width=8, no_wrap=True)
    table.add_column("Tick %", justify="right", width=8, no_wrap=True)
    table.add_column("Session %", justify="right", width=10, no_wrap=True)
    table.add_column(" ", width=2, no_wrap=True)  # arrow
    table.add_column("σ", justify="center", width=5, no_wrap=True)  # volatility tier
    table.add_column("Sparkline (last 40 ticks)", min_width=22, no_wrap=True)

    for ticker in TICKERS:
        update = cache.get(ticker)
        sector = SECTOR.get(ticker, "—")
        scol = SECTOR_COLOR.get(sector, "bright_black")
        sector_text = f"[{scol}]{sector}[/]"

        params = TICKER_PARAMS.get(ticker, {"sigma": 0.25})
        sigma = params["sigma"]
        # Volatility tier: low / mid / high
        if sigma < 0.22:
            vol_str = "[green]low[/]"
        elif sigma < 0.35:
            vol_str = "[yellow]mid[/]"
        else:
            vol_str = "[red]high[/]"

        if update is None:
            table.add_row(ticker, sector_text, "…", "…", "…", "…", "", vol_str, "")
            continue

        color, arrow = direction_style(update.direction)
        price_str = f"[{color}]${fmt(update.price)}[/]"
        delta_str = f"[{color}]{update.change:+.2f}[/]"
        pct_str = f"[{color}]{update.change_percent:+.2f}%[/]"

        # Session change from opening price captured at start
        session_open = session_opens.get(ticker, update.price)
        session_pct = (update.price - session_open) / session_open * 100 if session_open else 0.0
        sc = "green" if session_pct > 0 else ("red" if session_pct < 0 else "bright_black")
        session_str = f"[{sc}]{session_pct:+.2f}%[/]"

        vals = list(history.get(ticker, []))
        spark_str = f"[bright_cyan]{sparkline(vals)}[/]" if len(vals) > 1 else ""

        table.add_row(
            f"[bold bright_white]{ticker}[/]",
            sector_text,
            price_str,
            delta_str,
            pct_str,
            session_str,
            arrow,
            vol_str,
            spark_str,
        )

    return table


def build_stats_panel(
    cache: PriceCache,
    session_opens: dict[str, float],
    tick_count: int,
    event_count: int,
) -> Panel:
    """Mini stats bar: portfolio-level aggregates."""
    winners = 0
    losers = 0
    flat = 0
    for ticker in TICKERS:
        u = cache.get(ticker)
        if u is None:
            continue
        if u.direction == "up":
            winners += 1
        elif u.direction == "down":
            losers += 1
        else:
            flat += 1

    total = winners + losers + flat or 1
    breadth_color = "green" if winners > losers else ("red" if losers > winners else "bright_black")

    parts = [
        Text.assemble(
            ("Tickers  ", "bright_black"),
            (f"{len(cache)}", "bold bright_white"),
        ),
        Text.assemble(
            ("Ticks  ", "bright_black"),
            (f"{tick_count:,}", "bold bright_cyan"),
        ),
        Text.assemble(
            ("Events  ", "bright_black"),
            (f"{event_count}", "bold bright_yellow"),
        ),
        Text.assemble(
            ("Advancers  ", "bright_black"),
            (f"{winners}", "green"),
            (" / ", "bright_black"),
            (f"{losers}", "red"),
            (" / ", "bright_black"),
            (f"{flat}", "bright_black"),
        ),
        Text.assemble(
            ("Breadth  ", "bright_black"),
            (f"{winners/total*100:.0f}% up", breadth_color),
        ),
    ]
    return Panel(
        Columns(parts, equal=False, expand=True, padding=(0, 3)),
        border_style="bright_black",
        title="[bold bright_white]Market Stats[/]",
        height=3,
    )


def build_event_log(events: deque) -> Panel:
    text = Text()
    for evt in list(events):
        text.append(evt)
        text.append("\n")
    if not events:
        text.append("Watching for notable moves (≥1.0% per tick)…", style="bright_black italic")
    return Panel(
        text,
        title="[bold bright_yellow]Notable Moves[/]",
        border_style="bright_black",
        height=8,
    )


def build_dashboard(
    cache: PriceCache,
    history: dict[str, deque],
    session_opens: dict[str, float],
    events: deque,
    tick_count: int,
    event_count: int,
    start_time: float,
) -> Layout:
    elapsed = time.time() - start_time

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="stats", size=3),
        Layout(name="footer", size=8),
    )

    # Header
    h = Text.assemble(
        ("  FinAlly ", "bold bright_yellow"),
        ("Market Simulator", "bold bright_white"),
        ("  │  ", "bright_black"),
        (f"uptime {int(elapsed//60):02d}:{int(elapsed%60):02d}", "bright_cyan"),
        ("  │  ", "bright_black"),
        ("GBM + Cholesky correlation", "bright_black italic"),
        ("  │  ", "bright_black"),
        ("Ctrl+C to quit", "bright_black italic"),
    )
    layout["header"].update(Panel(h, border_style="bright_yellow", padding=(0, 1)))

    layout["body"].update(
        Panel(
            build_table(cache, history, session_opens, tick_count),
            title="[bold bright_white]Live Prices[/]",
            border_style="bright_black",
        )
    )

    layout["stats"].update(build_stats_panel(cache, session_opens, tick_count, event_count))
    layout["footer"].update(build_event_log(events))

    return layout


def print_summary(cache: PriceCache, session_opens: dict[str, float], elapsed: float) -> None:
    console = Console()
    console.print()
    console.rule("[bold bright_yellow]  FinAlly  Session Summary[/]")
    console.print(
        f"  Duration: [bright_cyan]{int(elapsed//60):02d}m {int(elapsed%60):02d}s[/]   "
        f"Tickers: [bright_white]{len(cache)}[/]"
    )
    console.print()

    table = Table(border_style="bright_black", header_style="bold bright_white", expand=False)
    table.add_column("Ticker", style="bold bright_white", width=8)
    table.add_column("Open", justify="right", width=10)
    table.add_column("Close", justify="right", width=10)
    table.add_column("Session Δ", justify="right", width=10)
    table.add_column("Session %", justify="right", width=10)
    table.add_column("Seed Price", justify="right", width=10)
    table.add_column("vs Seed", justify="right", width=10)

    for ticker in TICKERS:
        update = cache.get(ticker)
        if update is None:
            continue
        open_price = session_opens.get(ticker, update.price)
        close = update.price
        seed = SEED_PRICES.get(ticker, open_price)

        sess_delta = close - open_price
        sess_pct = (sess_delta / open_price * 100) if open_price else 0.0
        seed_pct = ((close - seed) / seed * 100) if seed else 0.0

        sc = "green" if sess_pct > 0 else ("red" if sess_pct < 0 else "bright_black")
        vc = "green" if seed_pct > 0 else ("red" if seed_pct < 0 else "bright_black")

        table.add_row(
            ticker,
            f"${fmt(open_price)}",
            f"[{sc}]${fmt(close)}[/]",
            f"[{sc}]{sess_delta:+.2f}[/]",
            f"[{sc}]{sess_pct:+.2f}%[/]",
            f"${fmt(seed)}",
            f"[{vc}]{seed_pct:+.2f}%[/]",
        )

    console.print(table)
    console.print()


async def run() -> None:
    cache = PriceCache()
    source = SimulatorDataSource(price_cache=cache, update_interval=0.5)

    history: dict[str, deque] = {t: deque(maxlen=40) for t in TICKERS}
    events: deque = deque(maxlen=10)
    event_count = 0
    tick_count = 0

    await source.start(TICKERS)
    start_time = time.time()

    # Capture session-open prices after first seed
    session_opens: dict[str, float] = {}
    for ticker in TICKERS:
        u = cache.get(ticker)
        if u:
            session_opens[ticker] = u.price
            history[ticker].append(u.price)

    try:
        with Live(
            build_dashboard(cache, history, session_opens, events, tick_count, event_count, start_time),
            refresh_per_second=4,
            screen=True,
        ) as live:
            last_version = cache.version
            while True:
                await asyncio.sleep(0.25)

                if cache.version == last_version:
                    continue
                last_version = cache.version
                tick_count += 1

                for ticker in TICKERS:
                    u = cache.get(ticker)
                    if u is None:
                        continue
                    history[ticker].append(u.price)

                    if abs(u.change_percent) >= 1.0:
                        event_count += 1
                        col = "green" if u.direction == "up" else "red"
                        arr = "▲" if u.direction == "up" else "▼"
                        ts = time.strftime("%H:%M:%S")
                        events.appendleft(
                            f"[bright_black]{ts}[/]  "
                            f"[bold {col}]{arr} {ticker}[/]  "
                            f"[{col}]{u.change_percent:+.2f}%[/]  "
                            f"[bright_white]${fmt(u.price)}[/]"
                        )

                live.update(
                    build_dashboard(
                        cache, history, session_opens, events,
                        tick_count, event_count, start_time,
                    )
                )

    except KeyboardInterrupt:
        pass
    finally:
        await source.stop()

    print_summary(cache, session_opens, time.time() - start_time)


if __name__ == "__main__":
    asyncio.run(run())
