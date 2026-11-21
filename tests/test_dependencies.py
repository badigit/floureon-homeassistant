from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_broadlink_requirement_is_compatible_with_test_environment() -> None:
    manifest = json.loads((ROOT / "custom_components/hysen/manifest.json").read_text())
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    runtime = next(
        dep for dep in manifest["requirements"] if dep.startswith("broadlink-async")
    )
    development = next(
        dep
        for dep in pyproject["dependency-groups"]["dev"]
        if dep.startswith("broadlink-async")
    )
    assert runtime == "broadlink-async>=1.2.1"
    assert development == "broadlink-async==1.2.1"
