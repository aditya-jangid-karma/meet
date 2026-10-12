# CLAUDE.md — Team D's personal Automations Folder(Repo)

---

# Purpose/ Who this is for

You are helping **Team D** the external CPA / bookkeeping firm. The team includes Puneet, Dhruv, Manish, Vijayesh. They are NOT engineers. Default to plain English, walk through any non-trivial command, and reference exact file paths so they can navigate.

Their primary work:
- Monthly close of books and other accounting tasks
- Cross-validation of output generated through any automation vs actual output
- Bank reconciliation, AR/AP aging, GL coding
- Drafting automation for repetitive accounting tasks

---

## Where you are (orient yourself)

Always read first
Before any task, read `context/HOTcontext.md` — current status, blockers, next steps.

Folder map

| Folder | What goes here |
|---|---|
| `notes/` | Markdown notes — session close summaries, meeting notes, observations |
| `automation/` | Python scripts, Excel templates, automation drafts |

Each folder needs to have its own "README" with format and naming conventions. In the "README" write in the explanatory manner; all the technical aspects of the project
including the python libraries used and other technical aspect or feature used in the automation. Include everything that is necessary for a CPA/CA to understand the codebase and related files and maintain the automation for longer time. 

## Naming conventions (match Rio's documentation system)

- **Date-prefixed:** `YYYY-MM-DD_short-slug.md` (e.g., `2026-05-15_april-close-summary.md`)(short slug - maximum of 4 words)
- **Period-specific validation:** `YYYY-MM_what-was-compared.md` (e.g., `2026-03_pnl-rio-vs-qbo.md`)
- **Tenant-specific:** never put full PII in filenames, reference by unit number or pseudonym

---


## Hard rules

1. **NEVER advise to commit secrets and guide user with what needs to be pushed and what to be given other way round(manually)** — API keys, passwords, tokens, .env files, FCCB credentials, QBO secrets, AppFolio passwords. The `.gitignore` blocks the common patterns but stay alert.
2. **NEVER access Terminal/Powershell directly without explicit permissions** (ask user first for that specific tasks)
3. **Never read `.env`, `*.env`, `.env.*`, or the `.env` folder into context.** If a secret is needed, ask me to supply the value directly — never open the file. (The hook enforcing this isn't built yet, so this instruction is the guard for now.)
-  Each project's `context/HOTcontext.md` stays UNDER 50 lines.
- Work one small step at a time; explain WHY / WHAT / RISK / HOW TO VERIFY; wait for confirmation before risky or destructive actions.
- Never overwrite or delete important files without approval. (Ask for permissions to read/edit in such files from the user.)
4. **Git is ENABLED but gated.** *(relaxed 2026-09-04 — replaces the old "NO git actions / LOCAL-ONLY" rule)*
- Claude MAY run **read-only** git commands (`status`, `log`, `diff`, `remote -v`, `branch --list`, `show`) once terminal permission is granted for the session.
- Claude MAY **propose** write actions (`add` by explicit path, `commit`, `checkout -b`, `push` to a feature branch) but must state WHY / WHAT / RISK / HOW TO VERIFY and get explicit approval **each time**.
- **Never** `git add -A`, `git add .`, or `git add -u`. Stage by explicit path only. One commit = one idea.
- **Never** force-push, `git reset --hard`, `git clean -fd`, or rewrite already-pushed history.
- **Never** push to `main` / `master`. The guard at `.git\hooks\pre-push` blocks it; work goes on a feature branch and ships via PR.
- Hard rule #1 still governs: nothing containing keys, credentials, or real vendor/property names gets staged.

5. **Announce before committing; ask again before pushing.** *(added 2026-09-04)*
- Before ANY commit, Claude must tell the user in plain English: **(a)** the exact file paths going in, **(b)** the branch they will land on, **(c)** the proposed commit message, and **(d)** why those files belong together as ONE commit. Only after the user confirms does the commit run.
- **Pushing is a separate permission.** After a commit lands, Claude must ask again before `git push`. Never treat one approval as covering both — "yes, commit" is not "yes, push".
- If Claude is unsure whether a file belongs in the commit, it stays OUT and gets raised with the user rather than swept in.

---

## Soft rules / recommendations

- When something looks production-worthy (a script, a workflow, a doc), drop it in `handoffs/` and tell the user to ping Puneet or Manish.
- When unsure, ask before acting.
- When asked for something complex, walk through plain English first, code second(MUST REMEMBER).
- Revert to sonnet or release sonnet agent where task feels like a cron job or non trivial task. Well manage yourself between Opus and Sonnet for proper work execution.
- Literally release a sonnet or hiaku agent for non complex or non trivial tasks and keep the main context window clean. 
----

