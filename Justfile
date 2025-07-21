list:
    @just --list

start_conf _file args='':
    #!/usr/bin/env bash
    uv run  claude-code-proxy  --env $HOME/.config/claude-code-proxy/{{_file}} {{args}}


updatedeps:
    uv export --no-editable --no-dev --no-hashes  --no-emit-project >requirements.txt


load args='':
    #!/usr/bin/env bash
    uv run  claude-code-proxy  --conf $HOME/.config/claude-code-proxy/providers.toml {{args}}
