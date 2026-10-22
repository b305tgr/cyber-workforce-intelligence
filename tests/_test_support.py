import importlib
import sys
from types import SimpleNamespace
from unittest.mock import Mock


def ensure_ollama_importable():
    try:
        importlib.import_module("ollama")
    except ModuleNotFoundError:
        sys.modules["ollama"] = SimpleNamespace(
            Client=Mock(),
            chat=Mock(),
            list=Mock(),
            show=Mock(),
        )
