"""
Custom ML Agent Template for Pokemon Showdown 3v3 Battles
Edit this file to implement your custom Machine Learning model (PyTorch, TensorFlow, Scikit-learn, or Heuristic RL).
"""

class PokemonAgent:
    """
    Every submitted ML algorithm must define class `PokemonAgent` with a `decide(self, observation)` method.
    """
    def __init__(self):
        # TODO: Load your trained model weights, parameters, or policy here
        # Example: self.model = torch.load('model.pt')
        pass

    def decide(self, observation: dict) -> str:
        """
        Input observation dictionary contains:
        ---------------------------------------
        observation["turn"]: int                -> Current turn number
        observation["team_preview"]: bool       -> True on team preview phase
        observation["force_switch"]: bool       -> True if active Pokemon fainted
        observation["my_active"]: dict          -> { name, types, hp_percent, stats, boosts, condition }
        observation["foe"]: dict                -> { name, types, hp_percent, status, boosts }
        observation["my_team"]: list[dict]      -> 3 Pokemon on your side with { name, hp_percent, active, fainted }
        observation["valid_moves"]: list[dict]  -> [{ index: 1, name: 'Thunderbolt', type: 'Electric', base_power: 90, type_multiplier: 2.0, stab: True }, ...]
        observation["valid_switches"]: list[dict]-> [{ index: 2, name: 'Charizard', hp_percent: 100, types: ['Fire', 'Flying'] }, ...]

        Return choice string:
        ---------------------
        'move 1'   -> Use move slot 1
        'move 2'   -> Use move slot 2
        'switch 2' -> Swap to bench Pokemon slot 2
        'team 123' -> Default team order during team preview
        """
        # 1. Team preview phase
        if observation.get("team_preview"):
            return "team 123"

        # 2. Forced switch phase (current Pokemon fainted)
        valid_switches = observation.get("valid_switches", [])
        if observation.get("force_switch"):
            if valid_switches:
                return f"switch {valid_switches[0]['index']}"
            return "pass"

        # 3. Decision phase: choose your move
        valid_moves = observation.get("valid_moves", [])
        if valid_moves:
            # Simple baseline: pick highest base power move
            best_move = max(valid_moves, key=lambda m: (m.get("base_power") or 0) * m.get("type_multiplier", 1.0))
            return f"move {best_move['index']}"

        return "move 1"
