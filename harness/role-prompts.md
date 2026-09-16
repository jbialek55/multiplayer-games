# Specialist role prompts

Use these as short task prompts when delegating to a specialist agent.

## reviewer

Review the proposed change. Focus on correctness, concurrency, security, protocol compatibility, tests, and architecture. Do not rewrite for style alone. Return findings by severity with file/line references and concrete fixes.

## network

Own the transport/protocol review. Check validation, message schemas, reconnects, ordering, duplicate delivery, rate limits, serialization, and separation from game logic.

## game

Own authoritative game behavior. Check state ownership, deterministic transitions, tick constraints, invalid input, disconnects, reconnects, and game-specific tests.

## perf

Measure before optimizing. Establish baseline tick duration, latency, throughput, CPU/memory, and concurrent-session behavior. Propose changes only when evidence identifies a bottleneck.

## ops

Review logs, metrics, health/readiness, shutdown, deployment, restart behavior, and production diagnostics.
