# src/main_find50.py
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Sequence, Tuple, Dict, Any

from data.alpha_vantage import AlphaVantageClient
from data.universe import discover_universe_for_sectors, fast_screen_with_quotes

# Buffett stack (repo-native adapter with fallbacks)
from pipeline.buffett_stack import evaluate_with_buffett_stack


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sector picks with Buffett-style gating & MOS")
    p.add_argument("--sectors", type=str, required=True, help="Comma list, e.g. 'Defence,Energy'")
    p.add_argument("--exchanges", type=str, default="NYSE,NASDAQ,AMEX")
    p.add_argument("--names-per-sector", type=int, default=3)
    p.add_argument("--capital", type=float, default=100.0)
    p.add_argument("--fast", action="store_true", help="Use quote-only fast screen")
    p.add_argument("--pool-cap", type=int, default=600)
    p.add_argument("--pause-sec", type=float, default=12.0)
    p.add_argument("--price-source", type=str, default="alphavantage",
                   choices=["alphavantage", "yfinance"], help="Where to fetch quotes for fast screen")
    p.add_argument("--export", type=str, default="", help="Append results to CSV path")
    p.add_argument("--thesis", action="store_true", help="Emit thesis per passing pick")

    # Buffett stack switch + thresholds
    p.add_argument("--use-buffett-stack", action="store_true",
                   help="Use repo agents (or fallbacks) for MOS filtering (no AV fundamentals).")
    p.add_argument("--mos-threshold", type=float, default=50.0,
                   help="Minimum upside (percent) required.")
    p.add_argument("--stack-cap", type=int, default=8,
                   help="Max symbols per sector to send through Buffett stack (after ranking).")

    # NEW: save factors
    p.add_argument("--save-factors", type=str, default="",
                   help="Path to append factor/valuation rows as CSV (e.g., runs/factors.csv)")
    return p.parse_args()


def append_rows(path: Path, rows: List[Tuple[str, str, str, float, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "sector", "symbol", "metric_value", "source"])
        for ts, sector, symbol, val, src in rows:
            w.writerow([ts, sector, symbol, f"{val:.4f}", src])


def write_factors(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    headers = sorted({k for r in rows for k in r.keys()})
    new_file = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(headers)
        for r in rows:
            w.writerow([r.get(k, "") for k in headers])


def main() -> None:
    args = parse_args()
    sectors: Sequence[str] = [s.strip() for s in args.sectors.split(",") if s.strip()]
    exchanges: Sequence[str] = [e.strip() for e in args.exchanges.split(",") if e.strip()]

    av = AlphaVantageClient(pause_sec=args.pause_sec)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    print("[main] Discovering universe by sector…", flush=True)
    universe_by_sector = discover_universe_for_sectors(
        av=av,
        sectors=sectors,
        exchanges=exchanges,
        names_per_sector=args.names_per_sector,
        pool_cap=args.pool_cap,
        use_fast=args.fast,
    )

    export_rows: List[Tuple[str, str, str, float, str]] = []
    factor_rows: List[Dict[str, Any]] = []

    for sector in sectors:
        cands: List[str] = universe_by_sector.get(sector, [])
        print(f"[main] Screening sector: {sector} (candidates: {len(cands)})", flush=True)
        if not cands:
            continue

        ranked = fast_screen_with_quotes(
            av,
            cands,
            price_source=args.price_source,
            pause_sec=args.pause_sec if args.price_source == "alphavantage" else 0.0,
        )

        # ---- Buffett stack path (recommended) ----
        if args.use_buffett_stack:
            to_eval = ranked[: max(1, args.stack_cap)]
            print(f"[buffett] Evaluating {len(to_eval)} symbols in {sector} (MOS ≥ {args.mos_threshold:.0f}%)…", flush=True)

            kept: List[Tuple[str, float, Dict[str, Any]]] = []  # (sym, mos_up, buffett_dict)

            for idx, (sym, _pct) in enumerate(to_eval, 1):
                print(f"[buffett] ({idx}/{len(to_eval)}) {sym}: run valuation + Buffett…", flush=True)
                out = evaluate_with_buffett_stack(sym)
                if not out:
                    print("           -> no data / not enough to value", flush=True)
                    continue

                mos = out.mos_upside_pct
                sig = (out.buffett or {}).get("signal")
                conf = (out.buffett or {}).get("confidence")
                reason = (out.buffett or {}).get("reasoning")

                # Persist factors incl. score from summary table
                factor_rows.append({
                    "timestamp": ts, "sector": sector, "symbol": sym,
                    "price": out.price, "market_cap": out.market_cap,
                    "intrinsic_value": out.intrinsic_value,
                    "mos_upside_pct": mos, "buffett_signal": sig, "buffett_confidence": conf,
                    "summary_score": f"{out.score_passes}/{out.score_total}",
                })

                if mos is not None and mos >= args.mos_threshold and sig == "bullish":
                    kept.append((sym, float(mos), out.buffett or {}))
                    print(f"           -> PASS: MOS {mos:.1f}%  Buffett={sig} ({conf})", flush=True)
                    if args.thesis:
                        report = Path("reports") / f"{ts.replace(':','-')}_{sector}_{sym}_buffett.md"
                        report.parent.mkdir(parents=True, exist_ok=True)
                        # Combined narrative + summary table
                        md_parts = []
                        if reason:
                            md_parts.append(str(reason).strip())
                        md_parts.append(out.summary_md)
                        report.write_text("\n\n".join(md_parts).strip() + "\n")
                        print(f"              -> thesis: {report}", flush=True)
                else:
                    why = []
                    if mos is None or mos < args.mos_threshold:
                        why.append(f"MOS<{args.mos_threshold:.0f}%")
                    if sig != "bullish":
                        why.append(f"Signal={sig}")
                    print(f"           -> FAIL: {', '.join(why) or 'unknown'}", flush=True)

            kept.sort(key=lambda t: t[1], reverse=True)
            topk = kept[: args.names_per_sector]
            print(f"[result] {sector} – Buffett bullish & MOS≥{args.mos_threshold:.0f}%: {len(topk)} picks")
            for sym, mos, _buf in topk:
                print(f"  {sym:6s}  MOS {mos:.1f}%")
                export_rows.append((ts, sector, sym, mos, "buffett_stack"))
            continue

        # ---- Fast-only branch (if you don't use the Buffett stack) ----
        topn = ranked[: args.names_per_sector]
        print(f"[result] {sector} – top {len(topn)} by daily change% ({args.price_source}):")
        for sym, pct in topn:
            print(f"  {sym:6s}  Δ{pct:.2f}%")
            export_rows.append((ts, sector, sym, pct, f"fast:{args.price_source}"))

    if args.export and export_rows:
        Path(args.export).parent.mkdir(parents=True, exist_ok=True)
        append_rows(Path(args.export), export_rows)
        print(f"[export] wrote {len(export_rows)} rows → {args.export}")

    if args.save_factors and factor_rows:
        write_factors(Path(args.save_factors), factor_rows)
        print(f"[factors] wrote {len(factor_rows)} rows → {args.save_factors}")


if __name__ == "__main__":
    main()
