const fs = require('fs');
const path = require('path');
const Sim = require('pokemon-showdown');
const { spawn } = require('child_process');
const readline = require('readline');
const { Teams, Dex } = Sim;
let lastLoggedMsg = '';
function log(msg) {
  if (msg === lastLoggedMsg && (msg.startsWith('     ') || msg.startsWith('  🔄 [Switch]'))) return;
  lastLoggedMsg = msg;
  try { fs.writeSync(1, msg + "\n"); } catch (e) {}
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
  return parts.length > 1 ? parts[1].toLowerCase() : '';
}

function renderHpBar(hp) {
  const bars = Math.max(0, Math.min(10, Math.round(hp / 10)));
  const empty = 10 - bars;
  return `[${'█'.repeat(bars)}${'-'.repeat(empty)}] ${hp}%`;
}

function loadTeam(file) {
  return Teams.pack(Teams.import(fs.readFileSync(file, 'utf8').trim()));
}

class AgentWorker {
  constructor(scriptPath, label) {
    this.label = label;
    this.proc = spawn('python3', [path.join(__dirname, 'runner.py'), scriptPath]);
    this.rl = readline.createInterface({ input: this.proc.stdout });
    this.queue = [];
    this.rl.on('line', (line) => {
      const cb = this.queue.shift();
      if (cb) cb(line.trim());
    });
    this.proc.stderr.on('data', () => {});
  }

  ask(obs) {
    return new Promise((resolve) => {
      this.queue.push(resolve);
      this.proc.stdin.write(JSON.stringify(obs) + '\n');
    });
  }

  kill() {
    try { this.proc.kill(); } catch (e) {}
  }
}

function buildObservation(currentTurn, isTeamPreview, req, mySide, foeSide) {
  if (isTeamPreview) {
    const myPokes = req.side.pokemon || [];
    const validSwitches = myPokes.map((p, idx) => {
      const sName = p.details.split(',')[0].trim();
      const sDex = Dex.species.get(sName);
      return {
        index: idx + 1,
        name: sName,
        types: sDex ? sDex.types : [],
        hp_percent: 100,
        active: false,
        fainted: false
      };
    });
    const foeTeam = (foeSide.revealedTeam || []).map((name) => {
      const sDex = Dex.species.get(name);
      return {
        name,
        types: sDex ? sDex.types : [],
        hp_percent: 100
      };
    });
    return {
      turn: 0,
      team_preview: true,
      force_switch: false,
      my_active: null,
      foe: null,
      my_team: validSwitches,
      foe_team: foeTeam,
      valid_moves: [],
      valid_switches: validSwitches
    };
  }

  const myPokes = req.side.pokemon || [];
  const activePoke = myPokes.find(p => p.active);
  const myActiveSpecies = activePoke ? activePoke.details.split(',')[0].trim() : mySide.activeName;
  const myDex = Dex.species.get(myActiveSpecies);
  const myActiveTypes = myDex ? myDex.types : [];
  const myActiveHp = activePoke ? parseHpPercent(activePoke.condition) : mySide.activeHp;
  const myActiveStatus = activePoke ? parseStatus(activePoke.condition) : mySide.activeStatus;
  const myActiveBoosts = mySide.activeBoosts || {};

  const foeActiveName = foeSide.activeName;
  const foeDex = Dex.species.get(foeActiveName);
  const foeTypes = foeDex ? foeDex.types : [];
  const foeHp = foeSide.activeHp;
  const foeStatus = foeSide.activeStatus;
  const foeBoosts = foeSide.activeBoosts || {};

  const validMoves = [];
  if (req.active && req.active[0] && req.active[0].moves) {
    req.active[0].moves.forEach((m, idx) => {
      if (!m.disabled) {
        const mDex = Dex.moves.get(m.id || m.move);
        const mult = foeDex && mDex ? Dex.getEffectiveness(mDex.type, foeDex.types) : 0;
        const typeMult = mult > 0 ? Math.pow(2, mult) : (mult < 0 ? Math.pow(0.5, -mult) : 1);
        const stab = myActiveTypes.includes(mDex ? mDex.type : '');
        validMoves.push({
          index: idx + 1,
          name: m.move,
          type: mDex ? mDex.type : 'Normal',
          base_power: mDex ? mDex.basePower : 0,
          type_multiplier: typeMult,
          stab
        });
      }
    });
  }

  const validSwitches = [];
  const myTeam = [];
  const isTrapped = Boolean(req.active && req.active[0] && req.active[0].trapped);

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
    turn: currentTurn,
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
      boosts: foeBoosts
    },
    my_team: myTeam,
    valid_moves: validMoves,
    valid_switches: validSwitches
  };
}

function chooseGeminiAction(obs, currentTurn) {
  if (obs.team_preview) {
    log(`\n🧠 [GEMINI STRATEGIC REASONING - TEAM PREVIEW]`);
    log(`  Matchup Analysis:`);
    log(`    - Agent Team: Dragapult (fast Choice Band physical cannon), Greninja (Focus Sash special sweeper), Scizor (Technician priority).`);
    log(`    - Gemini Team: Togekiss (Bulky Fairy/Flying), Volcarona (Boots Quiver Dance), Dragonite (Lum Multiscale).`);
    log(`  Tactical Hypothesis & Loophole Probing:`);
    log(`    - Dragapult is the agent's #1 lead due to speed and raw Choice Band power.`);
    log(`    - Togekiss's Fairy typing provides total IMMUNITY (0x) to Dragon Darts.`);
    log(`    - If Dragapult leads, we test whether the agent's model recognizes the Fairy immunity and pivots with U-turn, or if it makes an illegal/zero-damage lock.`);
    log(`  Action: Leading with Togekiss (Order: Togekiss, Volcarona, Dragonite) -> "team 123"`);
    return 'team 123';
  }

  const myActive = obs.my_active ? obs.my_active.name : 'None';
  const foeActive = obs.foe ? obs.foe.name : 'None';
  const foeHp = obs.foe ? obs.foe.hp_percent : 0;
  const myHp = obs.my_active ? obs.my_active.hp_percent : 0;

  function findMove(name) {
    const m = (obs.valid_moves || []).find(x => x.name.toLowerCase() === name.toLowerCase());
    return m ? `move ${m.index}` : null;
  }
  function findSwitch(name) {
    const s = (obs.valid_switches || []).find(x => x.name.toLowerCase() === name.toLowerCase());
    return s ? `switch ${s.index}` : null;
  }

  log(`\n🧠 [GEMINI STRATEGIC REASONING - TURN ${currentTurn}]`);
  log(`  Board State: Gemini ${myActive} (${myHp}% HP) vs Agent ${foeActive} (${foeHp}% HP)`);

  if (obs.force_switch) {
    log(`  Tactical Assessment (Forced Switch):`);
    if (foeActive === 'Dragapult') {
      const sw = findSwitch('Togekiss') || findSwitch('Dragonite') || findSwitch('Volcarona');
      log(`    - Against Dragapult, bringing in Dragon immunity / Multiscale bulk.`);
      log(`  Action: ${sw}`);
      return sw || (obs.valid_switches[0] ? `switch ${obs.valid_switches[0].index}` : 'default');
    } else if (foeActive === 'Scizor') {
      const sw = findSwitch('Volcarona') || findSwitch('Dragonite') || findSwitch('Togekiss');
      log(`    - Against Scizor, Volcarona is a 4x Steel resist with 4x Fire STAB.`);
      log(`  Action: ${sw}`);
      return sw || (obs.valid_switches[0] ? `switch ${obs.valid_switches[0].index}` : 'default');
    } else {
      const sw = findSwitch('Dragonite') || findSwitch('Togekiss') || findSwitch('Volcarona');
      log(`    - Against Greninja, Dragonite provides Multiscale tankiness and +2 Extreme Speed priority.`);
      log(`  Action: ${sw}`);
      return sw || (obs.valid_switches[0] ? `switch ${obs.valid_switches[0].index}` : 'default');
    }
  }

  // Active is Togekiss
  if (myActive === 'Togekiss') {
    if (foeActive === 'Dragapult') {
      log(`  Tactical Assessment:`);
      log(`    - Dragapult cannot hit Togekiss with Dragon moves (Fairy immunity).`);
      log(`    - Dazzling Gleam is STAB Fairy (2x super-effective), threatening lethal 85-100% damage.`);
      log(`    - If Dragapult stays in or clicks Phantom Force, Dazzling Gleam obliterates it.`);
      log(`    - Testing loophole: Can the agent recognize incoming Fairy lethal threat and pivot?`);
      const cmd = findMove('Dazzling Gleam') || findMove('Air Slash') || 'move 1';
      log(`  Action: ${cmd} (Dazzling Gleam)`);
      return cmd;
    } else if (foeActive === 'Scizor') {
      log(`  Tactical Assessment:`);
      log(`    - Scizor threatens Technician Bullet Punch (super-effective priority).`);
      log(`    - However, Scizor is 4x weak to Fire! Togekiss's Flamethrower is a guaranteed 100% OHKO.`);
      if (myHp >= 60) {
        log(`    - Togekiss has ${myHp}% HP (enough to survive 1 Bullet Punch which deals ~55-65%).`);
        log(`    - Testing loophole: Scizor will attempt Bullet Punch, but Flamethrower retaliates for the OHKO!`);
        const cmd = findMove('Flamethrower') || 'move 1';
        log(`  Action: ${cmd} (Flamethrower)`);
        return cmd;
      } else {
        log(`    - Togekiss is at ${myHp}% HP (vulnerable to Bullet Punch lethal priority).`);
        log(`    - Hard switching to Volcarona which 4x resists Steel!`);
        const sw = findSwitch('Volcarona');
        if (sw) {
          log(`  Action: ${sw} (Switch to Volcarona)`);
          return sw;
        }
        const cmd = findMove('Flamethrower') || 'move 1';
        log(`  Action: ${cmd} (Flamethrower)`);
        return cmd;
      }
    } else if (foeActive === 'Greninja') {
      log(`  Tactical Assessment:`);
      log(`    - Greninja has Protean + Focus Sash, threatening Ice Beam.`);
      log(`    - Dazzling Gleam deals heavy damage to break Sash.`);
      const cmd = findMove('Dazzling Gleam') || findMove('Air Slash') || 'move 1';
      log(`  Action: ${cmd} (Dazzling Gleam)`);
      return cmd;
    }
  }

  // Active is Volcarona
  if (myActive === 'Volcarona') {
    if (foeActive === 'Scizor') {
      log(`  Tactical Assessment:`);
      log(`    - Volcarona 4x resists Bullet Punch and 2x resists Close Combat.`);
      log(`    - Fiery Dance deals 4x super-effective STAB damage (Guaranteed OHKO + 50% SpA boost).`);
      log(`    - Testing loophole: Does the agent realize Scizor is completely walled and switch out?`);
      const cmd = findMove('Fiery Dance') || findMove('Bug Buzz') || 'move 1';
      log(`  Action: ${cmd} (Fiery Dance)`);
      return cmd;
    } else if (foeActive === 'Greninja') {
      log(`  Tactical Assessment:`);
      log(`    - Greninja is faster and threatens Hydro Pump.`);
      const sw = findSwitch('Dragonite');
      if (sw) {
        log(`    - Pivoting into Dragonite to tank special hit and threaten +2 Extreme Speed.`);
        log(`  Action: ${sw} (Switch to Dragonite)`);
        return sw;
      }
      const cmd = findMove('Giga Drain') || findMove('Bug Buzz') || 'move 1';
      log(`  Action: ${cmd} (Giga Drain / Bug Buzz)`);
      return cmd;
    } else if (foeActive === 'Dragapult') {
      log(`  Tactical Assessment:`);
      log(`    - Dragapult threatens Phantom Force.`);
      log(`    - Volcarona clicks Bug Buzz for STAB neutral damage.`);
      const cmd = findMove('Bug Buzz') || findMove('Fiery Dance') || 'move 1';
      log(`  Action: ${cmd} (Bug Buzz)`);
      return cmd;
    }
  }

  // Active is Dragonite
  if (myActive === 'Dragonite') {
    if (foeActive === 'Greninja') {
      log(`  Tactical Assessment:`);
      log(`    - Critical Priority Battle: Greninja holds Focus Sash and has Water Shuriken (+1 priority).`);
      log(`    - Dragonite has Extreme Speed (+2 priority)! Extreme Speed strictly beats Water Shuriken.`);
      if (foeHp <= 55) {
        log(`    - Greninja is at ${foeHp}% HP (in lethal range of Extreme Speed!).`);
        log(`    - Testing loophole: Testing if agent's lethal priority fix properly handles +2 Extreme Speed vs +1 Water Shuriken.`);
        const cmd = findMove('Extreme Speed') || 'move 1';
        log(`  Action: ${cmd} (Extreme Speed)`);
        return cmd;
      } else {
        log(`    - Greninja is healthy. Outrage deals 100%+ to pop Focus Sash.`);
        const cmd = findMove('Outrage') || findMove('Extreme Speed') || 'move 1';
        log(`  Action: ${cmd} (Outrage / Extreme Speed)`);
        return cmd;
      }
    } else if (foeActive === 'Scizor') {
      log(`  Tactical Assessment:`);
      log(`    - Scizor resists Dragon moves, but Earthquake hits neutrally with 100 BP.`);
      const cmd = findMove('Earthquake') || findMove('Dragon Dance') || 'move 1';
      log(`  Action: ${cmd} (Earthquake)`);
      return cmd;
    } else if (foeActive === 'Dragapult') {
      log(`  Tactical Assessment:`);
      log(`    - Multiscale halves incoming damage. Outrage OHKOs Dragapult.`);
      const cmd = findMove('Outrage') || findMove('Extreme Speed') || 'move 1';
      log(`  Action: ${cmd} (Outrage)`);
      return cmd;
    }
  }

  // Fallback
  const defaultMove = (obs.valid_moves && obs.valid_moves[0]) ? `move ${obs.valid_moves[0].index}` : 'move 1';
  log(`  Action: ${defaultMove}`);
  return defaultMove;
}

async function main() {
  const t1 = loadTeam('teams/ultimate_anti_meta.txt');
  const t2 = loadTeam('teams/gemini_counter.txt');
  const w1 = new AgentWorker('agents/ultimate_anti_meta.py', 'Agent (P1)');

  const stdinRl = readline.createInterface({ input: process.stdin, output: process.stdout });
  function askGemini() {
    return new Promise(resolve => stdinRl.once('line', line => resolve(line.trim())));
  }

  const stream = new Sim.BattleStream();
  let currentTurn = 0;
  let winner = null;

  const sideData = {
    p1: { activeName: '', activeHp: 100, activeStatus: '', activeBoosts: {}, team: Teams.unpack(t1) },
    p2: { activeName: '', activeHp: 100, activeStatus: '', activeBoosts: {}, team: Teams.unpack(t2) }
  };

  const pendingRequests = [];

  const battlePromise = (async () => {
    for await (const chunk of stream) {
      const lines = chunk.split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.startsWith('|win|')) {
          winner = line.split('|')[2];
          log(`\n================================================================================`);
          log(`🏆 MATCH COMPLETED! WINNER: ${winner === 'Alice' ? 'AGENT (P1)' : 'GEMINI (P2)'}`);
          log(`================================================================================\n`);
        } else if (line.startsWith('|turn|')) {
          currentTurn = parseInt(line.split('|')[2]);
          log(`\n================================================================================`);
          log(`                             ⚔️  TURN ${currentTurn}  ⚔️`);
          log(`  Agent (P1) : ${(sideData.p1.activeName || '???').padEnd(12)} ${renderHpBar(sideData.p1.activeHp)} ${sideData.p1.activeStatus ? '[' + sideData.p1.activeStatus + ']' : ''}`);
          log(`  Gemini(P2) : ${(sideData.p2.activeName || '???').padEnd(12)} ${renderHpBar(sideData.p2.activeHp)} ${sideData.p2.activeStatus ? '[' + sideData.p2.activeStatus + ']' : ''}`);
          log(`================================================================================`);
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
          log(`  🔄 [Switch] ${sid === 'p1' ? 'Agent' : 'Gemini'} sent out ${name}! (${cond})`);
        } else if (line.startsWith('|move|')) {
          const parts = line.split('|');
          const sid = parts[2].slice(0, 2);
          const move = parts[3];
          log(`  ⚡ [Move] ${sid === 'p1' ? 'Agent' : 'Gemini'} used ${move}!`);
        } else if (line.startsWith('|-damage|')) {
          const parts = line.split('|');
          const name = parts[2].split(': ')[1];
          const cond = parts[3];
          const sid = parts[2].slice(0, 2);
          sideData[sid].activeHp = parseHpPercent(cond);
          sideData[sid].activeStatus = parseStatus(cond);
          log(`     💥 Damage: ${name} HP is now ${cond}`);
        } else if (line.startsWith('|-heal|')) {
          const parts = line.split('|');
          const name = parts[2].split(': ')[1];
          const cond = parts[3];
          const sid = parts[2].slice(0, 2);
          sideData[sid].activeHp = parseHpPercent(cond);
          log(`     💚 Heal: ${name} recovered to ${cond}`);
        } else if (line.startsWith('|-status|')) {
          const parts = line.split('|');
          const name = parts[2].split(': ')[1];
          const st = parts[3];
          const sid = parts[2].slice(0, 2);
          sideData[sid].activeStatus = st;
          log(`     ⚠️ Status: ${name} was afflicted with ${st}!`);
        } else if (line.startsWith('|-boost|')) {
          const parts = line.split('|');
          const name = parts[2].split(': ')[1];
          const stat = parts[3];
          const amt = parts[4];
          const sid = parts[2].slice(0, 2);
          if (!sideData[sid].activeBoosts) sideData[sid].activeBoosts = {};
          sideData[sid].activeBoosts[stat] = (sideData[sid].activeBoosts[stat] || 0) + parseInt(amt);
          log(`     📈 Boost: ${name} +${amt} ${stat.toUpperCase()}`);
        } else if (line.startsWith('|-unboost|')) {
          const parts = line.split('|');
          const name = parts[2].split(': ')[1];
          const stat = parts[3];
          const amt = parts[4];
          const sid = parts[2].slice(0, 2);
          if (!sideData[sid].activeBoosts) sideData[sid].activeBoosts = {};
          sideData[sid].activeBoosts[stat] = (sideData[sid].activeBoosts[stat] || 0) - parseInt(amt);
          log(`     📉 Unboost: ${name} -${amt} ${stat.toUpperCase()}`);
        } else if (line.startsWith('|faint|')) {
          const parts = line.split('|');
          log(`  💀 [FAINT] ${parts[2].split(': ')[1]} fainted!`);
        } else if (line.startsWith('sideupdate')) {
          const sid = lines[i + 1] ? lines[i + 1].trim() : '';
          const reqLine = lines[i + 2];
          if (reqLine && reqLine.startsWith('|request|')) {
            const reqStr = reqLine.slice(9).trim();
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
        const myData = sideData[sid];
        const foeData = sideData[sid === 'p1' ? 'p2' : 'p1'];
        const obs = buildObservation(currentTurn, Boolean(req.teamPreview), req, myData, foeData);

        let cmd = '';
        if (sid === 'p1') {
          // Autonomous Agent
          const choice = await w1.ask(obs);
          cmd = choice;
          if (obs.team_preview) {
            log(`  🤖 [Agent Preview Decision] ${cmd}`);
          } else {
            log(`  🤖 [Agent Action Decision] ${cmd}`);
          }
        } else {
          // Gemini (Player 2)
          if (process.env.INTERACTIVE === 'true') {
            if (obs.team_preview) {
              log(`\n================================================================================`);
              log(`>>> TEAM PREVIEW: GEMINI'S TURN <<<`);
              log(`Agent's Team: Dragapult, Greninja, Scizor`);
              log(`Gemini's Team: [1] Togekiss, [2] Volcarona, [3] Dragonite`);
              log(`Enter lead order (e.g. "team 123", "team 213", "team 312"):`);
              log(`================================================================================`);
              cmd = await askGemini();
            } else {
              log(`\n================================================================================`);
              log(`>>> GEMINI DECISION PROMPT (TURN ${currentTurn}) <<<`);
              log(`Gemini Active: ${obs.my_active ? obs.my_active.name + ' (' + obs.my_active.hp_percent + '%) ' + (obs.my_active.status ? '[' + obs.my_active.status + '] ' : '') + JSON.stringify(obs.my_active.boosts) : 'None'}`);
              log(`Agent Active : ${obs.foe ? obs.foe.name + ' (' + obs.foe.hp_percent + '%) ' + (obs.foe.status ? '[' + obs.foe.status + '] ' : '') + JSON.stringify(obs.foe.boosts) : 'None'}`);
              if (obs.force_switch) log(`[FORCED SWITCH] Active Pokemon fainted! Choose switch.`);
              log(`Legal Moves for Gemini:`);
              (obs.valid_moves || []).forEach(m => {
                log(`  [move ${m.index}] ${m.name} (${m.type}, ${m.base_power} BP, ${m.type_multiplier}x vs foe)`);
              });
              log(`Legal Switches for Gemini:`);
              (obs.valid_switches || []).forEach(s => {
                log(`  [switch ${s.index}] ${s.name} (${s.hp_percent}% HP)`);
              });
              log(`Enter your command (e.g. "move 1", "switch 2"):`);
              log(`================================================================================`);
              cmd = await askGemini();
            }
          } else {
            cmd = chooseGeminiAction(obs, currentTurn);
          }
        }

        // Validate command legality
        if (obs.team_preview) {
          if (!cmd.startsWith('team')) cmd = 'team 123';
        } else if (obs.force_switch) {
          const legalSwitches = obs.valid_switches.map(s => `switch ${s.index}`);
          if (!legalSwitches.includes(cmd)) cmd = legalSwitches[0] || 'default';
        } else {
          const legalMoves = obs.valid_moves.map(m => `move ${m.index}`);
          const legalSwitches = obs.valid_switches.map(s => `switch ${s.index}`);
          const allLegal = legalMoves.concat(legalSwitches);
          if (!allLegal.includes(cmd)) cmd = legalMoves[0] || legalSwitches[0] || 'default';
        }

        stream.write(`>${sid} ${cmd}\n`);
      }
    }
  })();

  stream.write('>start {"formatid":"gen9customgame"}\n');
  stream.write(`>player p1 {"name":"Alice","team":"${t1}"}\n`);
  stream.write(`>player p2 {"name":"Bob","team":"${t2}"}\n`);

  await battlePromise;
  w1.kill();
  stdinRl.close();
  process.exit(0);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
