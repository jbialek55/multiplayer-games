# First-use commands

The official quick start currently uses:

    npx @deepseek-ai/dsh web

The Web UI starts on localhost by default. Then:
1. Open Settings -> Models.
2. Configure your DeepSeek API key/model.
3. Choose this repository as the workspace.
4. Start a session.
5. Ask the agent to inspect the repository and read `AGENTS.md`.

For a first task, use something like:

    Read AGENTS.md, docs/architecture.md and docs/development-workflow.md.
    Inspect the repository.
    Do not modify code yet.
    Propose the architecture and implementation plan for the next smallest milestone.

After that, let the agent implement one milestone at a time.
