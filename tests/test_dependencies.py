from __future__ import annotations

import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_broadlink_requirement_matches_test_environment() -> None:
    manifest = json.loads(
        (ROOT / "custom_components/floureon/manifest.json").read_text()
    )
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    runtime = next(
        dep for dep in manifest["requirements"] if dep.startswith("broadlink-async==")
    )
    development = next(
        dep for dep in pyproject["dependency-groups"]["dev"]
        if dep.startswith("broadlink-async==")
    )
    assert runtime == development
