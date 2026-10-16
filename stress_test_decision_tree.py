#!/usr/bin/env python3
"""
Stress Test Runner for PokéDuel AI:
Evaluates agent specifically against the Scikit-Learn Decision Tree Bot
across thousands of randomized opponent teams using parallel workers.
"""

import sys
import os
import json
import time
import subprocess
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed

def run_batch(batch_idx, bot_path, agent_path, team_path, count, seed):
    cmd = [
        "node", "harness.js",
        "--a1", agent_path,
        "--a2", bot_path,
        "--t1", team_path,
        "-n", str(count),
        "--random",
        "--seed", str(seed)
    ]
    t0 = time.time()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    dt = time.time() - t0
    
    if proc.returncode != 0:
        return {"batch": batch_idx, "error": proc.stderr, "dt": dt}
    
    lines = proc.stdout.strip().split("\n")
    data = None
    for l in reversed(lines):
        if l.strip().startswith("{") and l.strip().endswith("}"):
            try:
                data = json.loads(l)
                break
            except Exception:
                continue
    return {"batch": batch_idx, "data": data, "dt": dt}

def main():
    parser = argparse.ArgumentParser(description="Stress test agent against Decision Tree Bot")
    parser.add_argument("--total", type=int, default=5000, help="Total matches to run (default: 5000)")
    parser.add_argument("--workers", type=int, default=10, help="Parallel worker processes (default: 10)")
    parser.add_argument("--batch-size", type=int, default=250, help="Matches per worker batch (default: 250)")
    parser.add_argument("--agent", default="agent.py", help="Path to our agent")
    parser.add_argument("--team", default="teams/ultimate_anti_meta.txt", help="Path to our team")
    parser.add_argument("--bot", default="agents/decision_tree_agent.py", help="Opponent bot")
    args = parser.parse_args()

    total_matches = args.total
    batch_size = args.batch_size
    num_batches = (total_matches + batch_size - 1) // batch_size
    
    print("=" * 76)
    print("⚔️  POKÉDUEL STRESS TEST: AGENT VS SCIKIT-LEARN DECISION TREE")
    print(f"Agent    : {args.agent}")
    print(f"Team     : {args.team}")
    print(f"Target   : {total_matches:,} matches against randomized teams")
    print(f"Workers  : {args.workers} parallel processes ({num_batches} batches of ~{batch_size})")
    print("=" * 76)

    tasks = []
    base_seed = 42000
    remaining = total_matches
    for i in range(num_batches):
        cnt = min(batch_size, remaining)
        tasks.append((i + 1, args.bot, args.agent, args.team, cnt, base_seed + i * 997))
        remaining -= cnt

    completed_matches = 0
    total_wins = 0
    total_illegals = 0
    total_errors = 0
    max_ms = 0.0
    sum_weighted_ms = 0.0
    total_decisions = 0
    t_start = time.time()

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_batch, *t): t[0] for t in tasks}
        
        for future in as_completed(futures):
            b_id = futures[future]
            res = future.result()
            if "error" in res:
                print(f"❌ Batch {b_id} failed with error: {res['error'][:200]}")
                continue
            
            d = res.get("data")
            if not d:
                print(f"⚠️ Batch {b_id} returned no valid JSON data")
                continue

            n = d.get("matches", 0)
            w = d.get("a1_wins", 0)
            st = d.get("a1_stats", {})
            ill = st.get("illegal", 0)
            err = st.get("errors", 0)
            m_ms = st.get("maxMs", 0.0)
            a_ms = st.get("avgMs", 0.0)
            decs = st.get("decisions", 0)

            completed_matches += n
            total_wins += w
            total_illegals += ill
            total_errors += err
            max_ms = max(max_ms, m_ms)
            sum_weighted_ms += a_ms * decs
            total_decisions += decs

            elapsed = time.time() - t_start
            rate = completed_matches / max(0.1, elapsed)
            current_wr = (total_wins / completed_matches) * 100 if completed_matches else 0.0

            # Progress line
            print(f"[{completed_matches:6d}/{total_matches:6d}] "
                  f"WinRate: {current_wr:5.1f}% ({total_wins}/{completed_matches}) | "
                  f"Rate: {rate:4.1f} match/s | "
                  f"Avg: {a_ms:4.1f}ms | Max: {m_ms:5.1f}ms | "
                  f"Illegals: {total_illegals} | Errors: {total_errors}")

    total_time = time.time() - t_start
    final_wr = (total_wins / completed_matches) * 100 if completed_matches else 0.0
    overall_avg_ms = sum_weighted_ms / max(1, total_decisions)

    print("\n" + "=" * 76)
    print("📊 STRESS TEST COMPLETE SUMMARY")
    print("=" * 76)
    print(f"Total Matches Simulated : {completed_matches:,}")
    print(f"Agent Wins              : {total_wins:,} / {completed_matches:,}")
    print(f"Overall Win Rate        : {final_wr:.2f}%")
    print(f"Illegal Moves           : {total_illegals}  {'✅ PERFECT' if total_illegals == 0 else '❌ ISSUE DETECTED'}")
    print(f"Timeouts / Errors       : {total_errors}  {'✅ PERFECT' if total_errors == 0 else '❌ ISSUE DETECTED'}")
    print(f"Average Decision Time   : {overall_avg_ms:.2f} ms")
    print(f"Maximum Decision Time   : {max_ms:.2f} ms (Timeout threshold: 1000 ms)")
    print(f"Total Wall Time         : {total_time:.1f} s ({completed_matches / max(0.1, total_time):.1f} matches/sec)")
    print("=" * 76)

if __name__ == "__main__":
    main()
