#!/usr/bin/env python3
"""Compatibility entry point; install ./python or use this repository checkout."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "python"))
from nersc_tokens._backend import main

if __name__ == "__main__":
    main()
