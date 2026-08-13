# -*- coding: utf-8 -*-

from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


class DebugLogger:

    @staticmethod
    def section(title):

        print()
        print("=" * 40)
        print(title)
        print("=" * 40)

    @staticmethod
    def value(name, value):

        print(f"{name:<12}: {value}")

    @staticmethod
    def subtitle(title):

        print()
        print(title)
        print("-" * 40)

    @staticmethod
    def item(text):

        print(text)

    @staticmethod
    def success(message):

        print(f"PASS: {message}")

    @staticmethod
    def warning(message):

        print(f"WARNING: {message}")

    @staticmethod
    def error(message):

        print(f"ERROR: {message}")
