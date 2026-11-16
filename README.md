# AIReview

Review Python changes in a React and TypeScript dashboard. Paste before and after versions to see a summary and findings limited to changed lines. Expand a finding to inspect its source line, rationale, and suggested correction. Accept, reject, or record a correction. Feedback persists in SQLite by default, with PostgreSQL supported through SQLAlchemy.

```sh
python -m pip install -r requirements.txt
python benchmark.py
python -m pytest -q
pnpm --dir web install --frozen-lockfile
pnpm --dir web run build
python -m uvicorn api:app --host 127.0.0.1 --port 8040
```

Open `http://127.0.0.1:8040`. Configure PostgreSQL with `DATABASE_URL=postgresql+psycopg://...`. The app stores review reports and feedback locally. The optional draft button submits rule metadata and line numbers to the configured provider (set `LLM_CHAT_URL`, `LLM_API_KEY`, and `LLM_MODEL`). It omits source snippets and reviewer notes. With the provider off, the AST review remains available.

## Verification

The deterministic analyzer matched **10 of 10** expected rule/line sets from curated positive and negative fixtures, including pre-existing issues, syntax errors, mutable defaults and exception handlers. The API test verifies correction validation and persisted feedback. The confidence labels distinguish direct syntax patterns from suggestions requiring judgment. The fixture does not measure broad reviewer agreement, LLM quality, or production PostgreSQL reliability. [Results](results.json)
