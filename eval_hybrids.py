import subprocess
import json

HYBRIDS = {
    # Hybrid 1: Greninja + Scizor + Togekiss
    "hybrid_1": """Greninja @ Life Orb
Ability: Protean
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Ice Beam
- Dark Pulse
- Hydro Pump
- U-turn

Scizor @ Metal Coat
Ability: Technician
EVs: 252 HP / 252 Atk / 4 SpD
Adamant Nature
- Bullet Punch
- Close Combat
- Swords Dance
- U-turn

Togekiss @ Leftovers
Ability: Serene Grace
EVs: 252 HP / 4 SpA / 252 Spe
Timid Nature
- Air Slash
- Dazzling Gleam
- Aura Sphere
- Roost
""",

    # Hybrid 2: Dragapult + Scizor + Togekiss
    "hybrid_2": """Dragapult @ Choice Band
Ability: Infiltrator
EVs: 252 Atk / 4 SpD / 252 Spe
Jolly Nature
- Dragon Darts
- Phantom Force
- Flamethrower
- U-turn

Scizor @ Metal Coat
Ability: Technician
EVs: 252 HP / 252 Atk / 4 SpD
Adamant Nature
- Bullet Punch
- Close Combat
- Swords Dance
- U-turn

Togekiss @ Leftovers
Ability: Serene Grace
EVs: 252 HP / 4 SpA / 252 Spe
Timid Nature
- Air Slash
- Dazzling Gleam
- Aura Sphere
- Roost
""",

    # Hybrid 3: Dragapult + Greninja + Scizor
    "hybrid_3": """Dragapult @ Choice Band
Ability: Infiltrator
EVs: 252 Atk / 4 SpD / 252 Spe
Jolly Nature
- Dragon Darts
- Phantom Force
- Flamethrower
- U-turn

Greninja @ Life Orb
Ability: Protean
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Ice Beam
- Dark Pulse
- Hydro Pump
- U-turn

Scizor @ Metal Coat
Ability: Technician
EVs: 252 HP / 252 Atk / 4 SpD
Adamant Nature
- Bullet Punch
- Close Combat
- Swords Dance
- U-turn
""",

    # Hybrid 4: Dragonite + Scizor + Togekiss
    "hybrid_4": """Dragonite @ Lum Berry
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
- Swords Dance
- U-turn

Togekiss @ Leftovers
Ability: Serene Grace
EVs: 252 HP / 4 SpA / 252 Spe
Timid Nature
- Air Slash
- Dazzling Gleam
- Aura Sphere
- Roost
"""
}

def main():
    for name, content in HYBRIDS.items():
        team_path = f"teams/{name}.txt"
        agent_path = f"agents/{name}.py"
        with open(team_path, "w") as f:
            f.write(content)
        subprocess.run(["python3", "build_agent.py", team_path, agent_path], check=True, stdout=subprocess.DEVNULL)
        
        # Test 1: vs Base Team (50 matches)
        cmd_base = ["node", "harness.js", "--a1", agent_path, "--a2", "agents/template_agent.py", "--t1", team_path, "--t2", "teams/base.txt", "-n", "40"]
        d_base = json.loads(subprocess.check_output(cmd_base).decode().strip().split("\n")[-1])

        # Test 2: vs Random Teams (40 matches)
        cmd_rnd = ["node", "harness.js", "--a1", agent_path, "--a2", "agents/q_learning_agent.py", "--t1", team_path, "-n", "40", "--random", "--seed", "11"]
        d_rnd = json.loads(subprocess.check_output(cmd_rnd).decode().strip().split("\n")[-1])

        print(f"{name:12s}: vs Base={d_base['a1_winrate']*100:5.1f}% ({d_base['a1_wins']}/{d_base['matches']}) | vs Random={d_rnd['a1_winrate']*100:5.1f}% ({d_rnd['a1_wins']}/{d_rnd['matches']})")

if __name__ == "__main__":
    main()
