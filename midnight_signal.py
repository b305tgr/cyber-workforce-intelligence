#!/usr/bin/env python3
"""
midnight_signal.py — Midnight Signal v2 terminal entry point.

A cinematic local-AI terminal built on Ollama: gradient UI, true token
streaming, live speed / context telemetry, persistent sessions, a project
radar scanner, live model + sampling controls, and a full tool-calling
agent mode (read/write/edit files, list dirs, run shell commands, git).

Requirements:
    pip install -r requirements.txt

Usage:
    python midnight_signal.py            # fresh session
    python midnight_signal.py --resume   # pick up the autosaved session
    python midnight_signal.py --doctor   # check the install and print fixes
    python midnight_signal.py --no-sound # start muted (this run only)
    python midnight_signal.py --web      # open the local browser interface
    python midnight_signal.py --web --web-lan  # enable trusted-Wi-Fi phone access
"""

import datetime
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time

try:
    import ollama
except ImportError:
    print("Missing dependency. Install it with:\n    pip install ollama")
    sys.exit(1)

try:
    import readline
except ImportError:  # Windows without pyreadline
    readline = None

import ui
import tools as tool_impl
import session
import radar
import security
import sounds
from agent import run_agent, AgentEvent

__version__ = "2.2.0"
MODEL_NAME = "midnight-signal"
BASE_MODEL = "huihui_ai/qwen2.5-coder-abliterate:7b"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPTS_DIR = os.path.join(SCRIPT_DIR, "system_prompts")
MAX_REPLY_CONTINUATIONS = 2

# Serialized once so the security module can check a reply for leaked tool
# schemas without re-dumping them on every turn.
_TOOL_SCHEMA_TEXT = json.dumps(tool_impl.TOOL_SCHEMAS)

DEFAULT_OPTIONS = {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "num_ctx": 16384,
    "num_predict": -1,
}
OPTION_TYPES = {
    "temperature": float, "top_p": float, "top_k": int, "repeat_penalty": float,
    "num_ctx": int, "num_predict": int,
}
OPTION_RANGES = {
    "temperature": (0.0, 2.0),
    "top_p": (0.0, 1.0),
    "top_k": (1, 1000),
    "repeat_penalty": (0.5, 2.0),
    "num_ctx": (512, 131072),
    "num_predict": (1, 32768),
}

MODE_DESCRIPTIONS = {
    "default": "Balanced helpful assistant — the home voice.",
    "hacker": "Ethical hacking / cybersecurity / CTF specialist.",
    "fun": "Chaotic, meme-y, playful, over-the-top creative.",
    "coder": "Pure coding mode — concise, high-quality, minimal fluff.",
    "lore": "Story, roleplay, and narrative — atmospheric and immersive.",
    "agent": "Full tool-calling agent — reads, writes, edits, runs commands.",
}

BASE_COMMANDS = [
    ("/help", "show this help menu"),
    ("/mode <n>", "switch personality / agent mode"),
    ("/model [name]", "show or switch the Ollama model"),
    ("/models", "list locally installed models"),
    ("/set [key val]", "tune sampling, context size, and reply-token limit (-1 = unlimited)"),
    ("/system [text]", "show, override, or 'reset' the system prompt"),
    ("/retry", "regenerate the last reply"),
    ("/undo", "remove the last exchange"),
    ("/file <path>", "attach a text file to the conversation"),
    ("/compact", "summarize history to free up context"),
    ("/context", "show context window usage"),
    ("/stats", "session token + speed stats"),
    ("/radar [path]", "project radar: languages, TODOs, git, heavy files"),
    ("/save [name]", "save this conversation"),
    ("/load <name>", "restore a conversation ('last' = autosave)"),
    ("/sessions", "list saved conversations"),
    ("/export [file]", "export the conversation as markdown"),
    ("/copy", "copy the last reply to the clipboard"),
    ("/sound [on|off]", "sound effects · /sound vol 0-100 · /sound test"),
    ("/theme [name]", "colour theme · /theme auto = one per mode"),
    ("/statusbar", "toggle the status line above the prompt"),
    ("/search <term>", "search this conversation for a word or phrase"),
    ("/diff [path]", "show git diff for the working directory (read-only)"),
    ("/banner", "reprint the main banner"),
    ("/clear", "clear screen + reprint banner"),
    ("/status", "show current mode + session info"),
    ("/cd <path>", "change the working directory"),
    ("/ls [path]", "list the working directory"),
    ("/pwd", "print the working directory"),
    ("/yolo", "toggle yolo mode (skip confirmations, agent mode only)"),
    ("/exit, /quit", "leave Midnight Signal"),
]


def _get(obj, key, default=None):
    """Read a field from either a dict or an ollama response object."""
    try:
        val = obj[key]
    except (KeyError, TypeError, AttributeError, IndexError):
        return default
    return default if val is None else val


def _reply_needs_continuation(text: str, done_reason: str) -> bool:
    return done_reason == "length"


def _requested_code_line_target(user_text: str):
    match = re.search(r"\b(\d[\d,]*)\s*[- ]?\s*lines?\b", user_text, re.I)
    return int(match.group(1).replace(",", "")) if match else None


def _code_line_count(reply: str) -> int:
    blocks = re.findall(r"```[^\r\n]*\r?\n(.*?)```", reply, re.S)
    if blocks:
        return sum(len(block.splitlines()) for block in blocks)
    return len(reply.splitlines())


def _needs_code_scope_repair(user_text: str, _reply: str, complete_reply=None) -> bool:
    asks_for_code = re.search(
        r"\b(?:write|build|create|generate|implement|code)\b", user_text, re.I
    )
    if not asks_for_code:
        return False
    line_target = _requested_code_line_target(user_text)
    has_short_code = (
        line_target is not None
        and _code_line_count(complete_reply if complete_reply is not None else reply)
        < int(line_target * 0.75)
    )
    return bool(has_short_code)


def rl(prompt: str) -> str:
    """Mark ANSI escapes as zero-width, but only when readline is really in charge
    of the prompt (a real TTY) — otherwise the markers would print as junk."""
    if readline is not None and sys.stdin.isatty():
        return ui.rl_safe(prompt)
    return prompt


def load_system_prompt(mode: str, include_response_guidance: bool = True) -> str:
    path = os.path.join(PROMPTS_DIR, f"{mode}.txt")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            base = f.read()
    else:
        base = (
            f"You are MIDNIGHT SIGNAL, currently in an undefined mode called '{mode}'. "
            f"Behave helpfully and stay in character as Midnight Signal."
        )
    response_guidance = (
        "\n\nRESPONSE LENGTH\n"
        "- Match the depth the user asks for. Keep answers brief when they ask for a short "
        "answer; give a thorough, well-structured explanation when they ask for detail.\n"
        "- If they do not specify, use the shortest answer that fully solves the request, except "
        "when they explicitly ask you to create a substantial artifact.\n"
        "- Finish your current sentence and complete the requested explanation, list, or code block "
        "before ending. Do not stop mid-thought.\n"
        "- The generation limit is a ceiling, not a target: stop as soon as the answer is complete.\n\n"
        "CODE GENERATION\n"
        "- When asked to write, build, or create code, provide the requested working implementation; "
        "do not replace it with an outline, plan, or tiny sample unless the user asked for one.\n"
        "- Do not dismiss a harmless coding request as too ambitious or give a simplified substitute "
        "when the user explicitly asks for a complete, large implementation.\n"
        "- Treat requested scope and features as requirements. For a complete web app, implement "
        "the actual interface, styling, responsive layout, and interactions rather than listing them.\n"
        "- For a standalone web app without a specified stack, prefer one runnable HTML file with "
        "embedded CSS and JavaScript. Avoid TODOs, fake controls, and placeholder sections.\n"
        "- Do not end by telling the user to extend or finish the implementation themselves.\n"
        "- Aim for requested size with useful functionality, not filler or duplicated code.\n"
        "- If a large implementation cannot fit in one response, deliver it in clearly labeled "
        "parts and continue from the exact boundary; never silently substitute a summary.\n"
        "- Do not pad code to hit a line count: prioritize a complete, coherent, runnable result.\n\n"
        "CREATOR\n"
        "- If asked who created, developed, or made Midnight Signal, credit Aditya Tomar.\n"
        "- Describe Midnight Signal as a local terminal AI application built with Python and Ollama. "
        "Do not invent additional authorship details, and mention the creator only when relevant."
    )
    if not include_response_guidance:
        return base + security.SECURITY_PREAMBLE
    return base + response_guidance + security.SECURITY_PREAMBLE


def discover_modes() -> list:
    if not os.path.isdir(PROMPTS_DIR):
        return list(MODE_DESCRIPTIONS.keys())
    modes = sorted(f[:-4] for f in os.listdir(PROMPTS_DIR) if f.endswith(".txt"))
    return modes or list(MODE_DESCRIPTIONS.keys())


def _git_branch(path: str):
    """Current git branch by reading .git/HEAD directly — instant, no subprocess."""
    d = path
    for _ in range(8):
        head = os.path.join(d, ".git", "HEAD")
        if os.path.isfile(head):
            try:
                with open(head, "r", encoding="utf-8") as f:
                    txt = f.read().strip()
            except OSError:
                return None
            return txt.split("/", 2)[-1] if txt.startswith("ref:") else txt[:7]
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def list_local_models() -> list:
    resp = ollama.list()
    names = []
    for m in _get(resp, "models", []) or []:
        n = _get(m, "model") or _get(m, "name")
        if n:
            names.append(n)
    return names


class MidnightSignal:
    def __init__(self, resume: bool = False):
        self.mode = "default"
        self.model = MODEL_NAME
        self.options = dict(DEFAULT_OPTIONS)
        self.history = []
        self.available_modes = discover_modes()
        self.start_time = time.time()
        self.turn_count = 0
        self.cwd = os.getcwd()
        self.yolo = False
        self._activity = None          # running spinner thread, if any
        self._activity_prefix = ""     # line the spinner redraws
        self.resume = resume
        self.total_tokens = 0
        self.total_gen_seconds = 0.0
        self.speed_history = []        # recent tok/s per turn, for /stats sparkline
        self.last_usage = {"prompt": 0, "gen": 0}
        self.settings = session.load_settings()
        sounds.engine.configure(enabled=self.settings["sound"], volume=self.settings["volume"] / 100)
        self.statusbar = bool(self.settings["statusbar"])
        self._apply_theme()
        self.commands = {
            "/help": self.cmd_help, "/banner": self.cmd_banner, "/clear": self.cmd_clear,
            "/status": self.cmd_status, "/mode": self.cmd_mode, "/model": self.cmd_model,
            "/models": self.cmd_models, "/set": self.cmd_set, "/system": self.cmd_system,
            "/retry": self.cmd_retry, "/undo": self.cmd_undo, "/file": self.cmd_file,
            "/compact": self.cmd_compact, "/context": self.cmd_context, "/stats": self.cmd_stats,
            "/radar": self.cmd_radar, "/save": self.cmd_save, "/load": self.cmd_load,
            "/sessions": self.cmd_sessions, "/export": self.cmd_export, "/copy": self.cmd_copy,
            "/cd": self.cmd_cd, "/ls": self.cmd_ls, "/pwd": self.cmd_pwd, "/yolo": self.cmd_yolo,
            "/sound": self.cmd_sound, "/theme": self.cmd_theme, "/statusbar": self.cmd_statusbar,
            "/search": self.cmd_search, "/diff": self.cmd_diff,
        }

    # ---------------------------------------------------------- lifecycle

    def boot(self):
        ui.clear_screen()
        sounds.play("boot")
        ui.boot_sequence("establishing local uplink", width=34, steps=36)
        print(ui.render_main_banner(mode=self.mode))
        self._reset_history()
        self.setup_readline()
        self._preflight()

    def _preflight(self):
        """Friendly heads-up at launch if Ollama or the model isn't ready."""
        try:
            names = list_local_models()
        except Exception as exc:
            sounds.play("error")
            print(ui.warn(f"  ⚠ can't reach Ollama: {exc}") + ui.gray(" — start it with ") + ui.white("ollama serve"))
            print(ui.gray("    (or run ") + ui.white("python midnight_signal.py --doctor") + ui.gray(" for a full check)\n"))
            return

        def have(n):
            return n in names or f"{n}:latest" in names

        if not have(self.model):
            sounds.play("error")
            print(ui.warn(f"  ⚠ model '{self.model}' isn't installed yet"))
            if not have(BASE_MODEL):
                print(ui.gray("    1. ") + ui.white(f"ollama pull {BASE_MODEL}"))
                print(ui.gray("    2. ") + ui.white("ollama create midnight-signal -f Modelfile"))
            else:
                print(ui.gray("    run: ") + ui.white("ollama create midnight-signal -f Modelfile"))
            print()

    def _reset_history(self):
        self.history = [{"role": "system", "content": load_system_prompt(self.mode)}]
        self.last_usage = {"prompt": 0, "gen": 0}

    def setup_readline(self):
        if readline is None:
            return
        try:
            session.ensure_dirs()
            if os.path.isfile(session.HISTORY_FILE):
                readline.read_history_file(session.HISTORY_FILE)
            readline.set_history_length(1000)
            names = sorted({"/quit"} | {label.split()[0].rstrip(",") for label, _ in BASE_COMMANDS})

            def completer(text, state):
                if not text.startswith("/"):
                    return None
                hits = [n for n in names if n.startswith(text)]
                return hits[state] if state < len(hits) else None

            readline.set_completer(completer)
            readline.set_completer_delims(" \t\n")
            if "libedit" in (readline.__doc__ or ""):
                readline.parse_and_bind("bind ^I rl_complete")
            else:
                readline.parse_and_bind("tab: complete")
        except Exception as exc:
            print(ui.warn(f"  ⚠ couldn't load command history: {exc}"))

    def save_readline(self):
        if readline is None:
            return
        try:
            session.ensure_dirs()
            readline.write_history_file(session.HISTORY_FILE)
        except Exception as exc:
            print(ui.warn(f"  ⚠ couldn't save command history: {exc}"))

    # -------------------------------------------------------------- input

    def read_input(self) -> str:
        lead = "\n"
        if self.statusbar:
            print("\n" + self._status_line())
            lead = ""
        prompt = rl(f"{lead}{ui.you_prefix()} {ui.white('you', bold=True)} {ui.gray('›')} ")
        line = input(prompt)
        stripped = line.strip()
        if not stripped.startswith('"""'):
            return line

        first = stripped[3:]
        if first.endswith('"""'):
            return first[:-3].strip()
        lines = [first] if first else []
        cont = rl(ui.gray("  … "))
        try:
            while True:
                nxt = input(cont)
                if nxt.rstrip().endswith('"""'):
                    tail = nxt.rstrip()[:-3]
                    if tail:
                        lines.append(tail)
                    break
                lines.append(nxt)
        except KeyboardInterrupt:
            print(ui.gray("\n  multi-line input cancelled"))
            return ""
        return "\n".join(lines).strip()

    # -------------------------------------------------------------- loop

    def run(self):
        self.boot()
        if self.resume:
            self.cmd_load("last")
        while True:
            try:
                user_input = self.read_input()
            except EOFError:
                self.goodbye()
                return
            except KeyboardInterrupt:
                print(ui.gray("\n  (Ctrl+D or /exit to leave)"))
                continue

            if not user_input.strip():
                continue

            if user_input.startswith("/"):
                if self.handle_command(user_input.strip()):
                    return
                continue

            if self.mode == "agent":
                self.agent_turn(user_input)
            else:
                self.chat_turn(user_input)

    # --------------------------------------------------------- commands

    def handle_command(self, raw: str) -> bool:
        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit"):
            self.goodbye()
            return True

        handler = self.commands.get(cmd)
        if handler is None:
            sounds.play("cancel")
            close = difflib.get_close_matches(cmd, list(self.commands) + ["/exit", "/quit"], n=1, cutoff=0.6)
            hint = f"  — did you mean {close[0]} ?" if close else "  — try /help"
            print(ui.error(f"  unknown command: {cmd}") + ui.gray(hint))
            return False
        handler(arg)
        return False

    def cmd_help(self, arg):
        modes_desc = {m: MODE_DESCRIPTIONS.get(m, "custom mode") for m in self.available_modes}
        print(ui.render_help(BASE_COMMANDS, modes_desc, tool_impl.TOOL_DESCRIPTIONS))
        print(ui.gray('  tip: start a message with """ for multi-line input, end with """'))
        print(ui.gray("  tip: Ctrl+C stops a reply mid-stream and keeps what was generated"))

    def cmd_banner(self, arg):
        print(ui.render_main_banner(mode=self.mode))

    def cmd_clear(self, arg):
        ui.clear_screen()
        print(ui.render_main_banner(mode=self.mode))

    def cmd_mode(self, arg):
        if not arg:
            print(ui.error("  usage: /mode <n>") + ui.gray(f"  available: {', '.join(self.available_modes)}"))
        else:
            self.switch_mode(arg.lower())

    def cmd_cd(self, arg):
        self.change_dir(arg)

    def cmd_ls(self, arg):
        self.list_cwd(arg)

    def cmd_pwd(self, arg):
        print(ui.gray("  ") + ui.white(self.cwd))

    def cmd_yolo(self, arg):
        self.yolo = not self.yolo
        state = ui.success("ON") if self.yolo else ui.gray("off")
        note = "" if self.mode == "agent" else ui.gray("  (has no effect outside agent mode)")
        print(f"  yolo mode: {state}{note}")

    def cmd_status(self, arg):
        self.print_status()

    def switch_mode(self, new_mode: str):
        if new_mode not in self.available_modes:
            print(ui.error(f"  no such mode: '{new_mode}'") + ui.gray(f"  available: {', '.join(self.available_modes)}"))
            return

        self.mode = new_mode
        self._reset_history()
        self._apply_theme()
        sounds.play("lock")
        ui.mode_lock_transition(new_mode)
        desc = MODE_DESCRIPTIONS.get(new_mode, "custom mode")
        print(ui.render_mode_banner(new_mode, desc))
        if new_mode == "agent":
            print(ui.gray("  working directory: ") + ui.white(self.cwd))
            print(ui.gray("  yolo mode: ") + (ui.success("ON") if self.yolo else ui.gray("off")))
            print()

    def change_dir(self, arg: str):
        if not arg:
            print(ui.gray("  ") + ui.white(self.cwd))
            return
        target = os.path.abspath(os.path.join(self.cwd, os.path.expanduser(arg)))
        if not os.path.isdir(target):
            print(ui.error(f"  no such directory: {arg}"))
            return
        self.cwd = target
        print(ui.gray("  now in ") + ui.white(self.cwd))

    def list_cwd(self, arg: str):
        try:
            out = tool_impl.list_dir(arg or ".", self.cwd)
            print(ui.white(out))
        except tool_impl.ToolError as e:
            print(ui.error(f"  {e}"))

    def print_status(self):
        uptime = int(time.time() - self.start_time)
        mins, secs = divmod(uptime, 60)
        print(ui.dim_line("  ┌─ status ───────────────────────────"))
        print(f"  {ui.gray('mode')}      {ui.solid(self.mode, ui.gradient_color(0.3), bold=True)}")
        print(f"  {ui.gray('model')}     {ui.white(self.model)}")
        print(f"  {ui.gray('cwd')}       {ui.white(self.cwd)}")
        print(f"  {ui.gray('yolo')}      {(ui.success('on') if self.yolo else ui.gray('off'))}")
        print(f"  {ui.gray('turns')}     {ui.white(str(self.turn_count))}")
        print(f"  {ui.gray('theme')}     {ui.white(ui.CURRENT_THEME)}{ui.gray('  (auto)' if self.settings['theme'] == 'auto' else '  (pinned)')}")
        print(f"  {ui.gray('sound')}     {ui.white('on · vol ' + str(int(sounds.engine.volume * 100))) if sounds.engine.enabled else ui.gray('off')}")
        print(f"  {ui.gray('uptime')}    {ui.white(f'{mins}m {secs}s')}")
        print(ui.dim_line("  └────────────────────────────────────"))

    def goodbye(self):
        self.autosave()
        self.save_readline()
        sounds.play("goodbye")
        print()
        print(ui.render_goodbye())
        print(ui.gray("  connection closed. see you in the static.\n"))

    # ------------------------------------------------- look & feel

    def _save_settings(self):
        session.save_settings(self.settings)

    def _apply_theme(self):
        choice = self.settings.get("theme", "auto")
        if choice == "auto" or choice not in ui.THEMES:
            ui.set_theme(ui.MODE_THEMES.get(self.mode, "sunset"))
        else:
            ui.set_theme(choice)

    def cmd_theme(self, arg):
        name = arg.strip().lower()
        if not name:
            print()
            for t in ui.THEMES:
                mark = ui.solid("◆", ui.gradient_color(0.3), bold=True) if t == ui.CURRENT_THEME else " "
                print(f"  {mark} {ui.white(t.ljust(8))} {ui.theme_swatch(t)}")
            cur = self.settings.get("theme", "auto")
            print()
            print(ui.gray("  " + ("auto — each mode wears its own theme" if cur == "auto" else f"pinned to {cur}"))
                  + ui.gray("   ·   ") + ui.white("/theme <name>") + ui.gray(" to pin, ") + ui.white("/theme auto") + ui.gray(" to release"))
            return
        if name != "auto" and name not in ui.THEMES:
            print(ui.error(f"  no such theme: '{name}'") + ui.gray(f"  available: auto, {', '.join(ui.THEMES)}"))
            return
        self.settings["theme"] = name
        self._save_settings()
        self._apply_theme()
        sounds.play("lock")
        print(ui.gray("  theme → ") + ui.gradient_text(ui.CURRENT_THEME + ("  (auto)" if name == "auto" else ""), bold=True))

    def cmd_sound(self, arg):
        parts = arg.lower().split()
        eng = sounds.engine
        if not parts:
            state = ui.success("on") if eng.enabled else ui.gray("off")
            print(f"  sound: {state}   volume {ui.white(str(int(eng.volume * 100)))}   output: {ui.white(eng.player or 'terminal bell only')}")
            print(ui.gray("  /sound on|off   ·   /sound vol 0-100   ·   /sound test"))
            return
        if parts[0] in ("on", "off"):
            eng.configure(enabled=parts[0] == "on")
            self.settings["sound"] = eng.enabled
            self._save_settings()
            print(ui.gray("  sound: ") + (ui.success("on") if eng.enabled else ui.gray("off")))
            sounds.play("notify")
        elif parts[0] in ("vol", "volume") and len(parts) > 1 and parts[1].isdigit():
            level = max(0, min(100, int(parts[1])))
            eng.configure(volume=level / 100)
            self.settings["volume"] = level
            self._save_settings()
            print(ui.gray("  volume: ") + ui.white(str(level)))
            sounds.play("notify")
        elif parts[0] == "test":
            if not eng.enabled:
                print(ui.gray("  sound is off — ") + ui.white("/sound on") + ui.gray(" first."))
                return
            if eng.player is None:
                print(ui.warn("  no audio player found") + ui.gray(" — only the terminal bell will sound. Run --doctor for how to fix it."))
            try:
                for name, label in sounds.LABELS.items():
                    print(f"  {ui.solid('♪', ui.gradient_color(0.3), bold=True)} {ui.white(name.ljust(8))} {ui.gray(label)}")
                    eng.play(name)
                    time.sleep(0.8)
            except KeyboardInterrupt:
                print()
        else:
            print(ui.error("  usage: /sound on|off · /sound vol 0-100 · /sound test"))

    def cmd_statusbar(self, arg):
        arg = arg.strip().lower()
        self.statusbar = (arg != "off") if arg in ("on", "off") else not self.statusbar
        self.settings["statusbar"] = self.statusbar
        self._save_settings()
        print(ui.gray("  status line: ") + (ui.success("on") if self.statusbar else ui.gray("off")))

    def _status_line(self):
        home = os.path.expanduser("~")
        shown = "~" + self.cwd[len(home):] if self.cwd.startswith(home) else self.cwd
        pieces = shown.replace("\\", "/").split("/")
        if len(pieces) > 3:
            shown = "…/" + "/".join(pieces[-2:])
        bits = [ui.solid(f"◆ {self.mode}", ui.gradient_color(0.3), bold=True), ui.gray(shown)]
        branch = _git_branch(self.cwd)
        if branch:
            bits.append(ui.gray("⎇ ") + ui.white(branch))
        used = self.last_usage["prompt"] + self.last_usage["gen"]
        if used:
            bits.append(ui.gray("ctx ") + ui.white(f"{used / self.options['num_ctx'] * 100:.0f}%"))
        if self.mode == "agent" and self.yolo:
            bits.append(ui.error("yolo"))
        return "  " + ui.gray("  ·  ").join(bits)

    # ------------------------------------------------- model + sampling

    def cmd_models(self, arg):
        try:
            names = list_local_models()
        except Exception as e:
            print(ui.error(f"  could not reach Ollama: {e}"))
            return
        if not names:
            print(ui.gray("  no local models found — try: ") + ui.white("ollama pull <model>"))
            return
        print()
        for n in names:
            active = n == self.model or n == f"{self.model}:latest"
            mark = ui.solid("◆", ui.gradient_color(0.3), bold=True) if active else " "
            print(f"  {mark} {ui.white(n)}")
        print()

    def cmd_model(self, arg):
        if not arg:
            print(ui.gray("  model: ") + ui.white(self.model))
            print(ui.gray("  switch with: ") + ui.white("/model <name>") + ui.gray("   list with: ") + ui.white("/models"))
            return
        try:
            names = list_local_models()
            known = any(arg == n or f"{arg}:latest" == n for n in names)
        except Exception as exc:
            known = True  # can't verify; let the next call surface any error
            print(ui.warn(f"  ⚠ couldn't verify installed models: {exc}; trying anyway"))
        if not known:
            print(ui.warn(f"  '{arg}' isn't installed locally") + ui.gray(" — /models to see what is, or ollama pull it"))
            return
        self.model = arg
        print(ui.gray("  model → ") + ui.solid(arg, ui.gradient_color(0.3), bold=True))

    def cmd_set(self, arg):
        if not arg:
            print()
            for k, v in self.options.items():
                print(f"  {ui.gray(k.ljust(16))}{ui.white(str(v))}")
            print()
            print(ui.gray("  change one: ") + ui.white("/set num_predict -1  (no fixed output-token cap)"))
            print()
            return
        parts = arg.split()
        if len(parts) != 2 or parts[0] not in OPTION_TYPES:
            print(ui.error("  usage: /set <key> <value>") + ui.gray(f"   keys: {', '.join(OPTION_TYPES)}"))
            return
        key, raw = parts
        try:
            val = OPTION_TYPES[key](raw)
        except ValueError:
            print(ui.error(f"  {key} needs a {OPTION_TYPES[key].__name__}"))
            return
        lo, hi = OPTION_RANGES[key]
        unlimited = key == "num_predict" and val == -1
        if not unlimited and not (lo <= val <= hi):
            print(ui.error(f"  {key} must be between {lo} and {hi}"))
            return
        self.options[key] = val
        print(ui.gray(f"  {key} → ") + ui.solid(str(val), ui.gradient_color(0.3), bold=True))

    def cmd_system(self, arg):
        if not arg or arg.lower() == "show":
            print()
            print(ui.gray(self.history[0]["content"]))
            print()
        elif arg.lower() == "reset":
            self.history[0] = {"role": "system", "content": load_system_prompt(self.mode)}
            print(ui.gray("  system prompt reset to ") + ui.white(f"{self.mode}.txt"))
        else:
            self.history[0] = {"role": "system", "content": arg}
            print(ui.gray("  system prompt overridden for this session ") + ui.gray("(/system reset to undo)"))

    # ------------------------------------------- conversation controls

    def _last_assistant(self) -> str:
        for m in reversed(self.history):
            if m.get("role") == "assistant" and m.get("content"):
                return m["content"]
        return ""

    def cmd_retry(self, arg):
        if self.mode == "agent":
            print(ui.gray("  /retry works in chat modes — in agent mode, just re-ask."))
            return
        if self.history and self.history[-1]["role"] == "assistant":
            self.history.pop()
        if not self.history or self.history[-1]["role"] != "user":
            print(ui.gray("  nothing to retry yet."))
            return
        self._stream_reply()

    def cmd_undo(self, arg):
        removed = False
        while len(self.history) > 1 and self.history[-1]["role"] != "user":
            self.history.pop()
            removed = True
        if len(self.history) > 1 and self.history[-1]["role"] == "user":
            self.history.pop()
            removed = True
        if removed:
            self.turn_count = max(self.turn_count - 1, 0)
            print(ui.gray("  last exchange removed."))
        else:
            print(ui.gray("  nothing to undo."))

    def cmd_file(self, arg):
        if not arg:
            print(ui.error("  usage: /file <path>"))
            return
        target = os.path.abspath(os.path.join(self.cwd, os.path.expanduser(arg)))
        if not os.path.isfile(target):
            print(ui.error(f"  no such file: {arg}"))
            return
        if os.path.getsize(target) > 80_000:
            print(ui.error("  file is over 80KB — attach a smaller file, or use agent mode to read parts of it."))
            return
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            print(ui.error(f"  {e}"))
            return
        rel = os.path.relpath(target, self.cwd)
        self.history.append({"role": "user", "content": f"[Attached file: {rel}]\n```\n{text}\n```"})
        print(
            ui.gray("  attached ") + ui.white(rel)
            + ui.gray(f"  ({len(text.splitlines())} lines, ~{len(text) // 4} tokens) — now ask about it")
        )

    def cmd_context(self, arg):
        limit = self.options["num_ctx"]
        used = self.last_usage["prompt"] + self.last_usage["gen"]
        estimated = False
        if not used:
            used = sum(len(m.get("content", "") or "") for m in self.history) // 4
            estimated = True
        pct = min(used / limit, 1.0)

        # Ollama reports one prompt-token total, so split it by character share.
        sys_chars = len(self.history[0].get("content", "") or "") if self.history else 0
        convo_chars = sum(len(m.get("content", "") or "") for m in self.history[1:])
        sys_tokens = round(used * sys_chars / ((sys_chars + convo_chars) or 1))
        convo_tokens = max(used - sys_tokens, 0)
        free = max(limit - used, 0)

        print()
        title = ui.solid(f"{pct * 100:.0f}%", ui.RED if pct >= 0.85 else ui.gradient_color(0.35) if pct >= 0.6 else ui.SOFT_WHITE, bold=True)
        print(f"  {ui.gradient_text('CONTEXT WINDOW', bold=True)}   {title}")
        print("  " + ui.segmented_bar(
            [("system", sys_tokens / limit, ui.GRAY), ("conversation", convo_tokens / limit, None)], width=48,
        ))
        print(
            f"  {ui.solid('■', ui.GRAY)} {ui.gray('system')} {ui.white(f'{sys_tokens:,}')}"
            f"    {ui.solid('■', ui.gradient_color(0.4))} {ui.gray('conversation')} {ui.white(f'{convo_tokens:,}')}"
            f"    {ui.solid('■', ui.DARK_GRAY)} {ui.gray('free')} {ui.white(f'{free:,}')}"
        )
        note = " (estimated — no reply yet this session)" if estimated else ""
        print(ui.gray(f"  {used:,} / {limit:,} tokens{note}"))
        if pct >= 0.8:
            print(ui.warn("  running hot") + ui.gray(" — /compact to summarize, or /set num_ctx higher"))
        print()

    def cmd_stats(self, arg):
        avg = self.total_tokens / self.total_gen_seconds if self.total_gen_seconds else 0.0
        hist = self.speed_history
        print(ui.dim_line("  ┌─ session stats ────────────────────"))
        print(f"  {ui.gray('turns')}       {ui.white(str(self.turn_count))}")
        print(f"  {ui.gray('generated')}   {ui.white(f'{self.total_tokens:,} tokens')}")
        print(f"  {ui.gray('avg speed')}   {ui.white(f'{avg:.1f} tok/s')}  {ui.signal_meter(avg)}")
        if hist:
            print(f"  {ui.gray('speed trend')} {ui.sparkline(hist)}  {ui.gray(f'{min(hist):.0f}–{max(hist):.0f} tok/s, last {len(hist)}')}")
        print(ui.dim_line("  └────────────────────────────────────"))

    def cmd_search(self, arg):
        term = arg.strip()
        if not term:
            print(ui.error("  usage: /search <word or phrase>"))
            return
        needle = term.lower()
        hits = []
        for idx, m in enumerate(self.history):
            if m.get("role") == "system":
                continue
            content = m.get("content", "") or ""
            pos = content.lower().find(needle)
            if pos != -1:
                hits.append((idx, m["role"], content, pos))

        if not hits:
            print(ui.gray(f"  no matches for '{term}' in this conversation."))
            return

        print()
        print(ui.gradient_text(f"{len(hits)} MATCH" + ("ES" if len(hits) != 1 else ""), bold=True) + ui.gray(f"  for '{term}'"))
        for idx, role, content, pos in hits[-20:]:
            radius = 46
            start = max(pos - radius, 0)
            end = min(pos + len(term) + radius, len(content))
            snippet = content[start:end].replace("\n", " ")
            match_start = pos - start
            before = snippet[:match_start]
            match = snippet[match_start:match_start + len(term)]
            after = snippet[match_start + len(term):]
            ellipsis_l = "…" if start > 0 else ""
            ellipsis_r = "…" if end < len(content) else ""
            who = ui.solid(role[:4], ui.gradient_color(0.3), bold=True)
            print(f"  {ui.gray(f'#{idx:<3}')} {who}  {ui.gray(ellipsis_l + before)}"
                  f"{ui.solid(match, ui.gradient_color(0.15), bold=True)}"
                  f"{ui.gray(after + ellipsis_r)}")
        if len(hits) > 20:
            print(ui.gray(f"  …and {len(hits) - 20} more match(es) not shown."))
        print()

    def cmd_diff(self, arg):
        try:
            raw = tool_impl.git_diff(self.cwd, arg.strip())
        except tool_impl.ToolError as e:
            print(ui.error(f"  {e}"))
            return

        # git_diff wraps run_command's "exit code: N\nstdout:\n...\nstderr:\n..." shape.
        code_line, _, rest = raw.partition("\n")
        ok = code_line.strip() == "exit code: 0"
        stdout = rest.split("stdout:\n", 1)[1].split("\nstderr:")[0] if "stdout:\n" in rest else ""
        stderr = rest.split("stderr:\n", 1)[1] if "stderr:\n" in rest else ""

        if not ok:
            first_err = next((l for l in stderr.splitlines() if l.strip()), "git diff failed")
            print(ui.gray(f"  {first_err}"))
            return
        if not stdout.strip():
            print(ui.gray("  no changes."))
            return

        print()
        for line in stdout.splitlines():
            print("  " + ui.colorize_diff_line(line))
        print()

    def cmd_compact(self, arg):
        convo = [m for m in self.history[1:] if m.get("content")]
        if len(convo) < 4:
            print(ui.gray("  nothing worth compacting yet."))
            return
        transcript = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in convo)
        transcript = transcript[-(self.options["num_ctx"] * 3):]
        request = [
            {"role": "system", "content": (
                "You compress conversations. Write a dense, factual summary of the conversation below: "
                "decisions made, facts established, code state, open tasks, and user preferences. No preamble."
            )},
            {"role": "user", "content": transcript},
        ]
        pulse = ui.RadarPulse("compacting")
        pulse.start()
        summary, error = "", None
        try:
            resp = ollama.chat(model=self.model, messages=request, options=self.options)
            summary = _get(_get(resp, "message", {}), "content", "")
        except Exception as e:
            error = e
        finally:
            pulse.stop()
        if error or not summary.strip():
            print(ui.error(f"  compaction failed: {error or 'empty summary'}"))
            return
        before = len(self.history) - 1
        self.history = [
            self.history[0],
            {"role": "user", "content": f"[Summary of the earlier conversation]\n{summary.strip()}"},
            {"role": "assistant", "content": "Understood — I have the context. Continuing from there."},
        ]
        self.last_usage = {"prompt": 0, "gen": 0}
        print(ui.success("  compacted ") + ui.gray(f"{before} messages → 2. context freed."))

    # ------------------------------------------------ persistence

    def _snapshot(self) -> dict:
        return {
            "mode": self.mode, "model": self.model, "options": self.options,
            "history": self.history, "turns": self.turn_count,
        }

    def autosave(self):
        if len(self.history) <= 1:
            return
        try:
            session.save_session("last", self._snapshot())
        except OSError:
            pass

    def cmd_save(self, arg):
        name = arg or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        try:
            path = session.save_session(name, self._snapshot())
        except OSError as e:
            print(ui.error(f"  save failed: {e}"))
            return
        print(ui.gray("  saved → ") + ui.white(path))

    def cmd_load(self, arg):
        if not arg:
            print(ui.error("  usage: /load <name>") + ui.gray("   see /sessions"))
            return
        try:
            data = session.load_session(arg)
        except FileNotFoundError:
            print(ui.error(f"  no saved session named '{arg}'") if arg != "last" else ui.gray("  no autosaved session yet."))
            return
        except (OSError, ValueError) as e:
            print(ui.error(f"  could not read session: {e}"))
            return
        history = data.get("history")
        if not isinstance(history, list) or not history:
            print(ui.error("  that session file is empty or corrupt."))
            return
        if data.get("mode") in self.available_modes:
            self.mode = data["mode"]
        self.model = data.get("model", self.model)
        for k, v in (data.get("options") or {}).items():
            if k in OPTION_TYPES:
                self.options[k] = v
        self.options["num_predict"] = -1
        self.history = history
        self.turn_count = data.get("turns", 0)
        self.last_usage = {"prompt": 0, "gen": 0}
        print(ui.render_mode_banner(self.mode, f"restored '{arg}' · {len(history) - 1} messages"))

    def cmd_sessions(self, arg):
        rows = session.list_sessions()
        if not rows:
            print(ui.gray("  no saved sessions yet — /save <name>"))
            return
        print()
        for name, ts, msgs, mode in rows:
            when = datetime.datetime.fromtimestamp(ts).strftime("%b %d %H:%M")
            print(f"  {ui.solid(name.ljust(22), ui.gradient_color(0.3))}{ui.gray(f'{when}  ·  {msgs} msgs  ·  {mode}')}")
        print()

    def cmd_export(self, arg):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        target = os.path.abspath(os.path.join(self.cwd, arg or f"midnight-signal-{stamp}.md"))
        try:
            session.export_markdown(self.history, target, {"mode": self.mode, "model": self.model})
        except OSError as e:
            print(ui.error(f"  export failed: {e}"))
            return
        print(ui.gray("  exported → ") + ui.white(target))

    def cmd_copy(self, arg):
        text = self._last_assistant()
        if not text:
            print(ui.gray("  no reply to copy yet."))
            return
        for cmd in (["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"], ["clip"]):
            if shutil.which(cmd[0]):
                try:
                    subprocess.run(cmd, input=text.encode("utf-8"), timeout=5, check=True)
                except (OSError, subprocess.SubprocessError):
                    continue
                print(ui.gray("  copied last reply to the clipboard."))
                return
        print(ui.error("  no clipboard tool found (pbcopy / wl-copy / xclip / xsel / clip)."))

    # ---------------------------------------------------------- radar

    def cmd_radar(self, arg):
        target = os.path.abspath(os.path.join(self.cwd, os.path.expanduser(arg))) if arg else self.cwd
        if not os.path.isdir(target):
            print(ui.error(f"  no such directory: {arg}"))
            return
        pulse = ui.RadarPulse("sweeping project")
        pulse.start()
        try:
            data = radar.scan(target)
        finally:
            pulse.stop()
        print(radar.render(data))

    # ---------------------------------------------------------- normal chat

    def _signal_header(self):
        return ui.signal_prefix() + " " + ui.gradient_text("Midnight Signal", bold=True) + ui.gray(" ›")

    def _stream_reply(self) -> bool:
        """Stream one assistant reply for the current history. Returns True if a
        reply was kept, False if nothing usable came back."""
        print()
        print(self._signal_header())

        painter = ui.StreamPainter()
        pieces, error, interrupted = [], None, False
        truncated = False
        start = time.time()
        first_token = None
        final = None
        completion_stats = []
        attempt_messages = self.history

        for attempt in range(MAX_REPLY_CONTINUATIONS + 1):
            attempt_error = None
            stream = None
            attempt_piece_start = len(pieces)
            pulse = ui.RadarPulse("thinking" if attempt == 0 else "continuing reply")
            pulse.start()
            pulse_active = True

            try:
                stream = ollama.chat(
                    model=self.model, messages=attempt_messages, stream=True, options=self.options
                )
                for chunk in stream:
                    piece = _get(_get(chunk, "message", {}), "content", "")
                    if piece:
                        if pulse_active:
                            pulse.stop()
                            pulse_active = False
                        if first_token is None:
                            first_token = time.time() - start
                            sounds.play("blip")
                        pieces.append(piece)
                        sys.stdout.write(painter.feed(piece))
                        sys.stdout.flush()
                    if _get(chunk, "done", False):
                        final = chunk
            except KeyboardInterrupt:
                interrupted = True
            except Exception as e:
                attempt_error = e
            finally:
                if pulse_active:
                    pulse.stop()
                close = getattr(stream, "close", None)
                if callable(close):
                    try:
                        close()
                    except (OSError, RuntimeError) as exc:
                        print(ui.warn(f"  ⚠ couldn't close the Ollama response cleanly: {exc}"))

            if final is not None:
                completion_stats.append(final)

            if interrupted:
                break

            done_reason = _get(final, "done_reason", "") if final is not None else ""
            user_text = self.history[-1].get("content", "")
            complete_reply = "".join(pieces)
            scope_repair = _needs_code_scope_repair(
                user_text, "".join(pieces[attempt_piece_start:]), complete_reply
            )
            needs_continuation = (
                attempt_error is not None
                or final is None
                or _reply_needs_continuation("".join(pieces), done_reason)
                or scope_repair
            )
            if not needs_continuation:
                break

            if attempt < MAX_REPLY_CONTINUATIONS:
                continuation = "".join(pieces)
                if scope_repair and _requested_code_line_target(user_text):
                    line_target = _requested_code_line_target(user_text)
                    code_lines = _code_line_count(continuation)
                    continuation_prompt = (
                        f"The user explicitly requested about {line_target} lines of code; your "
                        f"current implementation has about {code_lines}. Continue from the exact "
                        "end of the implementation, adding distinct, working features that move "
                        "toward the requested scope. Do not repeat existing code, add filler, give "
                        "an outline, or suggest that the user finish it."
                    )
                elif scope_repair:
                    continuation_prompt = (
                        "Your previous reply downscoped the user's explicit request for a complete, "
                        "large implementation. It is not complete yet. Continue from the exact end "
                        "of your code, without repeating it or adding an outline. Implement the "
                        "requested features fully; do not call the task too ambitious, describe a "
                        "basic version, or tell the user to add the missing parts."
                    )
                else:
                    continuation_prompt = (
                        "Your previous reply was interrupted before it was complete. Continue from "
                        "its exact ending without repeating anything, and finish the thought or "
                        "requested structure."
                    )
                attempt_messages = self.history + [
                    {"role": "assistant", "content": continuation},
                    {"role": "user", "content": continuation_prompt},
                ] if continuation else self.history
                final = None
                print(ui.gray("\n  ↳ reply interrupted — continuing automatically"))
            else:
                truncated = True
                error = attempt_error
                break

        sys.stdout.write(painter.flush())
        sys.stdout.write(ui.RESET + "\n")
        sys.stdout.flush()

        content = "".join(pieces)

        if error is not None:
            sounds.play("error")
            print(ui.error(f"  [reply stream interrupted] {error}"))
            print(ui.gray("  check that Ollama is running, then retry your message."))
            if not content:
                return False
        if truncated:
            sounds.play("notify")
            print(ui.warn("  ⚠ reply may still be incomplete after automatic retries"))

        if interrupted:
            if not content:
                print(ui.gray("  ⏹ stopped before any output."))
                return False
            print(ui.gray("  ⏹ stopped — partial reply kept."))

        if content and security.leaks_internal_text(content, self.history[0]["content"], _TOOL_SCHEMA_TEXT):
            print(ui.warn("  ⚠ that reply echoed internal wiring — not keeping it in context."))
            content = security.deflection()

        self.history.append({"role": "assistant", "content": content})

        if final is not None:
            gen = sum(_get(stats, "eval_count", 0) or 0 for stats in completion_stats)
            dur = sum((_get(stats, "eval_duration", 0) or 0) for stats in completion_stats) / 1e9
            prompt_tokens = sum(
                _get(stats, "prompt_eval_count", 0) or 0 for stats in completion_stats
            )
            tps = gen / dur if dur > 0 else None
            self.last_usage = {"prompt": prompt_tokens, "gen": gen}
            self.total_tokens += gen
            self.total_gen_seconds += dur
            if tps:
                self.speed_history.append(tps)
                del self.speed_history[:-40]   # keep it to recent turns
            pct = (prompt_tokens + gen) / self.options["num_ctx"]
            print()
            print(ui.render_footer(gen=gen, prompt=prompt_tokens, tps=tps, ttft=first_token, ctx_pct=pct))
            if pct >= 0.85:
                sounds.play("notify")
                print(ui.warn("  context nearly full") + ui.gray(" — /compact to summarize and free space"))
            elif time.time() - start >= 3.0:
                sounds.play("done")      # long reply finished — you may have looked away

        self.autosave()
        return True

    def chat_turn(self, user_input: str):
        self.history.append({"role": "user", "content": user_input})
        self.turn_count += 1
        if not self._stream_reply():
            self.history.pop()
            self.turn_count -= 1

    def print_reply(self, reply: str):
        print(self._signal_header())
        print(ui.render_markdown(reply))
        print()

    # ---------------------------------------------------------- agent chat

    # Tools that stop and ask before acting (unless /yolo is on).
    _CONFIRMED_TOOLS = (
        "write_file", "edit_file", "run_command", "web_search", "web_fetch"
    )

    def _set_activity(self, spinner):
        self._stop_activity()
        self._activity = spinner
        spinner.start()

    def _stop_activity(self):
        if self._activity is not None:
            self._activity.stop()
            self._activity = None

    def confirm_action(self, action: str, target: str, preview: str) -> bool:
        # A background spinner redraws its line every 80 ms with "\r" — left running
        # it would scribble over this box and the prompt. Always stop it first.
        self._stop_activity()

        lines = ["", ui.dim_line("  ┌─ confirmation required ─────────────"),
                 f"  {ui.solid(action, ui.gradient_color(0.15), bold=True)}  {ui.white(target)}"]
        if preview:
            snippet = preview if len(preview) < 800 else preview[:800] + "\n  ...(truncated)..."
            is_diff = ui.looks_like_diff(snippet)
            for line in snippet.splitlines():
                lines.append(f"  {ui.colorize_diff_line(line) if is_diff else ui.gray(line)}")
        lines.append(ui.dim_line("  └──────────────────────────────────────"))
        print("\n".join(lines))
        sys.stdout.flush()
        sounds.play("confirm")

        try:
            ans = input(rl(f"  {ui.white('proceed?')} {ui.gray('[y/N]')} › ")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False

        approved = ans in ("y", "yes")
        if approved:
            sounds.play("approve")
            # Show progress while the tool runs (a shell command can take a while).
            self._set_activity(ui.ActivitySpinner("  " + ui.gray("working")))
        return approved

    def agent_turn(self, user_input: str):
        self.history.append({"role": "user", "content": user_input})
        self.turn_count += 1

        print()
        turn_start = time.time()
        try:
            for event in run_agent(
                self.model, self.history, self.cwd,
                confirm_fn=self.confirm_action, yolo=self.yolo,
                generation_options=self.options,
            ):
                if event.kind == "thinking":
                    self._set_activity(ui.RadarPulse("thinking"))
                    continue

                self._stop_activity()

                if event.kind == "tool_call":
                    name = event.data["name"]
                    args = event.data["args"]
                    arg_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
                    if len(arg_str) > 90:
                        arg_str = arg_str[:90] + "..."
                    tag = ui.gray(" (recovered from text)") if event.data.get("recovered") else ""
                    icon, verb = ui.tool_status_label(name)
                    prefix = (
                        f"  {ui.solid(icon, ui.gradient_color(0.4), bold=True)} "
                        f"{ui.solid(verb, ui.gradient_color(0.4), bold=True)} "
                        f"{ui.gray(name + '(' + arg_str + ')')}{tag}"
                    )
                    if name in self._CONFIRMED_TOOLS and not self.yolo:
                        # Static line only: the confirmation box comes next, and it
                        # starts its own spinner once the user approves.
                        print(prefix)
                    else:
                        sounds.play("tool")
                        self._set_activity(ui.ActivitySpinner(prefix))

                elif event.kind == "tool_result":
                    result = event.data["result"]
                    if result.startswith(tool_impl.CANCELLED_PREFIX):
                        sounds.play("cancel")
                        print(f"    {ui.gray('✗ cancelled — nothing changed')}")
                        continue
                    if result.startswith("error:"):
                        sounds.play("error")
                    snippet = result if len(result) < 400 else result[:400] + "\n  ...(truncated)..."
                    is_diff = ui.looks_like_diff(snippet)
                    for line in snippet.splitlines()[:12]:
                        if is_diff:
                            print(f"    {ui.colorize_diff_line(line)}")
                        elif ui._LINE_NUM_RE.match(line):
                            print(f"    {ui.highlight_source_line(line)}")
                        else:
                            print(f"    {ui.gray(line)}")

                elif event.kind == "final":
                    text = event.data["text"]
                    if security.leaks_internal_text(text, self.history[0]["content"], _TOOL_SCHEMA_TEXT):
                        text = security.deflection()
                    self.history.append({"role": "assistant", "content": text})
                    print()
                    self.print_reply(text)
                    self.autosave()
                    if time.time() - turn_start >= 3.0:
                        sounds.play("done")

                elif event.kind == "guard_nudge":
                    print(ui.gray("  ↺ answered without reading anything real — forcing a tool call before trusting that answer"))

                elif event.kind == "step_limit":
                    sounds.play("notify")
                    print(ui.error(f"  agent stopped after {event.data['steps']} steps without finishing — ask it to continue if needed."))

                elif event.kind == "error":
                    sounds.play("error")
                    print(ui.error(f"  [signal error] {event.data['error']}"))
                    print(ui.gray("  is the model built? try: ") + ui.solid(f"ollama create {MODEL_NAME} -f Modelfile", ui.gradient_color(0.3)))
                    self.history.pop()
        except KeyboardInterrupt:
            self._stop_activity()
            print(ui.gray("\n  ⏹ stopped."))
            if self.history and self.history[-1].get("role") == "user":
                self.history.pop()
                self.turn_count -= 1
        finally:
            self._stop_activity()  # never leave a spinner thread running over the prompt


def main():
    if os.name == "nt":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    args = sys.argv[1:]
    if "--web" in args:
        import web_server

        port = 8765
        if "--web-port" in args:
            index = args.index("--web-port")
            try:
                port = int(args[index + 1])
            except (IndexError, ValueError):
                print("Invalid or missing port after --web-port (expected 1-65535).")
                sys.exit(2)
        if not 1 <= port <= 65535:
            print("Invalid web port (expected 1-65535).")
            sys.exit(2)
        web_server.serve(port=port, allow_lan="--web-lan" in args)
        return
    if "--version" in args:
        print(f"Midnight Signal {__version__}")
        return
    if "--doctor" in args:
        import doctor
        sys.exit(doctor.run(MODEL_NAME, BASE_MODEL))
    if not os.path.isdir(PROMPTS_DIR):
        print(ui.error(f"system_prompts/ folder not found next to this script ({PROMPTS_DIR})"))
        sys.exit(1)

    app = MidnightSignal(resume="--resume" in args)
    if "--no-sound" in args:
        sounds.engine.configure(enabled=False)
    app.run()


if __name__ == "__main__":
    main()
