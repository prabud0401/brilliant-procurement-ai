# Agent run rules (short)

1. Read `AGENTS.md` first, then only the doc sections your prompt names. Do not read the whole repo history or unrelated docs.
2. One run = one task = one branch. Stay in the folders your prompt says you own.
3. Do not create cloud resources, call real Azure/OpenAI/Google/Odoo/Microsoft endpoints, or install global system packages. Python deps go in `services/backend/pyproject.toml` via `uv`.
4. No secrets anywhere in the repo, prompts output or logs. Use env var names.
5. Be efficient: do not over-explore; do not generate huge files (keep generated binaries such as PDFs/PNGs out of git unless the prompt says otherwise; commit the generator and small JSON instead).
6. Before finishing: `make lint`, `make test`, and `make test-int` when Postgres is available (start it with `docker compose up -d db` if needed). Fix failures. Then commit (conventional commits) and `git push -u origin <your-branch>`.
7. Final answer: a short report — files/areas changed, commit SHA(s), test counts (passed/failed), acceptance criteria checklist with yes/no, and anything left undone. No marketing language.
