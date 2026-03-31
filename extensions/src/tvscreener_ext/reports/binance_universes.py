from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


@dataclass(frozen=True, slots=True)
class BinanceUniversesReportPaths:
    out_dir: Path
    report_json: Path
    report_md: Path
    rows_parquet: Path
    summary_parquet: Path
    ticker_volumes_parquet: Path
    base_volumes_parquet: Path
    volume_bins_parquet: Path
    risky_assets_parquet: Path
    spot_quote_breakdown_parquet: Path
    strategy_readiness_parquet: Path


def _now_stamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")


def _quote_asset_from_ticker(ticker: str) -> str:
    sym = (ticker or "").split(":", 1)[-1]
    if sym.endswith(".P"):
        sym = sym[: -len(".P")]
    for q in ("USDT", "USDC", "BTC", "ETH", "FDUSD", "TRY", "BRL", "EUR", "JPY", "GBP"):
        if sym.endswith(q):
            return q
    return "OTHER"


def _base_from_ticker(ticker: str) -> str | None:
    sym = (ticker or "").split(":", 1)[-1]
    if sym.endswith(".P"):
        sym = sym[: -len(".P")]
    quote = _quote_asset_from_ticker(ticker)
    if quote == "OTHER":
        return None
    if not sym.endswith(quote):
        return None
    base = sym[: -len(quote)]
    return base or None


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "(no rows)"

    cols = [str(c) for c in df.columns]
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(["" if v is None else str(v) for v in row]) + " |")
    return "\n".join(lines)


def load_universe_jsons(in_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Loads universe.json files under an audit dir.

    Expected layout:
      <in_dir>/<universe-name>/universe.json
    """

    meta_rows: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    for uni_dir in sorted([p for p in in_dir.iterdir() if p.is_dir()]):
        if not uni_dir.name.startswith("binance_"):
            continue
        uni_path = uni_dir / "universe.json"
        if not uni_path.exists():
            continue

        payload = json.loads(uni_path.read_text(encoding="utf-8"))
        universe = uni_dir.name
        constraints = payload.get("constraints", {}) if isinstance(payload, dict) else {}

        diagnostics = payload.get("diagnostics", {}) if isinstance(payload, dict) else {}
        if not isinstance(diagnostics, dict):
            diagnostics = {}

        missing_tickers = payload.get("missing_tickers", []) or []
        missing_bases = payload.get("missing_bases", []) or []
        included_bases = payload.get("included_bases", []) or []
        excluded_risky = payload.get("excluded_risky", []) or []

        meta_rows.append(
            {
                "universe": universe,
                "selection": constraints.get("selection"),
                "instrument_type": constraints.get("instrument_type"),
                "count": payload.get("count"),
                "requested_tickers": len(payload.get("requested_tickers", []) or []),
                "missing_tickers": len(missing_tickers),
                "included_bases": len(included_bases),
                "missing_bases": len(missing_bases),
                "excluded_risky": len(excluded_risky) if isinstance(excluded_risky, list) else None,
                "excluded_risky_sample": (
                    ",".join(
                        [str(x.get("Symbol")) for x in excluded_risky[:25] if isinstance(x, dict)]
                    )
                    if isinstance(excluded_risky, list)
                    else ""
                ),
                "diag_candidates_total": diagnostics.get("candidates_total"),
                "diag_quote_asset_matched": diagnostics.get("candidates_quote_asset_matched"),
                "diag_pass_min_volume": diagnostics.get("candidates_pass_min_volume"),
                "diag_after_exclusions": diagnostics.get("candidates_after_exclusions"),
                "diag_after_dedup_bases": diagnostics.get("candidates_after_dedup_bases"),
                "diag_selected_count": diagnostics.get("selected_count"),
                "diag_volatility_native_nonnull": diagnostics.get("volatility_native_nonnull"),
                "diag_volatility_proxy_used": diagnostics.get("volatility_proxy_used"),
                "missing_tickers_sample": ",".join([str(x) for x in missing_tickers[:25]]),
                "missing_bases_sample": ",".join([str(x) for x in missing_bases[:25]]),
                "included_bases_sample": ",".join([str(x) for x in included_bases[:25]]),
                "universe_json": str(uni_path),
            }
        )

        for r in payload.get("rows", []) or []:
            ticker = str(r.get("ticker") or r.get("Symbol") or "")
            if not ticker:
                continue
            rows.append(
                {
                    "universe": universe,
                    "ticker": ticker,
                    "instrument_type": r.get("instrument_type")
                    or constraints.get("instrument_type"),
                    "base": r.get("base") or _base_from_ticker(ticker),
                    "quote_asset": r.get("quote_asset") or _quote_asset_from_ticker(ticker),
                    "quote_volume_usd": r.get("quote_volume_usd"),
                    "volatility_24h_pct": r.get("volatility_24h_pct"),
                    "meets_min_volatility": r.get("meets_min_volatility"),
                    "history_days": r.get("history_days"),
                    "entity_id": r.get("entity_id"),
                }
            )

    meta_df = pd.DataFrame(meta_rows)
    rows_df = pd.DataFrame(rows)

    if not rows_df.empty:
        rows_df["quote_volume_usd"] = pd.to_numeric(rows_df["quote_volume_usd"], errors="coerce")
        rows_df["volatility_24h_pct"] = pd.to_numeric(
            rows_df["volatility_24h_pct"], errors="coerce"
        )
        if "history_days" in rows_df.columns:
            rows_df["history_days"] = pd.to_numeric(rows_df["history_days"], errors="coerce")

    return meta_df, rows_df


def generate_binance_universes_report(
    *,
    in_dir: str | Path = "artifacts/audits/binance-universes",
    out_dir: str | Path = "artifacts/reports/binance-universes",
    stamp: str | None = None,
) -> BinanceUniversesReportPaths:
    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    stamp = stamp or _now_stamp()

    report_dir = out_dir / stamp
    report_dir.mkdir(parents=True, exist_ok=True)

    paths = BinanceUniversesReportPaths(
        out_dir=report_dir,
        report_json=report_dir / "report.json",
        report_md=report_dir / "report.md",
        rows_parquet=report_dir / "rows.parquet",
        summary_parquet=report_dir / "summary.parquet",
        ticker_volumes_parquet=report_dir / "ticker_volumes.parquet",
        base_volumes_parquet=report_dir / "base_volumes.parquet",
        volume_bins_parquet=report_dir / "volume_bins.parquet",
        risky_assets_parquet=report_dir / "risky_assets.parquet",
        spot_quote_breakdown_parquet=report_dir / "spot_quote_breakdown.parquet",
        strategy_readiness_parquet=report_dir / "strategy_readiness.parquet",
    )

    meta_df, rows_df = load_universe_jsons(in_dir)

    con = duckdb.connect(database=":memory:")
    con.register("meta", meta_df)
    if rows_df.empty:
        summary_df = pd.DataFrame()
        top100_diagnostics_df = pd.DataFrame()
        volume_percentiles_df = pd.DataFrame()
        volume_top_assets_df = pd.DataFrame()
        ticker_volumes_df = pd.DataFrame()
        base_volumes_df = pd.DataFrame()
        volume_bins_df = pd.DataFrame()
        risky_assets_df = pd.DataFrame()
        spot_quote_breakdown_df = pd.DataFrame()
        strategy_readiness_df = pd.DataFrame()
        scanner_readiness_df = pd.DataFrame()
        quote_dist_df = pd.DataFrame()
        overlap_df = pd.DataFrame()
        base_overlap_df = pd.DataFrame()
        spot_top100_quote_overview_df = pd.DataFrame()
        spot_perp_parity_df = pd.DataFrame()
    else:
        con.register("rows", rows_df)

        summary_df = con.execute(
            """
            WITH stats AS (
              SELECT
                universe,
                count(*) AS ticker_count,
                count(DISTINCT base) AS base_count,
                count(*) - count(DISTINCT base) AS duplicate_base_tickers,
                min(quote_volume_usd) AS min_quote_volume_usd,
                quantile_cont(quote_volume_usd, 0.5) AS median_quote_volume_usd,
                quantile_cont(quote_volume_usd, 0.95) AS p95_quote_volume_usd,
                min(volatility_24h_pct) AS min_volatility_24h_pct,
                quantile_cont(volatility_24h_pct, 0.5) AS median_volatility_24h_pct,
                quantile_cont(volatility_24h_pct, 0.95) AS p95_volatility_24h_pct
              FROM rows
              GROUP BY universe
            )
            SELECT
              stats.universe,
              meta.selection,
              meta.instrument_type,
              meta.count AS declared_count,
              meta.requested_tickers,
              meta.missing_tickers,
              meta.included_bases,
              meta.missing_bases,
              meta.excluded_risky,
              stats.ticker_count,
              stats.base_count,
              stats.duplicate_base_tickers,
              stats.min_quote_volume_usd,
              stats.median_quote_volume_usd,
              stats.p95_quote_volume_usd,
              stats.min_volatility_24h_pct,
              stats.median_volatility_24h_pct,
              stats.p95_volatility_24h_pct
            FROM stats
            LEFT JOIN meta USING (universe)
            ORDER BY stats.universe
            """
        ).df()

        top100_diagnostics_df = con.execute(
            """
            SELECT
              universe,
              selection,
              instrument_type,
              diag_candidates_total,
              diag_quote_asset_matched,
              diag_pass_min_volume,
              diag_selected_count,
              diag_after_exclusions,
              diag_after_dedup_bases,
              diag_volatility_native_nonnull,
              diag_volatility_proxy_used
            FROM meta
            WHERE universe IN ('binance_spot_top100', 'binance_perp_top100')
            ORDER BY universe
            """
        ).df()

        volume_percentiles_df = con.execute(
            """
            SELECT
              universe,
              count(*) AS ticker_count,
              min(quote_volume_usd) AS min_quote_volume_usd,
              quantile_cont(quote_volume_usd, 0.10) AS p10_quote_volume_usd,
              quantile_cont(quote_volume_usd, 0.25) AS p25_quote_volume_usd,
              quantile_cont(quote_volume_usd, 0.50) AS p50_quote_volume_usd,
              quantile_cont(quote_volume_usd, 0.75) AS p75_quote_volume_usd,
              quantile_cont(quote_volume_usd, 0.90) AS p90_quote_volume_usd,
              quantile_cont(quote_volume_usd, 0.95) AS p95_quote_volume_usd,
              quantile_cont(quote_volume_usd, 0.99) AS p99_quote_volume_usd,
              max(quote_volume_usd) AS max_quote_volume_usd
            FROM rows
            GROUP BY universe
            ORDER BY universe
            """
        ).df()

        volume_top_assets_df = con.execute(
            """
            WITH ranked AS (
              SELECT
                universe,
                ticker,
                base,
                quote_asset,
                quote_volume_usd,
                volatility_24h_pct,
                row_number() OVER (
                  PARTITION BY universe
                  ORDER BY quote_volume_usd DESC NULLS LAST, ticker
                ) AS volume_rank
              FROM rows
            )
            SELECT
              universe,
              volume_rank,
              ticker,
              base,
              quote_asset,
              quote_volume_usd,
              volatility_24h_pct
            FROM ranked
            WHERE volume_rank <= 25
            ORDER BY universe, volume_rank
            """
        ).df()

        ticker_volumes_df = con.execute(
            """
            SELECT
              universe,
              dense_rank() OVER (
                PARTITION BY universe
                ORDER BY quote_volume_usd DESC NULLS LAST, ticker
              ) AS volume_rank,
              ticker,
              base,
              quote_asset,
              quote_volume_usd,
              volatility_24h_pct
            FROM rows
            ORDER BY universe, volume_rank
            """
        ).df()

        base_volumes_df = con.execute(
            """
            WITH agg AS (
              SELECT
                universe,
                base,
                count(*) AS ticker_count,
                sum(quote_volume_usd) AS base_quote_volume_usd,
                max(quote_volume_usd) AS max_ticker_quote_volume_usd,
                quantile_cont(volatility_24h_pct, 0.5) AS median_volatility_24h_pct
              FROM rows
              WHERE base IS NOT NULL
              GROUP BY universe, base
            )
            SELECT
              universe,
              dense_rank() OVER (
                PARTITION BY universe
                ORDER BY base_quote_volume_usd DESC NULLS LAST, base
              ) AS base_volume_rank,
              base,
              ticker_count,
              base_quote_volume_usd,
              max_ticker_quote_volume_usd,
              median_volatility_24h_pct
            FROM agg
            ORDER BY universe, base_volume_rank
            """
        ).df()

        volume_bins_df = con.execute(
            """
            WITH labeled AS (
              SELECT
                universe,
                CASE
                  WHEN quote_volume_usd < 5e6 THEN '<5M'
                  WHEN quote_volume_usd < 1e7 THEN '5-10M'
                  WHEN quote_volume_usd < 2.5e7 THEN '10-25M'
                  WHEN quote_volume_usd < 5e7 THEN '25-50M'
                  WHEN quote_volume_usd < 1e8 THEN '50-100M'
                  WHEN quote_volume_usd < 2.5e8 THEN '100-250M'
                  WHEN quote_volume_usd < 5e8 THEN '250-500M'
                  WHEN quote_volume_usd < 1e9 THEN '500M-1B'
                  WHEN quote_volume_usd < 2.5e9 THEN '1-2.5B'
                  WHEN quote_volume_usd < 5e9 THEN '2.5-5B'
                  ELSE '>5B'
                END AS volume_bin
              FROM rows
              WHERE quote_volume_usd IS NOT NULL
            )
            SELECT universe, volume_bin, count(*) AS n
            FROM labeled
            GROUP BY universe, volume_bin
            ORDER BY universe,
              CASE volume_bin
                WHEN '<5M' THEN 1
                WHEN '5-10M' THEN 2
                WHEN '10-25M' THEN 3
                WHEN '25-50M' THEN 4
                WHEN '50-100M' THEN 5
                WHEN '100-250M' THEN 6
                WHEN '250-500M' THEN 7
                WHEN '500M-1B' THEN 8
                WHEN '1-2.5B' THEN 9
                WHEN '2.5-5B' THEN 10
                WHEN '>5B' THEN 11
                ELSE 99
              END
            """
        ).df()

        risky_assets_df = con.execute(
            """
            WITH mcap AS (
              SELECT DISTINCT base
              FROM rows
              WHERE universe IN ('binance_spot_mcap_top100', 'binance_perp_mcap_top100')
                AND base IS NOT NULL
            ),
            tradeable AS (
              SELECT
                universe,
                ticker,
                base,
                quote_asset,
                quote_volume_usd,
                volatility_24h_pct,
                history_days
              FROM rows
              WHERE universe IN ('binance_spot_tradeable_base', 'binance_perp_tradeable_base')
            )
            SELECT
              tradeable.universe,
              tradeable.ticker,
              tradeable.base,
              tradeable.quote_asset,
              tradeable.quote_volume_usd,
              tradeable.volatility_24h_pct,
              tradeable.history_days,
              CASE WHEN mcap.base IS NULL THEN 1 ELSE 0 END AS is_non_mcap_top100
            FROM tradeable
            LEFT JOIN mcap USING (base)
            WHERE mcap.base IS NULL
              AND tradeable.history_days IS NOT NULL
            ORDER BY tradeable.universe, tradeable.quote_volume_usd DESC NULLS LAST
            """
        ).df()

        spot_quote_breakdown_df = con.execute(
            """
            SELECT
              universe,
              quote_asset,
              count(*) AS ticker_count,
              count(DISTINCT base) AS base_count,
              count(*) - count(DISTINCT base) AS duplicate_base_tickers,
              sum(quote_volume_usd) AS total_quote_volume_usd,
              min(quote_volume_usd) AS min_quote_volume_usd,
              quantile_cont(quote_volume_usd, 0.5) AS median_quote_volume_usd,
              quantile_cont(quote_volume_usd, 0.95) AS p95_quote_volume_usd,
              max(quote_volume_usd) AS max_quote_volume_usd,
              quantile_cont(volatility_24h_pct, 0.5) AS median_volatility_24h_pct
            FROM rows
            WHERE instrument_type = 'spot'
              AND quote_asset IS NOT NULL
            GROUP BY universe, quote_asset
            ORDER BY universe, total_quote_volume_usd DESC NULLS LAST, quote_asset
            """
        ).df()

        strategy_readiness_df = con.execute(
            """
            WITH base_universes AS (
              SELECT
                universe,
                selection,
                instrument_type,
                excluded_risky,
                ticker_count,
                base_count,
                duplicate_base_tickers,
                min_quote_volume_usd,
                median_quote_volume_usd
              FROM (
                WITH stats AS (
                  SELECT
                    universe,
                    count(*) AS ticker_count,
                    count(DISTINCT base) AS base_count,
                    count(*) - count(DISTINCT base) AS duplicate_base_tickers,
                    min(quote_volume_usd) AS min_quote_volume_usd,
                    quantile_cont(quote_volume_usd, 0.5) AS median_quote_volume_usd
                  FROM rows
                  GROUP BY universe
                )
                SELECT
                  stats.universe,
                  meta.selection,
                  meta.instrument_type,
                  meta.excluded_risky,
                  stats.ticker_count,
                  stats.base_count,
                  stats.duplicate_base_tickers,
                  stats.min_quote_volume_usd,
                  stats.median_quote_volume_usd
                FROM stats
                LEFT JOIN meta USING (universe)
              )
              WHERE selection IN ('tradeable_base', 'tradeable_mcap_overlap', 'tradeable_mcap_tier')
            ),
            quote_ok AS (
              SELECT
                universe,
                bool_and(quote_asset IN ('USDT','USDC')) AS quote_pure_usd
              FROM rows
              WHERE universe IN (SELECT universe FROM base_universes)
              GROUP BY universe
            ),
            parity AS (
              SELECT
                family,
                spot_bases,
                perp_bases,
                overlap_bases,
                CASE
                  WHEN greatest(spot_bases, perp_bases) = 0 THEN NULL
                  ELSE overlap_bases * 1.0 / greatest(spot_bases, perp_bases)
                END AS overlap_ratio
              FROM (
                WITH universe_summary AS (
                  SELECT
                    universe,
                    any_value(instrument_type) AS instrument_type,
                    regexp_replace(universe, '^binance_(spot|perp)_', '') AS family,
                    count(DISTINCT base) AS base_count
                  FROM rows
                  GROUP BY universe
                ),
                spot AS (
                  SELECT family, base_count AS spot_bases
                  FROM universe_summary
                  WHERE instrument_type = 'spot'
                    AND family IN ('tradeable_base', 'tradeable_mcap_cs')
                ),
                perp AS (
                  SELECT family, base_count AS perp_bases
                  FROM universe_summary
                  WHERE instrument_type = 'perp'
                    AND family IN ('tradeable_base', 'tradeable_mcap_cs')
                ),
                bases AS (
                  SELECT DISTINCT universe, base
                  FROM rows
                  WHERE base IS NOT NULL
                ),
                base_overlap AS (
                  SELECT
                    regexp_replace(a.universe, '^binance_spot_', '') AS family,
                    count(*) AS overlap_bases
                  FROM bases a
                  JOIN bases b ON a.base = b.base
                  WHERE a.universe IN ('binance_spot_tradeable_base','binance_spot_tradeable_mcap_cs')
                    AND b.universe = regexp_replace(a.universe, '^binance_spot_', 'binance_perp_')
                  GROUP BY regexp_replace(a.universe, '^binance_spot_', '')
                )
                SELECT
                  spot.family,
                  spot.spot_bases,
                  perp.perp_bases,
                  coalesce(base_overlap.overlap_bases, 0) AS overlap_bases
                FROM spot
                JOIN perp USING (family)
                LEFT JOIN base_overlap USING (family)
              )
            )
            SELECT
              base_universes.universe,
              base_universes.selection,
              base_universes.instrument_type,
              base_universes.ticker_count,
              base_universes.base_count,
              base_universes.duplicate_base_tickers,
              quote_ok.quote_pure_usd,
              base_universes.excluded_risky,
              base_universes.min_quote_volume_usd,
              base_universes.median_quote_volume_usd,
              parity.overlap_ratio AS family_overlap_ratio,
              CASE
                WHEN base_universes.selection = 'tradeable_base' THEN 'strategy_base_default'
                WHEN base_universes.selection = 'tradeable_mcap_overlap' THEN 'strategy_base_cs_anchor'
                WHEN base_universes.selection = 'tradeable_mcap_tier' THEN 'strategy_base_mcap_tier'
                ELSE 'other'
              END AS role,
              CASE
                WHEN quote_ok.quote_pure_usd
                  AND base_universes.duplicate_base_tickers = 0
                  AND (
                    CASE
                      WHEN base_universes.selection = 'tradeable_mcap_tier' THEN base_universes.ticker_count >= 10
                      ELSE base_universes.ticker_count >= 20
                    END
                  )
                THEN true
                ELSE false
              END AS is_strategy_ready_default
            FROM base_universes
            LEFT JOIN quote_ok USING (universe)
            LEFT JOIN parity
              ON parity.family = regexp_replace(base_universes.universe, '^binance_(spot|perp)_', '')
            ORDER BY base_universes.universe
            """
        ).df()

        scanner_readiness_df = con.execute(
            """
            WITH stats AS (
              SELECT
                universe,
                count(*) AS ticker_count,
                count(DISTINCT base) AS base_count,
                count(*) - count(DISTINCT base) AS duplicate_base_tickers,
                min(quote_volume_usd) AS min_quote_volume_usd,
                quantile_cont(quote_volume_usd, 0.25) AS p25_quote_volume_usd,
                quantile_cont(quote_volume_usd, 0.5) AS median_quote_volume_usd
              FROM rows
              GROUP BY universe
            ),
            u AS (
              SELECT
                stats.universe,
                meta.selection,
                meta.instrument_type,
                meta.excluded_risky,
                stats.ticker_count,
                stats.base_count,
                stats.duplicate_base_tickers,
                stats.min_quote_volume_usd,
                stats.p25_quote_volume_usd,
                stats.median_quote_volume_usd,
                CASE
                  WHEN stats.universe LIKE '%_majors' THEN 'majors'
                  WHEN stats.universe LIKE '%_minors' THEN 'minors'
                  ELSE NULL
                END AS tier
              FROM stats
              LEFT JOIN meta USING (universe)
            ),
            quote_ok AS (
              SELECT
                universe,
                bool_and(quote_asset IN ('USDT','USDC')) AS quote_pure_usd
              FROM rows
              GROUP BY universe
            )
            SELECT
              u.universe,
              u.selection,
              u.instrument_type,
              u.tier,
              u.ticker_count,
              u.base_count,
              u.duplicate_base_tickers,
              quote_ok.quote_pure_usd,
              u.excluded_risky,
              u.min_quote_volume_usd,
              u.p25_quote_volume_usd,
              u.median_quote_volume_usd,
              CASE
                WHEN u.selection IN ('tradeable_base','tradeable_mcap_overlap','tradeable_mcap_tier')
                THEN true
                ELSE false
              END AS is_strategy_input_universe,
              CASE
                WHEN quote_ok.quote_pure_usd
                  AND u.duplicate_base_tickers = 0
                  AND (
                    CASE
                      WHEN u.selection = 'tradeable_mcap_tier' AND u.tier = 'majors' THEN u.ticker_count >= 10
                      WHEN u.selection = 'tradeable_mcap_tier' THEN u.ticker_count >= 20
                      ELSE u.ticker_count >= 20
                    END
                  )
                THEN true
                ELSE false
              END AS is_strategy_ready,
              CASE
                WHEN quote_ok.quote_pure_usd
                  AND u.duplicate_base_tickers = 0
                  AND (
                    CASE
                      WHEN u.selection = 'tradeable_mcap_tier' AND u.tier = 'majors' THEN u.ticker_count >= 10
                      ELSE u.ticker_count >= 20
                    END
                  )
                  AND (
                    CASE
                      WHEN u.instrument_type = 'spot' THEN u.p25_quote_volume_usd >= 2.5e6
                      WHEN u.instrument_type = 'perp' THEN u.p25_quote_volume_usd >= 2.0e7
                      ELSE false
                    END
                  )
                THEN true
                ELSE false
              END AS is_opportunity_ready,
              CASE
                WHEN u.selection IN ('tradeable_mcap_overlap','tradeable_mcap_tier') THEN true
                ELSE false
              END AS is_cross_section_anchor,
              CASE
                WHEN u.selection = 'tradeable_base' AND coalesce(u.excluded_risky, 0) > 0 THEN true
                WHEN u.selection != 'tradeable_base' THEN NULL
                ELSE false
              END AS has_risky_exclusions
            FROM u
            LEFT JOIN quote_ok USING (universe)
            ORDER BY u.universe
            """
        ).df()

        quote_dist_df = con.execute(
            """
            SELECT universe, quote_asset, count(*) AS n
            FROM rows
            GROUP BY universe, quote_asset
            ORDER BY universe, n DESC, quote_asset
            """
        ).df()

        overlap_df = con.execute(
            """
            SELECT a.universe AS a, b.universe AS b, count(*) AS overlap
            FROM rows a
            JOIN rows b
              ON a.ticker = b.ticker
            GROUP BY a.universe, b.universe
            ORDER BY a.universe, b.universe
            """
        ).df()

        base_overlap_df = con.execute(
            """
            WITH bases AS (
              SELECT DISTINCT universe, base
              FROM rows
              WHERE base IS NOT NULL
            )
            SELECT a.universe AS a, b.universe AS b, count(*) AS overlap_bases
            FROM bases a
            JOIN bases b
              ON a.base = b.base
            GROUP BY a.universe, b.universe
            ORDER BY a.universe, b.universe
            """
        ).df()

        spot_top100_quote_overview_df = con.execute(
            """
            WITH spot AS (
              SELECT *
              FROM rows
              WHERE universe = 'binance_spot_top100'
            ),
            ranked AS (
              SELECT
                quote_asset,
                ticker,
                quote_volume_usd,
                row_number() OVER (
                  PARTITION BY quote_asset
                  ORDER BY quote_volume_usd DESC NULLS LAST, ticker
                ) AS rn
              FROM spot
            ),
            samples AS (
              SELECT
                quote_asset,
                string_agg(ticker, ', ') AS sample_tickers
              FROM ranked
              WHERE rn <= 10
              GROUP BY quote_asset
            )
            SELECT
              spot.quote_asset,
              count(*) AS ticker_count,
              count(DISTINCT spot.base) AS base_count,
              count(*) - count(DISTINCT spot.base) AS duplicate_base_tickers,
              min(spot.quote_volume_usd) AS min_quote_volume_usd,
              quantile_cont(spot.quote_volume_usd, 0.5) AS median_quote_volume_usd,
              quantile_cont(spot.quote_volume_usd, 0.95) AS p95_quote_volume_usd,
              min(spot.volatility_24h_pct) AS min_volatility_24h_pct,
              quantile_cont(spot.volatility_24h_pct, 0.5) AS median_volatility_24h_pct,
              quantile_cont(spot.volatility_24h_pct, 0.95) AS p95_volatility_24h_pct,
              any_value(samples.sample_tickers) AS sample_tickers
            FROM spot
            LEFT JOIN samples USING (quote_asset)
            GROUP BY spot.quote_asset
            ORDER BY ticker_count DESC, spot.quote_asset
            """
        ).df()

        spot_perp_parity_df = con.execute(
            """
            WITH universe_summary AS (
              SELECT
                universe,
                any_value(instrument_type) AS instrument_type,
                count(*) AS ticker_count,
                count(DISTINCT base) AS base_count,
                count(*) - count(DISTINCT base) AS duplicate_base_tickers,
                quantile_cont(quote_volume_usd, 0.5) AS median_quote_volume_usd,
                quantile_cont(volatility_24h_pct, 0.5) AS median_volatility_24h_pct
              FROM rows
              GROUP BY universe
            ),
            labeled AS (
              SELECT
                universe,
                meta.selection,
                universe_summary.instrument_type AS instrument_type,
                regexp_replace(universe, '^binance_(spot|perp)_', '') AS family,
                ticker_count,
                base_count,
                duplicate_base_tickers,
                median_quote_volume_usd,
                median_volatility_24h_pct
              FROM universe_summary
              LEFT JOIN meta USING (universe)
              WHERE universe LIKE 'binance_spot_%' OR universe LIKE 'binance_perp_%'
            ),
            spot AS (
              SELECT * FROM labeled WHERE instrument_type = 'spot'
            ),
            perp AS (
              SELECT * FROM labeled WHERE instrument_type = 'perp'
            ),
            base_overlap AS (
              SELECT
                regexp_replace(a, '^binance_spot_', '') AS family,
                overlap_bases
              FROM (
                SELECT * FROM (
                  WITH bases AS (
                    SELECT DISTINCT universe, base
                    FROM rows
                    WHERE base IS NOT NULL
                  )
                  SELECT
                    a.universe AS a,
                    b.universe AS b,
                    count(*) AS overlap_bases
                  FROM bases a
                  JOIN bases b ON a.base = b.base
                  GROUP BY a.universe, b.universe
                )
              )
              WHERE a LIKE 'binance_spot_%' AND b = regexp_replace(a, '^binance_spot_', 'binance_perp_')
            )
            SELECT
              spot.family,
              spot.universe AS spot_universe,
              perp.universe AS perp_universe,
              spot.selection,
              spot.ticker_count AS spot_tickers,
              perp.ticker_count AS perp_tickers,
              spot.base_count AS spot_bases,
              perp.base_count AS perp_bases,
              coalesce(base_overlap.overlap_bases, 0) AS overlap_bases,
              spot.duplicate_base_tickers AS spot_duplicate_bases,
              perp.duplicate_base_tickers AS perp_duplicate_bases,
              spot.median_quote_volume_usd AS spot_median_quote_volume_usd,
              perp.median_quote_volume_usd AS perp_median_quote_volume_usd,
              spot.median_volatility_24h_pct AS spot_median_volatility_24h_pct,
              perp.median_volatility_24h_pct AS perp_median_volatility_24h_pct
            FROM spot
            JOIN perp USING (family)
            LEFT JOIN base_overlap USING (family)
            ORDER BY spot.family
            """
        ).df()

    meta_out = meta_df.sort_values(["universe"]).to_dict(orient="records")
    payload = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "in_dir": str(in_dir),
        "universes": meta_out,
        "summary": summary_df.to_dict(orient="records"),
        "top100_diagnostics": top100_diagnostics_df.to_dict(orient="records"),
        "volume_percentiles": volume_percentiles_df.to_dict(orient="records"),
        "volume_top_assets": volume_top_assets_df.to_dict(orient="records"),
        "ticker_volumes": {
            "rows": ticker_volumes_df.to_dict(orient="records"),
            "parquet": str(paths.ticker_volumes_parquet),
        },
        "base_volumes": {
            "rows": base_volumes_df.to_dict(orient="records"),
            "parquet": str(paths.base_volumes_parquet),
        },
        "volume_bins": {
            "rows": volume_bins_df.to_dict(orient="records"),
            "parquet": str(paths.volume_bins_parquet),
        },
        "risky_assets": {
            "rows": risky_assets_df.to_dict(orient="records"),
            "parquet": str(paths.risky_assets_parquet),
        },
        "spot_quote_breakdown": {
            "rows": spot_quote_breakdown_df.to_dict(orient="records"),
            "parquet": str(paths.spot_quote_breakdown_parquet),
        },
        "strategy_readiness": {
            "rows": strategy_readiness_df.to_dict(orient="records"),
            "parquet": str(paths.strategy_readiness_parquet),
        },
        "scanner_readiness": scanner_readiness_df.to_dict(orient="records"),
        "quote_asset_dist": quote_dist_df.to_dict(orient="records"),
        "spot_top100_quote_overview": spot_top100_quote_overview_df.to_dict(orient="records"),
        "spot_perp_parity": spot_perp_parity_df.to_dict(orient="records"),
        "overlap": overlap_df.to_dict(orient="records"),
        "base_overlap": base_overlap_df.to_dict(orient="records"),
        "paths": {
            "rows_parquet": str(paths.rows_parquet),
            "summary_parquet": str(paths.summary_parquet),
            "ticker_volumes_parquet": str(paths.ticker_volumes_parquet),
            "base_volumes_parquet": str(paths.base_volumes_parquet),
            "volume_bins_parquet": str(paths.volume_bins_parquet),
            "risky_assets_parquet": str(paths.risky_assets_parquet),
            "spot_quote_breakdown_parquet": str(paths.spot_quote_breakdown_parquet),
            "strategy_readiness_parquet": str(paths.strategy_readiness_parquet),
        },
    }

    paths.report_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if not rows_df.empty:
        rows_df.to_parquet(paths.rows_parquet, index=False)
    if not summary_df.empty:
        summary_df.to_parquet(paths.summary_parquet, index=False)
    if not ticker_volumes_df.empty:
        ticker_volumes_df.to_parquet(paths.ticker_volumes_parquet, index=False)
    if not base_volumes_df.empty:
        base_volumes_df.to_parquet(paths.base_volumes_parquet, index=False)
    if not volume_bins_df.empty:
        volume_bins_df.to_parquet(paths.volume_bins_parquet, index=False)
    if not risky_assets_df.empty:
        risky_assets_df.to_parquet(paths.risky_assets_parquet, index=False)
    if not spot_quote_breakdown_df.empty:
        spot_quote_breakdown_df.to_parquet(paths.spot_quote_breakdown_parquet, index=False)
    if not strategy_readiness_df.empty:
        strategy_readiness_df.to_parquet(paths.strategy_readiness_parquet, index=False)

    md = [
        "# Binance Universe Report",
        "",
        f"Generated: `{payload['generated_at_utc']}`",
        f"Input: `{payload['in_dir']}`",
        "",
        "## Summary",
        "",
        _df_to_markdown_table(summary_df),
        "",
        "## Top100 Diagnostics",
        "",
        _df_to_markdown_table(top100_diagnostics_df),
        "",
        "## Volume Percentiles",
        "",
        _df_to_markdown_table(volume_percentiles_df),
        "",
        "## Volume Bins",
        "",
        _df_to_markdown_table(volume_bins_df),
        "",
        "## Top Volume Assets",
        "",
        "(Top 25 by `quote_volume_usd` per universe)",
        "",
        _df_to_markdown_table(volume_top_assets_df),
        "",
        "## All Asset Volumes",
        "",
        f"Ticker volumes: `{paths.ticker_volumes_parquet}`",
        f"Base volumes: `{paths.base_volumes_parquet}`",
        "",
        "## Risky Assets",
        "",
        "(Non-market-cap-top100 bases inside tradeable universes; requires `history_days`)",
        "",
        f"Risky assets parquet: `{paths.risky_assets_parquet}`",
        "",
        "## Spot Quote Breakdown",
        "",
        "(Spot universes grouped by `quote_asset`, with volume distributions)",
        "",
        f"Spot quote breakdown parquet: `{paths.spot_quote_breakdown_parquet}`",
        "",
        _df_to_markdown_table(spot_quote_breakdown_df),
        "",
        "## Strategy Readiness",
        "",
        f"Strategy readiness parquet: `{paths.strategy_readiness_parquet}`",
        "",
        _df_to_markdown_table(strategy_readiness_df),
        "",
        "## Scanner Readiness",
        "",
        "(Heuristic readiness checks for opportunity and strategy scanners)",
        "",
        _df_to_markdown_table(scanner_readiness_df),
        "",
        "## Quote Assets",
        "",
        _df_to_markdown_table(quote_dist_df),
        "",
        "## binance_spot_top100 Quote Overview",
        "",
        _df_to_markdown_table(spot_top100_quote_overview_df),
        "",
        "## Spot vs Perp Parity",
        "",
        _df_to_markdown_table(spot_perp_parity_df),
        "",
        "## Overlap (Tickers)",
        "",
        _df_to_markdown_table(overlap_df),
        "",
        "## Overlap (Bases)",
        "",
        _df_to_markdown_table(base_overlap_df),
        "",
    ]
    paths.report_md.write_text("\n".join(md), encoding="utf-8")

    return paths
