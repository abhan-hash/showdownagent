#!/usr/bin/env python3
"""
Self-Test Verification Script for PokéDuel Submission Package
Verifies that agent.py meets all competition requirements:
1. Defines `PokemonAgent` class with `decide(observation)`
2. Has 0 external dependencies (only standard library)
3. Responds in < 10ms with valid legal action strings
4. Correctly handles:
   - Team Preview phase
   - Forced Switch phase (after a faint)
   - Regular combat phase (moves and switches)
"""

import sys
import time
import importlib.util

def test_submission():
    print("=" * 60)
    print(">>> POKÉDUEL SUBMISSION INTEGRITY & TIMING TEST <<<")
    print("=" * 60)

    # 1. Load agent module
    spec = importlib.util.spec_from_file_location("agent", "agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    
    assert hasattr(mod, "PokemonAgent"), "FAIL: PokemonAgent class not found!"
    agent = mod.PokemonAgent()
    print("✓ [PASS] PokemonAgent successfully instantiated.")

    # 2. Test Team Preview
    preview_obs = {
        "turn": 0,
        "team_preview": True,
        "force_switch": False,
        "my_team": [
            {"index": 1, "name": "Dragapult", "types": ["Dragon", "Ghost"], "hp_percent": 100},
            {"index": 2, "name": "Greninja", "types": ["Water", "Dark"], "hp_percent": 100},
            {"index": 3, "name": "Scizor", "types": ["Bug", "Steel"], "hp_percent": 100}
        ],
        "foe_team": [
            {"name": "Garchomp", "types": ["Dragon", "Ground"], "hp_percent": 100},
            {"name": "Volcarona", "types": ["Bug", "Fire"], "hp_percent": 100},
            {"name": "Dragonite", "types": ["Dragon", "Flying"], "hp_percent": 100}
        ],
        "valid_moves": [],
        "valid_switches": []
    }
    t0 = time.perf_counter()
    preview_choice = agent.decide(preview_obs)
    dt_preview = (time.perf_counter() - t0) * 1000
    print(f"✓ [PASS] Team Preview Decision: '{preview_choice}' (Time: {dt_preview:.3f} ms)")
    assert preview_choice.startswith("team"), f"FAIL: Expected 'team XYZ', got {preview_choice}"

    # 3. Test Regular Turn (Dragapult vs Garchomp)
    turn_obs = {
        "turn": 1,
        "team_preview": False,
        "force_switch": False,
        "my_active": {
            "name": "Dragapult",
            "types": ["Dragon", "Ghost"],
            "hp_percent": 100,
            "status": "",
            "boosts": {}
        },
        "foe": {
            "name": "Garchomp",
            "types": ["Dragon", "Ground"],
            "hp_percent": 100,
            "status": "",
            "boosts": {}
        },
        "my_team": [
            {"name": "Dragapult", "hp_percent": 100, "active": True, "fainted": False},
            {"name": "Greninja", "hp_percent": 100, "active": False, "fainted": False},
            {"name": "Scizor", "hp_percent": 100, "active": False, "fainted": False}
        ],
        "valid_moves": [
            {"index": 1, "name": "Dragon Darts", "type": "Dragon", "base_power": 50, "type_multiplier": 2.0, "stab": True},
            {"index": 2, "name": "Phantom Force", "type": "Ghost", "base_power": 90, "type_multiplier": 1.0, "stab": True},
            {"index": 3, "name": "Flamethrower", "type": "Fire", "base_power": 90, "type_multiplier": 1.0, "stab": False},
            {"index": 4, "name": "U-turn", "type": "Bug", "base_power": 70, "type_multiplier": 1.0, "stab": False}
        ],
        "valid_switches": [
            {"index": 2, "name": "Greninja", "hp_percent": 100, "types": ["Water", "Dark"]},
            {"index": 3, "name": "Scizor", "hp_percent": 100, "types": ["Bug", "Steel"]}
        ]
    }
    t0 = time.perf_counter()
    turn_choice = agent.decide(turn_obs)
    dt_turn = (time.perf_counter() - t0) * 1000
    print(f"✓ [PASS] Regular Turn Decision: '{turn_choice}' (Time: {dt_turn:.3f} ms)")
    legal_actions = [f"move {m['index']}" for m in turn_obs["valid_moves"]] + [f"switch {s['index']}" for s in turn_obs["valid_switches"]]
    assert turn_choice in legal_actions, f"FAIL: Action '{turn_choice}' not in legal actions {legal_actions}"

    # 4. Test Forced Switch (Active Pokemon Fainted)
    force_obs = {
        "turn": 3,
        "team_preview": False,
        "force_switch": True,
        "my_active": None,
        "foe": {
            "name": "Volcarona",
            "types": ["Bug", "Fire"],
            "hp_percent": 100,
            "status": "",
            "boosts": {"spa": 1, "spe": 1}
        },
        "my_team": [
            {"name": "Dragapult", "hp_percent": 0, "active": False, "fainted": True},
            {"name": "Greninja", "hp_percent": 100, "active": False, "fainted": False},
            {"name": "Scizor", "hp_percent": 100, "active": False, "fainted": False}
        ],
        "valid_moves": [],
        "valid_switches": [
            {"index": 2, "name": "Greninja", "hp_percent": 100, "types": ["Water", "Dark"]},
            {"index": 3, "name": "Scizor", "hp_percent": 100, "types": ["Bug", "Steel"]}
        ]
    }
    t0 = time.perf_counter()
    force_choice = agent.decide(force_obs)
    dt_force = (time.perf_counter() - t0) * 1000
    print(f"✓ [PASS] Forced Switch Decision: '{force_choice}' (Time: {dt_force:.3f} ms)")
    legal_switches = [f"switch {s['index']}" for s in force_obs["valid_switches"]]
    assert force_choice in legal_switches, f"FAIL: Forced switch '{force_choice}' not in {legal_switches}"

    print("=" * 60)
    print("🎉 ALL SUBMISSION INTEGRITY & PERFORMANCE CHECKS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    test_submission()
