#!/usr/bin/env bash
# Midnight Signal — one-shot installer for macOS and Linux.
#   ./scripts/install.sh
# Checks Python + Ollama, builds a virtualenv, downloads the base model,
# builds the `midnight-signal` model from the Modelfile, then runs --doctor.
set -euo pipefail

BASE_MODEL="huihui_ai/qwen2.5-coder-abliterate:7b"
CUSTOM_MODEL="midnight-signal"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

org=$'\033[38;2;255;140;0m'; grn=$'\033[32m'; ylw=$'\033[33m'; red=$'\033[31m'; off=$'\033[0m'
step() { printf '\n%s▌ %s%s\n' "$org" "$*" "$off"; }
ok()   { printf '  %s✓%s %s\n' "$grn" "$off" "$*"; }
warn() { printf '  %s!%s %s\n' "$ylw" "$off" "$*"; }
die()  { printf '  %s✗ %s%s\n' "$red" "$*" "$off" >&2; exit 1; }

# ── 1. Python ────────────────────────────────────────────────────────
step "1/5  Python"
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && \
     "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PY="$cand"; break
  fi
done
[ -n "$PY" ] || die "Python 3.9 or newer not found — get it from https://www.python.org/downloads/"
ok "$("$PY" --version)"

# ── 2. Ollama ────────────────────────────────────────────────────────
step "2/5  Ollama"
if ! command -v ollama >/dev/null 2>&1; then
  warn "Ollama isn't installed."
  case "$(uname -s)" in
    Darwin)
      echo "    Install it with:  brew install ollama     (or the app from https://ollama.com/download)" ;;
    Linux)
      echo "    Official installer:  curl -fsSL https://ollama.com/install.sh | sh"
      read -r -p "    Run it now? [y/N] " answer || answer=""
      if [[ "$answer" =~ ^[Yy]$ ]]; then curl -fsSL https://ollama.com/install.sh | sh; fi ;;
  esac
  command -v ollama >/dev/null 2>&1 || die "Install Ollama, then re-run this script."
fi
ok "found $(command -v ollama)"

if ! ollama list >/dev/null 2>&1; then
  warn "Ollama server isn't running — starting it in the background."
  (nohup ollama serve >/tmp/ollama-serve.log 2>&1 &)
  for _ in $(seq 1 20); do ollama list >/dev/null 2>&1 && break; sleep 1; done
  ollama list >/dev/null 2>&1 || die "Couldn't start Ollama (see /tmp/ollama-serve.log). Run 'ollama serve' yourself, then re-run."
fi
ok "server is running"

# ── 3. Python environment ────────────────────────────────────────────
step "3/5  Python environment"
if [ ! -d .venv ]; then
  "$PY" -m venv .venv || die "Couldn't create a virtualenv (Debian/Ubuntu: sudo apt install python3-venv)."
fi
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
ok "dependencies installed in .venv"

# ── 4. Models ────────────────────────────────────────────────────────
step "4/5  Model"
if ollama list | awk -v m="$BASE_MODEL" 'NR > 1 && $1 == m { f = 1 } END { exit !f }'; then
  ok "$BASE_MODEL already downloaded"
else
  echo "    downloading $BASE_MODEL (about 4-5 GB) …"
  ollama pull "$BASE_MODEL"
  ok "downloaded $BASE_MODEL"
fi
ollama create "$CUSTOM_MODEL" -f Modelfile >/dev/null
ok "built '$CUSTOM_MODEL' from the Modelfile"

# ── 5. Health check ──────────────────────────────────────────────────
step "5/5  Health check"
python midnight_signal.py --doctor

printf '\n%s▌ Done.%s Launch it with:  %s./run.sh%s\n\n' "$org" "$off" "$grn" "$off"
