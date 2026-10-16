const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const readline = require('readline');
const Sim = require('pokemon-showdown');
const { Teams, Dex } = Sim;

const DATA = JSON.parse(fs.readFileSync(path.join(__dirname, 'data.json'), 'utf8'));
const SPECIES = Object.keys(DATA.species);

function mulberry(a) {
  return function() {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function setFor(name) {
  const p = DATA.species[name];
  const e = p.evs;
  return {
    name, species: name, item: p.item, ability: p.ab[0], moves: p.dm, nature: p.nature, level: 100,
    evs: { hp: e[0], atk: e[1], def: e[2], spa: e[3], spd: e[4], spe: e[5] },
    ivs: { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 }, gender: ''
  };
}

function randomTeam(rng) {
  const pool = SPECIES.slice();
  const out = [];
  for (let i = 0; i < 3; i++) {
    const idx = Math.floor(rng() * pool.length);
    out.push(setFor(pool.splice(idx, 1)[0]));
  }
  return Teams.pack(out);
}

function loadTeam(file) {
  if (!file || !fs.existsSync(file)) return null;
  const content = fs.readFileSync(file, 'utf8').trim();
  if (!content) return null;
  return Teams.pack(Teams.import(content));
}

class AgentWorker {
  constructor(scriptPath, label) {
    this.label = label;
    this.scriptPath = scriptPath;
    this.proc = spawn('python3', [path.join(__dirname, 'runner.py'), scriptPath]);
    this.rl = readline.createInterface({ input: this.proc.stdout });
    this.queue = [];
    this.rl.on('line', (line) => {
      const cb = this.queue.shift();
      if (cb) cb(line.trim());
    });
    this.proc.stderr.on('data', (d) => process.stderr.write(d));
  }

  ask(obs) {
    return new Promise((resolve) => {
      const start = process.hrtime.bigint();
      const timer = setTimeout(() => {
        // Fallback on timeout (1000ms)
        const idx = this.queue.indexOf(handler);
        if (idx !== -1) {
          this.queue.splice(idx, 1);
          resolve({ choice: 'move 1', ms: 1000, error: true });
        }
      }, 1000);

      const handler = (choice) => {
        clearTimeout(timer);
        const ms = Number(process.hrtime.bigint() - start) / 1e6;
        resolve({ choice, ms, error: false });
      };
      this.queue.push(handler);
      this.proc.stdin.write(JSON.stringify(obs) + '\n');
    });
  }

  kill() {
    try { this.proc.kill(); } catch (e) {}
  }
}

function parseHpPercent(condition) {
  if (!condition || condition === '0 fnt' || condition.endsWith('fnt')) return 0;
  const parts = condition.split(' ')[0].split('/');
  if (parts.length === 2) {
    const cur = parseFloat(parts[0]);
    const max = parseFloat(parts[1]);
    return max > 0 ? Math.round((cur / max) * 100) : 0;
  }
  return parseInt(parts[0]) || 0;
}

function parseStatus(condition) {
  if (!condition) return '';
  const parts = condition.split(' ');
  return parts.length > 1 ? parts[1] : '';
}

function calcTypeMultiplier(moveType, defTypes) {
  let mult = 1.0;
  const row = DATA.types[moveType];
  if (!row) return 1.0;
  for (const t of defTypes) {
    mult *= (row[t] !== undefined ? row[t] : 1.0);
  }
  return mult;
}

function buildObservation(turn, isPreview, req, mySideData, foeSideData) {
  const foeTeamList = foeSideData.revealedTeam || (foeSideData.team ? foeSideData.team.map(p => p.name) : []);
  if (isPreview) {
    return {
      turn: 0,
      team_preview: true,
      force_switch: false,
      my_active: null,
      foe: null,
      my_team: mySideData.team.map(p => ({
        name: p.name,
        hp_percent: 100,
        active: false,
        fainted: false
      })),
      foe_team: foeTeamList.map(name => ({
        name,
        hp_percent: 100
      })),
      valid_moves: [],
      valid_switches: mySideData.team.map((p, idx) => ({
        index: idx + 1,
        name: p.name,
        types: p.types,
        hp_percent: 100,
        active: false,
        fainted: false
      }))
    };
  }

  const myPokes = req.side.pokemon;
  let activePoke = null;
  let activeIdx = 0;
  for (let i = 0; i < myPokes.length; i++) {
    if (myPokes[i].active) {
      activePoke = myPokes[i];
      activeIdx = i;
      break;
    }
  }

  const foeActiveName = foeSideData.activeName || (foeSideData.team[0] && foeSideData.team[0].name) || '';
  const foeDex = Dex.species.get(foeActiveName);
  const foeTypes = foeDex ? foeDex.types : [];
  const foeHp = foeSideData.activeHp !== undefined ? foeSideData.activeHp : 100;
  const foeStatus = foeSideData.activeStatus || '';
  const foeBoosts = foeSideData.activeBoosts || {};

  const myActiveSpecies = activePoke ? activePoke.details.split(',')[0].trim() : '';
  const myActiveDex = Dex.species.get(myActiveSpecies);
  const myActiveTypes = myActiveDex ? myActiveDex.types : [];
  const myActiveHp = activePoke ? parseHpPercent(activePoke.condition) : 0;
  const myActiveStatus = activePoke ? parseStatus(activePoke.condition) : '';
  const myActiveBoosts = mySideData.activeBoosts || {};

  const validMoves = [];
  if (req.active && req.active[0] && req.active[0].moves) {
    const rawMoves = req.active[0].moves;
    for (let i = 0; i < rawMoves.length; i++) {
      const rm = rawMoves[i];
      if (rm.disabled || rm.pp <= 0) continue;
      const dexMove = Dex.moves.get(rm.id);
      const mType = dexMove.type || 'Normal';
      const mCat = dexMove.category || 'Physical';
      const mult = calcTypeMultiplier(mType, foeTypes);
      const isStab = myActiveTypes.includes(mType);
      validMoves.push({
        index: i + 1,
        id: rm.id,
        name: rm.move,
        type: mType,
        category: mCat,
        base_power: dexMove.basePower || 0,
        accuracy: dexMove.accuracy === true ? 100 : (dexMove.accuracy || 100),
        type_multiplier: mult,
        stab: isStab
      });
    }
  }

  const isTrapped = Boolean(!req.forceSwitch && req.active && req.active[0] && req.active[0].trapped);
  const validSwitches = [];
  const myTeam = [];
  for (let i = 0; i < myPokes.length; i++) {
    const p = myPokes[i];
    const sName = p.details.split(',')[0].trim();
    const sDex = Dex.species.get(sName);
    const hpPct = parseHpPercent(p.condition);
    const isFnt = hpPct <= 0 || p.condition.endsWith('fnt');
    myTeam.push({
      name: sName,
      hp_percent: hpPct,
      active: p.active,
      fainted: isFnt
    });
    if (!p.active && !isFnt && !isTrapped) {
      validSwitches.push({
        index: i + 1,
        name: sName,
        types: sDex ? sDex.types : [],
        hp_percent: hpPct,
        active: false,
        fainted: false
      });
    }
  }

  return {
    turn,
    team_preview: false,
    force_switch: Boolean(req.forceSwitch),
    my_active: activePoke ? {
      name: myActiveSpecies,
      types: myActiveTypes,
      hp_percent: myActiveHp,
      condition: activePoke.condition,
      status: myActiveStatus,
      stats: activePoke.stats,
      boosts: myActiveBoosts
    } : null,
    foe: {
      name: foeActiveName,
      types: foeTypes,
      hp_percent: foeHp,
      status: foeStatus,
      boosts: foeBoosts,
      last_move: foeSideData.lastMove || '',
      moves: foeSideData.movesUsed || []
    },
    my_team: myTeam,
    valid_moves: validMoves,
    valid_switches: validSwitches
  };
}

async function playOne(w1, w2, t1, t2, swap, stats, traceLabel) {
  const stream = new Sim.BattleStream();
  const [team1, team2] = swap ? [t2, t1] : [t1, t2];
  const [worker1, worker2] = swap ? [w2, w1] : [w1, w2];
  const [st1, st2] = swap ? [stats[1], stats[0]] : [stats[0], stats[1]];

  let currentTurn = 0;
  let winner = null;

  const sideData = {
    p1: { activeName: '', activeHp: 100, activeStatus: '', activeBoosts: {}, team: Teams.unpack(team1) },
    p2: { activeName: '', activeHp: 100, activeStatus: '', activeBoosts: {}, team: Teams.unpack(team2) }
  };

  const pendingRequests = [];
  const battleChunks = [];
  const battlePromise = (async () => {
    for await (const chunk of stream) {
      battleChunks.push(chunk);
      const lines = chunk.split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.startsWith('|win|')) {
          winner = line.split('|')[2];
        } else if (line.startsWith('|turn|')) {
          currentTurn = parseInt(line.split('|')[2]);
        } else if (line.startsWith('|poke|')) {
          const parts = line.split('|');
          const sid = parts[2].slice(0, 2);
          const name = parts[3].split(',')[0].trim();
          if (!sideData[sid].revealedTeam) sideData[sid].revealedTeam = [];
          if (!sideData[sid].revealedTeam.includes(name)) sideData[sid].revealedTeam.push(name);
        } else if (line.startsWith('|switch|') || line.startsWith('|drag|')) {
          const parts = line.split('|');
          const sid = parts[2].slice(0, 2);
          const name = parts[3].split(',')[0].trim();
          const cond = parts[4];
          sideData[sid].activeName = name;
          sideData[sid].activeHp = parseHpPercent(cond);
          sideData[sid].activeStatus = parseStatus(cond);
          sideData[sid].activeBoosts = {};
          sideData[sid].lastMove = '';
        } else if (line.startsWith('|-damage|') || line.startsWith('|-heal|')) {
          const parts = line.split('|');
          const sid = parts[2].slice(0, 2);
          const cond = parts[3];
          sideData[sid].activeHp = parseHpPercent(cond);
          sideData[sid].activeStatus = parseStatus(cond);
        } else if (line.startsWith('|-status|')) {
          const parts = line.split('|');
          const sid = parts[2].slice(0, 2);
          sideData[sid].activeStatus = parts[3];
        } else if (line.startsWith('|-curestatus|')) {
          const parts = line.split('|');
          const sid = parts[2].slice(0, 2);
          sideData[sid].activeStatus = '';
        } else if (line.startsWith('|-boost|')) {
          const parts = line.split('|');
          const sid = parts[2].slice(0, 2);
          const stat = parts[3];
          const amt = parseInt(parts[4]) || 1;
          sideData[sid].activeBoosts[stat] = (sideData[sid].activeBoosts[stat] || 0) + amt;
        } else if (line.startsWith('|-unboost|')) {
          const parts = line.split('|');
          const sid = parts[2].slice(0, 2);
          const stat = parts[3];
          const amt = parseInt(parts[4]) || 1;
          sideData[sid].activeBoosts[stat] = (sideData[sid].activeBoosts[stat] || 0) - amt;
        } else if (line.startsWith('|move|')) {
          const parts = line.split('|');
          const sid = parts[2].slice(0, 2);
          const moveName = parts[3];
          if (sideData[sid]) {
            sideData[sid].lastMove = moveName;
            if (!sideData[sid].movesUsed) sideData[sid].movesUsed = [];
            if (!sideData[sid].movesUsed.includes(moveName)) sideData[sid].movesUsed.push(moveName);
          }
        } else if (line.startsWith('sideupdate')) {
          const sid = lines[i + 1].trim();
          const reqLine = lines[i + 2];
          if (reqLine && reqLine.startsWith('|request|')) {
            const reqStr = reqLine.slice(9);
            if (reqStr) {
              const req = JSON.parse(reqStr);
              if (!req.wait) {
                pendingRequests.push({ sid, req });
              }
            }
          }
        }
      }

      while (pendingRequests.length > 0) {
        const { sid, req } = pendingRequests.shift();
        const worker = sid === 'p1' ? worker1 : worker2;
        const st = sid === 'p1' ? st1 : st2;
        const myData = sideData[sid];
        const foeData = sideData[sid === 'p1' ? 'p2' : 'p1'];

        const obs = buildObservation(currentTurn, Boolean(req.teamPreview), req, myData, foeData);
        const { choice, ms, error } = await worker.ask(obs);

        st.decisions++;
        st.totalMs += ms;
        st.maxMs = Math.max(st.maxMs, ms);
        if (error) st.errors++;

        let cmd = choice;
        // Validate legality
        if (obs.team_preview) {
          if (!cmd.startsWith('team')) cmd = 'team 123';
        } else if (obs.force_switch) {
          const legalSwitches = obs.valid_switches.map(s => `switch ${s.index}`);
          if (legalSwitches.length === 0) {
            cmd = 'default';
          } else if (!legalSwitches.includes(cmd)) {
            console.error(`[ILLEGAL SWITCH ${worker.label}] choice="${cmd}" legalSwitches=${JSON.stringify(legalSwitches)}`);
            st.illegal++;
            cmd = legalSwitches[0];
          }
        } else {
          const legalMoves = obs.valid_moves.map(m => `move ${m.index}`);
          const legalSwitches = obs.valid_switches.map(s => `switch ${s.index}`);
          const allLegal = legalMoves.concat(legalSwitches);
          if (!allLegal.includes(cmd)) {
            console.error(`[ILLEGAL MOVE ${worker.label}] choice="${cmd}" allLegal=${JSON.stringify(allLegal)}`);
            st.illegal++;
            cmd = legalMoves.length > 0 ? legalMoves[0] : (legalSwitches.length > 0 ? legalSwitches[0] : 'default');
          }
        }

        if (traceLabel && worker.label === traceLabel) {
          const myAct = obs.my_active;
          const foeAct = obs.foe;
          console.error(`T${obs.turn} ${myAct ? myAct.name : 'Team'} ${myAct ? myAct.hp_percent + '%' : ''} vs ${foeAct ? foeAct.name : 'Foe'} ${foeAct ? foeAct.hp_percent + '%' : ''} => ${cmd}${obs.force_switch ? ' (forced)' : ''} [moves=${obs.valid_moves ? obs.valid_moves.map(m=>m.name).join(',') : ''} sw=${obs.valid_switches ? obs.valid_switches.map(s=>s.name).join(',') : ''}]`);
        }

        stream.write(`>${sid} ${cmd}\n`);
      }
    }
  })();

  stream.write('>start {"formatid":"gen9customgame"}\n');
  stream.write(`>player p1 {"name":"Alice","team":"${team1}"}\n`);
  stream.write(`>player p2 {"name":"Bob","team":"${team2}"}\n`);

  await battlePromise;
  const p1won = winner === 'Alice';
  const a1won = swap ? !p1won : p1won;
  return { a1won, turns: currentTurn, log: battleChunks.join('\n') };
}

async function main() {
  const args = require('minimist')(process.argv.slice(2));
  const a1 = args.a1;
  const a2 = args.a2;
  const N = parseInt(args.n || '10');
  const isRandom = Boolean(args.random);
  const seed = parseInt(args.seed || '1');
  const trace = args.trace || null;

  if (!a1 || !a2) {
    console.error('Usage: node harness.js --a1 agents/ours.py --a2 agents/template_agent.py -n 100 [--random] [--seed 7]');
    process.exit(1);
  }

  const rng = isRandom ? mulberry(seed) : null;
  const t1 = args.t1 ? loadTeam(args.t1) : loadTeam(path.join(__dirname, 'teams/base.txt'));
  const t2 = args.t2 ? loadTeam(args.t2) : t1;

  const w1 = new AgentWorker(a1, 'p1');
  const w2 = new AgentWorker(a2, 'p2');

  const stats1 = { decisions: 0, totalMs: 0, maxMs: 0, illegal: 0, errors: 0 };
  const stats2 = { decisions: 0, totalMs: 0, maxMs: 0, illegal: 0, errors: 0 };

  let a1Wins = 0;
  let totalTurns = 0;
  let pairA = null, pairB = null;

  for (let i = 0; i < N; i++) {
    const swap = i % 2 === 1;
    let T1 = t1, T2 = t2;
    if (args['random-foe'] || (isRandom && args.t1)) {
      T1 = t1;
      T2 = randomTeam(rng);
    } else if (rng) {
      if (i % 2 === 0) {
        pairA = randomTeam(rng);
        pairB = randomTeam(rng);
      }
      T1 = pairA;
      T2 = pairB;
    }

    const res = await playOne(w1, w2, T1, T2, swap, [stats1, stats2], trace);
    if (args.verbose) {
      console.error(res.log);
    }
    if (res.a1won) {
      a1Wins++;
    } else if (args['loss-log']) {
      try {
        const ourSid = swap ? 'p2' : 'p1';
        const foeSid = swap ? 'p1' : 'p2';
        const logStr = res.log || '';
        const crits = (logStr.match(new RegExp(`\\|-crit\\|${ourSid}`, 'g')) || []).length;
        const misses = (logStr.match(new RegExp(`\\|-miss\\|${ourSid}`, 'g')) || []).length;
        const flinches = (logStr.match(new RegExp(`\\|cant\\|${ourSid}[^|]*\\|flinch`, 'g')) || []).length;
        const pars = (logStr.match(new RegExp(`\\|cant\\|${ourSid}[^|]*\\|par`, 'g')) || []).length;
        const frzs = (logStr.match(new RegExp(`\\|cant\\|${ourSid}[^|]*\\|frz`, 'g')) || []).length;
        const ourTeamNames = Teams.unpack(T1).map(p => p.name);
        const foeTeamNames = Teams.unpack(T2).map(p => p.name);

        const record = {
          matchIndex: i + 1,
          turns: res.turns,
          ourTeam: ourTeamNames,
          foeTeam: foeTeamNames,
          critsOnUs: crits,
          missesByUs: misses,
          flinchesOnUs: flinches,
          paralysisOnUs: pars,
          freezeOnUs: frzs,
          isRng: (crits > 0 || misses > 0 || flinches > 0 || pars > 0 || frzs > 0),
          log: logStr
        };
        fs.appendFileSync(args['loss-log'], JSON.stringify(record) + '\n');
      } catch (e) {}
    }
    totalTurns += res.turns;
  }

  w1.kill();
  w2.kill();

  const out = {
    a1: path.basename(a1),
    a2: path.basename(a2),
    matches: N,
    a1_wins: a1Wins,
    a2_wins: N - a1Wins,
    a1_winrate: Number((a1Wins / N).toFixed(3)),
    avg_turns: Number((totalTurns / N).toFixed(1)),
    a1_stats: {
      illegal: stats1.illegal,
      errors: stats1.errors,
      maxMs: Number(stats1.maxMs.toFixed(1)),
      avgMs: Number((stats1.totalMs / Math.max(1, stats1.decisions)).toFixed(1)),
      decisions: stats1.decisions
    }
  };

  console.log(JSON.stringify(out));
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
