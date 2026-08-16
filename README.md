# pyspace-minimal

Generic GCP Cloud Functions (1st gen, Python) Flask host. `main.py`
owns no routes or business logic - it dynamically loads whichever
routers `routers.yaml` declares (each one just a Python module
exposing `register(app)`) and mounts them, then hands
functions-framework a fallback function to use as its required target.

## Adding/pinning routers

Router source is fetched with the [`repo`](https://gerrit.googlesource.com/git-repo)
multi-repo tool, driven by `manifest/default.xml`. Install it once:

```
mkdir -p ~/.bin
export PATH="${HOME}/.bin:${PATH}"
curl https://storage.googleapis.com/git-repo-downloads/repo > ~/.bin/repo
chmod a+rx ~/.bin/repo
```

Then, from this repo's root:

```
tools/sync-routers.sh
```

This fetches every project `manifest/default.xml` declares into the
`path` given there (e.g. `routers/gcp-python-function-inspector`),
merges each one's own `requirements.txt` into this repo's, and leaves
the result ready for `routers.yaml` to import. Add a new router by
adding a `<project>` to the manifest and a matching entry to
`routers.yaml` (`path`, `module`, and optionally `mount` - a URL
prefix, default `/`).

`.github/actions/sync-routers` wraps the same flow for CI, including
per-router revision overrides (`revision-overrides` input) without
editing the checked-in manifest - see
`xd-dash/huram-abi`'s `deploy-runtime-introspection` workflow for how
it's used to deploy this as a Cloud Function.

## Running locally

```
tools/sync-routers.sh
pip install -r requirements.txt
functions-framework --target=main --source=main.py
```

Or run `python3 tools/check_routers.py` for a faster check that every
router still imports and registers without colliding, without needing
a live server.
