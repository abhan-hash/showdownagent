"""
REDLINE Pokemon agent - search-based, standard library only.

Pipeline each turn:
  1. Update memory (foe moves seen/inferred, speed evidence, switch-in turns).
  2. Build a model of every mon (ours from MY_TEAM, foe from portal defaults + evidence).
  3. For each of my legal actions, simulate the turn against a distribution of foe actions
     (priority, speed probability, accuracy, damage rolls, KO thresholds), score the leaf
     with a material + 1v1-race evaluation, and pick the best blend of expected / worst case.
Everything is wrapped so that decide() can never return an illegal action.
"""
import json
import math

DATA = json.loads(r'''@@DATA@@''')
MY_TEAM = json.loads(r'''@@TEAM@@''')
TEAM_ORDER = "@@ORDER@@"
PARAMS = json.loads(r'''@@PARAMS@@''')

SP = DATA["species"]
MV = DATA["moves"]
TC = DATA["types"]
LVL = 100

NATURES = {
    "adamant": ("atk", "spa"), "jolly": ("spe", "spa"), "modest": ("spa", "atk"), "timid": ("spe", "atk"),
    "bold": ("def", "atk"), "calm": ("spd", "atk"), "impish": ("def", "spa"), "careful": ("spd", "spa"),
    "naive": ("spe", "spd"), "hasty": ("spe", "def"), "relaxed": ("def", "spe"),
}
STATS = ["hp", "atk", "def", "spa", "spd", "spe"]
PRIORITY_FOE_FIRST_TURN = {"fakeout", "firstimpression"}
HEAL_MOVES = {"roost", "recover", "morningsun", "synthesis", "softboiled", "slackoff", "wish", "rest"}
SETUP = {
    "swordsdance": {"atk": 2}, "dragondance": {"atk": 1, "spe": 1}, "nastyplot": {"spa": 2},
    "quiverdance": {"spa": 1, "spd": 1, "spe": 1}, "calmmind": {"spa": 1, "spd": 1}, "bulkup": {"atk": 1, "def": 1},
    "irondefense": {"def": 2}, "agility": {"spe": 2}, "growth": {"atk": 1, "spa": 1}, "curse": {"atk": 1, "def": 1},
}
STATUS_MOVES = {
    "willowisp": ("brn", 85), "thunderwave": ("par", 90), "sleeppowder": ("slp", 75), "toxic": ("psn", 90),
    "yawn": ("slp", 60), "leechseed": ("seed", 90)
}
OHKO_BAD = {"explosion"}
TWO_TURN_MOVES = {
    "phantomforce", "bounce", "solarbeam", "solarbeblade", "fly", "dig", "dive",
    "meteorbeam", "skullbash", "skyattack", "geomancy"
}
SEMI_INVULNERABLE_MOVES = {
    "phantomforce", "bounce", "fly", "dig", "dive"
}

SPECIES_ITEM_PRIOR = {
    "gengar": {"choicescarf": 0.35, "focussash": 0.35, "lifeorb": 0.30},
    "excadrill": {"focussash": 0.50, "choicescarf": 0.30, "lifeorb": 0.20},
    "hydreigon": {"choicespecs": 0.50, "choicescarf": 0.35, "lifeorb": 0.15},
    "togekiss": {"leftovers": 0.60, "choicescarf": 0.30, "heavydutyboots": 0.10},
    "garchomp": {"lifeorb": 0.50, "choicescarf": 0.25, "focussash": 0.15, "leftovers": 0.10},
    "alakazam": {"focussash": 0.60, "lifeorb": 0.40},
    "dragapult": {"choiceband": 0.45, "choicespecs": 0.30, "lifeorb": 0.25},
    "volcarona": {"heavydutyboots": 0.85, "focussash": 0.15},
    "arcanine": {"heavydutyboots": 0.80, "leftovers": 0.20},
    "dragonite": {"lumberry": 0.50, "weaknesspolicy": 0.30, "heavydutyboots": 0.20},
    "metagross": {"assaultvest": 0.80, "choiceband": 0.20},
    "scizor": {"metalcoat": 0.45, "choiceband": 0.35, "lifeorb": 0.20},
    "ferrothorn": {"leftovers": 0.65, "rockyhelmet": 0.35},
    "corviknight": {"leftovers": 0.65, "rockyhelmet": 0.35},
    "lapras": {"assaultvest": 0.60, "leftovers": 0.40},
    "snorlax": {"assaultvest": 0.50, "leftovers": 0.50},
    "blastoise": {"leftovers": 0.70, "lifeorb": 0.30},
    "venusaur": {"blacksludge": 0.80, "lifeorb": 0.20},
    "charizard": {"choicespecs": 0.50, "heavydutyboots": 0.30, "lifeorb": 0.20},
    "lucario": {"lifeorb": 0.60, "focussash": 0.30, "choiceband": 0.10},
    "gyarados": {"leftovers": 0.50, "lifeorb": 0.30, "lumberry": 0.20},
    "tyranitar": {"leftovers": 0.50, "choiceband": 0.30, "assaultvest": 0.20},
    "greninja": {"lifeorb": 0.50, "focussash": 0.35, "choicespecs": 0.15},
    "cloyster": {"focussash": 0.80, "lifeorb": 0.20}
}



def norm(s):
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def boost_mult(s):
    s = max(-6, min(6, int(s or 0)))
    return (2 + s) / 2.0 if s >= 0 else 2.0 / (2 - s)


def calc_stats(name, evs, nature):
    b = SP[name]["b"]
    up, down = NATURES.get(nature, (None, None))
    out = {}
    for i, st in enumerate(STATS):
        base = b[i]
        ev = evs[i]
        if st == "hp":
            out[st] = (2 * base + 31 + ev // 4) * LVL // 100 + LVL + 10
        else:
            v = (2 * base + 31 + ev // 4) * LVL // 100 + 5
            m = 1.1 if st == up else (0.9 if st == down else 1.0)
            out[st] = int(v * m)
    return out


def type_eff(mt, types):
    e = 1.0
    row = TC.get(mt)
    if not row:
        return 1.0
    for t in types:
        e *= row.get(t, 1.0)
    return e


def move_info(mid, obs_mv=None):
    """Move record from DB; falls back to whatever the observation says."""
    m = MV.get(norm(mid))
    if m is None and obs_mv is not None:
        cat = str(obs_mv.get("category", "Physical"))[:1].upper()
        cat = {"P": "P", "S": "S"}.get(cat, "T")
        if str(obs_mv.get("category", "")).lower().startswith("stat"):
            cat = "T"
        acc = obs_mv.get("accuracy", 100)
        acc = 101 if acc is True or acc is None else int(acc)
        m = {
            "n": obs_mv.get("name", str(mid)), "t": obs_mv.get("type", "Normal"), "c": cat,
            "bp": int(obs_mv.get("base_power") or 0), "a": acc, "p": 0
        }
    return m


# ---------------------------------------------------------------------------
# Mon model
# ---------------------------------------------------------------------------
class Mon:
    __slots__ = ("name", "types", "stats", "maxhp", "hp", "item", "ability", "status", "boosts", "moves",
                 "ab_probs", "item_prob", "known")

    def __init__(self, name, stats, hp_frac, item, ability, moves, status="", boosts=None, ab_probs=None,
                 item_prob=1.0, known=True):
        self.name = name
        self.types = SP[name]["t"]
        self.stats = stats
        self.maxhp = stats["hp"]
        self.hp = max(0.0, self.maxhp * hp_frac)
        self.item = item
        self.ability = ability
        self.status = status
        self.boosts = boosts or {}
        self.moves = moves
        self.ab_probs = ab_probs or [(ability, 1.0)]
        self.item_prob = item_prob
        self.known = known

    @property
    def frac(self):
        return self.hp / self.maxhp if self.maxhp else 0.0


def my_mon_from_set(sset, hp_frac, status=""):
    name = sset["name"]
    evs = sset["evs"]
    stats = calc_stats(name, evs, sset["nature"])
    return Mon(name, stats, hp_frac, norm(sset["item"]), norm(sset["ability"]), [norm(m) for m in sset["moves"]], status)


def foe_mon_from_name(name, hp_frac, status="", boosts=None):
    p = SP[name]
    stats = calc_stats(name, p["evs"], p["nature"])
    abil = p["ab"]
    if len(abil) == 1:
        probs = [(abil[0], 1.0)]
    else:
        probs = [(abil[0], 0.65)] + [(a, 0.35 / (len(abil) - 1)) for a in abil[1:]]
    return Mon(name, stats, hp_frac, p["item"], abil[0], list(p["dm"]), status, boosts, probs, 0.6, False)


# ---------------------------------------------------------------------------
# Damage calculation
# ---------------------------------------------------------------------------
def eff_speed(m, weather="", scarf_prob=0.0):
    if isinstance(weather, bool):
        weather = "sand" if weather else ""
    s = m.stats["spe"] * boost_mult(m.boosts.get("spe", 0))
    if m.status == "par":
        s *= 0.5
    if m.item == "choicescarf":
        s *= 1.5
    if weather == "sand" and any(a == "sandrush" and p >= 0.5 for a, p in m.ab_probs):
        s *= 2
    elif weather == "sun" and any(a == "chlorophyll" and p >= 0.5 for a, p in m.ab_probs):
        s *= 2
    elif weather == "rain" and any(a == "swiftswim" and p >= 0.5 for a, p in m.ab_probs):
        s *= 2
    elif weather in ("snow", "hail") and any(a == "slushrush" and p >= 0.5 for a, p in m.ab_probs):
        s *= 2
    return s


def ability_mult(att, dfn, mv, ab, atk_ab):
    """Defender ability multiplier for a move (immunities etc)."""
    t = mv["t"]
    if atk_ab == "moldbreaker":
        return 1.0
    if ab == "levitate" and t == "Ground":
        return 0.0
    if ab == "flashfire" and t == "Fire":
        return 0.0
    if ab in ("waterabsorb", "stormdrain") and t == "Water":
        return 0.0
    if ab == "voltabsorb" and t == "Electric":
        return 0.0
    if ab == "thickfat" and t in ("Fire", "Ice"):
        return 0.5
    if ab == "multiscale" and dfn.hp >= dfn.maxhp - 0.5:
        return 0.5
    return 1.0


_cache = {}


def damage_rolls(att, dfn, mid, weather=""):
    """16 damage rolls (absolute HP) of move mid from att to dfn."""
    mv = MV.get(mid)
    if mv is None or mv["c"] == "T":
        return [0.0] * 16
    if isinstance(weather, bool):
        weather = "sand" if weather else ""
    key = (
        att.name, att.hp > 0, round(att.frac, 2), tuple(sorted(att.boosts.items())), att.status, att.item, att.ability,
        dfn.name, round(dfn.frac, 2), tuple(sorted(dfn.boosts.items())), dfn.status, dfn.item, mid, weather,
        tuple(sorted(att.stats.items())), tuple(sorted(dfn.stats.items()))
    )
    r = _cache.get(key)
    if r is not None:
        return r

    cat = mv["c"]
    bp = mv["bp"]
    types_def = dfn.types
    mt = mv["t"]
    if mv.get("speedbp") == "gyroball":
        bp = min(150, int(25 * eff_speed(dfn, weather) / max(1, eff_speed(att, weather))) + 1)
    if mv.get("knock"):
        has_item = bool(dfn.item and dfn.item != "none" and dfn.item_prob > 0.1)
        bp = 97 if has_item else 65
    if mv.get("cond") == "facade" and att.status:
        bp *= 2
    if att.ability == "technician" and bp <= 60:
        bp = bp * 1.5

    mh = mv.get("mh")
    hits = 1
    if mh:
        hits = mh if isinstance(mh, int) else (3.1 if mh == [2, 5] else sum(mh) / 2.0)

    if mv.get("bodypress"):
        A = att.stats["def"] * boost_mult(att.boosts.get("def", 0))
    elif cat == "P":
        A = att.stats["atk"] * boost_mult(att.boosts.get("atk", 0))
        if mv.get("foulplay"):
            A = dfn.stats["atk"] * boost_mult(dfn.boosts.get("atk", 0))
    else:
        A = att.stats["spa"] * boost_mult(att.boosts.get("spa", 0))

    if cat == "P" or mv.get("ods") == "def":
        D = dfn.stats["def"] * boost_mult(dfn.boosts.get("def", 0))
        if weather == "snow" and "Ice" in types_def:
            D *= 1.5
    else:
        D = dfn.stats["spd"] * boost_mult(dfn.boosts.get("spd", 0))
        if weather == "sand" and "Rock" in types_def:
            D *= 1.5

    if cat == "S" and dfn.item == "assaultvest":
        D *= 1.0 + 0.5 * dfn.item_prob

    mod = 1.0
    it = att.item
    ip = att.item_prob
    if it == "lifeorb":
        mod *= 1 + 0.3 * ip
    elif it == "choiceband" and cat == "P":
        mod *= 1 + 0.5 * ip
    elif it == "choicespecs" and cat == "S":
        mod *= 1 + 0.5 * ip
    elif it == "metalcoat" and mt == "Steel":
        mod *= 1 + 0.2 * ip

    if weather == "rain":
        if mt == "Water":
            mod *= 1.5
        elif mt == "Fire":
            mod *= 0.5
    elif weather == "sun":
        if mt == "Fire":
            mod *= 1.5
        elif mt == "Water":
            mod *= 0.5
    elif weather == "sand":
        for ab, pb in att.ab_probs:
            if ab == "sandforce" and mt in ("Ground", "Steel", "Rock"):
                mod *= 1.0 + 0.3 * pb

    if mid == "solarbeam" and weather in ("rain", "sand", "snow"):
        mod *= 0.5

    if mid == "freezedry":
        eff = 1.0
        for t in types_def:
            e = TC["Ice"].get(t, 1.0)
            eff *= 2.0 if t == "Water" else e
    else:
        eff = type_eff(mt, types_def)

    if eff == 0:
        _cache[key] = [0.0] * 16
        return _cache[key]

    stab = 1.5 if (mt in att.types or att.ability == "protean") else 1.0
    if att.status == "brn" and cat == "P" and att.ability != "guts":
        mod *= 0.5

    if att.hp <= att.maxhp / 3.0:
        for ab, pb in att.ab_probs:
            if (ab == "blaze" and mt == "Fire") or (ab == "torrent" and mt == "Water") or (ab == "overgrow" and mt == "Grass") or (ab == "swarm" and mt == "Bug"):
                mod *= 1 + 0.5 * pb

    base = int(int(int(2 * LVL / 5 + 2) * bp * A / max(1.0, D)) / 50) + 2

    am = 0.0
    for ab, pb in dfn.ab_probs:
        am += pb * ability_mult(att, dfn, mv, ab, att.ability)

    rolls = []
    for r in range(85, 101):
        d = int(base * r / 100.0)
        d = d * stab * eff * mod * am
        rolls.append(float(int(d)) * hits)

    _cache[key] = rolls
    return rolls


def roll_samples(rolls):
    """Compress 16 rolls to 3 weighted samples (low, mid, high)."""
    return ((rolls[1], 0.3), (rolls[8], 0.4), (rolls[14], 0.3))


# ---------------------------------------------------------------------------
# Memory & State
# ---------------------------------------------------------------------------
class FoeMemory:
    def __init__(self):
        self.seen = set()
        self.inferred = {}
        self.turns_active = 0
        self.speed_lo = 0.0
        self.speed_hi = 1e9
        self.item_known = None
        self.ability_known = None
        self.charging_move = None
        self.charge_turn = -1


class PokemonAgent:
    def __init__(self):
        self.reset()

    def reset(self):
        self.foe_mem = {}
        self.prev = None
        self.prev_action = None
        self.prev_move = ""
        self.foe_switched_count = 0
        self.foe_switched_on_phantom = False
        self.last_turn = -1
        self.foe_team_hp = {}
        self.weather = ""
        self.sand_turns = 0
        self.my_known_stats = {}
        self.my_seen_hp = {}
        self.foe_switch_turn = 0
        self.errors = 0

    def decide(self, observation):
        try:
            a = self._decide(observation)
            if self._legal(observation, a):
                return a
        except Exception:
            self.errors += 1
        return self._fallback(observation)

    def _legal(self, obs, a):
        if obs.get("team_preview"):
            return isinstance(a, str) and a.startswith("team ")
        if a == "pass":
            return True
        moves = {"move %d" % m.get("index", 0) for m in obs.get("valid_moves", []) or []}
        sw = {"switch %d" % s.get("index", 0) for s in obs.get("valid_switches", []) or []}
        if obs.get("force_switch"):
            return a in sw
        return a in moves or a in sw

    def _fallback(self, obs):
        if obs.get("team_preview"):
            return "team " + TEAM_ORDER
        sw = obs.get("valid_switches", []) or []
        mv = obs.get("valid_moves", []) or []
        if obs.get("force_switch"):
            if sw:
                best = max(sw, key=lambda s: s.get("hp_percent", 0))
                return "switch %d" % best.get("index", sw[0].get("index", 2))
            return "pass"
        if mv:
            try:
                best = max(mv, key=lambda m: (m.get("base_power") or 0) * m.get("type_multiplier", 1.0) * (1.5 if m.get("stab") else 1.0))
                return "move %d" % best.get("index", 1)
            except Exception:
                return "move %d" % mv[0].get("index", 1)
        if sw:
            return "switch %d" % sw[0].get("index", 2)
        return "pass"

    def _decide(self, obs):
        if obs.get("team_preview"):
            return self._decide_team_preview(obs)

        turn = obs.get("turn", 0) or 0
        if turn < self.last_turn:
            self.reset()
        self.last_turn = turn

        my = obs.get("my_active") or {}
        foe = obs.get("foe") or {}
        fname = foe.get("name")
        if fname not in SP:
            return self._fallback(obs)

        self._update_memory(obs)

        me = self._build_my_active(obs)
        foe_m = self._build_foe(obs)
        bench = self._build_bench(obs)

        ctx = Ctx(self, obs, me, foe_m, bench)
        if obs.get("force_switch"):
            choice = ctx.best_forced_switch()
        else:
            choice = ctx.best_action()

        self.prev = {
            "turn": turn, "my_name": my.get("name"), "my_hp": my.get("hp_percent"),
            "foe_name": fname, "foe_hp": foe.get("hp_percent"), "my_maxhp": me.maxhp, "action": choice
        }
        self.prev_action = choice
        self.prev_move = ""
        if choice and choice.startswith("move "):
            try:
                idx = int(choice.split()[1])
                for m in obs.get("valid_moves", []) or []:
                    if m.get("index") == idx:
                        self.prev_move = norm(m.get("id") or m.get("name"))
                        break
            except Exception:
                pass
        return choice

    def _decide_team_preview(self, obs):
        """Pick optimal lead based on damage calculation matchups if foe team known, otherwise default order."""
        my_team = obs.get("my_team") or obs.get("valid_switches") or []
        foe_team = obs.get("foe_team") or []
        if not foe_team or len(my_team) < 3:
            return "team " + TEAM_ORDER

        foe_names = [p.get("name") for p in foe_team if p.get("name") in SP]
        if not foe_names:
            return "team " + TEAM_ORDER

        has_sand = any(n in ("Tyranitar", "Hippowdon") for n in foe_names)
        foe_mons = [foe_mon_from_name(n, 1.0) for n in foe_names]

        scores = []
        for i, my_p in enumerate(my_team[:3]):
            mname = my_p.get("name")
            if mname not in SP:
                continue
            sset = self._set_for(mname)
            if not sset:
                continue
            me = my_mon_from_set(sset, 1.0)
            has_sash = (me.item == "focussash" and not has_sand)

            total_sc = 0.0
            for foe in foe_mons:
                my_best_dmg = 0.0
                for m in me.moves:
                    mid = norm(m)
                    if mid in MV and MV[mid]["c"] != "T":
                        rl = damage_rolls(me, foe, mid, has_sand)
                        dmg_pct = max(rl) / max(1.0, foe.maxhp)
                        if dmg_pct > my_best_dmg:
                            my_best_dmg = dmg_pct

                foe_best_dmg = 0.0
                for m in foe.moves:
                    mid = norm(m if isinstance(m, str) else m[0])
                    if mid in MV and MV[mid]["c"] != "T":
                        rl = damage_rolls(foe, me, mid, has_sand)
                        dmg_pct = max(rl) / max(1.0, me.maxhp)
                        if dmg_pct > foe_best_dmg:
                            foe_best_dmg = dmg_pct

                w_str = "sand" if has_sand else ""
                my_spe = eff_speed(me, w_str)
                foe_spe = eff_speed(foe, w_str)
                faster = (my_spe > foe_spe)
                speed_tie = (my_spe == foe_spe)

                foe_bypasses_sash = any(
                    (MV.get(norm(m if isinstance(m, str) else m[0]), {}).get("mh") or
                     norm(m if isinstance(m, str) else m[0]) in {"uturn", "voltswitch", "flipturn"})
                    for m in foe.moves
                )
                effective_sash = has_sash and not foe_bypasses_sash

                if faster:
                    if my_best_dmg >= 1.0:
                        sc = 3.0
                    elif my_best_dmg >= 0.5:
                        sc = 1.5 if foe_best_dmg < 1.0 else 0.5
                    else:
                        sc = -1.0 if foe_best_dmg >= 1.0 else 0.0
                elif speed_tie:
                    if my_best_dmg >= 1.0:
                        sc = 2.0 if foe_best_dmg < 1.0 else 1.0
                    elif my_best_dmg >= 0.5:
                        sc = 1.0 if foe_best_dmg < 1.0 else 0.0
                    else:
                        sc = -1.5 if foe_best_dmg >= 1.0 else -0.5
                else:
                    if effective_sash:
                        if my_best_dmg >= 1.0:
                            sc = 2.0
                        else:
                            sc = 0.5
                    else:
                        if foe_best_dmg >= 1.0:
                            sc = -2.5
                        elif my_best_dmg >= 1.0:
                            sc = 2.0
                        else:
                            sc = my_best_dmg - foe_best_dmg

                total_sc += sc
            scores.append((total_sc, i + 1))

        if not scores:
            return "team " + TEAM_ORDER

        scores.sort(key=lambda x: -x[0])
        best_lead = scores[0][1]
        other = [str(x) for x in (1, 2, 3) if x != best_lead]
        return f"team {best_lead}{other[0]}{other[1]}"

    def _set_for(self, name):
        for s in MY_TEAM:
            if s["name"] == name:
                return s
        return None

    def _build_my_active(self, obs):
        my = obs.get("my_active") or {}
        name = my.get("name")
        sset = self._set_for(name)
        hp = (my.get("hp_percent", 100) or 0) / 100.0
        status = self._status_from(my)
        stats = None
        if name in SP:
            st = my.get("stats")
            if isinstance(st, dict) and all(k in st for k in ("atk", "def", "spa", "spd", "spe")):
                mh = self._maxhp_from_condition(my.get("condition"))
                base = calc_stats(name, (sset or {"evs": SP[name]["evs"]})["evs"], (sset or {"nature": SP[name]["nature"]})["nature"])
                stats = {"hp": mh or base["hp"], "atk": st["atk"], "def": st["def"], "spa": st["spa"], "spd": st["spd"], "spe": st["spe"]}
                self.my_known_stats[name] = stats
            elif name in self.my_known_stats:
                stats = self.my_known_stats[name]

        if sset is None:
            sset = {
                "name": name, "item": SP.get(name, {}).get("item", "leftovers"),
                "nature": SP.get(name, {}).get("nature", "adamant"),
                "evs": SP.get(name, {}).get("evs", [0] * 6),
                "ability": SP.get(name, {}).get("ab", [""])[0], "moves": []
            }
        m = my_mon_from_set(sset, hp, status)
        if stats:
            m.stats = stats
            m.maxhp = stats["hp"]
            m.hp = m.maxhp * hp
        m.boosts = dict(my.get("boosts") or {})

        vm = [norm(x.get("id") or x.get("name")) for x in obs.get("valid_moves", []) or []]
        if vm and not obs.get("force_switch"):
            m.moves = vm
            for x in obs.get("valid_moves", []) or []:
                mid = norm(x.get("id") or x.get("name"))
                if mid not in MV:
                    mm = move_info(mid, x)
                    if mm:
                        MV[mid] = mm
        if my.get("item"):
            m.item = norm(my.get("item"))
        if my.get("ability"):
            m.ability = norm(my.get("ability"))
            m.ab_probs = [(m.ability, 1.0)]
        return m

    def _status_from(self, d):
        s = d.get("status") if isinstance(d, dict) else None
        if s:
            return str(s)
        cond = d.get("condition") if isinstance(d, dict) else None
        if isinstance(cond, str):
            parts = cond.split()
            if len(parts) > 1 and parts[1] in ("brn", "par", "slp", "psn", "tox", "frz"):
                return parts[1]
        return ""

    def _maxhp_from_condition(self, cond):
        try:
            return int(str(cond).split()[0].split("/")[1])
        except Exception:
            return None

    def _build_foe(self, obs):
        foe = obs.get("foe") or {}
        name = foe.get("name")
        hp = (foe.get("hp_percent", 100) or 0) / 100.0
        status = str(foe.get("status") or "")
        m = foe_mon_from_name(name, hp, status, dict(foe.get("boosts") or {}))
        mem = self.foe_mem.setdefault(name, FoeMemory())
        m.moves = self._foe_candidates(name, mem)
        if mem.ability_known:
            m.ab_probs = [(mem.ability_known, 1.0)]
        if getattr(mem, "has_no_item", False) or mem.item_known == "none":
            m.item = "none"
            m.item_prob = 0.0
        elif mem.item_known:
            m.item = mem.item_known
            m.item_prob = 1.0
        return m

    def _foe_candidates(self, name, mem):
        """list of (move_id, q) - q = probability foe owns this move."""
        p = SP[name]
        out = {}
        legal = p["legal"]
        defaults = set(p["dm"])
        known = set(mem.seen)
        q_def = PARAMS.get("q_default", 0.85)
        q_oth = PARAMS.get("q_other", 0.04)

        for mid in legal:
            if mid in known:
                out[mid] = 1.0
            elif mid in mem.inferred:
                out[mid] = max(0.65, mem.inferred[mid])
            elif mid in defaults:
                out[mid] = q_def
            else:
                out[mid] = q_oth

        for mid in known:
            out[mid] = 1.0

        if len(known) >= 4:
            out = {k: (1.0 if k in known else 0.0) for k in out}

        return [(k, v) for k, v in out.items() if v > 0]

    def _build_bench(self, obs):
        out = []
        for s in obs.get("valid_switches", []) or []:
            name = s.get("name")
            if name not in SP:
                continue
            sset = self._set_for(name) or {
                "name": name, "item": SP[name]["item"], "nature": SP[name]["nature"],
                "evs": SP[name]["evs"], "ability": SP[name]["ab"][0], "moves": SP[name]["dm"]
            }
            m = my_mon_from_set(sset, (s.get("hp_percent", 100) or 0) / 100.0)
            if name in self.my_known_stats:
                m.stats = self.my_known_stats[name]
                m.maxhp = m.stats["hp"]
                m.hp = m.maxhp * (s.get("hp_percent", 100) or 0) / 100.0
            out.append((s.get("index"), m))
        return out

    def _update_memory(self, obs):
        foe = obs.get("foe") or {}
        fname = foe.get("name")
        mem = self.foe_mem.setdefault(fname, FoeMemory())
        if self.prev and self.prev["foe_name"] != fname:
            self.foe_switch_turn = obs.get("turn", 0)
            self.foe_switched_count = getattr(self, "foe_switched_count", 0) + 1
            if getattr(self, "prev_move", "") == "phantomforce":
                self.foe_switched_on_phantom = True
            mem.turns_active = 0
            mem.charging_move = None
        elif self.prev:
            mem.turns_active += 1

        if self.prev and (obs.get("turn", 0) or 0) > (self.prev.get("turn", 0) or 0):
            if self.sand_turns > 0:
                self.sand_turns -= 1
                if self.sand_turns == 0:
                    self.weather = ""

        self._ingest_reveals(obs, fname, mem)

        w_raw = str(obs.get("weather") or "").lower()
        if "sand" in w_raw:
            self.weather = "sand"
            self.sand_turns = 5
        elif "rain" in w_raw:
            self.weather = "rain"
            self.sand_turns = 0
        elif "sun" in w_raw:
            self.weather = "sun"
            self.sand_turns = 0
        elif "snow" in w_raw or "hail" in w_raw:
            self.weather = "snow"
            self.sand_turns = 0
        elif w_raw == "none":
            self.weather = ""
            self.sand_turns = 0
        elif fname == "Tyranitar" and (not self.prev or self.prev["foe_name"] != fname):
            self.weather = "sand"
            self.sand_turns = 5
        my = obs.get("my_active") or {}
        if my.get("name") == "Tyranitar" and (not self.prev or self.prev["my_name"] != "Tyranitar"):
            self.weather = "sand"
            self.sand_turns = 5

        if self.prev_action and "knock" in self.prev_action.lower() and self.prev and self.prev["foe_name"] == fname:
            mem.item_known = "none"
            mem.has_no_item = True

        # Infer move from damage
        if self.prev and self.prev["my_name"] == my.get("name") and self.prev["foe_name"] == fname and my.get("name") in SP:
            lost = (self.prev["my_hp"] or 0) - (my.get("hp_percent", 0) or 0)
            if lost >= 3:
                self._infer_from_damage(obs, lost, fname, mem)

    def _ingest_reveals(self, obs, fname, mem):
        foe = obs.get("foe") or {}
        cands = []
        for k in ("moves", "known_moves", "revealed_moves", "moves_seen", "seen_moves", "used_moves"):
            v = foe.get(k)
            if isinstance(v, (list, tuple)):
                cands.extend(v)
        for k in ("last_move", "last_move_used", "last_used_move"):
            if foe.get(k):
                cands.append(foe.get(k))
        for k in ("last_foe_move", "foe_last_move"):
            if obs.get(k):
                cands.append(obs.get(k))
        for ent in cands:
            mid = norm(ent.get("id") or ent.get("name") or ent.get("move")) if isinstance(ent, dict) else norm(ent)
            if mid:
                mem.seen.add(mid)

        ab = foe.get("ability")
        if ab:
            mem.ability_known = norm(ab)
        it = foe.get("item")
        if it:
            mem.item_known = norm(it)

        current_turn = obs.get("turn", 0) or 0
        if getattr(mem, "charging_move", None) and current_turn > getattr(mem, "charge_turn", -1) + 1:
            mem.charging_move = None

        last_cands = []
        for k in ("last_move", "last_move_used", "last_used_move"):
            if foe.get(k):
                last_cands.append(foe.get(k))
        for k in ("last_foe_move", "foe_last_move"):
            if obs.get(k):
                last_cands.append(obs.get(k))

        my = obs.get("my_active") or {}
        lost = ((self.prev["my_hp"] or 0) - (my.get("hp_percent", 0) or 0)) if (self.prev and my) else 999
        f_legal = (SP.get(fname) or SP.get(str(fname).capitalize()) or SP.get(str(fname).title()) or {}).get("legal", [])
        for ent in last_cands:
            mid = norm(ent.get("id") or ent.get("name") or ent.get("move")) if isinstance(ent, dict) else norm(ent)
            if mid in TWO_TURN_MOVES and mid in f_legal and getattr(mem, "turns_active", 0) > 0:
                if lost <= 1 or not getattr(mem, "charging_move", None):
                    mem.charging_move = mid
                    mem.charge_turn = current_turn

        foe_cond = str(foe.get("condition") or "").lower()
        foe_st = str(foe.get("status") or "").lower()
        for ttm in TWO_TURN_MOVES:
            if (ttm in foe_cond or ttm in foe_st) and ttm in f_legal:
                mem.charging_move = ttm
                mem.charge_turn = current_turn
                break

        # Infer semi-invulnerable charging move (e.g. Phantom Force, Bounce, Fly, Dig, Dive)
        # when foe took 0 damage from a 100% accurate attack move and our active mon took 0 damage:
        if self.prev and self.prev.get("foe_name") == fname and self.prev.get("my_name") == my.get("name"):
            prev_m = getattr(self, "prev_move", "")
            pmv = MV.get(prev_m)
            if pmv and pmv["c"] != "T" and pmv.get("a", 100) >= 100:
                foe_hp_prev = self.prev.get("foe_hp", 100)
                foe_hp_now = foe.get("hp_percent", 100)
                my_hp_prev = self.prev.get("my_hp", 100)
                my_hp_now = my.get("hp_percent", 100)
                if foe_hp_now >= foe_hp_prev - 0.5 and my_hp_now >= my_hp_prev - 0.5:
                    for ttm in SEMI_INVULNERABLE_MOVES:
                        if ttm in f_legal:
                            mem.charging_move = ttm
                            mem.charge_turn = current_turn - 1
                            break

    def _infer_from_damage(self, obs, lost_pct, fname, mem):
        try:
            my = obs.get("my_active") or {}
            sset = self._set_for(my.get("name"))
            if sset is None:
                return
            me = my_mon_from_set(sset, (self.prev["my_hp"] or 100) / 100.0)
            if my.get("name") in self.my_known_stats:
                me.stats = self.my_known_stats[my.get("name")]
                me.maxhp = me.stats["hp"]
                me.hp = me.maxhp * (self.prev["my_hp"] or 100) / 100.0
            f = foe_mon_from_name(fname, (obs.get("foe") or {}).get("hp_percent", 100) / 100.0)
            f.hp = f.maxhp

            matches = []
            for mid in SP[fname]["legal"]:
                mv = MV.get(mid)
                if not mv or mv["c"] == "T" or mv["bp"] == 0 and not mv.get("speedbp"):
                    continue
                rl = damage_rolls(f, me, mid, self.weather)
                lo, hi = rl[0] / me.maxhp * 100, rl[-1] / me.maxhp * 100
                hi_c = hi * 1.5 * 1.1
                if lo * 0.85 - 2 <= lost_pct <= hi_c + 3:
                    matches.append((mid, abs((lo + hi) / 2 - lost_pct)))

            if not matches:
                return
            matches.sort(key=lambda x: x[1])
            dm = set(SP[fname]["dm"])
            dmatch = [m for m in matches if m[0] in dm]
            pool = dmatch if dmatch else matches
            if len(pool) == 1 and len(matches) <= 3:
                mem.seen.add(pool[0][0])
            else:
                for mid, _ in pool[:2]:
                    if mid not in mem.seen:
                        mem.inferred[mid] = max(mem.inferred.get(mid, 0), 0.7 if len(pool) <= 2 else 0.55)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Search Context
# ---------------------------------------------------------------------------
class Ctx:
    def __init__(self, agent, obs, me, foe, bench):
        self.agent = agent
        self.obs = obs
        self.me = me
        self.foe = foe
        self.bench = bench
        self.foe_mem = agent.foe_mem.get(foe.name) or FoeMemory()
        w_raw = str(obs.get("weather") or "").lower()
        if "sand" in w_raw:
            self.sand = True
            self.weather = "sand"
        elif "rain" in w_raw:
            self.sand = False
            self.weather = "rain"
        elif "sun" in w_raw:
            self.sand = False
            self.weather = "sun"
        elif "snow" in w_raw or "hail" in w_raw:
            self.sand = False
            self.weather = "snow"
        elif w_raw == "none":
            self.sand = False
            self.weather = ""
        else:
            self.weather = agent.weather
            self.sand = (self.weather == "sand") or (agent.sand_turns > 0)
            if self.sand:
                self.weather = "sand"
        self.foe_first_turn = self.foe_mem.turns_active == 0
        self.P = PARAMS

        self.my_team_hp = {}
        for t in obs.get("my_team", []) or []:
            self.my_team_hp[t.get("name")] = (t.get("hp_percent", 0) or 0) / 100.0
        self.foe_charging_move = getattr(self.foe_mem, "charging_move", None)
        self.foe_alive_other = self._foe_other_count(obs)
        self.foe_dist = self._foe_distribution()

    def _foe_other_count(self, obs):
        ag = self.agent
        ag.foe_team_hp[self.foe.name] = self.foe.frac
        seen = len(ag.foe_team_hp)
        unseen = max(0, 3 - seen)
        others_hp = sum(v for n, v in ag.foe_team_hp.items() if n != self.foe.name)
        return others_hp + unseen

    def p_faster(self, my_mon, my_boosts_extra=0, foe_boost_extra=0):
        """P(my_mon moves before foe) from speed alone (ties 0.5)."""
        ms = eff_speed(my_mon, self.weather)
        fm = self.foe
        base = SP[fm.name]["b"][5]
        fs_default = fm.stats["spe"]
        mix = [
            (fs_default, 0.62),
            (int(((2 * base + 31 + 63) * LVL // 100 + 5) * 1.1), 0.12),
            (int(((2 * base + 31 + 63) * LVL // 100 + 5) * 1.0), 0.14),
            (int(((2 * base + 31) * LVL // 100 + 5) * 1.0), 0.12)
        ]
        stage = boost_mult(fm.boosts.get("spe", 0) + foe_boost_extra)
        par = 0.5 if fm.status == "par" else 1.0
        p_weather_speed = 0.0
        if self.weather == "sand":
            if any(a == "sandrush" for a, _ in fm.ab_probs):
                p_weather_speed = 1.0 if self.foe_mem.ability_known == "sandrush" else (0.0 if self.foe_mem.ability_known else 0.85)
        elif self.weather == "sun":
            if any(a == "chlorophyll" for a, _ in fm.ab_probs):
                p_weather_speed = 1.0 if self.foe_mem.ability_known == "chlorophyll" else (0.0 if self.foe_mem.ability_known else 0.85)
        elif self.weather == "rain":
            if any(a == "swiftswim" for a, _ in fm.ab_probs):
                p_weather_speed = 1.0 if self.foe_mem.ability_known == "swiftswim" else (0.0 if self.foe_mem.ability_known else 0.85)
        elif self.weather in ("snow", "hail"):
            if any(a == "slushrush" for a, _ in fm.ab_probs):
                p_weather_speed = 1.0 if self.foe_mem.ability_known == "slushrush" else (0.0 if self.foe_mem.ability_known else 0.85)

        mem = self.foe_mem
        if mem.item_known == "choicescarf":
            scarf = 1.0
        elif mem.item_known is not None:
            scarf = 0.0
        else:
            fn_low = fm.name.lower()
            scarf = SPECIES_ITEM_PRIOR.get(fn_low, {}).get("choicescarf", self.P.get("scarf_prob", 0.07))

        total = 0.0
        wsum = 0.0
        weather_options = ((2.0, p_weather_speed), (1.0, 1.0 - p_weather_speed)) if p_weather_speed > 0 else ((1.0, 1.0),)
        for s, w in mix:
            for weathermult, w_p in weather_options:
                for sc_mult, sc_w in ((1.0, 1 - scarf), (1.5, scarf)):
                    es = s * stage * par * weathermult * sc_mult
                    if es < mem.speed_lo * 0.999 or es > mem.speed_hi * 1.001:
                        continue
                    ww = w * sc_w * w_p
                    wsum += ww
                    if ms > es:
                        total += ww
                    elif ms == es:
                        total += ww * 0.5

        if wsum <= 0:
            return 0.5
        return total / wsum

    def _foe_distribution(self):
        """Distribution over foe actions with greedy-priority weighting."""
        if getattr(self, "foe_charging_move", None):
            return [(1.0, ("atk", self.foe_charging_move))]
        foe, me = self.foe, self.me
        scored = []
        for mid, q in foe.moves:
            mv = MV.get(mid)
            if not mv:
                continue
            if mv["c"] == "T":
                u = self._util_value(mid)
                scored.append((u, q, mid, False))
                continue
            rl = damage_rolls(foe, me, mid, self.weather)
            avg = sum(rl) / 16.0 / me.maxhp
            acc = min(1.0, mv["a"] / 100.0)
            v = avg * acc
            if mv.get("sucker"):
                # If we are within Sucker Punch kill range, enemy is VERY likely to click it
                if rl[8] >= me.hp:
                    v += 2.0
                else:
                    v *= 0.9
            if mv.get("first") and not self.foe_first_turn:
                v = 0
            if mv["p"] > 0 and rl[4] >= me.hp:
                v += 2.5
            elif rl[8] >= me.hp:
                v += 0.35
            scored.append((v, q, mid, True))

        scored.sort(key=lambda x: -x[0])
        w = []
        not_better = 1.0
        tot_q = sum(q for _, q, _, _ in scored) or 1.0
        greedy = self.P.get("foe_greedy", 0.72)
        for v, q, mid, atk in scored:
            wi = q * not_better * greedy + (1 - greedy) * q / tot_q
            not_better *= (1 - q)
            w.append([wi, mid, atk])

        s = sum(x[0] for x in w) or 1.0
        # If foe is critically low and facing a bad matchup, switch probability increases
        base_sw = self.P.get("foe_switch", 0.05)
        if foe.frac < 0.25:
            base_sw = self.P.get("foe_switch_low", 0.12)
        ps = base_sw

        out = [((x[0] / s) * (1 - ps), ("atk" if x[2] else "util", x[1])) for x in w if x[0] / s > 0.01]
        out.append((ps, ("switch",)))
        tot = sum(p for p, _ in out)
        return [(p / tot, a) for p, a in out]

    def _util_value(self, mid):
        if mid in SETUP:
            return 0.16
        if mid in HEAL_MOVES:
            return 0.15 if self.foe.frac < 0.55 else 0.0
        if mid in STATUS_MOVES:
            return 0.14 if not self.me.status else 0.0
        if mid == "protect":
            return 0.06
        return 0.02

    def leaf(self, my_mon, my_hp, foe_hp, my_status="", foe_boost=None, intim=0.0, foe_atk_stage=0, my_atk_stage=0, foe_status=""):
        me_frac = max(0.0, my_hp) / my_mon.maxhp
        foe_frac = max(0.0, foe_hp) / self.foe.maxhp

        mat_me = me_frac
        for n, hp in self.my_team_hp.items():
            if n != my_mon.name:
                mat_me += hp
        mat_foe = foe_frac + self.foe_alive_other

        v = (mat_me - mat_foe) * self.P.get("w_mat", 1.0)
        w_race = self.P.get("w_race", 0.25)
        ko_bonus = self.P.get("ko_bonus", 0.20)

        if my_hp <= 0 and foe_hp <= 0:
            return v
        if my_hp <= 0:
            return v - w_race - ko_bonus
        if foe_hp <= 0:
            return v + w_race + ko_bonus

        v += w_race * self._race(my_mon, my_hp, foe_hp, my_status, intim, foe_atk_stage, my_atk_stage, foe_status)
        return v

    def _best_dmg(self, att, dfn, hp_def, intim=0.0, att_status=""):
        best_t = 99.0
        prio_kill = False
        moves_list = att.moves if isinstance(att.moves[0] if att.moves else "", str) else [m for m, _ in att.moves]
        for mid in moves_list:
            mv = MV.get(mid)
            if not mv or mv["c"] == "T":
                continue
            rl = damage_rolls(att, dfn, mid, self.weather)
            d = rl[8]
            if intim and mv["c"] == "P":
                d *= (1 - intim / 3.0)
            if att_status == "brn" and mv["c"] == "P" and att.status != "brn":
                d *= 0.5
            if d <= 0:
                continue
            acc = min(1.0, mv["a"] / 100.0)
            if mv.get("rch"):
                acc *= 0.5
            if mid == "outrage":
                acc *= 0.95
            t = math.ceil(hp_def / d) / max(0.2, acc)
            if mv["p"] > 0 and d >= hp_def:
                prio_kill = True
            if t < best_t:
                best_t = t
        return best_t, prio_kill

    def _race(self, my_mon, my_hp, foe_hp, my_status, intim, foe_atk_stage, my_atk_stage=0, foe_status=""):
        saved_my_b = dict(my_mon.boosts)
        if my_atk_stage:
            my_mon.boosts["atk"] = my_mon.boosts.get("atk", 0) + my_atk_stage
            my_mon.boosts["spa"] = my_mon.boosts.get("spa", 0) + my_atk_stage
        t_me, my_prio = self._best_dmg(my_mon, self.foe, foe_hp, intim, my_status)
        my_mon.boosts = saved_my_b

        foe_cands = [(m, q) for m, q in self.foe.moves if q >= 0.5]
        if not foe_cands:
            foe_cands = self.foe.moves
        tmp_moves = [m for m, _ in foe_cands]
        saved = self.foe.moves
        self.foe.moves = tmp_moves
        saved_b = dict(self.foe.boosts)
        if foe_atk_stage:
            self.foe.boosts["atk"] = self.foe.boosts.get("atk", 0) + foe_atk_stage
            self.foe.boosts["spa"] = self.foe.boosts.get("spa", 0) + foe_atk_stage
        saved_fst = self.foe.status
        if foe_status:
            self.foe.status = foe_status
        t_foe, foe_prio = self._best_dmg(self.foe, my_mon, my_hp)
        self.foe.moves = saved
        self.foe.boosts = saved_b
        self.foe.status = saved_fst

        pf = self.p_faster(my_mon)
        if my_prio and not foe_prio:
            pf = 1.0
        elif foe_prio and not my_prio:
            pf = 0.0
        if my_status == "par":
            pf *= 0.5
        if foe_status == "par" or self.foe.status == "par":
            pf = min(1.0, pf * 1.5)

        t_me = min(t_me, 20)
        t_foe = min(t_foe, 20)
        win_first = 1.0 if t_me <= t_foe else 0.0
        win_second = 1.0 if t_me < t_foe else 0.0
        pw = pf * win_first + (1 - pf) * win_second
        margin = math.tanh((t_foe - t_me) * 0.45)
        return 0.5 * (2 * pw - 1) + 0.5 * margin

    def best_action(self):
        obs = self.obs
        scores = []
        for m in obs.get("valid_moves", []) or []:
            mid = norm(m.get("id") or m.get("name"))
            s = self.eval_move(mid)
            scores.append([s, "move %d" % m.get("index", 1), mid])

        # Desperation Priority Rule:
        # If we are slower than the foe, in lethal danger of being KO'd before acting,
        # and not protected by Focus Sash: prioritize guaranteed chip damage via priority
        # moves rather than clicking a 0-priority move that will never execute because we faint first.
        p_faster = self.p_faster(self.me)
        has_sash = (self.me.item == "focussash" and self.me.hp >= self.me.maxhp - 0.5 and not self.sand)

        if p_faster < 0.5 and not has_sash:
            foe_lethal = False
            foe_guaranteed_lethal = False
            foe_max_pri = 0
            for fmid, q in self.foe.moves:
                if q < 0.40 or fmid in ("explosion", "selfdestruct"):
                    continue
                fmv = MV.get(fmid)
                if fmv and fmv["c"] != "T":
                    rl = damage_rolls(self.foe, self.me, fmid, self.weather)
                    max_dmg = rl[-1]
                    min_dmg = rl[0]
                    fn_low = self.foe.name.lower()
                    priors = SPECIES_ITEM_PRIOR.get(fn_low, {})
                    if self.foe_mem.item_known == "lifeorb" or (self.foe_mem.item_known is None and priors.get("lifeorb", 0.0) >= 0.40):
                        max_dmg = max(max_dmg, rl[-1] * 1.3)
                        min_dmg = max(min_dmg, rl[0] * 1.3)
                    elif self.foe_mem.item_known == "choiceband" or (self.foe_mem.item_known is None and priors.get("choiceband", 0.0) >= 0.40):
                        if fmv["c"] == "P":
                            max_dmg = max(max_dmg, rl[-1] * 1.5)
                            min_dmg = max(min_dmg, rl[0] * 1.5)
                    elif self.foe_mem.item_known == "choicespecs" or (self.foe_mem.item_known is None and priors.get("choicespecs", 0.0) >= 0.40):
                        if fmv["c"] == "S":
                            max_dmg = max(max_dmg, rl[-1] * 1.5)
                            min_dmg = max(min_dmg, rl[0] * 1.5)
                    if max_dmg >= self.me.hp:
                        foe_lethal = True
                        foe_max_pri = max(foe_max_pri, fmv.get("p", 0))
                        f_acc = fmv.get("a", 100)
                        if f_acc >= 100 and min_dmg >= self.me.hp:
                            foe_guaranteed_lethal = True

            if foe_lethal and getattr(self, "foe_charging_move", None) not in SEMI_INVULNERABLE_MOVES:
                best_prio = None
                max_prio_dmg = 0.0
                for m in obs.get("valid_moves", []) or []:
                    mid = norm(m.get("id") or m.get("name"))
                    mv = MV.get(mid)
                    if mv and mv.get("p", 0) > foe_max_pri and mv["c"] != "T":
                        rl = damage_rolls(self.me, self.foe, mid, self.weather)
                        dmg = rl[8]
                        if dmg > max_prio_dmg:
                            max_prio_dmg = dmg
                            best_prio = (m.get("index"), mid, dmg)

                if best_prio is not None and max_prio_dmg > 0:
                    best_prio_mid = best_prio[1]
                    prio_is_lethal = (max_prio_dmg >= self.foe.hp)
                    living_bench = [mon for _, mon in self.bench if mon.hp > 0]
                    has_bench = len(living_bench) > 0

                    if prio_is_lethal:
                        for i, (sc, cmd, mid) in enumerate(scores):
                            if mid == best_prio_mid:
                                scores[i][0] = sc + 1.0
                            else:
                                scores[i][0] = sc - 1.0
                    elif not has_bench:
                        # No bench remaining: dying with non-lethal chip damage still results in an immediate 100% loss.
                        # If we have any 0-priority move that can achieve a lethal KO, gambling on that move (hoping
                        # the foe misses an inaccurate move like Hydro Pump/Focus Blast or rolls low) is our ONLY winning line!
                        has_ko_move = any(
                            (damage_rolls(self.me, self.foe, norm(m.get("id") or m.get("name")), self.weather)[-1] >= self.foe.hp)
                            for m in obs.get("valid_moves", []) or []
                            if norm(m.get("id") or m.get("name")) != best_prio_mid and MV.get(norm(m.get("id") or m.get("name")), {}).get("c") != "T"
                        )
                        for i, (sc, cmd, mid) in enumerate(scores):
                            if mid == best_prio_mid:
                                scores[i][0] = sc - 0.50 if has_ko_move else sc
                            else:
                                mv = MV.get(mid)
                                if mv and mv.get("p", 0) <= foe_max_pri and mv["c"] != "T":
                                    m_rl = damage_rolls(self.me, self.foe, mid, self.weather)
                                    can_ko = (m_rl[-1] >= self.foe.hp)
                                    if can_ko:
                                        scores[i][0] = sc + 0.75
                                    else:
                                        scores[i][0] = sc - 0.50
                    else:
                        # Has bench remaining: evaluate whether dying with chip damage secures a clean revenge kill
                        # that would be forfeited if we died dealing 0 damage.
                        hp_chipped = max(0.0, self.foe.hp - max_prio_dmg)
                        hp_unchipped = self.foe.hp
                        fn_low = self.foe.name.lower()
                        foe_sash_risk = (self.foe.hp >= self.foe.maxhp - 0.5 and (
                            self.foe_mem.item_known == "focussash" or
                            (self.foe_mem.item_known is None and "focussash" in SPECIES_ITEM_PRIOR.get(fn_low, {}))
                        ))

                        chip_secures_revenge = False
                        can_revenge_anyway = False

                        bench_has_safe_ohko_counter = False
                        for b in living_bench:
                            b_faster = (self.p_faster(b) >= 0.5)
                            b_safe_dmg = 0.0
                            b_prio_safe_dmg = 0.0
                            b_can_ohko = False
                            moves_list = b.moves if isinstance(b.moves[0] if b.moves else "", str) else [bm for bm, _ in b.moves]
                            for b_mid in moves_list:
                                b_mv = MV.get(b_mid)
                                if not b_mv or b_mv["c"] == "T":
                                    continue
                                b_rl = damage_rolls(b, self.foe, b_mid, self.weather)
                                b_dmg = b_rl[4]
                                if b_rl[8] >= self.foe.hp:
                                    b_can_ohko = True
                                if b_mv.get("p", 0) > 0:
                                    b_prio_safe_dmg = max(b_prio_safe_dmg, b_dmg)
                                b_safe_dmg = max(b_safe_dmg, b_dmg)

                            f_max_on_b = max(
                                (damage_rolls(self.foe, b, fmid, self.weather)[-1]
                                 for fmid, q in self.foe.moves if q >= 0.40 and MV.get(fmid, {}).get("c") != "T"),
                                default=999
                            )
                            b_survives = (b.hp > f_max_on_b) or (b.item == "focussash" and b.hp >= b.maxhp - 0.5 and not self.sand)
                            if b_faster and b_can_ohko and b_survives:
                                bench_has_safe_ohko_counter = True

                            b_kills_chipped = (b_faster and b_safe_dmg >= hp_chipped) or (b_prio_safe_dmg >= hp_chipped)
                            b_kills_unchipped = (not foe_sash_risk) and ((b_faster and b_safe_dmg >= hp_unchipped) or (b_prio_safe_dmg >= hp_unchipped))

                            foe_threatens_b = False
                            for fmid, q in self.foe.moves:
                                fmv = MV.get(fmid)
                                if fmv and fmv["c"] != "T":
                                    f_on_b_rl = damage_rolls(self.foe, b, fmid, self.weather)
                                    if f_on_b_rl[-1] >= b.hp or f_on_b_rl[8] >= b.hp * 0.70:
                                        foe_threatens_b = True
                                        break

                            if b_kills_chipped and (not b_kills_unchipped or foe_threatens_b):
                                chip_secures_revenge = True
                            if b_kills_unchipped and not foe_threatens_b:
                                can_revenge_anyway = True

                        self.bench_has_safe_ohko_counter = bench_has_safe_ohko_counter
                        if (foe_guaranteed_lethal or (chip_secures_revenge and not can_revenge_anyway)) and not bench_has_safe_ohko_counter:
                            # Dying with chip guarantees a safe revenge kill, while dying without chip risks losing our bench mon.
                            # Priority chip is strictly dominant over gambling on a miss!
                            for i, (sc, cmd, mid) in enumerate(scores):
                                if mid == best_prio_mid:
                                    scores[i][0] = sc + 0.75
                                else:
                                    scores[i][0] = sc - 0.60
                        else:
                            # Bench can either revenge kill regardless, or cannot revenge kill even with chip,
                            # or bench has a safe OHKO counter that preserves active mon upon switching.
                            for i, (sc, cmd, mid) in enumerate(scores):
                                if mid == best_prio_mid:
                                    scores[i][0] = sc + (0.15 if bench_has_safe_ohko_counter else 0.35)
                                else:
                                    mv = MV.get(mid)
                                    if mv and mv.get("p", 0) <= foe_max_pri:
                                        m_rl = damage_rolls(self.me, self.foe, mid, self.weather)
                                        can_ko = (m_rl[-1] >= self.foe.hp)
                                        if not can_ko:
                                            scores[i][0] = sc - 0.50

        sw_scores = []
        for idx, mon in self.bench:
            s = self.eval_switch(mon)
            sw_scores.append((s, "switch %d" % idx, mon.name))

        allsc = scores + sw_scores
        if not allsc:
            return self.agent._fallback(obs)

        best_move = max(scores, key=lambda x: x[0]) if scores else None
        best_sw = max(sw_scores, key=lambda x: x[0]) if sw_scores else None

        if best_move is None:
            return best_sw[1]

        sw_margin = self.P.get("switch_margin", 0.10)
        if len(obs.get("valid_moves", [])) == 1 and self.me.item in ("choiceband", "choicespecs"):
            m_info = obs.get("valid_moves", [])[0]
            mult = m_info.get("type_multiplier", 1.0)
            if mult <= 0.05:
                # Immune (e.g. Ghost vs Normal Snorlax, Dragon vs Fairy Togekiss) -> decisively switch out to reset Choice Band!
                sw_margin = -0.35
            elif mult < 0.9:
                # Resisted (0.5x, 0.25x) -> switch out if bench has a better counter!
                sw_margin = -0.05

        # Double-Turn Move Defense:
        # If the opponent is using or charging a double-turn move (phantomforce, bounce, solarbeam, fly, dig, dive)
        # that is lethal to our active Pokémon, see if switching to a bench Pokémon is better!
        is_tt_lethal = False
        target_tt = getattr(self, "foe_charging_move", None)
        if not target_tt:
            for fmid, q in self.foe.moves:
                if fmid in TWO_TURN_MOVES:
                    rl = damage_rolls(self.foe, self.me, fmid, self.weather)
                    if rl[-1] >= self.me.hp or rl[8] >= self.me.hp * 0.88:
                        is_tt_lethal = True
                        target_tt = fmid
                        break
        else:
            rl = damage_rolls(self.foe, self.me, target_tt, self.weather)
            if rl[-1] >= self.me.hp or rl[8] >= self.me.hp * 0.88:
                is_tt_lethal = True

        if target_tt and best_sw is not None:
            if getattr(self, "foe_charging_move", None) in SEMI_INVULNERABLE_MOVES:
                sw_margin = min(sw_margin, -0.30)
            elif is_tt_lethal:
                sw_margin = min(sw_margin, -0.10)
            else:
                sw_margin = min(sw_margin, -0.05)

        if getattr(self, "bench_has_safe_ohko_counter", False) and best_sw is not None:
            sw_margin = min(sw_margin, -0.20)

        # Never switch out if our active Pokémon can achieve a lethal KO on the foe this turn:
        # If any valid move KOs the foe, and we execute before taking lethal damage (either we are
        # faster, have priority, or survive the foe's hit): take the guaranteed KO!
        # EXCEPTION: If the foe is charging or using a two-turn move (e.g. phantomforce, bounce, solarbeam),
        # we must always evaluate whether switching is better or eating the attack is better!
        # Furthermore, if the foe is semi-invulnerable, normal moves cannot hit them this turn anyway!
        can_guaranteed_ko = False
        foe_charging = getattr(self, "foe_charging_move", None)
        if not target_tt and not foe_charging:
            foe_max_dmg = 0.0
            for fmid, q in self.foe.moves:
                fmv = MV.get(fmid)
                if fmv and fmv["c"] != "T":
                    frl = damage_rolls(self.foe, self.me, fmid, self.weather)
                    foe_max_dmg = max(foe_max_dmg, frl[-1])

            p_me_faster = self.p_faster(self.me)
            for m in obs.get("valid_moves", []) or []:
                mid = norm(m.get("id") or m.get("name"))
                mv = MV.get(mid)
                if mv and mv["c"] != "T":
                    rl = damage_rolls(self.me, self.foe, mid, self.weather)
                    if rl[4] >= self.foe.hp:
                        pri = mv.get("p", 0)
                        if pri > 0 or p_me_faster >= 0.5 or foe_max_dmg < self.me.hp:
                            can_guaranteed_ko = True
                            break

        if can_guaranteed_ko:
            best_sw = None

        if best_sw is not None and best_sw[0] > best_move[0] + sw_margin:
            charging = getattr(self, "foe_charging_move", None)
            if self.p_faster(self.me) >= 0.5 and charging not in SEMI_INVULNERABLE_MOVES:
                for m in obs.get("valid_moves", []) or []:
                    pmid = norm(m.get("id") or m.get("name"))
                    if pmid in ("uturn", "voltswitch", "flipturn"):
                        p_rl = damage_rolls(self.me, self.foe, pmid, self.weather)
                        if p_rl[8] > 0:
                            return "move %d" % m.get("index", 1)
            return best_sw[1]
        return best_move[1]

    def best_forced_switch(self):
        best = None
        for idx, mon in self.bench:
            intim = self._intim_prob()
            if mon.ability in ("clearbody", "innerfocus"):
                intim = 0.0
            v = self.leaf(mon, mon.hp, self.foe.hp, "", None, intim)
            v += 0.2 * (self.p_faster(mon) - 0.5)
            if best is None or v > best[0]:
                best = (v, idx)
        return "switch %d" % best[1] if best else self.agent._fallback(self.obs)

    def _intim_prob(self):
        return sum(p for a, p in self.foe.ab_probs if a == "intimidate")

    def eval_move(self, mid):
        mv = MV.get(mid)
        if mv is None:
            return -9
        total = 0.0
        worst = 9e9
        for w, fa in self.foe_dist:
            v = self.outcome_move(mid, mv, fa)
            total += w * v
            if w >= self.P.get("worst_w", 0.1):
                worst = min(worst, v)
        if worst > 1e8:
            worst = total

        lam = self.P.get("lam_worst", 0.3)
        score = (1 - lam) * total + lam * worst

        if mv.get("sb"):
            neg = sum(-x for x in mv["sb"].values() if x < 0)
            my_rl = damage_rolls(self.me, self.foe, mid, self.weather)
            if my_rl[8] < self.foe.hp:
                score -= 0.03 * neg
            else:
                score -= 0.01 * neg
        if mid in ("outrage", "petaldance"):
            score -= self.P.get("lock_pen", 0.15)
        if mid == "phantomforce":
            foe_has_ghost_counter = False
            for t in self.obs.get("foe_team", []) or []:
                if t.get("name") != self.foe.name and (t.get("hp_percent", 0) or 0) > 0:
                    t_sp = SP.get(t.get("name"), {})
                    t_types = t_sp.get("types", [])
                    if "Normal" in t_types or "Dark" in t_types:
                        foe_has_ghost_counter = True
                        break
            if getattr(self.agent, "foe_switched_on_phantom", False) or (getattr(self.agent, "foe_switched_count", 0) > 0 and foe_has_ghost_counter):
                score -= 0.25
        elif mid in ("solarbeam", "fly", "dig", "bounce"):
            score -= 0.20

        # Choice Band / Choice Specs Lock Quality Rule:
        # If holding Choice Band, locking into a Special move (e.g. Flamethrower on Dragapult)
        # when a Physical move can ALSO achieve a lethal KO is a blunder because it leaves us
        # locked into an unboosted attack against the opponent's next Pokémon!
        has_bench = any(m.hp > 0 for _, m in self.bench)
        if self.me.item == "choiceband" and mv["c"] == "S":
            phys_ko = False
            for m in self.obs.get("valid_moves", []) or []:
                pmid = norm(m.get("id") or m.get("name"))
                pmv = MV.get(pmid)
                if pmv and pmv["c"] == "P":
                    prl = damage_rolls(self.me, self.foe, pmid, self.weather)
                    if prl[4] >= self.foe.hp:
                        phys_ko = True
                        break
            if phys_ko:
                score -= 0.60
            elif has_bench:
                my_rl = damage_rolls(self.me, self.foe, mid, self.weather)
                if my_rl[-1] < self.foe.hp:
                    score -= 0.35
        elif self.me.item == "choicespecs" and mv["c"] == "P":
            spec_ko = False
            for m in self.obs.get("valid_moves", []) or []:
                pmid = norm(m.get("id") or m.get("name"))
                pmv = MV.get(pmid)
                if pmv and pmv["c"] == "S":
                    prl = damage_rolls(self.me, self.foe, pmid, self.weather)
                    if prl[4] >= self.foe.hp:
                        spec_ko = True
                        break
            if spec_ko:
                score -= 0.60
            elif has_bench:
                my_rl = damage_rolls(self.me, self.foe, mid, self.weather)
                if my_rl[-1] < self.foe.hp:
                    score -= 0.35
        return score

    def outcome_move(self, mid, mv, fa):
        me, foe = self.me, self.foe
        my_pri = mv["p"]
        is_status = (mv["c"] == "T")
        my_rl = damage_rolls(me, foe, mid, self.weather) if not is_status else [0.0] * 16
        my_acc = min(1.0, mv["a"] / 100.0)

        kind = fa[0]
        if kind == "switch":
            dmg = sum(my_rl) / 16.0 * 0.55
            frac_dmg = (dmg * my_acc) / max(1.0, foe.maxhp)
            return self.leaf(me, me.hp, foe.maxhp * (1.0 - frac_dmg), "", None, 0.0)

        fmid = fa[1] if len(fa) > 1 else None
        fmv = MV.get(fmid) if fmid else None
        f_rl = [0.0] * 16
        f_pri = 0
        f_acc = 1.0

        if kind == "atk" and fmv:
            f_rl = damage_rolls(foe, me, fmid, self.weather)
            f_pri = fmv["p"]
            f_acc = min(1.0, fmv["a"] / 100.0)
            if fmv.get("first") and not self.foe_first_turn:
                f_rl = [0.0] * 16

        sucker = bool(fmv and fmv.get("sucker"))
        p_first = self.p_faster(me)

        is_pivot = mid in ("uturn", "voltswitch", "flipturn")
        best_bench_mon = None
        b_rl = None
        if is_pivot and self.bench:
            best_v = -999.0
            for idx, b in self.bench:
                v_b = self.leaf(b, b.hp, foe.hp)
                if v_b > best_v:
                    best_v = v_b
                    best_bench_mon = b
            if best_bench_mon and fmid and fmv:
                b_rl = damage_rolls(foe, best_bench_mon, fmid, self.weather)

        if my_pri > f_pri:
            p_me_first = 1.0
        elif my_pri < f_pri:
            p_me_first = 0.0
        else:
            p_me_first = p_first

        foe_boost_atk = 0
        heal_foe = 0.0
        my_new_status = ""
        protect = (fmid == "protect")
        if kind == "util":
            if fmid in SETUP:
                foe_boost_atk = SETUP[fmid].get("atk", 0) + SETUP[fmid].get("spa", 0)
                foe_boost_atk = min(2, foe_boost_atk)
            if fmid in HEAL_MOVES:
                heal_foe = foe.maxhp * 0.5
            if fmid in STATUS_MOVES:
                st, acc = STATUS_MOVES[fmid]
                if not me.status and st in ("brn", "par", "slp", "psn"):
                    my_new_status = st

        if not is_status and mv.get("t") == "Dark":
            for ab, pb in foe.ab_probs:
                if ab == "justified":
                    foe_boost_atk = min(4, foe_boost_atk + int(round(1 * pb)))

        # Model our own status moves
        my_boost_atk = 0
        heal_me = 0.0
        foe_new_status = ""
        my_protect = (mid == "protect")
        if is_status:
            if mid in SETUP:
                my_boost_atk = min(2, SETUP[mid].get("atk", 0) + SETUP[mid].get("spa", 0))
            if mid in HEAL_MOVES:
                heal_me = me.maxhp * 0.5
            if mid in STATUS_MOVES:
                st, acc = STATUS_MOVES[mid]
                if not foe.status and st in ("brn", "par", "slp", "psn"):
                    foe_new_status = st

        recoil = 0.0
        if me.item == "lifeorb" and not is_status:
            recoil += me.maxhp * 0.10

        contact_chip = 0.0
        if mv.get("ct"):
            for ab, pb in foe.ab_probs:
                if ab in ("roughskin", "ironbarbs"):
                    contact_chip += pb * me.maxhp / 8.0
            if self.foe_mem.item_known == "rockyhelmet":
                contact_chip += me.maxhp / 6.0
            elif self.foe_mem.item_known is None:
                rh_p = SPECIES_ITEM_PRIOR.get(foe.name.lower(), {}).get("rockyhelmet", 0.0)
                contact_chip += rh_p * (me.maxhp / 6.0)

        foe_sash_p = 0.0
        if foe.hp >= foe.maxhp - 0.5 and me.ability != "moldbreaker":
            if self.foe_mem.item_known == "focussash":
                foe_sash_p = 1.0
            elif self.foe_mem.item_known is None:
                foe_sash_p = SPECIES_ITEM_PRIOR.get(foe.name.lower(), {}).get("focussash", 0.0)

        my_sash_p = 1.0 if (me.item == "focussash" and me.hp >= me.maxhp - 0.5) else 0.0

        my_samples = roll_samples(my_rl)
        f_samples = roll_samples(f_rl)
        orders = [(p_me_first, True), (1 - p_me_first, False)]
        total = 0.0

        for po, me_first in orders:
            if po <= 1e-9:
                continue
            for dm, pdm in my_samples:
                for hit_m, ph_m in ((1, my_acc), (0, 1 - my_acc)):
                    if ph_m <= 1e-9:
                        continue
                    for df, pdf in f_samples:
                        for hit_f, ph_f in ((1, f_acc), (0, 1 - f_acc)):
                            if ph_f <= 1e-9:
                                continue
                            pr_ = po * pdm * ph_m * pdf * ph_f
                            if pr_ <= 1e-7:
                                continue
                            dmg_m = (dm * hit_m if not protect else 0.0) if not (me_first and self.foe_charging_move in SEMI_INVULNERABLE_MOVES and not is_status) else 0.0
                            eff_my_protect = my_protect and (fmid != "phantomforce")
                            dmg_f = df * hit_f if not eff_my_protect else 0.0

                            if me_first:
                                # Player moves first
                                if is_status:
                                    m_hp = min(me.maxhp, me.hp + heal_me)
                                    f_hp = foe.hp
                                    if not sucker and dmg_f > 0:
                                        if my_sash_p > 0 and dmg_f >= m_hp and not (fmv and fmv.get("mh")):
                                            m_hp = 1.0
                                        else:
                                            m_hp = max(0.0, m_hp - dmg_f)
                                    f_hp = min(foe.maxhp, f_hp + heal_foe)
                                    st = my_new_status if (m_hp > 0) else ""
                                    total += pr_ * self.leaf(me, m_hp, f_hp, st or me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)
                                else:
                                    # Attack move
                                    if dmg_m >= foe.hp and not mv.get("mh"):
                                        # Lethal hit!
                                        # Subcase A: Foe survives via Focus Sash (prob foe_sash_p)
                                        if foe_sash_p > 0:
                                            if is_pivot and best_bench_mon:
                                                b_df = df if not b_rl else (df * b_rl[8] / max(1.0, f_rl[8]))
                                                b_dmg_f = b_df * hit_f if not eff_my_protect else 0.0
                                                b_hp = max(0.0, best_bench_mon.hp - b_dmg_f)
                                                f_hp_s = min(foe.maxhp, 1.0 + heal_foe)
                                                v_sash = self.leaf(best_bench_mon, b_hp, f_hp_s, "", None, 0.0, foe_boost_atk, 0, "")
                                            else:
                                                f_hp_s = 1.0
                                                m_hp_s = me.hp
                                                if hit_m and mv.get("ct"):
                                                    m_hp_s -= contact_chip
                                                eff_dmg_f = dmg_f
                                                if fmv and mv.get("sb"):
                                                    if fmv["c"] == "P" and mv["sb"].get("def", 0) < 0:
                                                        eff_dmg_f *= 1.5
                                                    elif fmv["c"] == "S" and mv["sb"].get("spd", 0) < 0:
                                                        eff_dmg_f *= 1.5
                                                if not sucker and eff_dmg_f > 0:
                                                    if my_sash_p > 0 and eff_dmg_f >= m_hp_s and not (fmv and fmv.get("mh")):
                                                        m_hp_s = 1.0
                                                    else:
                                                        m_hp_s = max(0.0, m_hp_s - eff_dmg_f)
                                                f_hp_s = min(foe.maxhp, f_hp_s + heal_foe)
                                                if m_hp_s > 0 and hit_m:
                                                    m_hp_s = max(0.0, m_hp_s - recoil)
                                                st = my_new_status if (m_hp_s > 0) else ""
                                                v_sash = self.leaf(me, m_hp_s, f_hp_s, st or me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)
                                        else:
                                            v_sash = 0.0

                                        # Subcase B: Foe does not have Sash -> Faints, 0 retaliation!
                                        f_hp_no = 0.0
                                        m_hp_no = me.hp
                                        if hit_m and mv.get("ct"):
                                            m_hp_no -= contact_chip
                                        if m_hp_no > 0 and hit_m:
                                            m_hp_no = max(0.0, m_hp_no - recoil)
                                        v_no = self.leaf(me, m_hp_no, f_hp_no, me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)

                                        total += pr_ * (foe_sash_p * v_sash + (1.0 - foe_sash_p) * v_no)
                                    else:
                                        # Non-lethal attack
                                        f_hp = max(0.0, foe.hp - dmg_m)
                                        if is_pivot and best_bench_mon:
                                            b_df = df if not b_rl else (df * b_rl[8] / max(1.0, f_rl[8]))
                                            b_dmg_f = b_df * hit_f if not eff_my_protect else 0.0
                                            b_hp = max(0.0, best_bench_mon.hp - b_dmg_f)
                                            f_hp = min(foe.maxhp, f_hp + heal_foe)
                                            total += pr_ * self.leaf(best_bench_mon, b_hp, f_hp, "", None, 0.0, foe_boost_atk, 0, "")
                                        else:
                                            m_hp = me.hp
                                            if hit_m and mv.get("ct"):
                                                m_hp -= contact_chip
                                            if f_hp > 0:
                                                eff_dmg_f = dmg_f
                                                if fmv and mv.get("sb"):
                                                    if fmv["c"] == "P" and mv["sb"].get("def", 0) < 0:
                                                        eff_dmg_f *= 1.5
                                                    elif fmv["c"] == "S" and mv["sb"].get("spd", 0) < 0:
                                                        eff_dmg_f *= 1.5
                                                if not sucker and eff_dmg_f > 0:
                                                    if my_sash_p > 0 and eff_dmg_f >= m_hp and not (fmv and fmv.get("mh")):
                                                        m_hp = 1.0
                                                    else:
                                                        m_hp = max(0.0, m_hp - eff_dmg_f)
                                                f_hp = min(foe.maxhp, f_hp + heal_foe)
                                            if m_hp > 0 and hit_m:
                                                m_hp = max(0.0, m_hp - recoil)
                                            m_hp = max(0.0, m_hp)
                                            st = my_new_status if (m_hp > 0) else ""
                                            total += pr_ * self.leaf(me, m_hp, f_hp, st or me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)
                            else:
                                # Foe moves first
                                if sucker and is_status:
                                    dmg_f = 0.0

                                m_hp = me.hp
                                if dmg_f > 0:
                                    if my_sash_p > 0 and dmg_f >= m_hp and not (fmv and fmv.get("mh")):
                                        m_hp = 1.0
                                    else:
                                        m_hp = max(0.0, m_hp - dmg_f)

                                if m_hp > 0:
                                    # Player survives and retaliates
                                    if is_status:
                                        m_hp = min(me.maxhp, m_hp + heal_me)
                                        f_hp = min(foe.maxhp, foe.hp + heal_foe)
                                        st = my_new_status if (m_hp > 0) else ""
                                        total += pr_ * self.leaf(me, m_hp, f_hp, st or me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)
                                    else:
                                        if dmg_m >= foe.hp and not mv.get("mh"):
                                            # Lethal retaliation at end of turn
                                            if foe_sash_p > 0:
                                                m_hp_s = m_hp - (contact_chip if (hit_m and mv.get("ct")) else 0)
                                                if m_hp_s > 0 and hit_m:
                                                    m_hp_s = max(0.0, m_hp_s - recoil)
                                                st = my_new_status if (m_hp_s > 0) else ""
                                                v_sash = self.leaf(me, m_hp_s, 1.0, st or me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)
                                            else:
                                                v_sash = 0.0

                                            m_hp_no = m_hp - (contact_chip if (hit_m and mv.get("ct")) else 0)
                                            if m_hp_no > 0 and hit_m:
                                                m_hp_no = max(0.0, m_hp_no - recoil)
                                            v_no = self.leaf(me, m_hp_no, 0.0, me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)

                                            total += pr_ * (foe_sash_p * v_sash + (1.0 - foe_sash_p) * v_no)
                                        else:
                                            f_hp = max(0.0, foe.hp - dmg_m)
                                            if is_pivot and best_bench_mon:
                                                f_hp = min(foe.maxhp, f_hp + heal_foe) if f_hp > 0 else 0.0
                                                total += pr_ * self.leaf(best_bench_mon, best_bench_mon.hp, f_hp, "", None, 0.0, foe_boost_atk, 0, "")
                                            else:
                                                if hit_m and mv.get("ct"):
                                                    m_hp -= contact_chip
                                                if m_hp > 0 and hit_m:
                                                    m_hp = max(0.0, m_hp - recoil)
                                                m_hp = max(0.0, m_hp)
                                                f_hp = min(foe.maxhp, f_hp + heal_foe) if f_hp > 0 else 0.0
                                                st = my_new_status if (m_hp > 0) else ""
                                                total += pr_ * self.leaf(me, m_hp, f_hp, st or me.status, None, 0.0, foe_boost_atk, my_boost_atk, foe_new_status)
                                else:
                                    # Player fainted before acting
                                    f_hp = min(foe.maxhp, foe.hp + heal_foe)
                                    total += pr_ * self.leaf(me, 0.0, f_hp, "", None, 0.0, foe_boost_atk, 0, "")
        return total

    def eval_switch(self, mon):
        foe = self.foe
        intim_p = self._intim_prob()
        if mon.ability in ("clearbody", "innerfocus", "oblivious", "owntempo", "scrappy"):
            intim_p = 0.0
        mon_moves = mon.moves if isinstance(mon.moves[0] if mon.moves else "", str) else [m for m, _ in mon.moves]
        can_ohko = any(
            damage_rolls(mon, foe, mid, self.weather)[8] >= foe.hp
            for mid in mon_moves if mid in MV and MV[mid]["c"] != "T"
        )
        total = 0.0
        worst = 9e9
        for w, fa in self.foe_dist:
            kind = fa[0]
            fmid = fa[1] if len(fa) > 1 else None
            fmv = MV.get(fmid) if fmid else None
            if kind == "atk" and fmv:
                rl = damage_rolls(foe, mon, fmid, self.weather)
                acc = min(1.0, fmv["a"] / 100.0)
                if fmv.get("first") and not self.foe_first_turn:
                    rl = [0.0] * 16
                # Sucker punch fails if target is switching!
                if fmv.get("sucker"):
                    rl = [0.0] * 16
                v = 0.0
                for d, pd in roll_samples(rl):
                    for hit, ph in ((1, acc), (0, 1 - acc)):
                        if ph <= 1e-9:
                            continue
                        hp = max(0.0, mon.hp - d * hit)
                        if mon.item == "focussash" and mon.hp >= mon.maxhp - 0.5 and not (fmv and fmv.get("mh")):
                            if hp <= 0:
                                hp = 1.0
                        if self.sand and not any(t in ("Rock", "Ground", "Steel") for t in mon.types):
                            hp = max(0.0, hp - mon.maxhp / 16.0)
                        if hp > 0 and d > 0:
                            best_t, prio_k = self._best_dmg(mon, foe, foe.hp, intim_p)
                            p_mon_faster = self.p_faster(mon)
                            if not prio_k and not (can_ohko and p_mon_faster >= 0.5):
                                if (best_t > 1.0 or p_mon_faster < 0.5) and hp <= d:
                                    v += pd * ph * (self.leaf(mon, 0.0, foe.hp, "", None, intim_p) - 0.25)
                                    continue
                        v += pd * ph * self.leaf(mon, hp, foe.hp, "", None, intim_p)
            elif kind == "util":
                foe_boost = 0
                if fmid in SETUP:
                    foe_boost = min(2, SETUP[fmid].get("atk", 0) + SETUP[fmid].get("spa", 0))
                sw_hp = mon.hp
                if self.sand and not any(t in ("Rock", "Ground", "Steel") for t in mon.types):
                    sw_hp = max(0.0, sw_hp - mon.maxhp / 16.0)
                v = self.leaf(mon, sw_hp, min(foe.maxhp, foe.hp + (foe.maxhp * 0.5 if fmid in HEAL_MOVES else 0)), "", None, intim_p, foe_boost)
            else:
                sw_hp = mon.hp
                if self.sand and not any(t in ("Rock", "Ground", "Steel") for t in mon.types):
                    sw_hp = max(0.0, sw_hp - mon.maxhp / 16.0)
                v = self.leaf(mon, sw_hp, foe.hp, "", None, intim_p)

            total += w * v
            if w >= self.P.get("worst_w", 0.1):
                worst = min(worst, v)

        if worst > 1e8:
            worst = total
        lam = self.P.get("lam_worst", 0.3)
        score = (1 - lam) * total + lam * worst

        score -= self.P.get("switch_cost", 0.03)
        if self.agent.prev_action and "switch" in self.agent.prev_action:
            score -= 0.25
        if self.me.status in ("slp", "frz"):
            score += 0.15
        return score
