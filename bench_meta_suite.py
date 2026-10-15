import os
import sys
import json
import subprocess
import time

ARCHETYPES = {
    "standard_meta": """Dragonite @ Lum Berry
Ability: Multiscale
EVs: 252 Atk / 4 SpD / 252 Spe
Adamant Nature
- Extreme Speed
- Outrage
- Earthquake
- Fire Punch

Metagross @ Assault Vest
Ability: Clear Body
EVs: 252 HP / 252 Atk / 4 Spe
Adamant Nature
- Meteor Mash
- Bullet Punch
- Earthquake
- Zen Headbutt

Garchomp @ Life Orb
Ability: Rough Skin
EVs: 252 Atk / 4 SpD / 252 Spe
Jolly Nature
- Earthquake
- Outrage
- Stone Edge
- Swords Dance
""",

    "sand_offense": """Tyranitar @ Choice Band
Ability: Sand Stream
EVs: 252 HP / 252 Atk / 4 SpD
Adamant Nature
- Stone Edge
- Crunch
- Earthquake
- Iron Head

Excadrill @ Focus Sash
Ability: Sand Rush
EVs: 252 Atk / 4 Def / 252 Spe
Adamant Nature
- Earthquake
- Iron Head
- Rock Slide
- Swords Dance

Dragapult @ Life Orb
Ability: Infiltrator
EVs: 252 Atk / 4 SpD / 252 Spe
Jolly Nature
- Dragon Darts
- Phantom Force
- Flamethrower
- U-turn
""",

    "stall_balance": """Ferrothorn @ Leftovers
Ability: Iron Barbs
EVs: 252 HP / 252 Def / 4 SpD
Relaxed Nature
- Gyro Ball
- Power Whip
- Leech Seed
- Protect

Corviknight @ Leftovers
Ability: Mirror Armor
EVs: 252 HP / 252 Def / 4 SpD
Impish Nature
- Body Press
- Iron Defense
- Roost
- Brave Bird

Togekiss @ Heavy-Duty Boots
Ability: Serene Grace
EVs: 252 HP / 4 SpA / 252 Spe
Timid Nature
- Air Slash
- Dazzling Gleam
- Roost
- Aura Sphere
""",

    "special_sweeper": """Volcarona @ Heavy-Duty Boots
Ability: Flame Body
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
- Quiver Dance
- Bug Buzz
- Fiery Dance
- Giga Drain

Gengar @ Focus Sash
Ability: Cursed Body
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
- Shadow Ball
- Sludge Bomb
- Focus Blast
- Thunderbolt

Hydreigon @ Choice Specs
Ability: Levitate
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
- Draco Meteor
- Dark Pulse
- Flamethrower
- Flash Cannon
""",

    "priority_offense": """Lucario @ Life Orb
Ability: Inner Focus
EVs: 252 Atk / 4 SpD / 252 Spe
Jolly Nature
- Close Combat
- Extreme Speed
- Meteor Mash
- Swords Dance

Dragonite @ Lum Berry
Ability: Multiscale
EVs: 252 Atk / 4 SpD / 252 Spe
Adamant Nature
- Extreme Speed
- Outrage
- Earthquake
- Fire Punch

Scizor @ Metal Coat
Ability: Technician
EVs: 252 HP / 252 Atk / 4 SpD
Adamant Nature
- Bullet Punch
- Close Combat
- Knock Off
- Swords Dance
""",

    "rain_bulky": """Gyarados @ Lum Berry
Ability: Intimidate
EVs: 252 Atk / 4 SpD / 252 Spe
Jolly Nature
- Waterfall
- Earthquake
- Stone Edge
- Dragon Dance

Lapras @ Assault Vest
Ability: Water Absorb
EVs: 252 HP / 252 SpA / 4 SpD
Modest Nature
- Freeze-Dry
- Hydro Pump
- Thunderbolt
- Ice Beam

Arcanine @ Leftovers
Ability: Intimidate
EVs: 252 HP / 4 Atk / 252 Spe
Jolly Nature
- Flare Blitz
- Extreme Speed
- Will-O-Wisp
- Close Combat
"""
}

def setup_archetypes():
    os.makedirs("teams/archetypes", exist_ok=True)
    for name, content in ARCHETYPES.items():
        path = f"teams/archetypes/{name}.txt"
        with open(path, "w") as f:
            f.write(content.strip() + "\n")

def run_match(a1, a2, t1, t2, n, random_foe=False, seed=42):
    cmd = ["node", "harness.js", "--a1", a1, "--a2", a2, "--t1", t1, "-n", str(n)]
    if random_foe:
        cmd += ["--random", "--seed", str(seed)]
    else:
        cmd += ["--t2", t2]
    out = subprocess.check_output(cmd).decode().strip()
    return json.loads(out.split("\n")[-1])

def main():
    agent_path = sys.argv[1] if len(sys.argv) > 1 else "agents/ultimate_anti_meta.py"
    team_path = sys.argv[2] if len(sys.argv) > 2 else "teams/ultimate_anti_meta.txt"
    matches_per_test = int(sys.argv[3]) if len(sys.argv) > 3 else 30

    setup_archetypes()
    print("=" * 72)
    print(f"BENCHMARKING AGENT: {agent_path}")
    print(f"TEAM: {team_path}")
    print(f"MATCHES PER ARCHETYPE: {matches_per_test}")
    print("=" * 72)

    total_wins = 0
    total_matches = 0
    max_ms = 0
    total_ms = 0
    total_decisions = 0
    total_illegals = 0

    opponents = [
        ("agents/template_agent.py", "Template Bot"),
        ("agents/decision_tree_agent.py", "Decision Tree Bot"),
        ("agents/q_learning_agent.py", "Q-Learning Bot")
    ]

    print("\n--- PHASE 1: TESTING ACROSS 6 FIXED COMPETITIVE ARCHETYPES ---")
    for arch_name in ARCHETYPES.keys():
        t2_path = f"teams/archetypes/{arch_name}.txt"
        print(f"\nArchetype: {arch_name.upper()}")
        for bot_path, bot_label in opponents:
            res = run_match(agent_path, bot_path, team_path, t2_path, matches_per_test)
            w = res["a1_wins"]
            n = res["matches"]
            wr = res["a1_winrate"] * 100
            st = res.get("a1_stats", {})
            total_wins += w
            total_matches += n
            total_illegals += st.get("illegal", 0)
            max_ms = max(max_ms, st.get("maxMs", 0))
            total_ms += st.get("avgMs", 0) * st.get("decisions", 0)
            total_decisions += st.get("decisions", 0)
            print(f"  vs {bot_label:18s}: {wr:5.1f}% ({w}/{n}) | avg={st.get('avgMs', 0):.1f}ms, max={st.get('maxMs', 0):.1f}ms, illegal={st.get('illegal', 0)}")

    print("\n--- PHASE 2: TESTING AGAINST RANDOM POOL TEAMS (GENERALIZATION) ---")
    for bot_path, bot_label in opponents:
        res = run_match(agent_path, bot_path, team_path, None, 40, random_foe=True, seed=1337)
        w = res["a1_wins"]
        n = res["matches"]
        wr = res["a1_winrate"] * 100
        st = res.get("a1_stats", {})
        total_wins += w
        total_matches += n
        total_illegals += st.get("illegal", 0)
        max_ms = max(max_ms, st.get("maxMs", 0))
        total_ms += st.get("avgMs", 0) * st.get("decisions", 0)
        total_decisions += st.get("decisions", 0)
        print(f"  vs Random Teams ({bot_label:18s}): {wr:5.1f}% ({w}/{n}) | avg={st.get('avgMs', 0):.1f}ms, max={st.get('maxMs', 0):.1f}ms")

    overall_wr = (total_wins / total_matches) * 100 if total_matches > 0 else 0
    overall_avg_ms = total_ms / max(1, total_decisions)
    print("\n" + "=" * 72)
    print("FINAL BENCHMARK SUMMARY")
    print("=" * 72)
    print(f"Total Matches:    {total_matches}")
    print(f"Total Wins:       {total_wins} / {total_matches}")
    print(f"Overall Win Rate: {overall_wr:.2f}%")
    print(f"Average Decision: {overall_avg_ms:.2f} ms")
    print(f"Max Decision:     {max_ms:.2f} ms")
    print(f"Illegal Moves:    {total_illegals}")
    print("=" * 72)

if __name__ == "__main__":
    main()
