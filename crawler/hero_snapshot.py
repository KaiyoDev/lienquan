#!/usr/bin/env python3
"""
Snapshot heroes.json before tier updates.
Used to detect tier changes (buff/nerf).
"""

import json
import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEROES_PATH = os.path.join(BASE_DIR, "..", "public", "heroes.json")
SNAPSHOT_PATH = os.path.join(BASE_DIR, "..", "public", "heroes_snapshot.json")

def snapshot():
    """Copy heroes.json to heroes_snapshot.json"""
    if not os.path.exists(HEROES_PATH):
        print(f"Warning: {HEROES_PATH} not found. Skipping snapshot.")
        return

    shutil.copy2(HEROES_PATH, SNAPSHOT_PATH)
    print(f"Snapshot created: {SNAPSHOT_PATH}")

if __name__ == "__main__":
    snapshot()
