"""
Tabular / Approximate Q-Learning Agent for Pokemon Showdown 3v3 Battles
Discretizes battlefield states and selects actions with the highest expected cumulative Q-value.
"""

import json
import numpy as np

class PokemonAgent:
    """
    Q-Learning Reinforcement Learning Agent for 3v3 Battles.
    """
    def __init__(self):
        # Q-table mapping discrete state keys to action values
        # Actions: 0: move 1, 1: move 2, 2: move 3, 3: move 4, 4: switch safe, 5: switch offensive
        self.q_table = {}
        self.default_action_values = [1.2, 1.2, 1.2, 1.2, 0.8, 0.9]

    def get_state_key(self, obs: dict) -> str:
        """
        Discretizes continuous battlefield dynamics into a compact state key.
        Format: (my_hp_bucket, foe_hp_bucket, foe_weakness_bucket, bench_alive_count)
        """
        my_hp = obs.get("my_active", {}).get("hp_percent", 100)
        foe_hp = obs.get("foe", {}).get("hp_percent", 100)

        # 3 HP bins: Critical (<30%), Mid (30-70%), Healthy (>70%)
        my_bin = 0 if my_hp < 30 else (1 if my_hp <= 70 else 2)
        foe_bin = 0 if foe_hp < 30 else (1 if foe_hp <= 70 else 2)

        # Max type multiplier available across legal moves
        valid_moves = obs.get("valid_moves", [])
        max_mult = max([m.get("type_multiplier", 1.0) for m in valid_moves], default=1.0)
        mult_bin = 2 if max_mult >= 2.0 else (1 if max_mult >= 1.0 else 0)

        # Alive teammates on bench
        valid_switches = obs.get("valid_switches", [])
        bench_count = min(2, len(valid_switches))

        return f"s_{my_bin}_{foe_bin}_{mult_bin}_{bench_count}"

    def decide(self, observation: dict) -> str:
        # Team Preview
        if observation.get("team_preview"):
            return "team 123"

        valid_switches = observation.get("valid_switches", [])
        valid_moves = observation.get("valid_moves", [])

        # Forced Switch
        if observation.get("force_switch"):
            if valid_switches:
                # Switch to highest HP teammate
                best = max(valid_switches, key=lambda s: s.get("hp_percent", 0))
                return f"switch {best.get('index', 1)}"
            return "pass"

        state_key = self.get_state_key(observation)
        q_values = self.q_table.get(state_key, list(self.default_action_values))

        # Score legal moves with Q-values + heuristics
        best_choice = "move 1"
        max_score = -9999.0

        for move in valid_moves:
            idx = move.get("index", 1) - 1
            base_q = q_values[idx] if idx < 4 else 1.0
            power = move.get("base_power", 50) or 50
            mult = move.get("type_multiplier", 1.0)
            stab = 1.5 if move.get("stab") else 1.0

            # Score = Q_value * Expected Damage Multiplier
            score = (base_q * 10.0) + (power * mult * stab * 0.5)

            if score > max_score:
                max_score = score
                best_choice = f"move {move.get('index', 1)}"

        # Evaluate tactical switch if at critical disadvantage
        my_hp = observation.get("my_active", {}).get("hp_percent", 100)
        if my_hp < 25 and valid_switches and q_values[4] > 1.5:
            best_switch = max(valid_switches, key=lambda s: s.get("hp_percent", 0))
            return f"switch {best_switch.get('index', 2)}"

        return best_choice
