#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: gdir_install.sh [--shell SHELL]

Options:
  --shell SHELL   Force installation for the given shell (bash|zsh|fish)
  -h, --help      Show this message
USAGE
}

shell_name=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --shell)
      shift
      shell_name="${1:-}"
      if [[ -z "$shell_name" ]]; then
        echo "--shell requires a value" >&2
        exit 64
      fi
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 64
      ;;
  esac
  shift
done

if [[ -z "$shell_name" ]]; then
  shell_name="${SHELL##*/}"
fi

config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/gdir"
wrapper_block='\n# --- gdir wrapper (BEGIN MANAGED BLOCK) ---\n'"gdir() {\n  case \"\$1\" in\n    go|back|fwd)\n      local target\n      target=\"\$(command gdir \"\$@\")\" || return \$?\n      [ -z \"\$target\" ] && return 2\n      cd \"\$target\" || return \$?\n      eval \"\$(command gdir env --format sh)\"\n      ;;\n    *)\n      command gdir \"\$@\"\n      ;;\n  esac\n}\ntrap 'command gdir save >/dev/null 2>&1' EXIT\n""# --- gdir wrapper (END MANAGED BLOCK) ---\n"

ensure_block() {
  local file="$1"
  local block="$2"
  mkdir -p "$(dirname "$file")"
  touch "$file"
  if grep -Fq "--- gdir wrapper (BEGIN MANAGED BLOCK) ---" "$file"; then
    return
  fi
  printf '%b\n' "$block" >> "$file"
}

install_bash() {
  ensure_block "$HOME/.bashrc" "$wrapper_block"
  mkdir -p "$config_dir/completions"
  cat > "$config_dir/completions/gdir.bash" <<'COMP'
_gdir_complete() {
  local curr prev
  COMPREPLY=()
  curr="${COMP_WORDS[COMP_CWORD]}"
  if [[ $COMP_CWORD -eq 1 ]]; then
    COMPREPLY=( $(compgen -W "list add rm clear go back fwd hist env save load import pick doctor help keywords" -- "$curr") )
    return 0
  fi
  case "${COMP_WORDS[1]}" in
    go|rm|pick)
      local keys
      keys="$(command gdir keywords 2>/dev/null)"
      COMPREPLY=( $(compgen -W "$keys" -- "$curr") )
      ;;
  esac
}
complete -F _gdir_complete gdir
COMP
  if ! grep -Fq 'gdir.bash' "$HOME/.bashrc"; then
    printf '\n[[ -f %q ]] && source %q\n' "$config_dir/completions/gdir.bash" "$config_dir/completions/gdir.bash" >> "$HOME/.bashrc"
  fi
}

install_zsh() {
  ensure_block "$HOME/.zshrc" "$wrapper_block"
  mkdir -p "$config_dir/completions"
  cat > "$config_dir/completions/_gdir" <<'COMP'
#compdef gdir
_arguments '*: :->subcmd'
case $state in
  subcmd)
    local -a commands
    commands=(list add rm clear go back fwd hist env save load import pick doctor help keywords)
    _describe 'command' commands
    ;;
  *)
    local -a keywords
    keywords=($(command gdir keywords 2>/dev/null))
    _values 'keyword' $keywords
    ;;
 esac
COMP
  if ! grep -Fq 'fpath+=${HOME}/.config/gdir/completions' "$HOME/.zshrc"; then
    printf '\nfpath+=(%q)\nautoload -Uz compinit && compinit\n' "$config_dir/completions" >> "$HOME/.zshrc"
  fi
}

install_fish() {
  mkdir -p "$HOME/.config/fish/functions" "$HOME/.config/fish/completions"
  cat > "$HOME/.config/fish/functions/gdir.fish" <<'FUNC'
function gdir
  set cmd $argv[1]
  switch $cmd
    case go back fwd
      set target (command gdir $argv)
      test $status -ne 0; and return $status
      cd $target; or return $status
      command gdir env --format fish | source
    case '*'
      command gdir $argv
  end
end
FUNC
  cat > "$HOME/.config/fish/completions/gdir.fish" <<'COMP'
complete -c gdir -n 'not __fish_seen_subcommand_from list add rm clear go back fwd hist env save load import pick doctor help keywords' -a 'list add rm clear go back fwd hist env save load import pick doctor help keywords'
complete -c gdir -n '__fish_seen_subcommand_from go rm pick' -a '(command gdir keywords 2>/dev/null)'
COMP
}

case "$shell_name" in
  bash)
    install_bash
    ;;
  zsh)
    install_zsh
    ;;
  fish)
    install_fish
    ;;
  *)
    echo "Unsupported shell: $shell_name" >&2
    exit 64
    ;;
esac

echo "gdir installed for $shell_name"
