#!/bin/bash
# usage: ./bench.sh <agent.py> <N> <seed> [opponents...]
A=${1:-agents/ours.py}
N=${2:-100}
S=${3:-7}
shift 3 2>/dev/null || true
OPP=${@:-template_agent decision_tree_agent q_learning_agent}

echo "=========================================================================================="
echo "Running Benchmark: Agent=$A | Matches=$N per opponent | Seed=$S | Opponents=$OPP"
echo "=========================================================================================="

for b in $OPP; do
  node harness.js --a1 $A --a2 agents/$b.py --random -n $N --seed $S 2>&1 | python3 -c "
import sys, json
raw = sys.stdin.read().strip()
lines = [l for l in raw.split('\n') if l.strip()]
if not lines:
    print('No output received')
    sys.exit(0)
try:
    d = json.loads(lines[-1])
    print('%-24s winrate: %6.1f%% (%3d-%-3d)  turns: %4.1f  illegal: %d  err: %d  maxMs: %4.0f  avgMs: %4.1f' % (
        d['a2'], d['a1_winrate']*100, d['a1_wins'], d['a2_wins'], d['avg_turns'],
        d['a1_stats']['illegal'], d['a1_stats']['errors'], d['a1_stats']['maxMs'], d['a1_stats']['avgMs']
    ))
except Exception as e:
    print('Failed to parse:', raw[:200])
"
done
echo "=========================================================================================="
