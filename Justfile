list:
    @just --list

start_conf _file:
    #!/usr/bin/env bash
    uv run  claude-code-proxy  --env $HOME/.config/claude-code-proxy/{{_file}}


updatedeps:
    uv export --no-editable --no-dev --no-hashes  --no-emit-project >requirements.txt
