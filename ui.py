"""
ui.py — Midnight Signal visual system.

Truecolor ANSI gradients, spy/radar-style animations, banners, help screen,
and the left-hand signal indicator. Pure stdlib, zero dependencies.
"""

import logging
import sys
import time
import re
import shutil
import threading

_logger = logging.getLogger(__name__)

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

# ── palette: sunset orange → amber → coral → soft red ─────────────────
STOPS = [
    (255, 106, 0),    # deep orange
    (255, 140, 0),    # orange
    (255, 176, 40),   # amber
    (255, 130, 90),   # coral
    (255, 90, 90),    # soft red
]

# ── themes ─────────────────────────────────────────────────────────────
# Five stops each, left → right across every gradient in the UI. set_theme()
# rewrites STOPS in place, so everything that paints with gradient_color()
# changes at once — banners, bars, prompts, spinners, the footer.

THEMES = {
    "sunset": [(255, 106, 0), (255, 140, 0), (255, 176, 40), (255, 130, 90), (255, 90, 90)],
    "ember":  [(255, 60, 0), (255, 90, 20), (255, 140, 40), (230, 60, 50), (170, 20, 40)],
    "cyber":  [(255, 0, 200), (200, 60, 255), (90, 120, 255), (0, 200, 255), (0, 255, 210)],
    "matrix": [(0, 120, 50), (0, 200, 90), (90, 255, 140), (170, 255, 120), (220, 255, 180)],
    "ice":    [(60, 120, 255), (80, 170, 255), (120, 220, 255), (170, 240, 255), (220, 250, 255)],
    "noir":   [(255, 255, 255), (215, 215, 215), (170, 170, 170), (130, 130, 130), (95, 95, 95)],
}

# Which theme each mode wears when the theme setting is "auto".
MODE_THEMES = {
    "default": "sunset", "agent": "sunset", "hacker": "matrix",
    "fun": "cyber", "coder": "ice", "lore": "ember",
}

CURRENT_THEME = "sunset"


def set_theme(name: str) -> bool:
    """Switch the live palette. Returns False for an unknown theme name."""
    global CURRENT_THEME, AMBER
    if name not in THEMES:
        return False
    STOPS[:] = THEMES[name]
    AMBER = STOPS[2]
    CURRENT_THEME = name
    return True


def theme_swatch(name: str, width: int = 24) -> str:
    stops = THEMES[name]
    return "".join(f"{fg(gradient_color(i / max(width - 1, 1), stops))}━" for i in range(width)) + RESET


SOFT_WHITE = (235, 230, 220)
SOFT_WHITE_FG = f"\033[38;2;{SOFT_WHITE[0]};{SOFT_WHITE[1]};{SOFT_WHITE[2]}m"
GRAY = (120, 120, 120)
DARK_GRAY = (60, 55, 55)
GREEN = (120, 220, 150)
RED = (255, 90, 90)


def fg(rgb):
    r, g, b = rgb
    return f"\033[38;2;{r};{g};{b}m"


def bg(rgb):
    r, g, b = rgb
    return f"\033[48;2;{r};{g};{b}m"


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_color(t: float, stops=STOPS):
    """t in [0,1] -> interpolated RGB across the stop list."""
    if t <= 0:
        return stops[0]
    if t >= 1:
        return stops[-1]
    seg = 1 / (len(stops) - 1)
    idx = min(int(t / seg), len(stops) - 2)
    local_t = (t - idx * seg) / seg
    return lerp(stops[idx], stops[idx + 1], local_t)


def gradient_text(text: str, bold: bool = False) -> str:
    """Paint a string left-to-right across the sunset gradient."""
    if not text:
        return text
    n = len(text)
    out = []
    prefix = BOLD if bold else ""
    for i, ch in enumerate(text):
        if ch == " ":
            out.append(" ")
            continue
        t = i / max(n - 1, 1)
        out.append(f"{prefix}{fg(gradient_color(t))}{ch}")
    return "".join(out) + RESET


def gradient_line(text: str, bold: bool = False) -> str:
    return gradient_text(text, bold=bold)


def solid(text: str, rgb, bold: bool = False) -> str:
    prefix = BOLD if bold else ""
    return f"{prefix}{fg(rgb)}{text}{RESET}"


def white(t, bold=False):
    return solid(t, SOFT_WHITE, bold)


def gray(t, bold=False):
    return solid(t, GRAY, bold)


def dim_line(t):
    return f"{DIM}{fg(DARK_GRAY)}{t}{RESET}"


def error(t):
    return solid(t, RED, bold=True)


def success(t):
    return solid(t, GREEN, bold=True)


def highlight_words(text: str, words) -> str:
    for w in words:
        if w in text:
            text = text.replace(w, gradient_text(w, bold=True))
    return text


def term_width(default=72):
    try:
        return max(shutil.get_terminal_size().columns, 40)
    except OSError:
        return default


# ── animations ─────────────────────────────────────────────────────────

def type_out(text: str, delay: float = 0.01, end: str = "\n"):
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(end)
    sys.stdout.flush()


def gradient_bar(pct: float, width: int = 34) -> str:
    """A smooth gradient-filled bar, no blocky ASCII look."""
    filled = int(width * pct)
    chars = []
    for i in range(width):
        t = i / max(width - 1, 1)
        if i < filled:
            chars.append(f"{fg(gradient_color(t))}━")
        else:
            chars.append(f"{fg(DARK_GRAY)}─")
    return "".join(chars) + RESET


_EIGHTHS = " ▏▎▍▌▋▊▉█"    # 0..8 eighths of a cell, for sub-character fill precision
_TRACK_DOT = "·"           # quiet unfilled track — a dotted line reads calmer than a dashed one


def smooth_bar(pct: float, width: int = 16, stops=None, cap: bool = True) -> str:
    """A fuel-gauge-style bar with eighth-block precision (up to width*8 fill
    steps instead of `width`), a bright leading edge where the fill ends,
    and soft bracket caps. Used for context/token usage everywhere in the UI."""
    pct = min(max(pct, 0.0), 1.0)
    units = round(pct * width * 8)
    full_cells, rem = divmod(units, 8)
    cells = []
    for i in range(width):
        t = i / max(width - 1, 1)
        color = fg(gradient_color(t, stops or STOPS))
        if i < full_cells:
            cells.append(f"{color}█")
        elif i == full_cells and rem:
            cells.append(f"{color}{_EIGHTHS[rem]}")
        else:
            cells.append(f"{fg(DARK_GRAY)}{_TRACK_DOT}")
    bar = "".join(cells) + RESET
    if not cap:
        return bar
    edge = gradient_color(min(pct, 1.0), stops or STOPS)
    left = solid("╢", DARK_GRAY)
    right = solid("╟", edge, bold=True) if pct > 0 else solid("╟", DARK_GRAY)
    return f"{left}{bar}{right}"


def segmented_bar(segments, width: int = 40) -> str:
    """A stacked usage bar: segments = [(label, fraction, rgb_or_None), ...]
    fractions need not sum to 1 (the remainder renders as empty track).
    None for a color falls back to the live gradient at that segment's
    midpoint, so it stays on-theme automatically."""
    cells, pos = [], 0.0
    total = sum(f for _, f, _ in segments)
    for _, frac, rgb in segments:
        n = round(frac * width)
        mid_t = min(max((pos + frac / 2) / max(total, 1e-9), 0.0), 1.0)
        color = rgb or gradient_color(mid_t)
        cells.append(fg(color) + "█" * n)
        pos += frac
    used_cells = sum(round(f * width) for _, f, _ in segments)
    cells.append(fg(DARK_GRAY) + _TRACK_DOT * max(width - used_cells, 0))
    return solid("╢", DARK_GRAY) + "".join(cells) + RESET + solid("╟", DARK_GRAY)


def sparkline(values, stops=None) -> str:
    """A one-line bar-height history, e.g. token speed across recent turns."""
    if not values:
        return dim_line("(no data yet)")
    glyphs = "▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    out = []
    for v in values:
        t = (v - lo) / span
        idx = min(int(t * (len(glyphs) - 1)), len(glyphs) - 1)
        out.append(f"{fg(gradient_color(t, stops or STOPS))}{glyphs[idx]}")
    return "".join(out) + RESET


def boot_sequence(label: str = "establishing local uplink", width: int = 34, steps: int = 40):
    """Boot animation: scan line sweep + gradient bar fill."""
    sys.stdout.write(HIDE_CURSOR)
    try:
        scan_frames = ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█", "▉", "▊", "▋", "▌", "▍", "▎"]
        for i in range(14):
            f = scan_frames[i % len(scan_frames)]
            t = i / 13
            sys.stdout.write(f"\r  {fg(gradient_color(t))}{f}{RESET}  {dim_line('scanning local signal...')}")
            sys.stdout.flush()
            time.sleep(0.02)
        sys.stdout.write("\r" + " " * 50 + "\r")

        for i in range(steps + 1):
            pct = i / steps
            bar = gradient_bar(pct, width)
            pct_label = solid(f"{int(pct * 100):>3}%", gradient_color(pct), bold=True)
            sys.stdout.write(f"\r  {gray(label)}  {bar}  {pct_label}")
            sys.stdout.flush()
            time.sleep(0.012)
        sys.stdout.write("\n")
    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()


def mode_lock_transition(mode_label: str, duration: float = 0.9):
    """Cinematic 'signal lock' effect for mode switching."""
    sys.stdout.write(HIDE_CURSOR)
    try:
        frames = ["◜", "◠", "◝", "◞", "◡", "◟"]
        start = time.time()
        i = 0
        while time.time() - start < duration:
            t = (time.time() - start) / duration
            f = frames[i % len(frames)]
            ring = solid(f, gradient_color(t), bold=True)
            sys.stdout.write(f"\r  {ring} {dim_line('locking signal')} {gray('→')} {solid(mode_label.upper(), gradient_color(t), bold=True)}")
            sys.stdout.flush()
            time.sleep(0.05)
            i += 1
        sys.stdout.write("\r" + " " * (len(mode_label) + 40) + "\r")
        lock_text = gradient_text(f"◆ SIGNAL LOCKED — {mode_label.upper()} ◆", bold=True)
        print(lock_text)
    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()


class RadarPulse:
    """Non-blocking radar/signal-pulse 'thinking' animation.
    Runs in its own thread; call .start() then .stop() once a response
    is ready, so it never blocks the actual Ollama call."""

    FRAMES = ["◐", "◓", "◑", "◒"]
    SWEEP = ["·", "∙", "•", "●", "•", "∙"]

    def __init__(self, label: str = "receiving"):
        self.label = label
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        i = 0
        while not self._stop.is_set():
            t = (i % 20) / 20
            radar = solid(self.FRAMES[i % len(self.FRAMES)], gradient_color(t), bold=True)
            sweep = solid(self.SWEEP[i % len(self.SWEEP)], gradient_color(1 - t))
            sys.stdout.write(f"\r  {radar} {sweep} {dim_line(self.label + '...')}")
            sys.stdout.flush()
            time.sleep(0.09)
            i += 1
        sys.stdout.write("\r" + " " * (len(self.label) + 20) + "\r")
        sys.stdout.flush()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()


class ActivitySpinner:
    """Inline spinner that redraws a single line: a fixed `prefix` (already
    ANSI-colored) followed by an animated braille frame. Used for tool calls
    and other short operations so the terminal shows visible progress
    instead of sitting blank. stop() clears the line."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, prefix: str):
        self.prefix = prefix
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        i = 0
        while not self._stop.is_set():
            frame = solid(self.FRAMES[i % len(self.FRAMES)], gradient_color((i % 20) / 20))
            sys.stdout.write(f"\r{self.prefix} {frame}")
            sys.stdout.flush()
            time.sleep(0.08)
            i += 1
        pad = " " * (visible_len(self.prefix) + 4)
        sys.stdout.write("\r" + pad + "\r")
        sys.stdout.flush()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()
            self._thread = None


_TOOL_STATUS = {
    "read_file": ("↳", "reading"),
    "write_file": ("↳", "writing"),
    "edit_file": ("↳", "editing"),
    "list_dir": ("↳", "listing"),
    "search_files": ("↳", "searching"),
    "run_command": ("↳", "running"),
    "git_status": ("↳", "checking git"),
    "git_diff": ("↳", "diffing"),
}


def tool_status_label(name: str) -> tuple:
    """(icon, present-participle verb) for a tool name, for status lines."""
    return _TOOL_STATUS.get(name, ("⚙", "calling"))


def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


# ── banners ─────────────────────────────────────────────────────────

LOGO_LINES = [
    "███╗   ███╗██╗██████╗ ███╗   ██╗██╗ ██████╗ ██╗  ██╗████████╗",
    "████╗ ████║██║██╔══██╗████╗  ██║██║██╔════╝ ██║  ██║╚══██╔══╝",
    "██╔████╔██║██║██║  ██║██╔██╗ ██║██║██║  ███╗███████║   ██║   ",
    "██║╚██╔╝██║██║██║  ██║██║╚██╗██║██║██║   ██║██╔══██║   ██║   ",
    "██║ ╚═╝ ██║██║██████╔╝██║ ╚████║██║╚██████╔╝██║  ██║   ██║   ",
    "╚═╝     ╚═╝╚═╝╚═════╝ ╚═╝  ╚═══╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ",
    " ███████╗██╗ ██████╗ ███╗   ██╗ █████╗ ██╗     ",
    " ██╔════╝██║██╔════╝ ████╗  ██║██╔══██╗██║     ",
    " ███████╗██║██║  ███╗██╔██╗ ██║███████║██║     ",
    " ╚════██║██║██║   ██║██║╚██╗██║██╔══██║██║     ",
    " ███████║██║╚██████╔╝██║ ╚████║██║  ██║███████╗",
    " ╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝",
]


def render_main_banner(mode: str = "default", version: str = "2.2") -> str:
    out = []
    for line in LOGO_LINES:
        out.append(gradient_line(line, bold=True))
    out.append("")
    sub = f"  local terminal intelligence · v{version}  ·  mode: {mode}"
    out.append(gray(sub))
    out.append(gray("  signal: ") + gradient_text("completely unhinged · no leash · no filter", bold=True))
    out.append("")
    out.append(dim_line("  " + "─" * min(60, term_width())))
    out.append("")
    out.append("  " + gray("· classified build ·  ") + gradient_text("engineered by ADITYA TOMAR", bold=True))
    out.append(dim_line("  " + "─" * min(60, term_width())))
    out.append("")
    out.append(white("  type ") + solid("/help", gradient_color(0.15), bold=True) + white(" to see everything this terminal can do"))
    out.append("")
    return "\n".join(out)


def render_mode_banner(mode: str, description: str) -> str:
    bar = dim_line("─" * min(60, term_width()))
    out = [
        "",
        bar,
        "",
        gradient_text(f"  ◆ {mode.upper()}", bold=True),
        gray(f"    {description}"),
        "",
        bar,
        "",
    ]
    return "\n".join(out)


def render_goodbye() -> str:
    lines = [
        "        · · ·",
        "     ·         ·",
        "   ·    ◌ ◍ ◌    ·",
        "     ·         ·",
        "        · · ·",
        "",
        "   carrier wave fading — signal lost",
    ]
    return "\n".join(gradient_text(l, bold=True) if l.strip() else l for l in lines)


def render_help(commands, modes, tools=None) -> str:
    w = min(64, term_width() - 2)
    top = dim_line("┌" + "─" * w + "┐")
    bottom = dim_line("└" + "─" * w + "┘")
    mid = dim_line("│")

    out = [top, mid]
    out.append(f"{mid} {gradient_text('MIDNIGHT SIGNAL — COMMAND REFERENCE', bold=True)}")
    out.append(f"{mid}")
    out.append(f"{mid}")
    out.append(f"{mid} {solid('COMMANDS', gradient_color(0.1), bold=True)}")
    out.append(f"{mid}")
    for cmd, desc in commands:
        out.append(f"{mid}   {solid(cmd.ljust(18), gradient_color(0.3))}{gray(desc)}")
    out.append(f"{mid}")
    out.append(f"{mid}")
    out.append(f"{mid} {solid('MODES', gradient_color(0.5), bold=True)}")
    out.append(f"{mid}")
    for m, desc in modes.items():
        out.append(f"{mid}   {solid(('/mode ' + m).ljust(18), gradient_color(0.6))}{gray(desc)}")
    if tools:
        out.append(f"{mid}")
        out.append(f"{mid}")
        out.append(f"{mid} {solid('AGENT TOOLS (mode: agent)', gradient_color(0.85), bold=True)}")
        out.append(f"{mid}")
        for name, desc in tools:
            out.append(f"{mid}   {solid(name.ljust(18), gradient_color(0.9))}{gray(desc)}")
    out.append(f"{mid}")
    out.append(bottom)
    return "\n".join(out)


def signal_prefix() -> str:
    """Left-side pulsing signal indicator used before assistant replies."""
    return solid("▌", gradient_color(0.25), bold=True)


def you_prefix() -> str:
    return solid("▌", gradient_color(0.75), bold=True)


# ── streaming, footer, readline helpers ───────────────────────────────

AMBER = (255, 176, 40)
_ANSI_RE = re.compile(r"(\033\[[0-9;?]*[A-Za-z])")
CODE_FG = fg(gradient_color(0.33))


def warn(t):
    return solid(t, AMBER, bold=True)


def rl_safe(s: str) -> str:
    """Wrap ANSI escapes so readline measures prompt width correctly."""
    return _ANSI_RE.sub("\001\\1\002", s)


def visible_len(s: str) -> int:
    """Length of a string as it will actually occupy on screen, ignoring ANSI escapes."""
    return len(_ANSI_RE.sub("", s))


# ─────────────────────────────────────────────────────── code highlighting
#
# Lightweight, language-agnostic. Single regex pass so colored spans never
# get re-scanned (which would corrupt already-inserted ANSI codes).

_KEYWORDS = {
    "def", "class", "import", "from", "return", "if", "elif", "else", "for", "while",
    "try", "except", "finally", "with", "as", "pass", "break", "continue", "yield",
    "lambda", "global", "nonlocal", "in", "is", "not", "and", "or", "raise", "assert",
    "None", "True", "False", "self", "async", "await", "del",
    "function", "const", "let", "var", "export", "default", "new", "this", "extends",
    "public", "private", "protected", "static", "void", "int", "float", "double",
    "string", "bool", "struct", "enum", "interface", "package", "func", "type",
    "switch", "case", "default", "typeof", "instanceof", "throw", "catch",
}
_CODE_TOKEN_RE = re.compile(
    r"(?P<comment>#.*$|//.*$)"
    r"|(?P<string>\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')"
    r"|(?P<number>\b\d+(?:\.\d+)?\b)"
    r"|(?P<keyword>\b(?:" + "|".join(sorted(_KEYWORDS, key=len, reverse=True)) + r")\b)",
    re.MULTILINE,
)


def highlight_code_line(line: str) -> str:
    """Color a single line of source: comments dim, strings warm, numbers
    amber, keywords bold — everything else left as-is."""
    def repl(m):
        if m.group("comment"):
            return dim_line(m.group("comment"))
        if m.group("string"):
            return solid(m.group("string"), gradient_color(0.6))
        if m.group("number"):
            return solid(m.group("number"), gradient_color(0.8))
        if m.group("keyword"):
            return solid(m.group("keyword"), gradient_color(0.15), bold=True)
        return m.group(0)
    return _CODE_TOKEN_RE.sub(repl, line)


_LINE_NUM_RE = re.compile(r"^(\s*\d+ \| )(.*)$")


def highlight_source_line(line: str) -> str:
    """Like highlight_code_line, but keeps a ` 12 | ` read_file-style line
    number prefix gray instead of trying to tokenize it as code."""
    m = _LINE_NUM_RE.match(line)
    if m:
        return gray(m.group(1)) + highlight_code_line(m.group(2))
    return highlight_code_line(line)


# ───────────────────────────────────────────────────────────── diff colors

def colorize_diff_line(line: str) -> str:
    """Color a single unified-diff line: +green / -red / @@cyan-ish / gray."""
    if line.startswith("+++") or line.startswith("---"):
        return gray(line)
    if line.startswith("@@"):
        return solid(line, gradient_color(0.55))
    if line.startswith("+"):
        return solid(line, GREEN)
    if line.startswith("-"):
        return solid(line, RED)
    return gray(line)


def looks_like_diff(text: str) -> bool:
    return any(
        line.startswith(("+++", "---", "@@")) or (line[:1] in "+-" and len(line) > 1)
        for line in text.splitlines()[:20]
    )


# ─────────────────────────────────────────────────────── markdown rendering
#
# Line-based, not character-based: markdown structure (a heading, a table
# row, a bullet) only makes sense once a full line is known, so streamed
# text is buffered per-line and rendered as each line completes. This still
# streams progressively (line by line rather than word by word) rather than
# waiting for the whole reply.

_FENCE_RE = re.compile(r"^```")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
_NUMLIST_RE = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
_TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")
_INLINE_MD_RE = re.compile(
    r"(?P<code>`[^`]+`)"
    r"|(?P<bold>\*\*[^*]+\*\*|__[^_]+__)"
    r"|(?P<italic>\*[^*]+\*|_[^_]+_)"
)


def _inline_markdown(text: str, base_color: bool = False) -> str:
    def repl(m):
        if m.group("code"):
            return solid(m.group("code")[1:-1], gradient_color(0.33))
        if m.group("bold"):
            return solid(m.group("bold")[2:-2], SOFT_WHITE, bold=True)
        if m.group("italic"):
            inner = m.group("italic")
            return solid(inner[1:-1], gradient_color(0.55))
        return m.group(0)
    rendered = _INLINE_MD_RE.sub(repl, text)
    return (SOFT_WHITE_FG + rendered + RESET) if base_color else rendered


def _render_markdown_line(line: str, in_code: bool) -> tuple:
    """Returns (rendered_line, new_in_code_state)."""
    stripped = line.strip()

    if _FENCE_RE.match(stripped):
        return dim_line(line), not in_code

    if in_code:
        return highlight_code_line(line), True

    h = _HEADING_RE.match(line)
    if h:
        level = len(h.group(1))
        t = min(0.15 + level * 0.12, 0.9)
        text = _inline_markdown(h.group(2))
        return solid(h.group(2).upper() if level == 1 else text, gradient_color(t), bold=True), False

    b = _BULLET_RE.match(line)
    if b:
        indent, text = b.group(1), b.group(2)
        bullet = solid("›", gradient_color(0.4), bold=True)
        return f"{indent}{bullet} {_inline_markdown(text)}", False

    n = _NUMLIST_RE.match(line)
    if n:
        indent, num, text = n.group(1), n.group(2), n.group(3)
        return f"{indent}{solid(num + '.', gradient_color(0.4), bold=True)} {_inline_markdown(text)}", False

    if _TABLE_SEP_RE.match(stripped) and "-" in stripped:
        return dim_line(line), False

    if "|" in stripped and stripped.count("|") >= 2:
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        return "  " + gray(" │ ").join(_inline_markdown(c) for c in cells), False

    return _inline_markdown(line, base_color=True), False


def render_markdown(text: str) -> str:
    """Fully render a complete (non-streaming) block of markdown-ish text."""
    in_code = False
    out = []
    for line in text.split("\n"):
        rendered, in_code = _render_markdown_line(line, in_code)
        out.append(rendered)
    return "\n".join(out)


class StreamPainter:
    """Renders streamed model output as it arrives, word by word — not line
    by line. A line's role (heading / bullet / numbered list / plain text)
    is usually knowable from its first few characters, so only that brief
    prefix is held back; everything after streams the instant it's received,
    the same way `ollama run` prints tokens. Only two things still wait for
    a full line, because they need the whole line to render correctly:
    a fenced code line (for syntax highlighting) and a table row (for
    column alignment) — both are short, so the wait is barely noticeable.
    """

    # Longest lookahead ever needed to tell a marker from plain text: a
    # heading needs up to six '#' plus the following char ("######x").
    _MAX_PEEK = 7

    def __init__(self):
        self._buf = ""
        self._mode = "line_start"      # line_start | plain | heading | bullet | numlist | fence_wait | table_wait | code
        self._in_code_block = False    # persists across lines: are we inside ``` ... ```
        self._span = None              # None | "bold" | "code" — an inline marker opened mid-stream
        self._safe = True              # False after any internal error; falls back to raw passthrough
        self._finalizing = False

    def feed(self, piece: str) -> str:
        self._buf += piece
        if not self._safe:
            out, self._buf = self._buf, ""
            return out
        try:
            return self._drain()
        except Exception as exc:
            # Never let a rendering edge case break the stream — show the
            # raw text (still correct, just unstyled) instead of stalling.
            _logger.warning("Markdown stream renderer fell back to plain text: %s", exc)
            self._safe = False
            out, self._buf = self._buf, ""
            return out

    def flush(self) -> str:
        """Call once the stream ends to render whatever's left unterminated."""
        self._buf += "\n"
        try:
            self._finalizing = True
            out = self._drain()
        except Exception as exc:
            _logger.warning("Markdown stream flush fell back to plain text: %s", exc)
            out = self._buf
            self._buf = ""
        finally:
            self._finalizing = False
        return out.rstrip("\n")

    # ── the drain loop: consume as much of self._buf as is safely decidable ──

    def _drain(self) -> str:
        out = []
        progress = True
        while progress:
            progress = False
            if self._mode == "line_start":
                chunk, progress = self._start_line()
            elif self._mode == "code":
                chunk, progress = self._consume_code_line()
            elif self._mode in ("fence_wait", "table_wait"):
                chunk, progress = self._consume_buffered_line()
            else:  # plain / heading / bullet / numlist — the word-by-word path
                chunk, progress = self._consume_words()
            if chunk:
                out.append(chunk)
        return "".join(out)

    def _start_line(self):
        """Decide what kind of line is starting. Most lines are plain text,
        which is knowable the instant a non-marker character appears — so
        the common case adds no delay at all."""
        buf = self._buf
        i = 0
        while i < len(buf) and buf[i] in " \t":
            i += 1
        if i == len(buf):
            return None, False                          # only whitespace so far — wait
        indent, rest = buf[:i], buf[i:]
        c = rest[0]

        if c == "\n":
            self._buf = buf[i + 1:]
            return indent + "\n", True                  # blank line

        if rest.startswith("```") or (len(rest) < 3 and "```"[:len(rest)] == rest):
            if len(rest) < 3:
                return None, False                       # could still become ``` — wait
            self._mode = "fence_wait"
            return None, True

        if c in "-*+":
            if len(rest) < 2:
                return None, False                       # need the char after the marker
            if rest[1] in " \t":
                self._buf = buf[i + 2:]
                self._mode = "bullet"
                self._span = None
                bullet = solid("›", gradient_color(0.4), bold=True)
                return indent + bullet + " ", True
            self._mode = "plain"
            return None, True                             # e.g. "*bold text*" — not a bullet

        if c.isdigit():
            j = i
            while j < len(buf) and buf[j].isdigit():
                j += 1
            if j == len(buf):
                return None, False                        # digits still growing — wait
            if buf[j] != ".":
                self._mode = "plain"
                return None, True                          # a number that isn't a list marker
            if j + 1 >= len(buf):
                return None, False                         # need the char after '.'
            if buf[j + 1] in " \t":
                num = buf[i:j]
                self._buf = buf[j + 2:]
                self._mode = "numlist"
                self._span = None
                return indent + solid(num + ".", gradient_color(0.4), bold=True) + " ", True
            self._mode = "plain"
            return None, True                              # "1.5x" etc. — not a list marker

        if c == "#":
            j = i
            while j < len(buf) and buf[j] == "#" and j - i < 6:
                j += 1
            if j == len(buf) and j - i < 6:
                return None, False                         # hashes still growing — wait
            if j < len(buf) and buf[j] in " \t":
                self._mode = "heading"
                self._heading_level = j - i
                self._span = None
                self._buf = buf[j + 1:]
                return None, True                           # swallow "### " — text streams next
            self._mode = "plain"
            return None, True

        if c == "|":
            self._mode = "table_wait"
            return None, True

        self._mode = "plain"
        self._span = None
        return None, True

    def _consume_buffered_line(self):
        """fence_wait / table_wait: these need the whole line, so hold it —
        both kinds of line are short, so the wait is a beat, not a stall."""
        if "\n" not in self._buf:
            return None, False
        line, rest = self._buf.split("\n", 1)
        self._buf = rest
        if self._mode == "fence_wait":
            self._in_code_block = not self._in_code_block
            self._mode = "code" if self._in_code_block else "line_start"
            return dim_line(line) + "\n", True
        rendered, _ = _render_markdown_line(line, False)
        self._mode = "line_start"
        return rendered + "\n", True

    def _consume_code_line(self):
        if "\n" not in self._buf:
            return None, False
        line, rest = self._buf.split("\n", 1)
        self._buf = rest
        if _FENCE_RE.match(line.strip()):
            self._in_code_block = False
            self._mode = "line_start"
            return dim_line(line) + "\n", True
        return highlight_code_line(line) + "\n", True

    def _consume_words(self):
        """The streaming path: emit every complete word the instant it's
        followed by whitespace or a newline, applying inline **bold** /
        `code` styling with a span that can stay open across chunks. A word
        still growing (no boundary yet) is simply not emitted yet — words
        are short, so this is the word-level granularity, not line-level."""
        buf = self._buf
        cut = -1
        for j, ch in enumerate(buf):
            if ch in " \t\n":
                cut = j
                break
        if cut == -1:
            return None, False

        word, newline = buf[:cut], buf[cut] == "\n"
        self._buf = buf[cut + 1:]
        styled = self._style(word)
        sep = "\n" if newline else " "
        if newline:
            self._mode = "line_start"
            self._span = None
        return styled + sep, True

    @staticmethod
    def _next_marker(text: str, i: int):
        """Earliest of `code`, **bold**, or *italic* starting at/after i, as
        (kind, start, marker_len) — or None. A lone '*' that's actually the
        first half of '**' is skipped so bold always wins over italic."""
        code_i = text.find("`", i)
        bold_i = text.find("**", i)
        p, ital_i = i, -1
        while True:
            p = text.find("*", p)
            if p == -1:
                break
            if text[p:p + 2] == "**":
                p += 2
                continue
            ital_i = p
            break
        candidates = [(k, pos, n) for k, pos, n in
                      (("code", code_i, 1), ("bold", bold_i, 2), ("italic", ital_i, 1)) if pos != -1]
        return min(candidates, key=lambda c: c[1]) if candidates else None

    def _style(self, text: str) -> str:
        """Apply heading / bold / italic / inline-code coloring to one
        word-sized chunk, honoring a span opened in an earlier chunk."""
        if not text:
            return text
        if self._mode == "heading":
            text = text.upper() if self._heading_level == 1 else text
            t = min(0.15 + self._heading_level * 0.12, 0.9)
            base = lambda s: solid(s, gradient_color(t), bold=True)
        else:
            base = lambda s: solid(s, SOFT_WHITE)

        out, i, n = [], 0, len(text)
        while i < n:
            if self._span == "code":
                end = text.find("`", i)
                close = solid(text[i:end if end != -1 else n], gradient_color(0.33))
                out.append(close)
                if end == -1:
                    i = n
                else:
                    self._span = None
                    i = end + 1
            elif self._span == "bold":
                end = text.find("**", i)
                out.append(solid(text[i:end if end != -1 else n], SOFT_WHITE, bold=True))
                if end == -1:
                    i = n
                else:
                    self._span = None
                    i = end + 2
            elif self._span == "italic":
                end = text.find("*", i)
                out.append(solid(text[i:end if end != -1 else n], gradient_color(0.55)))
                if end == -1:
                    i = n
                else:
                    self._span = None
                    i = end + 1
            else:
                marker = self._next_marker(text, i)
                if marker is None:
                    out.append(base(text[i:]))
                    i = n
                else:
                    kind, start, mlen = marker
                    out.append(base(text[i:start]))
                    closing = {"bold": "**", "italic": "*", "code": "`"}[kind]
                    if (
                        self._finalizing
                        and text.find(closing, start + mlen) == -1
                    ):
                        out.append(base(text[start:]))
                        i = n
                        continue
                    self._span = kind
                    i = start + mlen
        return "".join(out)


def signal_meter(tps, ceiling: float = 60.0) -> str:
    glyphs = "▂▃▅▆▇"
    level = 0.0 if not tps else min(max(tps / ceiling, 0.0), 1.0)
    filled = max(1, round(level * len(glyphs))) if tps else 0
    cells = []
    for i, g in enumerate(glyphs):
        if i < filled:
            cells.append(f"{fg(gradient_color(i / (len(glyphs) - 1)))}{g}")
        else:
            cells.append(f"{fg(DARK_GRAY)}{g}")
    return "".join(cells) + RESET


def context_bar(pct: float, width: int = 30) -> str:
    pct = min(max(pct, 0.0), 1.0)
    return gradient_bar(pct, width)


# ─────────────────────────────────────────────────────────── usage footer

def format_tokens(n) -> str:
    """142 -> '142', 1834 -> '1.8k'."""
    n = int(n or 0)
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def render_footer(gen=None, prompt=None, tps=None, ttft=None, ctx_pct=None) -> str:
    """One quiet line under each reply, e.g.

        38.2 tok/s · 142 gen · 1.8k prompt · ctx ━━────────  23% · 0.4s first token

    Values are bright, labels are dim; the ctx figure warms to amber, then
    red, as the context window fills up."""
    bits = []
    if tps:
        bits.append(white(f"{tps:.1f}") + gray(" tok/s"))
    if gen:
        bits.append(white(format_tokens(gen)) + gray(" gen"))
    if prompt:
        bits.append(white(format_tokens(prompt)) + gray(" prompt"))
    if ctx_pct is not None:
        tone = RED if ctx_pct >= 0.85 else gradient_color(0.35) if ctx_pct >= 0.6 else SOFT_WHITE
        bar = smooth_bar(ctx_pct, 12)
        bits.append(gray("ctx ") + bar + " " + solid(f"{ctx_pct * 100:.0f}%", tone))
    if ttft is not None:
        bits.append(white(f"{ttft:.1f}s") + gray(" first token"))
    return "  " + gray(" · ").join(bits)
