# Releasing molt to PyPI

molt publishes to PyPI automatically when a GitHub Release is published, using
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) — no API
token is stored in the repo or in GitHub secrets.

## One-time PyPI setup

Do this once, before the first release:

1. Log in to <https://pypi.org>.
2. Go to your account → **Publishing** → **Add a pending publisher** (works
   even before the project exists on PyPI — the first release creates it):
   - **PyPI Project Name:** `molt-audit`
   - **Owner:** `DhairyaShah981`
   - **Repository name:** `molt`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
3. In the GitHub repo, create an **Environment** named `pypi`
   (Settings → Environments → New environment). No secrets needed.

## Cutting a release

```bash
# 1. bump the version in pyproject.toml AND molt/__init__.py (must match)
# 2. update CHANGELOG.md
# 3. tag + release — the workflow verifies tag == molt.__version__, runs the
#    full test + eval suite, builds, and publishes on green.
gh release create vX.Y.Z --title "vX.Y.Z — ..." --notes "..."
```

`/ship` already does steps 1-2 and the tag/release. The `publish.yml` workflow
does the rest. If tag and `molt.__version__` disagree, or tests fail, the
publish job never runs.

## Manual fallback (if trusted publishing isn't set up yet)

```bash
python -m build
python -m twine upload dist/*   # needs a PyPI token in ~/.pypirc or $TWINE_PASSWORD
```
