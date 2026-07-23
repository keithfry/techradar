#!/usr/bin/env python3
"""Thin entrypoint for this repo's news-radar consumer.

Loads Gmail OAuth secrets from ~/keys/kfopenclaw-gmail.env (outside this
repo), then hands off to the newsradar CLI:

    uv run run.py --config config/config.toml --date YYYY-MM-DD --time HH:MM
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path.home() / "keys" / "kfopenclaw-gmail.env")

from newsradar.cli import main

if __name__ == "__main__":
    main()
