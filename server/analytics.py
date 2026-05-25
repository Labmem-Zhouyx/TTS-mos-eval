"""Aggregate rater session JSON files into per-system MOS statistics
and ABX preference tables."""

from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from scipy import stats as _scipy_stats  # type: ignore
except Exception:  # pragma: no cover
    _scipy_stats = None


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _t_ci95(values: List[float]) -> Tuple[float, float, float, float, int]:
    """Return (mean, std, ci_low, ci_high, n) using Student-t when scipy
    is available, otherwise fall back to a normal approximation."""
    n = len(values)
    if n == 0:
        return (float("nan"), float("nan"), float("nan"), float("nan"), 0)
    mean = sum(values) / n
    if n == 1:
        return (mean, 0.0, mean, mean, 1)
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    std = math.sqrt(var)
    se = std / math.sqrt(n)
    if _scipy_stats is not None:
        t = float(_scipy_stats.t.ppf(0.975, df=n - 1))
    else:
        t = 1.96
    margin = t * se
    return (mean, std, mean - margin, mean + margin, n)


def _binom_p(wins: int, total: int) -> float:
    """Two-sided binomial test p-value for H0: p == 0.5."""
    if total == 0:
        return float("nan")
    if _scipy_stats is not None:
        try:
            return float(
                _scipy_stats.binomtest(wins, total, 0.5, alternative="two-sided").pvalue
            )
        except AttributeError:  # scipy < 1.7
            return float(_scipy_stats.binom_test(wins, total, 0.5))  # type: ignore[attr-defined]
    # naive computation via the normal approximation
    p_hat = wins / total
    se = math.sqrt(0.25 / total)
    z = (p_hat - 0.5) / se
    # 2 * (1 - Phi(|z|))
    from math import erf, sqrt

    return 2.0 * (1.0 - 0.5 * (1.0 + erf(abs(z) / sqrt(2))))


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return f


# --------------------------------------------------------------------------- #
# Data containers                                                              #
# --------------------------------------------------------------------------- #


@dataclass
class MosStat:
    panel: str
    system: str
    dimension: str
    mean: float
    std: float
    ci_low: float
    ci_high: float
    n: int


def _ci_margin(stat: MosStat) -> float:
    return max(abs(stat.ci_high - stat.mean), abs(stat.mean - stat.ci_low))


def _mean_pm_text(stat: MosStat, decimals: int = 2) -> str:
    margin = _ci_margin(stat)
    return f"{stat.mean:.{decimals}f} ± {margin:.{decimals}f}"


@dataclass
class AbxStat:
    panel: str
    system_a: str
    system_b: str
    a_wins: int = 0
    b_wins: int = 0
    ties: int = 0
    total: int = 0
    a_win_rate: float = float("nan")
    b_win_rate: float = float("nan")
    tie_rate: float = float("nan")
    p_value: float = float("nan")


@dataclass
class AggregateReport:
    mos: List[MosStat] = field(default_factory=list)
    abx: List[AbxStat] = field(default_factory=list)
    raters: int = 0
    sessions: int = 0
    panels_summary: Dict[str, Dict[str, int]] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Aggregation                                                                  #
# --------------------------------------------------------------------------- #


def load_sessions(results_dir: Path) -> List[Dict[str, Any]]:
    sessions: List[Dict[str, Any]] = []
    for f in sorted(results_dir.glob("*.json")):
        try:
            sessions.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return sessions


def aggregate(
    sessions: Iterable[Dict[str, Any]],
    include_drafts: bool = False,
) -> AggregateReport:
    """Aggregate raw session dicts into per-panel statistics."""

    # MOS: panel -> system -> dimension -> [values]
    mos_buckets: Dict[str, Dict[str, Dict[str, List[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    # ABX: panel -> (sys_a, sys_b) -> {'A': int, 'B': int, 'tie': int}
    abx_buckets: Dict[str, Dict[Tuple[str, str], Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"A": 0, "B": 0, "tie": 0})
    )
    nicknames: set[str] = set()
    n_sessions = 0
    panel_counts: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"sessions": 0, "samples": 0}
    )

    for sess in sessions:
        if not include_drafts and not sess.get("submitted_at"):
            continue
        n_sessions += 1
        nick = sess.get("nickname") or sess.get("session_id") or "?"
        nicknames.add(nick)
        for panel in sess.get("panels", []):
            if not include_drafts and panel.get("status") != "submitted":
                continue
            panel_name = panel.get("panel")
            if not panel_name:
                continue
            panel_counts[panel_name]["sessions"] += 1
            for sample in panel.get("samples", []):
                panel_counts[panel_name]["samples"] += 1
                # ABX-style payload
                if sample.get("abx_choice") is not None:
                    choice = str(sample["abx_choice"]).strip().lower()
                    meta = sample.get("meta", {}) or {}
                    sys_a = (
                        meta.get("system_a")
                        or sample.get("abx_a_system")
                        or "A"
                    )
                    sys_b = (
                        meta.get("system_b")
                        or sample.get("abx_b_system")
                        or "B"
                    )
                    key = (sys_a, sys_b)
                    bucket = abx_buckets[panel_name][key]
                    if choice in ("a", "system_a"):
                        bucket["A"] += 1
                    elif choice in ("b", "system_b"):
                        bucket["B"] += 1
                    else:
                        bucket["tie"] += 1
                    continue
                # MOS-style payload
                for entry in sample.get("ratings", []):
                    system = entry.get("system")
                    if not system:
                        continue
                    scores = entry.get("scores") or {}
                    for dim, v in scores.items():
                        f = _safe_float(v)
                        if f is None:
                            continue
                        mos_buckets[panel_name][system][dim].append(f)

    mos_stats: List[MosStat] = []
    for panel, by_sys in mos_buckets.items():
        for system, by_dim in by_sys.items():
            for dim, values in by_dim.items():
                mean, std, lo, hi, n = _t_ci95(values)
                mos_stats.append(
                    MosStat(
                        panel=panel,
                        system=system,
                        dimension=dim,
                        mean=mean,
                        std=std,
                        ci_low=lo,
                        ci_high=hi,
                        n=n,
                    )
                )

    abx_stats: List[AbxStat] = []
    for panel, by_pair in abx_buckets.items():
        for (sys_a, sys_b), counts in by_pair.items():
            a = counts["A"]
            b = counts["B"]
            t = counts["tie"]
            total = a + b + t
            wins_total = a + b
            stat = AbxStat(
                panel=panel,
                system_a=sys_a,
                system_b=sys_b,
                a_wins=a,
                b_wins=b,
                ties=t,
                total=total,
            )
            if total > 0:
                stat.a_win_rate = a / total
                stat.b_win_rate = b / total
                stat.tie_rate = t / total
            if wins_total > 0:
                stat.p_value = _binom_p(a, wins_total)
            abx_stats.append(stat)

    return AggregateReport(
        mos=mos_stats,
        abx=abx_stats,
        raters=len(nicknames),
        sessions=n_sessions,
        panels_summary=dict(panel_counts),
    )


# --------------------------------------------------------------------------- #
# Writers                                                                      #
# --------------------------------------------------------------------------- #


def report_to_json(report: AggregateReport) -> Dict[str, Any]:
    return {
        "summary": {
            "raters": report.raters,
            "sessions": report.sessions,
            "panels": report.panels_summary,
        },
        "mos": [
            {
                **s.__dict__,
                "ci_margin": _ci_margin(s),
                "mean_pm_95ci": _mean_pm_text(s, decimals=4),
            }
            for s in report.mos
        ],
        "abx": [s.__dict__ for s in report.abx],
    }


def write_csv_mos(report: AggregateReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "panel",
                "system",
                "dimension",
                "n",
                "mean",
                "std",
                "ci_margin",
                "mean_pm_95ci",
                "ci_low",
                "ci_high",
            ]
        )
        for s in report.mos:
            w.writerow(
                [
                    s.panel,
                    s.system,
                    s.dimension,
                    s.n,
                    f"{s.mean:.4f}",
                    f"{s.std:.4f}",
                    f"{_ci_margin(s):.4f}",
                    _mean_pm_text(s, decimals=4),
                    f"{s.ci_low:.4f}",
                    f"{s.ci_high:.4f}",
                ]
            )


def write_csv_abx(report: AggregateReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "panel",
                "system_a",
                "system_b",
                "total",
                "a_wins",
                "b_wins",
                "ties",
                "a_win_rate",
                "b_win_rate",
                "tie_rate",
                "p_value",
            ]
        )
        for s in report.abx:
            w.writerow(
                [
                    s.panel,
                    s.system_a,
                    s.system_b,
                    s.total,
                    s.a_wins,
                    s.b_wins,
                    s.ties,
                    f"{s.a_win_rate:.4f}",
                    f"{s.b_win_rate:.4f}",
                    f"{s.tie_rate:.4f}",
                    f"{s.p_value:.6f}",
                ]
            )


def write_markdown(report: AggregateReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# MOS Evaluation Aggregate Report\n")
    lines.append(
        f"- sessions: {report.sessions}\n- raters: {report.raters}\n"
    )
    if report.panels_summary:
        lines.append("\n## Panel coverage\n")
        lines.append("| panel | sessions | sample ratings |")
        lines.append("|---|---|---|")
        for panel, c in report.panels_summary.items():
            lines.append(
                f"| {panel} | {c.get('sessions', 0)} | {c.get('samples', 0)} |"
            )
    if report.mos:
        lines.append("\n## MOS scores\n")
        lines.append(
            "| panel | system | dimension | n | mean ± 95% CI |"
        )
        lines.append("|---|---|---|---|---|")
        for s in sorted(
            report.mos, key=lambda x: (x.panel, x.dimension, -x.mean)
        ):
            lines.append(
                f"| {s.panel} | {s.system} | {s.dimension} | {s.n} | "
                f"{_mean_pm_text(s, decimals=2)} |"
            )
    if report.abx:
        lines.append("\n## ABX preferences\n")
        lines.append(
            "| panel | A | B | n | A win | B win | tie | p-value |"
        )
        lines.append("|---|---|---|---|---|---|---|---|")
        for s in report.abx:
            lines.append(
                f"| {s.panel} | {s.system_a} | {s.system_b} | {s.total} | "
                f"{s.a_win_rate:.2f} | {s.b_win_rate:.2f} | {s.tie_rate:.2f} | "
                f"{s.p_value:.4f} |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_all(report: AggregateReport, output_dir: Path) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    p_json = output_dir / "summary.json"
    p_csv_mos = output_dir / "mos_summary.csv"
    p_csv_abx = output_dir / "abx_summary.csv"
    p_md = output_dir / "summary.md"
    p_json.write_text(
        json.dumps(report_to_json(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv_mos(report, p_csv_mos)
    write_csv_abx(report, p_csv_abx)
    write_markdown(report, p_md)
    return {
        "json": p_json,
        "csv_mos": p_csv_mos,
        "csv_abx": p_csv_abx,
        "markdown": p_md,
    }
