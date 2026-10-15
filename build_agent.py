import json
import re
import sys
import argparse

def parse_team(path):
    if not path or path == 'none':
        return []
    txt = open(path).read().strip()
    mons = []
    for block in re.split(r'\n\s*\n', txt):
        lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
        if not lines:
            continue
        first = lines[0]
        item = ''
        if '@' in first:
            first, item = [x.strip() for x in first.split('@')]
        name = re.sub(r'\s*\(.*?\)', '', first).strip()
        s = {'name': name, 'item': item, 'ability': '', 'nature': 'adamant', 'evs': [0]*6, 'moves': []}
        for l in lines[1:]:
            if l.startswith('Ability:'):
                s['ability'] = l.split(':', 1)[1].strip()
            elif l.startswith('EVs:'):
                evs = [0]*6
                idx = {'HP': 0, 'Atk': 1, 'Def': 2, 'SpA': 3, 'SpD': 4, 'Spe': 5}
                for part in l.split(':', 1)[1].split('/'):
                    n, k = part.strip().split()
                    evs[idx[k]] = int(n)
                s['evs'] = evs
            elif l.endswith('Nature'):
                s['nature'] = l.split()[0].lower()
            elif l.startswith('-'):
                s['moves'].append(l[1:].strip())
        mons.append(s)
    return mons

def build(team_path, out_path, order='123', params=None):
    data = json.load(open('data.json'))
    src = open('agent_src.py').read()
    team = parse_team(team_path)
    
    default_params = {
        "foe_switch_low": 0.12,
        "foe_switch": 0.05,
        "w_race": 0.25,
        "lam_worst": 0.3,
        "switch_margin": 0.10,
        "q_other": 0.04,
        "q_default": 0.85,
        "lock_pen": 0.15,
        "switch_cost": 0.03,
        "w_mat": 1.0,
        "scarf_prob": 0.07,
        "foe_greedy": 0.72,
        "ko_bonus": 0.20
    }
    if params:
        default_params.update(params)

    src = src.replace('@@DATA@@', json.dumps(data, separators=(',', ':')))
    src = src.replace('@@TEAM@@', json.dumps(team))
    src = src.replace('@@ORDER@@', order)
    src = src.replace('@@PARAMS@@', json.dumps(default_params))

    open(out_path, 'w').write(src)
    print(f"Successfully built agent: {out_path} (team={team_path}, params={len(default_params)})")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Build self-contained PokemonAgent")
    parser.add_argument('team', nargs='?', default='teams/base.txt', help="Path to team file or 'none'")
    parser.add_argument('out', nargs='?', default='agents/ours.py', help="Output agent script path")
    parser.add_argument('--order', default='123', help="Team preview order")
    parser.add_argument('--params', default='{}', help="JSON string of parameter overrides")
    args = parser.parse_args()

    p_dict = json.loads(args.params)
    build(args.team, args.out, args.order, p_dict)
