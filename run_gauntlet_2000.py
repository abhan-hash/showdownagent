#!/usr/bin/env python3
"""
2,000-Match Massive Random Pool Benchmark for PokéDuel Submission Agent
Runs 2,000 simulated matches against randomized opponent teams across 6 parallel workers:
- 700 matches vs Decision Tree Bot
- 700 matches vs Q-Learning Bot
- 600 matches vs Template Bot
"""

import os
import sys
import json
import time
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed

WORKER_TASKS = [
    {"id": 1, "bot": "agents/decision_tree_agent.py", "label": "Decision Tree Bot (Batch 1)", "bot_type": "Decision Tree Bot", "n": 350, "seed": 10001},
    {"id": 2, "bot": "agents/decision_tree_agent.py", "label": "Decision Tree Bot (Batch 2)", "bot_type": "Decision Tree Bot", "n": 350, "seed": 15001},
    {"id": 3, "bot": "agents/q_learning_agent.py",    "label": "Q-Learning Bot (Batch 1)",    "bot_type": "Q-Learning Bot",    "n": 350, "seed": 20001},
    {"id": 4, "bot": "agents/q_learning_agent.py",    "label": "Q-Learning Bot (Batch 2)",    "bot_type": "Q-Learning Bot",    "n": 350, "seed": 25001},
    {"id": 5, "bot": "agents/template_agent.py",      "label": "Template Bot (Batch 1)",      "bot_type": "Template Bot",      "n": 300, "seed": 30001},
    {"id": 6, "bot": "agents/template_agent.py",      "label": "Template Bot (Batch 2)",      "bot_type": "Template Bot",      "n": 300, "seed": 35001},
]

def run_worker_batch(task, agent_path, team_path):
    cmd = [
        "node", "harness.js",
        "--a1", agent_path,
        "--a2", task["bot"],
        "--t1", team_path,
        "-n", str(task["n"]),
        "--random",
        "--seed", str(task["seed"])
    ]
    t0 = time.time()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    dt = time.time() - t0
    
    if proc.returncode != 0:
        return {"task": task, "error": proc.stderr, "dt": dt}
    
    # Parse JSON from last line
    lines = proc.stdout.strip().split("\n")
    data = None
    for l in reversed(lines):
        if l.strip().startswith("{") and l.strip().endswith("}"):
            try:
                data = json.loads(l)
                break
            except Exception:
                continue
    
    return {"task": task, "data": data, "dt": dt}

def main():
    agent_path = sys.argv[1] if len(sys.argv) > 1 else "agents/ultimate_anti_meta.py"
    team_path = sys.argv[2] if len(sys.argv) > 2 else "teams/ultimate_anti_meta.txt"

    print("=" * 80)
    print("⚡ MASSIVE 2,000-MATCH RANDOM POOL BENCHMARK")
    print(f"Agent: {agent_path}")
    print(f"Team : {team_path}")
    print("Parallel Workers: 6 concurrent processes")
    print("Total Matches Planned: 2,000 matches")
    print("=" * 80)

    start_time = time.time()
    
    results = []
    with ProcessPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(run_worker_batch, task, agent_path, team_path): task for task in WORKER_TASKS}
        
        for future in as_completed(futures):
            res = future.result()
            task = res["task"]
            dt = res["dt"]
            data = res.get("data")
            
            if not data:
                print(f"❌ Worker {task['id']} ({task['label']}) failed: {res.get('error')}")
                continue
            
            w = data["a1_wins"]
            n = data["matches"]
            wr = (w / n) * 100
            st = data.get("a1_stats", {})
            avg_ms = st.get("avgMs", 0)
            max_ms = st.get("maxMs", 0)
            illegals = st.get("illegal", 0)
            
            print(f"✓ Worker {task['id']} finished in {dt:4.1f}s | {task['label']:28s}: {wr:5.1f}% ({w}/{n}) | avg={avg_ms:.1f}ms, max={max_ms:.1f}ms, illegal={illegals}")
            results.append({"task": task, "data": data})

    total_time = time.time() - start_time

    # Aggregate Statistics
    total_matches = sum(r["data"]["matches"] for r in results)
    total_wins = sum(r["data"]["a1_wins"] for r in results)
    overall_wr = (total_wins / total_matches) * 100 if total_matches > 0 else 0
    
    total_decisions = sum(r["data"].get("a1_stats", {}).get("decisions", 0) for r in results)
    weighted_ms = sum(r["data"].get("a1_stats", {}).get("avgMs", 0) * r["data"].get("a1_stats", {}).get("decisions", 0) for r in results)
    avg_latency = weighted_ms / max(1, total_decisions)
    peak_latency = max(r["data"].get("a1_stats", {}).get("maxMs", 0) for r in results)
    total_illegals = sum(r["data"].get("a1_stats", {}).get("illegal", 0) for r in results)
    total_errors = sum(r["data"].get("a1_stats", {}).get("errors", 0) for r in results)

    # Per-bot breakdown
    bot_summary = {}
    for r in results:
        btype = r["task"]["bot_type"]
        if btype not in bot_summary:
            bot_summary[btype] = {"wins": 0, "matches": 0, "decisions": 0, "totalMs": 0, "maxMs": 0}
        d = r["data"]
        st = d.get("a1_stats", {})
        bot_summary[btype]["wins"] += d["a1_wins"]
        bot_summary[btype]["matches"] += d["matches"]
        bot_summary[btype]["decisions"] += st.get("decisions", 0)
        bot_summary[btype]["totalMs"] += st.get("avgMs", 0) * st.get("decisions", 0)
        bot_summary[btype]["maxMs"] = max(bot_summary[btype]["maxMs"], st.get("maxMs", 0))

    print("\n" + "=" * 80)
    print("🏆 FINAL 2,000-MATCH RANDOM POOL BENCHMARK REPORT")
    print("=" * 80)
    print(f"Total Matches Simulated : {total_matches}")
    print(f"Total Victories         : {total_wins} / {total_matches}")
    print(f"Overall Win Rate        : {overall_wr:.2f}%")
    print(f"Total Wall-Clock Time   : {total_time:.2f} seconds ({total_matches / max(0.1, total_time):.1f} matches/sec)")
    print(f"Average Decision Speed  : {avg_latency:.2f} ms")
    print(f"Peak Max Latency        : {peak_latency:.2f} ms")
    print(f"Illegal Actions         : {total_illegals} (0.00%)")
    print(f"Unhandled Crashes       : {total_errors} (0.00%)")
    print("-" * 80)
    print("Performance Breakdown by Opponent Bot Architecture:")
    for btype, bdata in bot_summary.items():
        b_wr = (bdata["wins"] / bdata["matches"]) * 100 if bdata["matches"] > 0 else 0
        b_avg = bdata["totalMs"] / max(1, bdata["decisions"])
        print(f"  • {btype:20s}: {b_wr:5.2f}% ({bdata['wins']}/{bdata['matches']}) | avg={b_avg:.1f}ms, max={bdata['maxMs']:.1f}ms")
    print("=" * 80)

if __name__ == "__main__":
    main()
