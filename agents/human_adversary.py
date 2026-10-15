"""
Human Expert Adversary for Gen 9 3v3 Singles.
Implements competitive human strategies:
- Prediction of Choice locks (Dragapult locked into Dragon Darts against Fairy)
- Strategic switching into immunities and 4x resists (Togekiss into Dragon, Lapras into Water, Arcanine into Scizor)
- Free Setup exploitation (Quiver Dance, Dragon Dance, Nasty Plot on forced switches or locks)
- Priority sniping (Extreme Speed +2 to bypass +1 priority Water Shuriken / Bullet Punch)
- Status crippling (Will-O-Wisp on physical sweepers, Sleep Powder, Thunder Wave)
"""

class PokemonAgent:
    def __init__(self):
        self.foe_choice_lock = None  # Tracks what move opponent locked into
        self.foe_prev_move = None
        self.foe_prev_mon = None

    def decide(self, obs: dict) -> str:
        if obs.get("team_preview"):
            # Counter-lead logic:
            # If opponent has Dragapult/Scizor, leading Togekiss or Arcanine is ideal
            foe_team = [p.get("name") for p in obs.get("foe_team", [])]
            my_team = [p.get("name") for p in obs.get("my_team", [])]
            
            # Prioritize Togekiss or Arcanine as lead
            lead_idx = 1
            for name in ["Togekiss", "Arcanine", "Gyarados", "Lapras", "Volcarona"]:
                if name in my_team:
                    lead_idx = my_team.index(name) + 1
                    break
            
            order = [lead_idx] + [i for i in [1, 2, 3] if i != lead_idx]
            return f"team {''.join(str(x) for x in order)}"

        foe = obs.get("foe") or {}
        my = obs.get("my_active") or {}
        valid_moves = obs.get("valid_moves", [])
        valid_switches = obs.get("valid_switches", [])
        force_switch = obs.get("force_switch", False)

        fname = foe.get("name")
        fhp = foe.get("hp_percent", 100)
        mname = my.get("name")
        mhp = my.get("hp_percent", 100)

        # Track Choice lock
        if self.foe_prev_mon == fname and self.foe_prev_move:
            if fname in ("Dragapult", "Hydreigon", "Charizard", "Tyranitar"):
                self.foe_choice_lock = self.foe_prev_move
        elif self.foe_prev_mon != fname:
            self.foe_choice_lock = None
            self.foe_prev_mon = fname

        # 1. FORCED SWITCH HANDLING (Human picks best matchup)
        if force_switch:
            if not valid_switches:
                return "pass"
            
            # Score each available bench switch against current foe
            best_sw = valid_switches[0]["index"]
            best_sc = -999
            for s in valid_switches:
                sname = s.get("name")
                sc = 0
                if fname == "Dragapult":
                    if sname == "Togekiss": sc += 100 # Fairy immunity
                    elif sname in ("Corviknight", "Ferrothorn"): sc += 50
                    elif sname == "Arcanine": sc += 30 # Intimidate
                elif fname == "Scizor":
                    if sname in ("Arcanine", "Volcarona", "Charizard"): sc += 100 # 4x Fire resist & OHKO
                    elif sname == "Corviknight": sc += 60
                elif fname == "Greninja":
                    if sname == "Lapras": sc += 100 # Water Absorb + Freeze-Dry
                    elif sname in ("Ferrothorn", "Togekiss"): sc += 50
                    elif sname == "Dragonite": sc += 40 # Extreme Speed check
                if sc > best_sc:
                    best_sc = sc
                    best_sw = s["index"]
            return f"switch {best_sw}"

        # Helper to find move by name
        def get_move(mname_substr):
            for m in valid_moves:
                if mname_substr.lower() in m.get("name", "").lower():
                    return m
            return None

        # 2. PRIORITY REVENGE KILLING (+2 Extreme Speed beats +1 priority)
        # If foe is low (<= 35% or Sash 1 HP), click Extreme Speed immediately!
        espeed = get_move("extreme speed")
        if espeed and (fhp <= 35 or fhp == 1):
            return f"move {espeed['index']}"
        
        # Other priority (+1 Bullet Punch, Ice Shard, Water Shuriken)
        bp = get_move("bullet punch") or get_move("ice shard") or get_move("aqua jet")
        if bp and (fhp <= 20 or fhp == 1):
            return f"move {bp['index']}"

        # 3. EXPLOITING DRAGAPULT'S CHOICE LOCK
        # If Dragapult is locked into Dragon Darts and we are Togekiss -> IMMUNITY!
        if fname == "Dragapult" and self.foe_choice_lock in ("dragondarts", "dragon darts", "draco meteor"):
            if mname == "Togekiss":
                # Free turn! Click Nasty Plot if available, or Thunder Wave / Air Slash
                np = get_move("nasty plot")
                if np and my.get("boosts", {}).get("spa", 0) < 4:
                    return f"move {np['index']}"
                tw = get_move("thunder wave")
                if tw and not foe.get("status"):
                    return f"move {tw['index']}"
                aslash = get_move("air slash") or get_move("dazzling gleam")
                if aslash:
                    return f"move {aslash['index']}"

        # 4. PREDICTIVE SWITCHING INTO IMMUNITIES / HARD RESISTS
        if fname == "Dragapult" and mname not in ("Togekiss", "Corviknight", "Ferrothorn"):
            # If we suspect Dragon Darts, switch to Togekiss
            for s in valid_switches:
                if s.get("name") == "Togekiss":
                    return f"switch {s['index']}"

        if fname == "Scizor" and mname not in ("Arcanine", "Volcarona", "Charizard", "Corviknight"):
            # Switch into 4x Fire resist
            for s in valid_switches:
                if s.get("name") in ("Arcanine", "Volcarona", "Charizard"):
                    return f"switch {s['index']}"

        if fname == "Greninja" and mname not in ("Lapras", "Ferrothorn"):
            # If foe Greninja is Water, switch to Lapras (Water Absorb)
            for s in valid_switches:
                if s.get("name") == "Lapras":
                    return f"switch {s['index']}"

        # 5. SETUP MOVES ON ADVANTAGEOUS MATCHUPS
        # Volcarona facing Scizor -> Click Quiver Dance!
        if mname == "Volcarona" and fname == "Scizor":
            qd = get_move("quiver dance")
            if qd and my.get("boosts", {}).get("spa", 0) < 2:
                return f"move {qd['index']}"
            fd = get_move("fiery dance") or get_move("flamethrower") or get_move("fire blast")
            if fd:
                return f"move {fd['index']}"

        # Dragonite facing non-Ice threat -> Dragon Dance
        if mname == "Dragonite" and mhp >= 80 and fhp > 40:
            dd = get_move("dragon dance")
            if dd and my.get("boosts", {}).get("atk", 0) < 1:
                return f"move {dd['index']}"

        # Corviknight facing physical mon (Scizor) -> Iron Defense
        if mname == "Corviknight" and fname == "Scizor":
            id_mv = get_move("iron defense")
            if id_mv and my.get("boosts", {}).get("def", 0) < 4:
                return f"move {id_mv['index']}"
            bp_mv = get_move("body press")
            if bp_mv:
                return f"move {bp_mv['index']}"

        # 6. STATUS CRIPPLING
        # Burn Dragapult or Scizor
        if fname in ("Dragapult", "Scizor", "Garchomp") and not foe.get("status"):
            wow = get_move("will-o-wisp")
            if wow:
                return f"move {wow['index']}"
            sp = get_move("sleep powder")
            if sp:
                return f"move {sp['index']}"
            tw = get_move("thunder wave")
            if tw:
                return f"move {tw['index']}"

        # 7. SUPER-EFFECTIVE & HIGH-DAMAGE MOVES
        best_move = None
        best_score = -1
        for m in valid_moves:
            bp_val = m.get("base_power") or 0
            mult = m.get("type_multiplier", 1.0)
            stab = 1.5 if m.get("stab") else 1.0
            
            # Freeze-Dry special case vs Water
            if "freeze-dry" in m.get("name", "").lower() and "Water" in foe.get("types", []):
                mult *= 4.0
                
            score = bp_val * mult * stab
            if score > best_score:
                best_score = score
                best_move = m

        if best_move and best_score > 0:
            return f"move {best_move['index']}"

        # Default fallback
        if valid_moves:
            return "move 1"
        if valid_switches:
            return f"switch {valid_switches[0]['index']}"
        return "pass"
