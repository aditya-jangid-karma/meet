---
name: cleanup
description: Use to find stale, dead, or junk files in a folder and propose a cleaner organization. Reviews for temp/debug artifacts, superseded drafts, and unreferenced code; proposes a folder structure; and only deletes or reorganizes after explicit approval. Trigger whenever the user says "clean up this folder", "organize the folder", "find dead files", "what can I delete", "declutter", or similar. Never deletes or moves anything without confirmation.
---

# Cleanup — Find Stale Files and Propose Organization

Goal: surface everything safe to remove or reorganize, get explicit sign-off, then execute exactly what was approved — never delete or move a single file before that sign-off.

## Step 0: Scope

Confirm which folder to clean if it's not obvious from context — the whole repo? a specific project subfolder (e.g. `AC_Automation/`)? just the current working directory? Ask if ambiguous rather than guessing.

## Step 1: Read Project Conventions

Read CLAUDE.md (root, plus any subfolder CLAUDE.md relevant to the target folder) for:
- The existing folder map and naming conventions
- Any hard rules about what must never be touched (secrets, `.env`, credential files, client-data files)

These rules override anything in this skill.

## Step 2: Scan for Candidates

Look across three categories. For each candidate, note: path, category, one-line reason, size, last-modified date.

**Junk / build artifacts** (safe by nature, low risk):
- `__pycache__/`, `*.pyc`, `.DS_Store`, `Thumbs.db`
- Temp/debug files this session or past sessions may have left behind (`debug_*.txt`, `*_test_log*.txt`, `*.tmp`, ad-hoc scratch scripts)
- Stray screenshots or exports clearly used for one-time debugging, not documentation

**Superseded files** (medium risk — verify before flagging):
- Multiple drafts/versions of the same script or note where a newer one has clearly replaced an older one. Actually open and compare both before claiming one supersedes the other — never guess from filenames alone.

**Dead code** (medium-high risk — verify before flagging):
- Functions, files, or scripts that nothing else imports, calls, or references. Grep the whole repo for the name before flagging anything as dead — a false positive here is worse than missing one.

**Always excluded, never even listed as a candidate:**
- `.env` files, credential/secret files, anything matching the project's gitignore secret patterns
- Any file containing real client/financial data (e.g. generated Excel logs) — these can be flagged for archiving/moving if genuinely stale, but never for deletion, and their contents should not be read in the process

## Step 3: Propose Structure

Only propose reorganizing what's actually messy relative to the project's own stated conventions (from Step 1) — don't invent a new structure for things that already fit. If there's no existing convention for a mess found, propose the smallest sensible fix.

## Step 4: Present and Wait

Show the full candidate list (grouped by category) and the proposed structure changes as a clear plan. Explicitly state nothing has been touched yet. Ask for approval.

Handle the response:
- **Full approval** → proceed to Step 5 as planned.
- **Partial approval / modifications** ("keep this one", "call the folder X instead", "also delete Y") → incorporate the changes, restate the updated plan, and confirm before proceeding if the changes are substantial.
- **Rejection** → stop, no changes made.

## Step 5: Execute

Only after explicit approval:
- Delete approved files
- Move/rename/create folders per the approved structure
- Never touch git (no `git rm`, no commits — the user handles version control themselves)
- Never delete or move anything that wasn't explicitly approved, even if it seems obviously junk

## Step 6: Confirm

Report exactly what was deleted and what was moved/created, with final paths. Keep it as a plain list, not prose.
