# PokéDuel AI - Official Submission Package (Backup & Fallback)

> **Status**: Verified & Tournament Ready  
> **Format**: Gen 9 3v3 Singles (Custom Roster)  
> **Engine**: Pokémon Showdown (`@pkmn/sim` / Python 3 Decision API)  
> **Dependencies**: Pure Standard Library (`json`, `math`). Zero external pip packages.

---

## 📦 What to Upload on the Portal / Website

Depending on how the submission portal accepts your algorithm and team, use the corresponding file(s) below:

| Submission Field | File to Use / Upload | Description |
| :--- | :--- | :--- |
| **Agent / Algorithm Script** | [`agent.py`](agent.py) | Standalone Python 3 algorithm containing `PokemonAgent` class with `decide(self, observation)` |
| **Team Text / Export** | [`team.txt`](team.txt) | 3-Pokémon team export in standard Pokémon Showdown format |
| **All-in-One ZIP Bundle** | [`submission.zip`](submission.zip) | Complete archive containing `agent.py`, `team.txt`, and documentation |

*(Note: `ultimate_anti_meta.py` and `ultimate_anti_meta.txt` are identical copies included in case the portal specifically requires the named project files).*

---

## 🛡️ Team Roster & Official EV Preset Compliance

All 3 Pokémon strictly use the official 6 EV presets allowed by the platform:

```text
Dragapult @ Choice Band
Ability: Infiltrator
EVs: 252 Atk / 4 SpD / 252 Spe
Jolly Nature
- Dragon Darts
- Phantom Force
- Flamethrower
- U-turn

Greninja @ Focus Sash
Ability: Protean
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
- Ice Beam
- Dark Pulse
- Hydro Pump
- Water Shuriken

Scizor @ Metal Coat
Ability: Technician
EVs: 252 HP / 252 Atk / 4 SpD
Adamant Nature
- Bullet Punch
- Close Combat
- Knock Off
- Swords Dance
```

### Official EV Preset Mapping:
1. **Dragapult**: `Physical Sweeper` (252 Atk / 252 Spe / 4 SpD, Jolly) — Base 142 Speed outspeeds the entire unboosted metagame. Infiltrator ignores screens and Substitute.
2. **Greninja**: `Special Sweeper` (252 SpA / 252 Spe / 4 SpD, Timid) — Focus Sash guarantees surviving any single hit. Protean provides STAB on all attacks. Priority Water Shuriken cleans up low-HP threats.
3. **Scizor**: `Bulky Attacker` (252 HP / 252 Atk / 4 SpD, Adamant) — Metal Coat + Technician powers Bullet Punch to 72 BP priority. Close Combat tears through Steel/Normal walls. Swords Dance punishes passive switches.

---

## ⚡ Core Engine Features & Bug Fixes Incorporated

The standalone agent in `agent.py` includes all critical competitive fixes:
1. **Type Immunity Handling (0x Multipliers)**:
   - Evaluates type immunities (e.g., Fairy immunity to Dragon) before committing Choice Band moves, preventing zero-damage lock loops.
2. **Lethal Priority Move Weighting (+2.5 bonus)**:
   - When facing foes with lethal priority (e.g., Extreme Speed, Bullet Punch, Water Shuriken), the opponent distribution anticipates priority execution rather than assuming slower high-BP moves.
3. **Choice-Lock Defensive Pivot Logic**:
   - If locked into a resisted move (`type_multiplier < 0.9`), the agent reduces switch margin from `+0.10` to `-0.02`, intelligently swapping to a better counter instead of staying in walled.
4. **Consecutive Switch Loop Prevention**:
   - Imposes a `-0.25` penalty if the agent switched on the previous turn, preventing endless back-and-forth flip-flops.
5. **Knock Off Item Stripping Mechanics**:
   - Damage calculations correctly scale Knock Off to 65 BP once the target's item has been removed.
6. **Sub-10ms Decision Speed**:
   - Average turn decision latency is ~5-9 ms, well below the portal timeout limits.

---

## 🧪 Verification & Self-Test

You can verify the package integrity at any time by running:
```bash
python3 test_submission.py
```
Expected output:
```text
✓ [PASS] PokemonAgent successfully instantiated.
✓ [PASS] Team Preview Decision: 'team 123' (Time: ~1.5 ms)
✓ [PASS] Regular Turn Decision: 'move 1' (Time: ~9.0 ms)
✓ [PASS] Forced Switch Decision: 'switch 2' (Time: ~0.1 ms)
🎉 ALL SUBMISSION INTEGRITY & PERFORMANCE CHECKS PASSED!
```
