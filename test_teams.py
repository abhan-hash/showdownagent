import os
import sys
import json
import subprocess

TEAMS = {
    "base": """Dragonite @ Lum Berry
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

    "anti_meta_1": """Togekiss @ Leftovers
Ability: Serene Grace
EVs: 252 HP / 4 SpA / 252 Spe
Timid Nature
- Air Slash
- Dazzling Gleam
- Aura Sphere
- Roost

Corviknight @ Leftovers
Ability: Mirror Armor
EVs: 252 HP / 252 Def / 4 SpD
Impish Nature
- Body Press
- Iron Defense
- Roost
- Brave Bird

Dragapult @ Choice Band
Ability: Infiltrator
EVs: 252 Atk / 4 SpD / 252 Spe
Jolly Nature
- Dragon Darts
- Phantom Force
- Flamethrower
- U-turn
""",

    "anti_meta_2": """Lapras @ Assault Vest
Ability: Water Absorb
EVs: 252 HP / 252 SpA / 4 SpD
Modest Nature
- Freeze-Dry
- Hydro Pump
- Thunderbolt
- Ice Beam

Togekiss @ Leftovers
Ability: Serene Grace
EVs: 252 HP / 4 SpA / 252 Spe
Timid Nature
- Air Slash
- Dazzling Gleam
- Aura Sphere
- Roost

Metagross @ Assault Vest
Ability: Clear Body
EVs: 252 HP / 252 Atk / 4 Spe
Adamant Nature
- Meteor Mash
- Bullet Punch
- Earthquake
- Zen Headbutt
""",

    "anti_meta_3": """Scizor @ Metal Coat
Ability: Technician
EVs: 252 HP / 252 Atk / 4 SpD
Adamant Nature
- Bullet Punch
- Close Combat
- Swords Dance
- U-turn

Dragonite @ Lum Berry
Ability: Multiscale
EVs: 252 Atk / 4 SpD / 252 Spe
Adamant Nature
- Extreme Speed
- Outrage
- Earthquake
- Fire Punch

Greninja @ Life Orb
Ability: Protean
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Ice Beam
- Dark Pulse
- Hydro Pump
- U-turn
""",

    "anti_meta_4": """Ferrothorn @ Leftovers
Ability: Iron Barbs
EVs: 252 HP / 252 Def / 4 SpD
Relaxed Nature
- Gyro Ball
- Power Whip
- Leech Seed
- Protect

Togekiss @ Leftovers
Ability: Serene Grace
EVs: 252 HP / 4 SpA / 252 Spe
Timid Nature
- Air Slash
- Dazzling Gleam
- Aura Sphere
- Roost

Garchomp @ Life Orb
Ability: Rough Skin
EVs: 252 Atk / 4 SpD / 252 Spe
Jolly Nature
- Earthquake
- Outrage
- Stone Edge
- Swords Dance
""",

    "anti_meta_5": """Dragapult @ Life Orb
Ability: Infiltrator
EVs: 252 Atk / 4 SpD / 252 Spe
Jolly Nature
- Dragon Darts
- Phantom Force
- Flamethrower
- U-turn

Metagross @ Assault Vest
Ability: Clear Body
EVs: 252 HP / 252 Atk / 4 Spe
Adamant Nature
- Meteor Mash
- Bullet Punch
- Earthquake
- Zen Headbutt

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
    os.makedirs("teams", exist_ok=True)
    for name, content in TEAMS.items():
        path = f"teams/{name}.txt"
        with open(path, "w") as f:
            f.write(content)

    print("Created team files:", list(TEAMS.keys()))

if __name__ == "__main__":
    main()
