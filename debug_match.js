
const Sim = require('pokemon-showdown');
const fs = require('fs');
const readline = require('readline');
const { spawn } = require('child_process');

class Worker {
  constructor(p) {
    this.proc = spawn('python3', ['runner.py', p]);
    this.rl = readline.createInterface({ input: this.proc.stdout });
    this.q = [];
    this.rl.on('line', l => { const cb = this.q.shift(); if (cb) cb(l.trim()); });
  }
  ask(obs) {
    return new Promise(res => {
      this.q.push(res);
      this.proc.stdin.write(JSON.stringify(obs) + '
');
    });
  }
  kill() { try { this.proc.kill(); } catch (e) {} }
}

async function run() {
  const t1 = fs.readFileSync('teams/ultimate_anti_meta.txt', 'utf8');
  const t2 = fs.readFileSync('teams/archetypes/rain_bulky.txt', 'utf8');
  const p1T = Sim.Teams.pack(Sim.Teams.import(t1));
  const p2T = Sim.Teams.pack(Sim.Teams.import(t2));

  const stream = new Sim.BattleStream();
  stream.write('>start {"formatid":"gen9customgame"}
');
  stream.write('>player p1 {"name":"Alice","team":"' + p1T + '"}
');
  stream.write('>player p2 {"name":"Bob","team":"' + p2T + '"}
');

  const w1 = new Worker('agents/ultimate_anti_meta.py');
  const w2 = new Worker('agents/q_learning_agent.py');

  for await (const chunk of stream) {
    const lines = chunk.split('
');
    for (const line of lines) {
      if (line.startsWith('|-status|') || line.startsWith('|-damage|') || line.startsWith('|cant|') || line.startsWith('|move|') || line.startsWith('|faint|')) {
        console.log(line);
      }
    }
  }
  w1.kill(); w2.kill();
}
run();
