# DeepSeek Harness setup for this project

This repository intentionally keeps the project rules in `AGENTS.md` and the reusable task-specific guidance in `.agents/skills/`.

Recommended starting mode:
- use the built-in `standard` agent preset
- let the project skills define the multiplayer-specific behavior
- use subagents for specialist review rather than creating many custom presets immediately

Suggested roles:
- `main`: implementation and coordination
- `reviewer`: code-review + security + architecture
- `network`: networking + protocol
- `game`: game-server + game-plugin
- `perf`: performance + load-testing
- `ops`: observability + deployment

A role is primarily a task/context choice. A DeepSeek Harness *agent preset* is a composition of tools/persona/prompt sections. Keep those separate.

For advanced custom agents, create a user preset by copying the shipped `standard` preset instead of modifying the installed preset. Current Harness documentation describes a preset as a directory containing `agent.cordis.yml` and optional `preset.yml`.
