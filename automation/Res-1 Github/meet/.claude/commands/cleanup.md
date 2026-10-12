Scan the target folder (ask which one if it's not obvious from context — the whole repo? a specific project like AC_Automation/? just the current working folder?) for files that are safe to delete and propose a cleaner organization. Do this:

1. Read CLAUDE.md (root, plus any subfolder CLAUDE.md relevant to the target) first, for the existing folder map, naming conventions, and hard rules about what must never be touched.

2. Identify candidates in three categories, noting path / category / one-line reason / size / last-modified date for each:
   - **Junk**: `__pycache__/`, `*.pyc`, `.DS_Store`, `Thumbs.db`, leftover temp/debug files (`debug_*.txt`, `*_test_log*.txt`, `*.tmp`), stray one-off screenshots.
   - **Superseded files**: multiple drafts/versions of the same script or note where a newer one clearly replaces an older one — actually open and compare both, never guess from filenames alone.
   - **Dead code**: files or functions nothing else references — grep the whole repo to confirm before flagging anything, never guess.

3. Never flag `.env` files, credentials, secrets, or anything matching the project's gitignore secret patterns — these are always off-limits, don't even list them as candidates. Files containing real client/financial data (e.g. generated Excel logs) can be flagged for archiving if genuinely stale, but never for deletion, and never read their contents.

4. Propose a folder structure that fits the project's existing conventions — only restructure what's actually messy, don't reinvent things that already work.

5. Present the full candidate list (grouped by category) and the proposed structure changes as a clear plan. State plainly that nothing has been touched yet. Wait for approval.

6. Handle the response: full approval → proceed. Modified instructions ("keep this one", "call it X instead", "also delete Y") → incorporate the changes and restate the plan before proceeding if the changes are substantial. Rejection → stop, no changes made.

7. Only after explicit approval, delete/move/rename exactly what was approved. Never touch git (no commits, no `git rm` — version control stays with the user). Never act on anything that wasn't explicitly approved, even if it looks obviously safe.

8. Report exactly what was deleted and what was moved/created, as a plain list, not prose.
