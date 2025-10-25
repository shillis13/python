#!/usr/bin/env bash
set -euo pipefail

TARGET_SHELL="${1:-}"
CONFIG_DIR="${GDIR_CONFIG:-$HOME/.config/gdir}"
WRAPPER_BEGIN="# --- gdir wrapper (BEGIN MANAGED BLOCK) ---"
WRAPPER_END="# --- gdir wrapper (END MANAGED BLOCK) ---"

usage() {
  cat <<USAGE
Usage: gdir_install.sh [shell]

Installs the gdir wrapper and completions for bash, zsh, or fish.
If no shell is provided the script detects the current shell.
USAGE
}

info() {
  printf 'gdir install: %s\n' "$1"
}

ensure_config() {
  mkdir -p "$CONFIG_DIR"
}

append_block() {
  local file="$1"
  local block="$2"
  mkdir -p "$(dirname "$file")"
  if [[ -f "$file" ]] && grep -Fq "$WRAPPER_BEGIN" "$file"; then
    info "Wrapper already installed in $file"
    return
  fi
  {
    echo "$WRAPPER_BEGIN"
    printf '%s\n' "$block"
    echo "$WRAPPER_END"
  } >>"$file"
  info "Installed wrapper in $file"
}

install_bash() {
  local rc="${HOME}/.bashrc"
  local block='gdir() {
  case "$1" in
    go|back|fwd)
      local target
      target="$(command gdir "$@")" || return $?
      [[ -z "$target" ]] && return 2
      cd "$target" || return $?
      eval "$(command gdir env --format sh)"
      ;;
    *)
      command gdir "$@"
      ;;
  esac
}
trap 'command gdir save >/dev/null 2>&1' EXIT'
  append_block "$rc" "$block"
  install_completion_bash
}

install_zsh() {
  local rc="${HOME}/.zshrc"
  local block='gdir() {
  case "$1" in
    go|back|fwd)
      local target
      target="$(command gdir "$@")" || return $?
      [[ -z "$target" ]] && return 2
      cd "$target" || return $?
      eval "$(command gdir env --format sh)"
      ;;
    *)
      command gdir "$@"
      ;;
  esac
}
trap 'command gdir save >/dev/null 2>&1' EXIT'
  append_block "$rc" "$block"
  install_completion_zsh
}

install_fish() {
  mkdir -p "$HOME/.config/fish/functions" "$HOME/.config/fish/completions"
  local fn="$HOME/.config/fish/functions/gdir.fish"
  local block='function gdir
  set cmd $argv[1]
  switch $cmd
    case go back fwd
      set target (command gdir $argv)
      or return $status
      if test -z "$target"
        return 2
      end
      cd "$target"
      command gdir env --format fish | source
    case '*'
      command gdir $argv
  end
end
function __gdir_complete
  command gdir list | awk 'NR>2 {print $2}'
end
complete -c gdir -f -a "(__gdir_complete)"'
  printf '%s\n' "$block" >"$fn"
  info "Installed fish function in $fn"
}

install_completion_bash() {
  local dir="${HOME}/.local/share/gdir"
  mkdir -p "$dir"
  local file="$dir/gdir_completion.sh"
  cat <<'COMP' >"$file"
_gdir_complete() {
  COMPREPLY=()
  local cur="${COMP_WORDS[COMP_CWORD]}"
  if [[ $COMP_CWORD -eq 1 ]]; then
    COMPREPLY=( $(compgen -W "list add rm clear go back fwd hist env save load import pick doctor help" -- "$cur") )
  elif [[ $COMP_CWORD -eq 2 && ${COMP_WORDS[1]} =~ ^(go|rm|back|fwd)$ ]]; then
    local keys=$(command gdir list | awk 'NR>2 {print $2}')
    COMPREPLY=( $(compgen -W "$keys" -- "$cur") )
  fi
}
complete -F _gdir_complete gdir
COMP
  info "Installed bash completion in $file"
}

install_completion_zsh() {
  local dir="${HOME}/.zsh/completions"
  mkdir -p "$dir"
  local file="$dir/_gdir"
  cat <<'COMP' >"$file"
#compdef gdir
local -a subcommands
subcommands=(list add rm clear go back fwd hist env save load import pick doctor help)
local -a keywords
keywords=($(command gdir list | awk 'NR>2 {print $2}'))
_arguments '1: :->cmd' '2:keyword:->keyword'
case $state in
  cmd)
    _describe -t commands 'gdir commands' subcommands ;;
  keyword)
    if [[ ${words[2]} == (go|rm|back|fwd) ]]; then
      _describe -t keywords 'gdir keywords' keywords
    fi ;;
esac
COMP
  info "Installed zsh completion in $file"
}

if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
  usage
  exit 0
fi

ensure_config

if [[ -z "$TARGET_SHELL" ]]; then
  TARGET_SHELL=$(basename "${SHELL:-}")
fi

case "$TARGET_SHELL" in
  bash)
    install_bash ;;
  zsh)
    install_zsh ;;
  fish)
    install_fish ;;
  *)
    usage
    exit 1 ;;
esac

info "Installation complete. Restart your shell to apply changes."
