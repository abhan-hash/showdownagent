import sys
import json
import importlib.util

def load_agent(agent_path):
    spec = importlib.util.spec_from_file_location("agent_mod", agent_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "PokemonAgent"):
        raise AttributeError(f"No PokemonAgent class found in {agent_path}")
    return mod.PokemonAgent()

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 runner.py <agent_file.py>", file=sys.stderr)
        sys.exit(1)
        
    agent = load_agent(sys.argv[1])
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            obs = json.loads(line)
            action = agent.decide(obs)
            if not isinstance(action, str):
                action = str(action)
            print(action, flush=True)
        except Exception as e:
            # Emergency fallback: never crash
            print("move 1", flush=True)

if __name__ == "__main__":
    main()
