list:
    @just --list

start_conf _file args='':
    #!/usr/bin/env bash
    uv run  cc-proxy  --env {{_file}} {{args}}


updatedeps:
    uv export --no-editable --no-dev --no-hashes  --no-emit-project >requirements.txt


load_toml file args='':
    #!/usr/bin/env bash
    uv run  cc-proxy  --conf {{file}} {{args}}
load args='':
    #!/usr/bin/env bash
    uv run  cc-proxy  --conf $HOME/.config/claude-code-proxy/providers.toml {{args}}
