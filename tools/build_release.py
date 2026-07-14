#!/usr/bin/env python3
"""Synchronize Agent distributions, validate them, and build release archives."""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable


ROOT = Path(__file__).resolve().parents[1]
VERSION = "3.0.0"
DIST = ROOT / "dist"
CLAUDE_SKILL = ROOT / "skills" / "huodongxing-cli"
CANONICAL_FILES = (
    "SKILL.md",
    "agents/openai.yaml",
    "scripts/hdx",
    "scripts/hdx.py",
    "scripts/hdx_browser.py",
    "references/agent-adapters.md",
    "references/browser-bridge.md",
    "references/cli-reference.md",
    "references/data-model.md",
    "references/event-draft.md",
    "references/platform-map.md",
    "references/profile.example.json",
    "references/policy.example.json",
    "references/signup.example.json",
    "references/recommendation-framework.md",
    "references/registration-policy.md",
    "references/safety.md",
    "references/workflow-templates.md",
)


def canonical_sources() -> Dict[str, Path]:
    return {relative: ROOT / relative for relative in CANONICAL_FILES}


def sync_claude_skill() -> None:
    if CLAUDE_SKILL.exists():
        shutil.rmtree(CLAUDE_SKILL)
    for relative, source in canonical_sources().items():
        target = CLAUDE_SKILL / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def validate() -> None:
    errors = []
    for relative, source in canonical_sources().items():
        target = CLAUDE_SKILL / relative
        if not source.is_file():
            errors.append("missing canonical file: %s" % relative)
        elif not target.is_file():
            errors.append("missing Claude skill file: %s" % relative)
        elif not filecmp.cmp(source, target, shallow=False):
            errors.append("Claude skill copy differs: %s" % relative)

    try:
        plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append("invalid Claude manifest: %s" % exc)
    else:
        if plugin.get("version") != VERSION:
            errors.append("plugin version does not match %s" % VERSION)
        if marketplace.get("plugins", [{}])[0].get("name") != plugin.get("name"):
            errors.append("marketplace and plugin names differ")

    version_line = 'VERSION = "%s"' % VERSION
    if version_line not in (ROOT / "scripts/hdx.py").read_text(encoding="utf-8"):
        errors.append("CLI version does not match %s" % VERSION)

    if errors:
        raise RuntimeError("\n".join(errors))


def write_zip(path: Path, files: Iterable[tuple[Path, str]]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, archive_name in files:
            archive.write(source, archive_name)


def skill_files(prefix: str, include_openai: bool = True) -> list[tuple[Path, str]]:
    result = []
    for relative, source in canonical_sources().items():
        if not include_openai and relative == "agents/openai.yaml":
            continue
        result.append((source, "%s/%s" % (prefix, relative)))
    result.append((ROOT / "LICENSE", "%s/LICENSE" % prefix))
    return result


def build() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    write_zip(DIST / ("hdx-cli-%s.zip" % VERSION), (
        (ROOT / "scripts/hdx", "hdx"),
        (ROOT / "scripts/hdx.py", "hdx.py"),
        (ROOT / "scripts/hdx_browser.py", "hdx_browser.py"),
        (ROOT / "references/cli-reference.md", "cli-reference.md"),
        (ROOT / "references/browser-bridge.md", "browser-bridge.md"),
        (ROOT / "references/event-draft.md", "event-draft.md"),
        (ROOT / "LICENSE", "LICENSE"),
    ))
    write_zip(
        DIST / ("huodongxing-openclaw-skill-%s.zip" % VERSION),
        skill_files("huodongxing-cli", include_openai=False),
    )
    write_zip(
        DIST / ("huodongxing-codex-skill-%s.zip" % VERSION),
        skill_files("huodongxing-cli", include_openai=True),
    )

    claude_files = [
        (ROOT / ".claude-plugin/plugin.json", ".claude-plugin/plugin.json"),
        (ROOT / "LICENSE", "LICENSE"),
    ]
    for relative in CANONICAL_FILES:
        source = CLAUDE_SKILL / relative
        claude_files.append((source, "skills/huodongxing-cli/%s" % relative))
    write_zip(DIST / ("huodongxing-claude-code-plugin-%s.zip" % VERSION), claude_files)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate without changing files")
    args = parser.parse_args()
    try:
        if not args.check:
            sync_claude_skill()
        validate()
        if not args.check:
            build()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
