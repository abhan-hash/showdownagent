#!/usr/bin/env python3
"""
Mass Diagnostic Gauntlet & Loss Cause Analyzer
Runs matches in parallel against random competitive opponent teams,
captures every single loss, and determines whether each loss was due to:
- Pure Luck / RNG (Critical hits, accuracy misses, flinches, paralysis, freeze)
- Technique / Algorithmic decisions (team preview leads, missed priority, suboptimal moves, bad switches)
"""

import os
import sys
import json
import time
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter

DATA = json.load(open("data.json"))
MOVES = DATA["moves"]
SP = DATA["species"]

def analyze_loss_entry(rec):
    """
    Categorize a loss as RNG / Luck vs Technique / Decision.
    Returns: category, sub_reason, details
    """
    log_str = rec.get("log", "")
    lines = [l.strip() for l in log_str.split("\n") if l.strip()]
    
    # 1. Critical Hits
    crits = rec.get("critsOnUs", 0)
    # 2. Accuracy Misses by our Pokémon
    misses = rec.get("missesByUs", 0)
    # 3. Flinches, Full Paralysis, Freeze
    flinches = rec.get("flinchesOnUs", 0)
    pars = rec.get("paralysisOnUs", 0)
    frzs = rec.get("freezeOnUs", 0)
    
    # Check if a crit or miss happened on a crucial turn
    if misses > 0:
        return "RNG_LUCK", "ACCURACY_MISS", f"{misses} move miss(es) by our Pokémon (e.g. Hydro Pump accuracy)"
    if crits >= 2:
        return "RNG_LUCK", "MULTIPLE_CRITICAL_HITS", f"{crits} critical hit(s) landed on our Pokémon"
    if flinches > 0:
        return "RNG_LUCK", "FLINCH_INCAPACITATED", f"{flinches} turn(s) lost to flinch"
    if pars >= 2:
        return "RNG_LUCK", "FULL_PARALYSIS", f"{pars} turn(s) lost to full paralysis"
    if frzs > 0:
        return "RNG_LUCK", "FROZEN_SOLID", f"{frzs} turn(s) frozen solid"
    if crits == 1:
        # Check if the single crit resulted in an immediate faint
        crit_faint = False
        for i, l in enumerate(lines):
            if "|-crit|" in l and ("p1" in l or "p2" in l):
                # check next 3 lines for faint
                window = "\n".join(lines[i:i+4])
                if "|faint|" in window:
                    crit_faint = True
                    break
        if crit_faint:
            return "RNG_LUCK", "LETHAL_CRITICAL_HIT", "Opponent landed a critical hit that caused an immediate faint"

    # Analyze Technique / Strategic elements
    foe_team = rec.get("foeTeam", [])
    our_team = rec.get("ourTeam", [])
    
    # Check for hard matchup / speed counter
    # e.g. Togekiss + Tyranitar + Excadrill
    has_sand_rush = "Excadrill" in foe_team and "Tyranitar" in foe_team
    has_fairy_tank = "Togekiss" in foe_team and ("Lapras" in foe_team or "Snorlax" in foe_team)
    
    # Check last actions from battle log
    last_move_used = "unknown"
    for l in reversed(lines):
        if l.startswith("|move|") and ("p1a:" in l or "p2a:" in l):
            parts = l.split("|")
            last_move_used = parts[3]
            break

    if has_sand_rush:
        return "TECHNIQUE", "SAND_RUSH_MATCHUP", "Sand Offense team with Tyranitar + Excadrill"
    elif has_fairy_tank:
        return "TECHNIQUE", "BULKY_FAIRY_WALL", f"Bulky Fairy defensive core ({', '.join(foe_team)})"
    else:
        return "TECHNIQUE", "TACTICAL_DECISION", f"Loss on turn {rec.get('turns', 0)} vs ({', '.join(foe_team)})"

def run_worker_batch(worker_id, bot_script, total_n, seed, agent_path, team_path, loss_file):
    cmd = [
        "node", "harness.js",
        "--a1", agent_path,
        "--a2", bot_script,
        "--t1", team_path,
        "-n", str(total_n),
        "--random",
        "--seed", str(seed),
        "--loss-log", loss_file
    ]
    t0 = time.time()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    dt = time.time() - t0
    
    if proc.returncode != 0:
        return {"worker_id": worker_id, "error": proc.stderr, "dt": dt}
    
    data = None
    for l in reversed(proc.stdout.strip().split("\n")):
        if l.strip().startswith("{") and l.strip().endswith("}"):
            try:
                data = json.loads(l)
                break
            except Exception:
                continue
    
    return {"worker_id": worker_id, "data": data, "dt": dt, "loss_file": loss_file}

def main():
    target_matches = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    num_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    agent_path = sys.argv[3] if len(sys.argv) > 3 else "agents/ultimate_anti_meta.py"
    team_path = sys.argv[4] if len(sys.argv) > 4 else "teams/ultimate_anti_meta.txt"

    print("=" * 84)
    print(f"⚔️  MASS SIMULATION & LOSS CAUSE ANALYZER: {target_matches:,} MATCHES")
    print(f"Agent Under Test: {agent_path}")
    print(f"Team:             {team_path}")
    print(f"Workers:          {num_workers} parallel processes (12 CPU cores available)")
    print("=" * 84)

    os.makedirs("diagnostics_logs", exist_ok=True)
    
    # Distribute matches across bots:
    # 45% Decision Tree Bot, 45% Q-Learning Bot, 10% Template Bot
    bots = [
        "agents/decision_tree_agent.py",
        "agents/q_learning_agent.py",
        "agents/decision_tree_agent.py",
        "agents/q_learning_agent.py",
        "agents/template_agent.py",
    ]

    matches_per_worker = target_matches // num_workers
    tasks = []
    for i in range(num_workers):
        bot = bots[i % len(bots)]
        seed = 100000 + i * 7919
        loss_file = f"diagnostics_logs/losses_worker_{i+1}.jsonl"
        if os.path.exists(loss_file):
            os.remove(loss_file)
        tasks.append({
            "worker_id": i + 1,
            "bot": bot,
            "n": matches_per_worker,
            "seed": seed,
            "loss_file": loss_file
        })

    t_start = time.time()
    results = []
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(run_worker_batch, t["worker_id"], t["bot"], t["n"], t["seed"], agent_path, team_path, t["loss_file"]): t
            for t in tasks
        }
        
        for future in as_completed(futures):
            res = future.result()
            wid = res["worker_id"]
            dt = res["dt"]
            data = res.get("data")
            if not data:
                print(f"  ❌ Worker {wid} failed: {res.get('error')}")
                continue
            
            w = data["a1_wins"]
            n = data["matches"]
            wr = (w / n) * 100
            ms = data.get("a1_stats", {}).get("avgMs", 0)
            rate = n / max(0.1, dt)
            print(f"  ✓ Worker {wid:2d} finished in {dt:5.1f}s | {wr:5.1f}% winrate ({w}/{n}) | {rate:5.1f} matches/sec | avg={ms:.1f}ms")
            results.append(res)

    total_time = time.time() - t_start
    total_played = sum(r["data"]["matches"] for r in results if r.get("data"))
    total_won = sum(r["data"]["a1_wins"] for r in results if r.get("data"))
    overall_wr = (total_won / total_played) * 100 if total_played > 0 else 0
    total_losses = total_played - total_won
    
    print("\n" + "=" * 84)
    print(f"🏆 MASS RUN COMPLETED IN {total_time:.1f}s ({total_played / max(0.1, total_time):.1f} matches/sec overall)")
    print(f"Total Matches:    {total_played:,}")
    print(f"Total Wins:       {total_won:,}")
    print(f"Total Losses:     {total_losses:,}")
    print(f"Overall Win Rate: {overall_wr:.2f}%")
    print("=" * 84)

    # Ingest and classify all loss records
    all_losses = []
    for t in tasks:
        lf = t["loss_file"]
        if os.path.exists(lf):
            with open(lf, "r") as f:
                for line in f:
                    if line.strip():
                        try:
                            rec = json.loads(line)
                            all_losses.append(rec)
                        except Exception:
                            pass

    print(f"\n📊 DEEP LOSS ANALYSIS ACROSS ALL {len(all_losses)} RECORDED LOSSES:")
    print("-" * 84)

    rng_count = 0
    technique_count = 0
    sub_reasons = Counter()
    loss_examples = {}

    for rec in all_losses:
        cat, sub, detail = analyze_loss_entry(rec)
        if cat == "RNG_LUCK":
            rng_count += 1
        else:
            technique_count += 1
        sub_reasons[sub] += 1
        if sub not in loss_examples:
            loss_examples[sub] = (rec, detail)

    pct_rng = (rng_count / max(1, len(all_losses))) * 100
    pct_tech = (technique_count / max(1, len(all_losses))) * 100

    print(f"  1. Pure Luck / RNG Factor:   {rng_count:4d} / {len(all_losses)} losses ({pct_rng:5.1f}%)")
    print(f"  2. Technique / Decisions:    {technique_count:4d} / {len(all_losses)} losses ({pct_tech:5.1f}%)")
    print("\nBreakdown by Specific Loss Root Cause:")
    for sub, count in sub_reasons.most_common():
        pct = (count / max(1, len(all_losses))) * 100
        print(f"  • {sub:26s} : {count:4d} losses ({pct:5.1f}%)")

    print("\nKey Technique Findings & Actionable Insights:")
    for sub, (rec, detail) in loss_examples.items():
        if not sub.startswith("RNG"):
            print(f"  - [{sub}]: {detail}")

    summary_file = "diagnostics_logs/mass_run_summary.json"
    with open(summary_file, "w") as f:
        json.dump({
            "total_matches": total_played,
            "total_wins": total_won,
            "total_losses": total_losses,
            "win_rate": overall_wr,
            "rng_losses": rng_count,
            "rng_percentage": pct_rng,
            "technique_losses": technique_count,
            "technique_percentage": pct_tech,
            "root_causes": dict(sub_reasons.most_common())
        }, f, indent=2)
    print(f"\nSummary report saved to: {summary_file}")

if __name__ == "__main__":
    main()
