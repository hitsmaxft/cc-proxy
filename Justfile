list:
    @just --list



updatedeps:
    uv export --no-editable --no-dev --no-hashes  --no-emit-project >requirements.txt


up:
    docker compose -f docker.yml up
start:
    docker compose -f docker.yml up -d

down:
    docker compose -f docker.yml down

load_toml file args='':
    #!/usr/bin/env bash
    uv run  cc-proxy  --conf {{file}} {{args}}
load args='':
    #!/usr/bin/env bash
    uv run  cc-proxy  --conf $HOME/.config/claude-code-proxy/providers.toml {{args}}
