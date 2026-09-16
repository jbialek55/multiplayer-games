# Development Workflow

For a normal feature:

1. Inspect the relevant architecture and code.
2. Write a short implementation plan.
3. Implement the smallest coherent change.
4. Add/update tests.
5. Run targeted tests and static checks.
6. Run the code-review skill.
7. Fix review findings.
8. Re-run affected checks.
9. Summarize changed files, checks, and remaining risks.

For protocol changes:

1. Read `docs/protocol.md`.
2. Define the compatibility impact.
3. Update schemas/handlers.
4. Add protocol tests.
5. Test malformed/duplicate/out-of-order cases where relevant.
6. Review reconnect behavior.

For performance work:

1. Define the metric.
2. Measure a baseline.
3. Identify the bottleneck.
4. Change one thing.
5. Re-measure.
6. Keep the change only if the evidence supports it.
