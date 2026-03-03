#!/usr/bin/env python3
import sys
import os

# Kishi kaynak kod dizinine isaret et
sys.path.insert(0, "/home/ozhan/Okul/Sistem&Gorsel/VizeProjesi")

from kishi.main import main

if __name__ == '__main__':
    # Hata yoneticisini kapatip dogrudan cagiriyoruz
    try:
        main()
    except KeyboardInterrupt:
        pass
