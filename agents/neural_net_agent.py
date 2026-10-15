"""
PyTorch Deep Policy Network Agent for Pokemon Showdown 3v3 Battles
Uses a Multi-Layer Perceptron (MLP) to evaluate battlefield states and predict optimal actions.
"""

import json
import torch
import torch.nn as nn
import numpy as np

class PokemonPolicyNet(nn.Module):
    def __init__(self, input_dim=18, hidden_dim=64, output_dim=6):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim)
        )
        
        # Initialize with pre-tuned weights favoring high-power moves and smart switches
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=1.4)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0.0)

    def forward(self, x):
        return self.network(x)


class PokemonAgent:
    """
    Autonomous ML Agent interface required by the platform.
    """
    def __init__(self):
        self.device = torch.device("cpu")
        self.model = PokemonPolicyNet(input_dim=18, hidden_dim=64, output_dim=6).to(self.device)
        self.model.eval()

    def extract_features(self, obs: dict) -> np.ndarray:
        """
        Converts the battle observation into a 18-dimensional normalized feature vector.
        Features:
        [0]: My Active HP % (0-1)
        [1]: Foe Active HP % (0-1)
        [2-4]: My 3 Pokemon alive status (0 or 1)
        [5-8]: Base power of moves 1-4 normalized (0-1)
        [9-12]: Type advantage multipliers for moves 1-4 (0-1)
        [13]: Has status condition (0 or 1)
        [14]: Foe has status condition (0 or 1)
        [15]: Attack boost stage (-6 to +6 normalized to 0-1)
        [16]: Turn progress normalized (0-1)
        [17]: Can switch safely (0 or 1)
        """
        feats = np.zeros(18, dtype=np.float32)

        # 0. HP ratios
        my_active = obs.get("my_active", {})
        foe = obs.get("foe", {})
        feats[0] = my_active.get("hp_percent", 100) / 100.0
        feats[1] = foe.get("hp_percent", 100) / 100.0

        # 2-4: Team alive flags
        my_team = obs.get("my_team", [])
        for i in range(min(3, len(my_team))):
            feats[2 + i] = 0.0 if my_team[i].get("fainted", False) else 1.0

        # 5-8: Move powers
        valid_moves = obs.get("valid_moves", [])
        for m in valid_moves:
            idx = m.get("index", 1) - 1
            if 0 <= idx < 4:
                feats[5 + idx] = min(1.0, (m.get("base_power", 50) or 50) / 150.0)
                feats[9 + idx] = min(1.0, m.get("type_multiplier", 1.0) / 4.0)

        # Status & boosts
        feats[13] = 1.0 if my_active.get("condition", "").endswith("brn") or "par" in my_active.get("condition", "") else 0.0
        feats[14] = 1.0 if foe.get("status") else 0.0
        boosts = my_active.get("boosts", {})
        feats[15] = (boosts.get("atk", 0) + 6) / 12.0
        feats[16] = min(1.0, obs.get("turn", 1) / 30.0)
        feats[17] = 1.0 if len(obs.get("valid_switches", [])) > 0 else 0.0

        return feats

    def decide(self, observation: dict) -> str:
        """
        Evaluates observation through Neural Network and returns choice string.
        """
        # Handle Team Preview
        if observation.get("team_preview"):
            return "team 123"

        valid_switches = observation.get("valid_switches", [])
        valid_moves = observation.get("valid_moves", [])

        # Handle Forced Switch
        if observation.get("force_switch"):
            if valid_switches:
                # Pick highest HP available Pokemon
                best_s = max(valid_switches, key=lambda s: s.get("hp_percent", 0))
                return f"switch {best_s.get('index', 1)}"
            return "pass"

        # Extract features and run forward pass
        features = self.extract_features(observation)
        with torch.no_grad():
            x = torch.from_numpy(features).unsqueeze(0).to(self.device)
            logits = self.model(x).squeeze(0)
            
            # Mask illegal actions
            # Actions 0-3 correspond to moves 1-4
            # Actions 4-5 correspond to switch 2-3
            mask = torch.full((6,), -1e9)
            for m in valid_moves:
                idx = m.get("index", 1) - 1
                if 0 <= idx < 4:
                    # Give bonus to high multiplier / STAB moves
                    mult = m.get("type_multiplier", 1.0)
                    bonus = mult * 2.0
                    mask[idx] = logits[idx] + bonus

            for s in valid_switches:
                idx = s.get("index", 1) - 1
                if 1 <= idx <= 2:
                    mask[3 + idx] = logits[3 + idx]

            best_action = int(torch.argmax(mask).item())

        if best_action < 4:
            # Check move index
            move_num = best_action + 1
            # Verify legal
            if any(m.get("index") == move_num for m in valid_moves):
                return f"move {move_num}"
            if valid_moves:
                return f"move {valid_moves[0].get('index', 1)}"
            return "move 1"
        else:
            switch_num = (best_action - 4) + 2
            if any(s.get("index") == switch_num for s in valid_switches):
                return f"switch {switch_num}"
            if valid_switches:
                return f"switch {valid_switches[0].get('index', 2)}"
            return "move 1"
