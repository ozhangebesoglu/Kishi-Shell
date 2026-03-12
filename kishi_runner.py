#!/usr/bin/env python3
import sys
import os

# Point to the Kishi source directory (auto-detect installation path)
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from kishi.main import main

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
