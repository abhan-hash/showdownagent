"""
Scikit-Learn Decision Tree Agent for Pokemon Showdown 3v3 Battles
Uses a trained DecisionTreeClassifier to predict optimal competitive actions from battlefield feature vectors.
"""

import numpy as np
from sklearn.tree import DecisionTreeClassifier

class PokemonAgent:
    """
    ML Agent using an interpretable Decision Tree policy.
    """
    def __init__(self):
        # Initialize and fit synthetic competitive decision policy tree
        self.clf = DecisionTreeClassifier(max_depth=6, random_state=42)
        
        # Fit with competitive battle state training vectors
        # Features: [my_hp, foe_hp, max_type_mult, is_my_turn_lead]
        X_train = np.array([
            [100, 100, 2.0, 1], # Healthy, 2x super effective -> Attack (0)
            [100, 50,  2.0, 1], # Healthy, foe half HP -> Finish with Super Effective (0)
            [20,  90,  0.5, 0], # Low HP, resisted -> Switch to Bench (4)
            [15,  30,  2.0, 1], # Low HP, but can KO foe -> Attack (0)
            [80,  100, 1.0, 1], # Even matchup -> Attack (0)
            [10,  100, 0.5, 0], # Dangerously low HP -> Switch (4)
            [90,  10,  1.0, 1], # Foe critically low -> Quick Attack (1)
            [50,  50,  4.0, 1], # 4x weakness on foe -> Massive Attack (0)
        ])
        y_train = np.array([0, 0, 4, 0, 0, 4, 1, 0])
        self.clf.fit(X_train, y_train)

    def decide(self, observation: dict) -> str:
        if observation.get("team_preview"):
            return "team 123"

        valid_switches = observation.get("valid_switches", [])
        valid_moves = observation.get("valid_moves", [])

        if observation.get("force_switch"):
            if valid_switches:
                best = max(valid_switches, key=lambda s: s.get("hp_percent", 0))
                return f"switch {best.get('index', 1)}"
            return "pass"

        my_hp = observation.get("my_active", {}).get("hp_percent", 100)
        foe_hp = observation.get("foe", {}).get("hp_percent", 100)
        max_mult = max([m.get("type_multiplier", 1.0) for m in valid_moves], default=1.0)
        has_lead = 1 if observation.get("turn", 1) <= 3 else 0

        features = np.array([[my_hp, foe_hp, max_mult, has_lead]])
        prediction = self.clf.predict(features)[0]

        # Action 4: Switch if beneficial
        if prediction == 4 and valid_switches and my_hp < 30:
            best_switch = max(valid_switches, key=lambda s: s.get("hp_percent", 0))
            return f"switch {best_switch.get('index', 2)}"

        # Find best move by predicted preference and damage
        best_move = valid_moves[0] if valid_moves else None
        max_score = -1.0

        for m in valid_moves:
            score = (m.get("base_power", 50) or 50) * m.get("type_multiplier", 1.0)
            if m.get("stab"):
                score *= 1.5
            if score > max_score:
                max_score = score
                best_move = m

        if best_move:
            return f"move {best_move.get('index', 1)}"
        return "move 1"
