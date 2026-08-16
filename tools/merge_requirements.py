"""Appends each router directory's own requirements.txt (if any) into
this repo's requirements.txt, deduped - so the Cloud Functions
buildpack installs their pip dependencies too. Run after
tools/sync-routers.sh's `repo sync` step, once each router's actual
code (and requirements.txt) exists on disk.
"""
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> None:
    config = yaml.safe_load((ROOT / "routers.yaml").read_text()) or {}

    base_path = ROOT / "requirements.txt"
    lines = [line.strip() for line in base_path.read_text().splitlines() if line.strip()]
    seen = set(lines)

    for entry in config.get("routers", []):
        router_requirements = ROOT / entry["path"] / "requirements.txt"
        if not router_requirements.exists():
            continue
        for line in router_requirements.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and line not in seen:
                lines.append(line)
                seen.add(line)

    base_path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
