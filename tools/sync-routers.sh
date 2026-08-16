#!/usr/bin/env bash
# Fetches/pins every router declared in routers.yaml + manifest/default.xml
# via the `repo` multi-repo tool (https://gerrit.googlesource.com/git-repo),
# then merges each synced router's own requirements.txt (if any) into
# this repo's so the Cloud Functions buildpack installs their pip
# dependencies too. See .github/actions/sync-routers for the CI wrapper,
# which also supports per-router revision overrides.
#
# Needs `repo` on PATH:
#   mkdir -p ~/.bin && export PATH="${HOME}/.bin:${PATH}"
#   curl https://storage.googleapis.com/git-repo-downloads/repo > ~/.bin/repo
#   chmod a+rx ~/.bin/repo
# and network access to storage.googleapis.com (repo's launcher) and
# gerrit.googlesource.com (repo's implementation, fetched by the
# launcher on first run), on top of whatever remotes the manifest
# itself points at.
set -euo pipefail
cd "$(dirname "$0")/.."

MANIFEST="$(python3 -c "import yaml; print(yaml.safe_load(open('routers.yaml'))['manifest'])")"

repo init -u "$(pwd)" -m "$MANIFEST" --depth=1
repo sync -j4 --no-tags --optimized-fetch

python3 tools/merge_requirements.py
