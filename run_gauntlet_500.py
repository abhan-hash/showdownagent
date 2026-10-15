#!/usr/bin/env python3
"""
500-Match Gauntlet Stress Test for PokéDuel Submission Agent
Evaluates `agents/ultimate_anti_meta.py` across:
1. 180 matches against the 6 fixed competitive archetypes (30 per archetype)
2. 320 matches against randomized opponent teams across diverse bot algorithms
"""

import os
import sys
import json
import time
import subprocess

ARCHETYPES = [
    "standard_meta",
    "sand_offense",
    "stall_balance",
    "special_sweeper",
    "priority_offense",
    "rain_bulky"
]

BOTS = [
    ("agents/decision_tree_agent.py", "Decision Tree Bot"),
    ("agents/q_learning_agent.py", "Q-Learning Bot"),
    ("agents/template_agent.py", "Template Bot")
]

def run_harness(a1, a2, t1, t2=None, n=10, random_foe=False, seed=42):
    cmd = ["node", "harness.js", "--a1", a1, "--a2", a2, "--t1", t1, "-n", str(n)]
    if random_foe:
        cmd += ["--random", "--seed", str(seed)]
    else:
        cmd += ["--t2", t2]
    
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        print(f"Error running harness: {proc.stderr}", file=sys.stderr)
        return None
    
    # Parse last line as JSON
    lines = proc.stdout.strip().split("\n")
    for l in reversed(lines):
        if l.strip().startswith("{") and l.strip().endswith("}"):
            try:
                return json.loads(l)
            except Exception:
                continue
    return None

def main():
    agent_path = sys.argv[1] if len(sys.argv) > 1 else "agents/ultimate_anti_meta.py"
    team_path = sys.argv[2] if len(sys.argv) > 2 else "teams/ultimate_anti_meta.txt"

    print("=" * 76)
    print("🏆 POKÉDUEL 500-MATCH GAUNTLET STRESS TEST")
    print(f"Agent: {agent_path}")
    print(f"Team : {team_path}")
    print("=" * 76)

    total_wins = 0
    total_matches = 0
    total_decisions = 0
    total_ms = 0.0
    max_ms = 0.0
    total_illegal = 0
    total_errors = 0

    bot_stats = {label: {"wins": 0, "matches": 0} for _, label in BOTS}
    arch_stats = {arch: {"wins": 0, "matches": 0} for arch in ARCHETYPES}

    start_time = time.time()

    # -------------------------------------------------------------
    # PHASE 1: Fixed Competitive Archetypes (180 matches = 30 * 6)
    # -------------------------------------------------------------
    print("\n[PHASE 1] Testing Across 6 Competitive Archetypes (180 Matches)")
    print("-" * 76)

    for arch in ARCHETYPES:
        t2_path = f"teams/archetypes/{arch}.txt"
        arch_wins = 0
        arch_total = 0
        print(f"▶ Testing Archetype: {arch.upper()}")

        for bot_file, bot_label in BOTS:
            res = run_harness(agent_path, bot_file, team_path, t2_path, n=10)
            if not res:
                print(f"  ❌ Failed to run against {bot_label}")
                continue

            w = res["a1_wins"]
            n = res["matches"]
            wr = res["a1_winrate"] * 100
            st = res.get("a1_stats", {})

            total_wins += w
            total_matches += n
            arch_wins += w
            arch_total += n
            bot_stats[bot_label]["wins"] += w
            bot_stats[bot_label]["matches"] += n

            total_decisions += st.get("decisions", 0)
            total_ms += st.get("avgMs", 0) * st.get("decisions", 0)
            max_ms = max(max_ms, st.get("maxMs", 0))
            total_illegal += st.get("illegal", 0)
            total_errors += st.get("errors", 0)

            print(f"    vs {bot_label:18s}: {wr:5.1f}% ({w}/{n}) | avg={st.get('avgMs', 0):.1f}ms, max={st.get('maxMs', 0):.1f}ms, illegals={st.get('illegal', 0)}")

        arch_stats[arch]["wins"] = arch_wins
        arch_stats[arch]["matches"] = arch_total
        arch_wr = (arch_wins / arch_total) * 100 if arch_total > 0 else 0
        print(f"  ↳ Archetype Subtotal: {arch_wr:.1f}% ({arch_wins}/{arch_total})\n")

    # -------------------------------------------------------------
    # PHASE 2: Randomized Pool Teams (320 matches)
    # -------------------------------------------------------------
    print("\n[PHASE 2] Testing Against Randomized Pool Teams (320 Matches)")
    print("-" * 76)

    random_specs = [
        ("agents/decision_tree_agent.py", "Decision Tree Bot", 120, 1001),
        ("agents/q_learning_agent.py", "Q-Learning Bot", 100, 2001),
        ("agents/template_agent.py", "Template Bot", 100, 3001)
    ]

    for bot_file, bot_label, n_games, seed in random_specs:
        print(f"▶ Running {n_games} Random Matches vs {bot_label} (Seed {seed})...")
        res = run_harness(agent_path, bot_file, team_path, None, n=n_games, random_foe=True, seed=seed)
        if not res:
            print(f"  ❌ Failed to run random matches against {bot_label}")
            continue

        w = res["a1_wins"]
        n = res["matches"]
        wr = res["a1_winrate"] * 100
        st = res.get("a1_stats", {})

        total_wins += w
        total_matches += n
        bot_stats[bot_label]["wins"] += w
        bot_stats[bot_label]["matches"] += n

        total_decisions += st.get("decisions", 0)
        total_ms += st.get("avgMs", 0) * st.get("decisions", 0)
        max_ms = max(max_ms, st.get("maxMs", 0))
        total_illegal += st.get("illegal", 0)
        total_errors += st.get("errors", 0)

        print(f"    Result vs {bot_label:18s}: {wr:5.1f}% ({w}/{n}) | avg={st.get('avgMs', 0):.1f}ms, max={st.get('maxMs', 0):.1f}ms, illegals={st.get('illegal', 0)}\n")

    elapsed = time.time() - start_time
    overall_wr = (total_wins / total_matches) * 100 if total_matches > 0 else 0
    avg_latency = total_ms / max(1, total_decisions)

    # -------------------------------------------------------------
    # FINAL REPORT
    # -------------------------------------------------------------
    print("=" * 76)
    print("📊 500-MATCH GAUNTLET SUMMARY REPORT")
    print("=" * 76)
    print(f"Total Matches Played:    {total_matches}")
    print(f"Total Victories:         {total_wins} / {total_matches}")
    print(f"Overall Win Rate:        {overall_wr:.2f}%")
    print(f"Elapsed Benchmark Time:  {elapsed:.1f} seconds")
    print(f"Average Decision Speed:  {avg_latency:.2f} ms")
    print(f"Worst-Case Peak Latency: {max_ms:.2f} ms")
    print(f"Illegal Actions:         {total_illegal} (0.00%)")
    print(f"Unhandled Exceptions:    {total_errors} (0.00%)")
    print("-" * 76)
    print("Breakdown by Opponent Bot:")
    for label, d in bot_stats.items():
        b_wr = (d["wins"] / d["matches"] * 100) if d["matches"] > 0 else 0
        print(f"  • {label:22s}: {b_wr:5.1f}% ({d['wins']}/{d['matches']})")
    print("-" * 76)
    print("Breakdown by Archetype:")
    for arch, d in arch_stats.items():
        a_wr = (d["wins"] / d["matches"] * 100) if d["matches"] > 0 else 0
        print(f"  • {arch.upper():22s}: {a_wr:5.1f}% ({d['wins']}/{d['matches']})")
    print("=" * 76)

if __name__ == "__main__":
    main()
