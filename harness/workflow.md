# Recommended Harness workflow

## Small feature

main -> implementation -> testing -> code-review -> fix -> testing

## New game

main -> game-plugin/game-server -> testing -> reviewer -> load-testing

## Protocol change

main -> networking -> testing -> security -> reviewer

## Performance issue

main -> observability -> performance -> load-testing -> reviewer

## Production incident

main -> incident-debugging -> testing -> code-review

Keep the first pass small. Ask specialist agents only for the part where their context materially improves the result.
