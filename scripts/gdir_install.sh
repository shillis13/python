#!/usr/bin/env bash
set -euo pipefail

WRAPPER_BEGIN="# --- gdir wrapper (BEGIN MANAGED BLOCK) ---"
WRAPPER_END="# --- gdir wrapper (END MANAGED BLOCK) ---"

install_bash() {
  local rc_file="$HOME/.bashrc"
  local block
  block=$(cat <<'EOF'
# --- gdir wrapper (BEGIN MANAGED BLOCK) ---
gdir() {
  case "$1" in
    go|back|fwd)
      local target
      target="$(command gdir "$@")" || return $?
      [ -z "$target" ] && return 2
      cd "$target" || return $?
      eval "$(command gdir env --format sh --per-key)"
      ;;
    *)
      command gdir "$@"
      ;;
  esac
}
trap 'command gdir save >/dev/null 2>&1' EXIT
# --- gdir wrapper (END MANAGED BLOCK) ---
EOF
)
  ensure_block "$rc_file" "$block"
  install_bash_completion
  printf 'Installed gdir wrapper in %s\n' "$rc_file"
}

install_zsh() {
  local rc_file="$HOME/.zshrc"
  local block
  block=$(cat <<'EOF'
# --- gdir wrapper (BEGIN MANAGED BLOCK) ---
function gdir() {
  case "$1" in
    go|back|fwd)
      local target
      target="$(command gdir "$@")" || return $?
      [[ -z "$target" ]] && return 2
      cd "$target" || return $?
      eval "$(command gdir env --format sh --per-key)"
      ;;
    *)
      command gdir "$@"
      ;;
  esac
}
trap 'command gdir save >/dev/null 2>&1' EXIT
# --- gdir wrapper (END MANAGED BLOCK) ---
EOF
)
  ensure_block "$rc_file" "$block"
  install_zsh_completion
  printf 'Installed gdir wrapper in %s\n' "$rc_file"
}

install_fish() {
  local func_dir="$HOME/.config/fish/functions"
  local comp_dir="$HOME/.config/fish/completions"
  mkdir -p "$func_dir" "$comp_dir"
  cat >"$func_dir/gdir.fish" <<'EOF'
function gdir
  switch $argv[1]
    case go back fwd
      set target (command gdir $argv)
      or return $status
      test -z "$target"; and return 2
      cd $target; or return $status
      command gdir env --format fish --per-key | source
    case '*'
      command gdir $argv
  end
end
function __gdir_autosave --on-event fish_exit
  command gdir save >/dev/null 2>&1
end
EOF
  cat >"$comp_dir/gdir.fish" <<'EOF'
function __gdir_keywords
  command gdir list 2>/dev/null | awk 'NR>2 { print $2 }'
end
complete -c gdir -n '__fish_seen_subcommand_from go rm' -a '(__gdir_keywords)'
EOF
  printf 'Installed gdir function in %s\n' "$func_dir/gdir.fish"
}

ensure_block() {
  local file="$1"
  local block="$2"
  mkdir -p "$(dirname "$file")"
  local tmp
  tmp=$(mktemp)
  if [[ -f "$file" ]]; then
    awk -v begin="$WRAPPER_BEGIN" -v end="$WRAPPER_END" '
      $0 == begin {in_block=1; next}
      $0 == end {in_block=0; next}
      !in_block {print}
    ' "$file" >"$tmp"
  fi
  printf '\n%s\n' "$block" >>"$tmp"
  mv "$tmp" "$file"
}

install_bash_completion() {
  local completion_dir="$HOME/.local/share/bash-completion/completions"
  mkdir -p "$completion_dir"
  cat >"$completion_dir/gdir" <<'EOF'
_gdir_complete() {
  local cur prev
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  mapfile -t keys < <(command gdir list 2>/dev/null | awk 'NR>2 { print $2 }')
  COMPREPLY=( $(compgen -W "${keys[*]}" -- "$cur") )
}
complete -F _gdir_complete gdir
EOF
}

install_zsh_completion() {
  local completion_dir="$HOME/.zsh/completions"
  mkdir -p "$completion_dir"
  cat >"$completion_dir/_gdir" <<'EOF'
#compdef gdir
_arguments '*:keyword:->keywords'
_keywords() {
  command gdir list 2>/dev/null | awk 'NR>2 { print $2 }'
}
case $state in
  keywords)
    _values 'gdir keywords' $(_keywords)
  ;;
esac
EOF
  if ! grep -Fq 'fpath+=~/.zsh/completions' "$HOME/.zshrc" 2>/dev/null; then
    printf '\nfpath+=~/.zsh/completions\n' >>"$HOME/.zshrc"
  fi
}

usage() {
  cat <<'EOF'
Usage: gdir_install.sh [--shell bash|zsh|fish]
EOF
}

shell_name=${1:-}
case "$shell_name" in
  --shell)
    shift
    shell_name=${1:-}
    shift || true
    ;;
  "")
    shell_name=$(basename "${SHELL:-bash}")
    ;;
esac

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
    usage
    exit 1
    ;;
esac

command gdir save >/dev/null 2>&1 || true
printf 'gdir installation complete. Restart your shell to use gdir.\n'
