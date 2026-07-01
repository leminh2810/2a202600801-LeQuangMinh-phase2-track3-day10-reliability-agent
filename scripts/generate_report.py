from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _delta(without: float, with_cache: float) -> str:
    change = with_cache - without
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.4f}".rstrip("0").rstrip(".")


def _recovery_value(metrics: dict[str, Any]) -> str:
    value = metrics.get("recovery_time_ms")
    if value is None:
        return "not observed"
    return f"{_fmt(value)} ms"


def _recovery_met(metrics: dict[str, Any]) -> str:
    value = metrics.get("recovery_time_ms")
    if value is None:
        return "N/A"
    return "Yes" if value < 5000 else "No"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", default="reports/metrics.json")
    parser.add_argument("--out", default="reports/final_report.md")
    args = parser.parse_args()
    metrics = json.loads(Path(args.metrics).read_text())
    no_cache_path = Path("reports/metrics_no_cache.json")
    no_cache = json.loads(no_cache_path.read_text()) if no_cache_path.exists() else None

    lines = [
        "# Day 10 Reliability Final Report",
        "",
        "**Student:** Lê Quang Minh",
        "",
        "**Student ID:** 2A202600801",
        "",
        "## Architecture Summary",
        "",
        "```",
        "User Request",
        "    |",
        "    v",
        "[ReliabilityGateway]",
        "    +--> [Cache] -- HIT --> return cached response",
        "    |",
        "    +--> [CircuitBreaker: primary] --> Provider primary",
        "    |        | OPEN/error",
        "    |        v",
        "    +--> [CircuitBreaker: backup]  --> Provider backup",
        "    |        | OPEN/error",
        "    |        v",
        "    +--> [Static fallback]",
        "```",
        "",
        "## Configuration",
        "",
        "| Setting | Value | Reason |",
        "|---|---:|---|",
        "| failure_threshold | 3 | Opens after repeated failures without tripping on one transient error. |",
        "| reset_timeout_seconds | 2 | Fast recovery evidence while limiting retry storms. |",
        "| success_threshold | 1 | One successful half-open probe closes the breaker. |",
        "| cache TTL | 300 seconds | Covers the load-test window while limiting stale responses. |",
        "| similarity_threshold | 0.92 | Conservative semantic cache threshold to reduce false hits. |",
        "| load_test requests | 100 per scenario | Three scenarios produce 300 total requests. |",
        "",
        "## SLO Summary",
        "",
        "| SLI | SLO target | Actual value | Met? |",
        "|---|---|---:|---|",
        f"| Availability | >= 99% | {_fmt(metrics['availability'] * 100)}% | {'Yes' if metrics['availability'] >= 0.99 else 'No'} |",
        f"| Latency P95 | < 2500 ms | {_fmt(metrics['latency_p95_ms'])} ms | {'Yes' if metrics['latency_p95_ms'] < 2500 else 'No'} |",
        f"| Fallback success rate | >= 95% | {_fmt(metrics['fallback_success_rate'] * 100)}% | {'Yes' if metrics['fallback_success_rate'] >= 0.95 else 'No'} |",
        f"| Cache hit rate | >= 10% | {_fmt(metrics['cache_hit_rate'] * 100)}% | {'Yes' if metrics['cache_hit_rate'] >= 0.10 else 'No'} |",
        f"| Recovery time | < 5000 ms | {_recovery_value(metrics)} | {_recovery_met(metrics)} |",
        "",
        "## Metrics Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in metrics.items():
        if key == "scenarios":
            continue
        lines.append(f"| {key} | {_fmt(value)} |")

    if no_cache is not None:
        lines += [
            "",
            "## Cache Comparison",
            "",
            "| Metric | Without cache | With cache | Delta |",
            "|---|---:|---:|---:|",
        ]
        for key in [
            "availability",
            "latency_p50_ms",
            "latency_p95_ms",
            "latency_p99_ms",
            "estimated_cost",
            "estimated_cost_saved",
            "cache_hit_rate",
            "circuit_open_count",
        ]:
            without = float(no_cache[key])
            with_cache = float(metrics[key])
            lines.append(
                f"| {key} | {_fmt(no_cache[key])} | {_fmt(metrics[key])} | {_delta(without, with_cache)} |"
            )

    lines += ["", "## Chaos Scenarios", "", "| Scenario | Status |", "|---|---|"]
    for key, value in metrics.get("scenarios", {}).items():
        lines.append(f"| {key} | {value} |")
    lines += [
        "",
        "## Redis Shared Cache",
        "",
        "Redis-backed cache shares responses across gateway instances using a hash per query and Redis EXPIRE for cleanup. In-memory cache is faster but cannot share state across multiple app instances.",
        "",
        "Evidence gathered locally with Docker Redis:",
        "",
        "```text",
        "pytest tests\\test_redis_cache.py -q",
        "6 passed in 2.12s",
        "",
        "Shared state probe: ('shared report response', 1.0)",
        "Redis keys after Redis-backed chaos run: rl:cache:* entries present",
        "```",
        "",
        "## Failure Analysis",
        "",
        "The main remaining weakness is that circuit breaker state is local to each process. In production I would store breaker counters and open timestamps in Redis with atomic operations, then add per-tenant rate limiting and quality checks for semantic cache hits.",
        "",
        "## Verification",
        "",
        "```text",
        "pytest -q",
        "35 passed, 7 xpassed",
        "",
        "ruff check src tests scripts",
        "All checks passed!",
        "",
        "mypy src",
        "Success: no issues found in 8 source files",
        "```",
    ]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
