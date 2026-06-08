"""Environment / key normalization.

The app uses GEMINI_API_KEY (Google AI Studio). LangChain + google-generativeai
read GOOGLE_API_KEY, so we mirror it. Call `ensure_env()` once at startup.
"""
from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv optional; .env can be sourced externally
    def load_dotenv(*_a, **_k) -> bool:  # type: ignore[misc]
        return False


def ensure_env() -> None:
    load_dotenv()
    gemini = os.environ.get("GEMINI_API_KEY")
    if gemini and not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = gemini


def has_key() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
