from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_PATH = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))


def percentile(values: list[float | int], p: int) -> float:
    if not values:
        return 0.0
    items = sorted(values)
    idx = max(0, min(len(items) - 1, round((p / 100) * len(items) + 0.5) - 1))
    return float(items[idx])


def compute_dashboard_metrics() -> dict[str, Any]:
    if not LOG_PATH.exists():
        records = []
    else:
        records = []
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass

    # Group by minute (HH:MM)
    buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "requests": 0,
        "failed": 0,
        "latencies": [],
        "ttfts": [],
        "costs": [],
        "tokens_in": 0,
        "tokens_out": 0,
        "quality_scores": [],
        "tool_total": 0,
        "tool_success": 0,
    })

    all_latencies: list[int] = []
    all_ttfts: list[int] = []
    all_costs: list[float] = []
    total_tokens_in = 0
    total_tokens_out = 0
    all_quality: list[float] = []
    total_req_received = 0
    total_req_failed = 0
    total_tool_calls = 0
    total_tool_success = 0
    error_breakdown: dict[str, int] = defaultdict(int)

    for r in records:
        ts_str = r.get("ts", "")
        # Parse minute label
        minute_label = "00:00"
        if ts_str:
            try:
                # Handle iso format
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                minute_label = dt.strftime("%H:%M")
            except Exception:
                minute_label = ts_str[11:16] if len(ts_str) >= 16 else "00:00"

        event = r.get("event")
        b = buckets[minute_label]

        if event == "request_received":
            b["requests"] += 1
            total_req_received += 1

        elif event == "request_failed":
            b["failed"] += 1
            total_req_failed += 1
            err_type = r.get("error_type", "UnknownError")
            error_breakdown[err_type] += 1
            if r.get("tool_name"):
                b["tool_total"] += 1
                total_tool_calls += 1
                if r.get("tool_success") is True:
                    b["tool_success"] += 1
                    total_tool_success += 1

        elif event == "response_sent":
            lat = r.get("latency_ms")
            if lat is not None:
                b["latencies"].append(lat)
                all_latencies.append(lat)

            ttft = r.get("ttft_ms")
            if ttft is not None:
                b["ttfts"].append(ttft)
                all_ttfts.append(ttft)

            cost = r.get("cost_usd", 0.0)
            b["costs"].append(cost)
            all_costs.append(cost)

            tin = r.get("tokens_in", 0)
            tout = r.get("tokens_out", 0)
            b["tokens_in"] += tin
            b["tokens_out"] += tout
            total_tokens_in += tin
            total_tokens_out += tout

            q = r.get("quality_score")
            if q is not None:
                b["quality_scores"].append(q)
                all_quality.append(q)

            if r.get("tool_name"):
                b["tool_total"] += 1
                total_tool_calls += 1
                if r.get("tool_success") is True:
                    b["tool_success"] += 1
                    total_tool_success += 1

    # Sorted minute labels (last 60 mins)
    sorted_labels = sorted(buckets.keys())[-60:]
    if not sorted_labels:
        sorted_labels = [datetime.now(timezone.utc).strftime("%H:%M")]

    p50_series = []
    p95_series = []
    p99_series = []
    ttft_series = []
    traffic_series = []
    error_rate_series = []
    retrieval_success_series = []
    cost_series = []
    tokens_in_series = []
    tokens_out_series = []
    quality_series = []

    for label in sorted_labels:
        b = buckets[label]
        p50_series.append(percentile(b["latencies"], 50) if b["latencies"] else 0)
        p95_series.append(percentile(b["latencies"], 95) if b["latencies"] else 0)
        p99_series.append(percentile(b["latencies"], 99) if b["latencies"] else 0)
        ttft_series.append(percentile(b["ttfts"], 95) if b["ttfts"] else 0)
        traffic_series.append(b["requests"])

        reqs = b["requests"] or len(b["latencies"]) or 1
        err_rate = round((b["failed"] / reqs) * 100, 2) if b["failed"] else 0.0
        error_rate_series.append(err_rate)

        ret_rate = round((b["tool_success"] / b["tool_total"]) * 100, 2) if b["tool_total"] else 100.0
        retrieval_success_series.append(ret_rate)

        cost_series.append(round(sum(b["costs"]), 4))
        tokens_in_series.append(b["tokens_in"])
        tokens_out_series.append(b["tokens_out"])

        q_avg = round(sum(b["quality_scores"]) / len(b["quality_scores"]), 2) if b["quality_scores"] else 0.0
        quality_series.append(q_avg)

    overall_p50 = percentile(all_latencies, 50)
    overall_p95 = percentile(all_latencies, 95)
    overall_p99 = percentile(all_latencies, 99)
    overall_ttft_p95 = percentile(all_ttfts, 95)
    total_cost = round(sum(all_costs), 4)
    overall_err_rate = round((total_req_failed / max(1, total_req_received)) * 100, 2)
    overall_retrieval_success = (
        round((total_tool_success / max(1, total_tool_calls)) * 100, 2)
        if total_tool_calls else 100.0
    )
    overall_quality = round(sum(all_quality) / len(all_quality), 2) if all_quality else 0.0

    return {
        "labels": sorted_labels,
        "panels": {
            "latency": {
                "p50": p50_series,
                "p95": p95_series,
                "p99": p99_series,
                "ttft_p95": ttft_series,
                "current_p95": overall_p95,
                "current_ttft": overall_ttft_p95,
                "threshold": 3000,
            },
            "traffic": {
                "values": traffic_series,
                "total": total_req_received,
                "threshold": 1,
            },
            "errors": {
                "error_rate": error_rate_series,
                "retrieval_success": retrieval_success_series,
                "current_error_rate": overall_err_rate,
                "current_retrieval_success": overall_retrieval_success,
                "error_breakdown": dict(error_breakdown),
                "threshold_error_rate": 2.0,
            },
            "cost": {
                "by_minute": cost_series,
                "total_cost": total_cost,
                "threshold": 2.5,
            },
            "tokens": {
                "tokens_in": tokens_in_series,
                "tokens_out": tokens_out_series,
                "total_tokens": total_tokens_in + total_tokens_out,
                "threshold": 500000,
            },
            "quality": {
                "values": quality_series,
                "current_avg": overall_quality,
                "threshold": 0.75,
            },
        },
    }


def render_dashboard_html() -> str:
    data = compute_dashboard_metrics()
    json_data = json.dumps(data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>K4-L3B Day 13 Monitoring &amp; LLMOps Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg: #090d16;
      --card-bg: #131c2e;
      --card-border: #1e293b;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #38bdf8;
      --secondary: #818cf8;
      --success: #34d399;
      --warning: #fbbf24;
      --danger: #ef4444;
      --accent: #f472b6;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    body {{
      background: var(--bg);
      color: var(--text-main);
      padding: 24px;
      min-height: 100vh;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--card-border);
      flex-wrap: wrap;
      gap: 16px;
    }}
    .title-box h1 {{
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.5px;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .title-box p {{
      color: var(--text-muted);
      font-size: 13px;
      margin-top: 4px;
    }}
    .meta-badges {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .badge {{
      background: rgba(30, 41, 59, 0.8);
      border: 1px solid var(--card-border);
      padding: 6px 12px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 500;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .badge.live {{
      color: var(--success);
      border-color: rgba(52, 211, 153, 0.3);
      background: rgba(52, 211, 153, 0.1);
    }}
    .badge.live::before {{
      content: "";
      width: 7px;
      height: 7px;
      background: var(--success);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--success);
    }}
    .btn-refresh {{
      background: var(--primary);
      color: #0f172a;
      border: none;
      padding: 6px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .btn-refresh:hover {{
      opacity: 0.9;
      transform: translateY(-1px);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 20px;
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 18px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
      display: flex;
      flex-direction: column;
    }}
    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
    }}
    .card-title {{
      font-size: 15px;
      font-weight: 600;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .card-unit {{
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      font-weight: 700;
      background: rgba(148, 163, 184, 0.1);
      padding: 2px 6px;
      border-radius: 4px;
    }}
    .stats-row {{
      display: flex;
      align-items: baseline;
      gap: 16px;
      margin-bottom: 14px;
    }}
    .stat-val {{
      font-size: 26px;
      font-weight: 700;
      color: #ffffff;
    }}
    .stat-sub {{
      font-size: 12px;
      color: var(--text-muted);
    }}
    .threshold-tag {{
      margin-left: auto;
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 6px;
      border: 1px dashed var(--danger);
      color: #fca5a5;
      background: rgba(239, 68, 68, 0.1);
      font-weight: 500;
    }}
    .chart-container {{
      position: relative;
      flex: 1;
      min-height: 180px;
      max-height: 220px;
    }}
    footer {{
      margin-top: 30px;
      text-align: center;
      font-size: 12px;
      color: var(--text-muted);
      border-top: 1px solid var(--card-border);
      padding-top: 16px;
    }}
  </style>
</head>
<body>
  <header>
    <div class="title-box">
      <h1>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
        K4-L3B Day 13 Monitoring &amp; LLMOps
      </h1>
      <p>Runtime observability dashboard mapped from <code>data/logs.jsonl</code> (Schema v1)</p>
    </div>
    <div class="meta-badges">
      <div class="badge live">Status: Live</div>
      <div class="badge">⏱ Time Range: 60m</div>
      <div class="badge">🔄 Auto-Refresh: 30s (<span id="countdown">30</span>s)</div>
      <button class="btn-refresh" onclick="location.reload()">Refresh Now</button>
    </div>
  </header>

  <div class="grid">
    <!-- Panel 1: Latency -->
    <div class="card" id="panel-latency">
      <div class="card-header">
        <div class="card-title">1. Latency percentiles and TTFT</div>
        <span class="card-unit">ms</span>
      </div>
      <div class="stats-row">
        <div class="stat-val" id="val-p95">-- ms</div>
        <div class="stat-sub" id="val-ttft">TTFT P95: -- ms</div>
        <div class="threshold-tag">SLO: P95 &le; 3000 ms</div>
      </div>
      <div class="chart-container">
        <canvas id="chart-latency"></canvas>
      </div>
    </div>

    <!-- Panel 2: Traffic -->
    <div class="card" id="panel-traffic">
      <div class="card-header">
        <div class="card-title">2. Request traffic</div>
        <span class="card-unit">req / min</span>
      </div>
      <div class="stats-row">
        <div class="stat-val" id="val-traffic">-- req</div>
        <div class="stat-sub">Total incoming requests</div>
        <div class="threshold-tag">Target: Rate &ge; 1 / min</div>
      </div>
      <div class="chart-container">
        <canvas id="chart-traffic"></canvas>
      </div>
    </div>

    <!-- Panel 3: Errors -->
    <div class="card" id="panel-errors">
      <div class="card-header">
        <div class="card-title">3. Error rate and retrieval success</div>
        <span class="card-unit">%</span>
      </div>
      <div class="stats-row">
        <div class="stat-val" id="val-error-rate">0.0%</div>
        <div class="stat-sub" id="val-retrieval-rate">Retrieval: 100%</div>
        <div class="threshold-tag">SLO: Error &le; 2%</div>
      </div>
      <div class="chart-container">
        <canvas id="chart-errors"></canvas>
      </div>
    </div>

    <!-- Panel 4: Cost -->
    <div class="card" id="panel-cost">
      <div class="card-header">
        <div class="card-title">4. Cost over time</div>
        <span class="card-unit">USD</span>
      </div>
      <div class="stats-row">
        <div class="stat-val" id="val-cost">$0.0000</div>
        <div class="stat-sub">Cumulative model spend</div>
        <div class="threshold-tag">Guardrail: Total &le; $2.5</div>
      </div>
      <div class="chart-container">
        <canvas id="chart-cost"></canvas>
      </div>
    </div>

    <!-- Panel 5: Tokens -->
    <div class="card" id="panel-tokens">
      <div class="card-header">
        <div class="card-title">5. Input and output tokens</div>
        <span class="card-unit">Tokens</span>
      </div>
      <div class="stats-row">
        <div class="stat-val" id="val-tokens">0</div>
        <div class="stat-sub">Total tokens processed</div>
        <div class="threshold-tag">Budget: Total &le; 500k</div>
      </div>
      <div class="chart-container">
        <canvas id="chart-tokens"></canvas>
      </div>
    </div>

    <!-- Panel 6: Quality -->
    <div class="card" id="panel-quality">
      <div class="card-header">
        <div class="card-title">6. Quality proxy score</div>
        <span class="card-unit">Score (0 - 1)</span>
      </div>
      <div class="stats-row">
        <div class="stat-val" id="val-quality">0.00</div>
        <div class="stat-sub">Average heuristic score</div>
        <div class="threshold-tag">Guardrail: Avg &ge; 0.75</div>
      </div>
      <div class="chart-container">
        <canvas id="chart-quality"></canvas>
      </div>
    </div>
  </div>

  <footer>
    Contract compliant with <code>config/dashboard.yaml</code> | Refreshes every 30 seconds automatically
  </footer>

  <script>
    const data = {json_data};
    const labels = data.labels;
    const panels = data.panels;

    // Update stats labels
    document.getElementById("val-p95").innerText = Math.round(panels.latency.current_p95) + " ms";
    document.getElementById("val-ttft").innerText = "TTFT P95: " + Math.round(panels.latency.current_ttft) + " ms";
    document.getElementById("val-traffic").innerText = panels.traffic.total + " req";
    document.getElementById("val-error-rate").innerText = panels.errors.current_error_rate + "%";
    document.getElementById("val-retrieval-rate").innerText = "Retrieval: " + panels.errors.current_retrieval_success + "%";
    document.getElementById("val-cost").innerText = "$" + panels.cost.total_cost.toFixed(4);
    document.getElementById("val-tokens").innerText = panels.tokens.total_tokens.toLocaleString();
    document.getElementById("val-quality").innerText = panels.quality.current_avg.toFixed(2);

    const baseOptions = {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ intersect: false, mode: 'index' }},
      plugins: {{
        legend: {{
          labels: {{ color: '#94a3b8', font: {{ size: 11 }} }},
          position: 'top'
        }}
      }},
      scales: {{
        x: {{
          ticks: {{ color: '#64748b', font: {{ size: 10 }} }},
          grid: {{ color: 'rgba(30, 41, 59, 0.5)' }}
        }},
        y: {{
          ticks: {{ color: '#64748b', font: {{ size: 10 }} }},
          grid: {{ color: 'rgba(30, 41, 59, 0.5)' }}
        }}
      }}
    }};

    // 1. Latency Chart
    new Chart(document.getElementById('chart-latency'), {{
      type: 'line',
      data: {{
        labels: labels,
        datasets: [
          {{ label: 'P95', data: panels.latency.p95, borderColor: '#38bdf8', backgroundColor: 'transparent', tension: 0.2 }},
          {{ label: 'P50', data: panels.latency.p50, borderColor: '#34d399', backgroundColor: 'transparent', tension: 0.2 }},
          {{ label: 'TTFT P95', data: panels.latency.ttft_p95, borderColor: '#818cf8', backgroundColor: 'transparent', tension: 0.2 }},
          {{
            label: 'SLO Threshold (3000ms)',
            data: labels.map(() => 3000),
            borderColor: '#ef4444',
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false
          }}
        ]
      }},
      options: baseOptions
    }});

    // 2. Traffic Chart
    new Chart(document.getElementById('chart-traffic'), {{
      type: 'bar',
      data: {{
        labels: labels,
        datasets: [
          {{ label: 'Requests / min', data: panels.traffic.values, backgroundColor: 'rgba(56, 189, 248, 0.7)', borderRadius: 4 }},
          {{
            type: 'line',
            label: 'Min Threshold (1 req/min)',
            data: labels.map(() => 1),
            borderColor: '#fbbf24',
            borderDash: [5, 5],
            pointRadius: 0
          }}
        ]
      }},
      options: baseOptions
    }});

    // 3. Errors Chart
    new Chart(document.getElementById('chart-errors'), {{
      type: 'line',
      data: {{
        labels: labels,
        datasets: [
          {{ label: 'Error Rate (%)', data: panels.errors.error_rate, borderColor: '#ef4444', tension: 0.2 }},
          {{ label: 'Retrieval Success (%)', data: panels.errors.retrieval_success, borderColor: '#34d399', tension: 0.2 }},
          {{
            label: 'SLO Error Limit (2%)',
            data: labels.map(() => 2),
            borderColor: '#ef4444',
            borderDash: [5, 5],
            pointRadius: 0
          }}
        ]
      }},
      options: {{
        ...baseOptions,
        scales: {{ ...baseOptions.scales, y: {{ ...baseOptions.scales.y, min: 0, max: 100 }} }}
      }}
    }});

    // 4. Cost Chart
    new Chart(document.getElementById('chart-cost'), {{
      type: 'line',
      data: {{
        labels: labels,
        datasets: [
          {{ label: 'Cost/min ($)', data: panels.cost.by_minute, borderColor: '#f472b6', fill: true, backgroundColor: 'rgba(244, 114, 182, 0.1)', tension: 0.2 }},
          {{
            label: 'Guardrail Limit ($2.5)',
            data: labels.map(() => 2.5),
            borderColor: '#ef4444',
            borderDash: [5, 5],
            pointRadius: 0
          }}
        ]
      }},
      options: baseOptions
    }});

    // 5. Tokens Chart
    new Chart(document.getElementById('chart-tokens'), {{
      type: 'bar',
      data: {{
        labels: labels,
        datasets: [
          {{ label: 'Tokens In', data: panels.tokens.tokens_in, backgroundColor: 'rgba(129, 140, 248, 0.7)', stack: 'tokens' }},
          {{ label: 'Tokens Out', data: panels.tokens.tokens_out, backgroundColor: 'rgba(56, 189, 248, 0.7)', stack: 'tokens' }}
        ]
      }},
      options: {{
        ...baseOptions,
        scales: {{ ...baseOptions.scales, x: {{ ...baseOptions.scales.x, stacked: true }}, y: {{ ...baseOptions.scales.y, stacked: true }} }}
      }}
    }});

    // 6. Quality Chart
    new Chart(document.getElementById('chart-quality'), {{
      type: 'line',
      data: {{
        labels: labels,
        datasets: [
          {{ label: 'Quality Score', data: panels.quality.values, borderColor: '#a78bfa', fill: true, backgroundColor: 'rgba(167, 139, 250, 0.1)', tension: 0.2 }},
          {{
            label: 'SLO Quality Floor (0.75)',
            data: labels.map(() => 0.75),
            borderColor: '#ef4444',
            borderDash: [5, 5],
            pointRadius: 0
          }}
        ]
      }},
      options: {{
        ...baseOptions,
        scales: {{ ...baseOptions.scales, y: {{ ...baseOptions.scales.y, min: 0, max: 1 }} }}
      }}
    }});

    // Auto-refresh countdown
    let secondsLeft = 30;
    const countdownEl = document.getElementById("countdown");
    setInterval(() => {{
      secondsLeft--;
      if (secondsLeft <= 0) {{
        location.reload();
      }} else {{
        countdownEl.innerText = secondsLeft;
      }}
    }}, 1000);
  </script>
</body>
</html>
"""
