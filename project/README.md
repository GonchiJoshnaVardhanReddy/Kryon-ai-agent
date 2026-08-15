# 🐙 Kryon

> A hypothesis-driven, autonomous, multi-agent framework for safe and verifiable security research.

Kryon runs structured security engagements: passive recon, active probing, hypothesis generation, exploit testing, verification, paired blue-team artifacts, and platform-specific reports. Every action is backed by a typed `Hypothesis`, every tool output becomes a node in a knowledge graph, and every engagement is gated by an 8-layer safety model enforced at the OS layer — not in the prompt.

## Install

**Windows (PowerShell):**

```powershell
.\install.ps1
```

**Linux / macOS (WSL, Kali):**

```bash
./install.sh
```

## Usage

```bash
# Check version
kryon --version

# Verify the activity system
kryon emit-test-event

# (Coming in later files) Run an engagement
kryon hunt --target example.com

# Tail activity logs
kryon logs tail
```

## Architecture

- **8 subagents**: `recon-passive`, `recon-active`, `analysis-hypothesis`, `exploit`, `post-exploit`, `verify`, `blue-team`, `report`
- **9-state loop**: `INIT → RECON_PASSIVE → RECON_ACTIVE → HYPOTHESIZE → EXPLOIT → VERIFY → BLUE_TEAM → REPORT → HALT`
- **Typed `Hypothesis`**: every vulnerability attempt is a structured claim with attack class, precondition, test plan, expected evidence, and confidence prior
- **Knowledge graph** (KùzuDB + Cypher): the agent's working memory. Every tool output is a node.
- **LiteLLM gateway**: swap between Anthropic, OpenAI, Azure, Bedrock, Ollama, and 100+ providers via config
- **Paired offensive/defensive output**: every confirmed finding is atomically paired with a Sigma detection rule and an IR playbook
- **Real-time visibility**: every action emits a structured `Event` to the activity bus, JSONL log, color console, and per-subagent transcript

## License

MIT — see [LICENSE](LICENSE).
