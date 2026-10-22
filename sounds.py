"""
sounds.py — Midnight Signal sound engine.

Every sound is synthesized from scratch with the standard library (sine /
bell / square voices with envelopes), written once to a tiny WAV cache under
~/.midnight_signal/sounds, and played by whatever the OS provides:

    Windows  winsound (built in)
    macOS    afplay   (built in)
    Linux    paplay / pw-play / aplay / play (sox) / ffplay — first one found

If no player exists, only the important events fall back to the terminal
bell. No audio files ship with the project and nothing here needs pip.

    import sounds
    sounds.play("lock")
"""

import math
import logging
import os
import shutil
import struct
import subprocess
import sys
import time
import wave

_logger = logging.getLogger(__name__)

RATE = 22050
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".midnight_signal", "sounds")

# ── voices ─────────────────────────────────────────────────────────────
# (start_s, freq_start, freq_end, duration_s, kind, gain, decay_per_s)
#   kind: "soft"   sine + a quiet octave — round, friendly blips
#         "bell"   inharmonic partials — glassy chimes
#         "square" buzzy — errors / static
#         "sine"   pure — sweeps and rumbles

SOUNDS = {
    # startup: low rumble under a rising four-note arpeggio, ending on a bell
    "boot": [
        (0.00, 70, 200, 0.55, "sine", 0.40, 3.0),
        (0.02, 523.25, 523.25, 0.16, "soft", 0.60, 6),
        (0.12, 659.25, 659.25, 0.16, "soft", 0.60, 6),
        (0.22, 783.99, 783.99, 0.16, "soft", 0.60, 6),
        (0.32, 1046.50, 1046.50, 0.60, "bell", 0.70, 4),
    ],
    # mode switch: a fast downward sweep, a mechanical click, then a locked-on ping
    "lock": [
        (0.00, 1500, 280, 0.13, "sine", 0.45, 9),
        (0.15, 900, 900, 0.04, "square", 0.25, 40),
        (0.21, 1318.5, 1318.5, 0.28, "bell", 0.70, 7),
    ],
    # first token arrives
    "blip": [(0.00, 1480, 1480, 0.05, "soft", 0.45, 30)],
    # agent calls a tool: two quick rising ticks
    "tool": [
        (0.00, 880, 880, 0.04, "soft", 0.55, 35),
        (0.06, 1318.5, 1318.5, 0.05, "soft", 0.55, 35),
    ],
    # a confirmation box is waiting for you: a two-note question
    "confirm": [
        (0.00, 659.25, 659.25, 0.12, "bell", 0.65, 9),
        (0.14, 987.77, 987.77, 0.26, "bell", 0.65, 6),
    ],
    # you said yes: bright upward blip
    "approve": [
        (0.00, 880, 880, 0.06, "soft", 0.55, 22),
        (0.07, 1318.5, 1318.5, 0.14, "bell", 0.55, 12),
    ],
    # you said no: soft downward step
    "cancel": [
        (0.00, 523.25, 523.25, 0.08, "soft", 0.55, 18),
        (0.09, 392.00, 392.00, 0.16, "soft", 0.55, 13),
    ],
    # something failed: low, buzzy double-thud
    "error": [
        (0.00, 175, 150, 0.16, "square", 0.32, 8),
        (0.19, 150, 120, 0.24, "square", 0.32, 7),
    ],
    # a long reply / task finished: glassy two-bell chime
    "done": [
        (0.00, 1318.5, 1318.5, 0.55, "bell", 0.60, 5.5),
        (0.10, 1975.5, 1975.5, 0.50, "bell", 0.40, 6.0),
    ],
    # gentle heads-up (context nearly full, etc.)
    "notify": [(0.00, 1046.5, 1046.5, 0.20, "bell", 0.55, 10)],
    # signal lost: long falling sweep with a low echo
    "goodbye": [
        (0.00, 1200, 180, 0.90, "sine", 0.45, 3.2),
        (0.28, 620, 90, 0.65, "soft", 0.25, 4.0),
    ],
}

# Shown by /sound test.
LABELS = {
    "boot": "startup arpeggio", "lock": "mode switch / theme change", "blip": "first token arrives",
    "tool": "agent runs a tool", "confirm": "a confirmation is waiting", "approve": "you said yes",
    "cancel": "you said no / bad command", "error": "something failed",
    "done": "a long reply finished", "notify": "heads-up (context full, volume set)", "goodbye": "signal lost",
}

# Relative loudness after normalisation (1.0 = full "volume" setting). Tiny
# feedback ticks sit well under the big moments so they never get annoying.
LEVEL = {"blip": 0.45, "tool": 0.55, "notify": 0.80, "cancel": 0.75, "approve": 0.80}

# When there is no audio player, only these events are worth a terminal bell.
_BELL_FALLBACK = {"confirm", "error", "done"}


# ── synthesis ──────────────────────────────────────────────────────────

def _voice(f0, f1, dur, kind, gain, decay):
    n = max(int(RATE * dur), 1)
    attack = max(int(RATE * 0.004), 1)
    tail = max(int(RATE * 0.006), 1)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / n
        phase += 2 * math.pi * (f0 + (f1 - f0) * t) / RATE
        if kind == "bell":
            s = (math.sin(phase) + 0.5 * math.sin(2.76 * phase) + 0.25 * math.sin(5.40 * phase)) / 1.75
        elif kind == "square":
            s = 0.55 * (1.0 if math.sin(phase) >= 0 else -1.0) + 0.25 * math.sin(phase)
        elif kind == "soft":
            s = (math.sin(phase) + 0.3 * math.sin(2 * phase)) / 1.3
        else:
            s = math.sin(phase)
        env = math.exp(-decay * i / RATE)
        if i < attack:
            env *= i / attack
        if i > n - tail:
            env *= (n - i) / tail          # fade the very end so there is no click
        out.append(s * env * gain)
    return out


def _render(name, volume):
    voices = SOUNDS[name]
    total = max(int(RATE * (start + dur)) for start, _, _, dur, *_ in voices) + 1
    mix = [0.0] * total
    for start, f0, f1, dur, kind, gain, decay in voices:
        offset = int(RATE * start)
        for i, s in enumerate(_voice(f0, f1, dur, kind, gain, decay)):
            mix[offset + i] += s
    peak = max(abs(x) for x in mix) or 1.0            # normalise, then apply level * volume
    scale = 32767 * 0.9 * LEVEL.get(name, 1.0) * max(0.0, min(volume, 1.0)) / peak
    return struct.pack(f"<{len(mix)}h", *(int(x * scale) for x in mix))


def _wav_path(name, volume):
    return os.path.join(CACHE_DIR, f"{name}_{int(round(volume * 100)):03d}.wav")


def _ensure_wav(name, volume):
    path = _wav_path(name, volume)
    if os.path.isfile(path):
        return path
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(_render(name, volume))
    os.replace(tmp, path)
    return path


# ── playback ───────────────────────────────────────────────────────────

_LINUX_PLAYERS = (
    ("paplay", []),
    ("pw-play", []),
    ("aplay", ["-q"]),
    ("play", ["-q"]),                                        # sox
    ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"]),
)


def detect_player():
    """Name of the audio backend that will be used, or None."""
    if sys.platform.startswith("win"):
        try:
            import winsound  # noqa: F401
            return "winsound"
        except ImportError:
            return None
    if sys.platform == "darwin":
        return "afplay" if shutil.which("afplay") else None
    for exe, _ in _LINUX_PLAYERS:
        if shutil.which(exe):
            return exe
    return None


class SoundEngine:
    def __init__(self):
        self.enabled = True
        self.volume = 0.6
        self._player = detect_player()
        self._procs = []
        self._broken = False

    def configure(self, enabled=None, volume=None):
        if enabled is not None:
            self.enabled = bool(enabled)
        if volume is not None:
            self.volume = max(0.0, min(float(volume), 1.0))

    @property
    def player(self):
        return self._player

    def _reap(self):
        self._procs = [p for p in self._procs if p.poll() is None]

    def play(self, name):
        """Fire-and-forget. Never raises, never blocks."""
        if not self.enabled or self.volume <= 0 or name not in SOUNDS:
            return
        if self._player is None or self._broken:
            if name in _BELL_FALLBACK and sys.stdout.isatty():
                sys.stdout.write("\a")
                sys.stdout.flush()
            return
        try:
            path = _ensure_wav(name, self.volume)
            if self._player == "winsound":
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                return
            if self._player == "afplay":
                cmd = ["afplay", path]
            else:
                extra = dict(_LINUX_PLAYERS)[self._player]
                cmd = [self._player, *extra, path]
            self._reap()
            self._procs.append(subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            ))
        except Exception as exc:
            self._broken = True
            _logger.warning("Sound playback disabled after an audio error: %s", exc)


engine = SoundEngine()


def play(name):
    engine.play(name)
