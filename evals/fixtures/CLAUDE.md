# Project rules

- Never use `pip install` directly; always use `uv pip` instead.
- Always run `pytest -q` before committing.
- Use `rg` instead of `grep` for searching.
- Deploy docs with `netlify deploy --prod`.
- Never commit `.env` files or secrets.
- Prefer `docker compose` over `docker-compose`.
- Always update `CHANGELOG.md` after each feature.
