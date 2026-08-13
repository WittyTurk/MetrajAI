from __future__ import annotations

from pathlib import Path

import ezdxf


def save_dxf(path: Path, *, units: int = 4):
    document = ezdxf.new("R2018")
    document.header["$INSUNITS"] = units
    return document
