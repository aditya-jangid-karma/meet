---
name: session-start
description: "Orient at the start of a work session with a lean, plain-English briefing built from HOTcontext — Project / Last session / Current state / Next steps / Open items — plus a short 'what changed since last session'. Use when the user starts or resumes work, or says 'brief me', 'where were we', 'orient me', 'catch me up', 'what's next', 'start session', '/session-start'. Reads HOTcontext (already auto-loaded by the SessionStart hook) and does NOT read handoff files. Allied context files are loaded ONLY when a task actually needs them."
---

# /session-start — Lean orientation for a new session

## What this skill is

The lean replacement for the old `/resume` flow. It gets you oriented at the start of a session **without** dragging a fat handoff note into context. Your `HOTcontext.md` is already auto-loaded by the SessionStart hook, so this skill mostly *reads what's already there* and turns it into a plain-English briefing for a non-engineer reader.

## Step 0 — Find the right context folder (works in BOTH layouts)

Two folder layouts are supported. Resolve `<CONTEXT>` **before** doing anything else:

- **Root layout** (this harness) — `context/HOTcontext.md` sits in the project root.
- **Per-automation layout** (e.g. `Desktop\Res1`) — the root holds several
  automation subfolders, and **each one has its own**
  `<subfolder>/context/HOTcontext.md`. There is no root-level context folder.

Resolution order — stop at the first that matches:

1. `context/HOTcontext.md` exists in the project root → **root layout**.
   `<CONTEXT>` = `context/`.
2. Otherwise run **one** `Glob` for `*/context/HOTcontext.md` (one level down only —
   do not walk the whole tree):
   - **Exactly one match** → `<CONTEXT>` = that subfolder's `context/`.
   - **Several matches** → if the user already named an automation, or the file they
     mentioned lives inside one, use that. Otherwise **ASK which automation** they're
     working on, listing the subfolder names. Never guess, and never open more than
     one `HOTcontext.md`.
3. **No match** → say plainly that no context file was found, and offer to create
   `context/HOTcontext.md`. Don't invent one silently.

Everywhere below, `<CONTEXT>/` means the folder resolved here.

**Note on the hook:** the SessionStart hook auto-loads the **root layout's**
HOTcontext only. In the per-automation layout nothing may be pre-loaded — in that
case read the single resolved `<CONTEXT>/HOTcontext.md`, and nothing else.

## The one rule that keeps startup lean

> ⚠️ **LOAD ALLIED FILES ONLY WHEN NEEDED.**
> Work from `<CONTEXT>/HOTcontext.md` alone by default. Do **NOT** auto-read
> `todos.md`, `decisions.md`, or `architecture.md` at startup. Read one of them
> **only** when the actual task in front of you needs that depth (e.g. the user
> asks about the task list, or about *why* a past decision was made). Every file
> you read at startup is context you're spending — the whole point of this skill
> is to spend as little as possible.

## What to do

1. **Do NOT read handoff files.** Ignore anything under `handoffs/`. That is the old system and reading it is exactly the double-load this skill exists to avoid.

2. **Work from `<CONTEXT>/HOTcontext.md`** — resolved in Step 0. In the root layout it's already in context from the hook (no re-read needed unless it's missing); in the per-automation layout, read that one file.

3. **Give the plain-English briefing** — five short sections, bullet points, no jargon (the reader is an accountant, not an engineer):
   - **Project** — one line on what this project is.
   - **Last session** — read the `## Last session` line at the top of HOTcontext and say what the previous session did.
   - **Current state** — what's built, what works, what's broken (from HOTcontext's "Active now" / "Broken / blocked").
   - **Next steps** — the immediate items, highest priority first.
   - **Open items** — anything unresolved or waiting on the team.

4. **Show "what changed since last session"** — this comes straight from the `## Last session` line in HOTcontext. If that line is missing, say so plainly (it means the previous session didn't run `/session-end`).

5. **End by asking what they want to tackle.** Don't start work unprompted.

## When to pull in an allied file (on demand only)

- User asks about the task list, or "what's left" in detail → read `<CONTEXT>/todos.md`.
- User asks *why* something was decided, or the history behind a choice → read `<CONTEXT>/decisions.md`.
- User asks how a part is wired / where a file goes → read `<CONTEXT>/architecture.md`.

In each case, read the **one** file that answers the question — not all of them, and
only from the `<CONTEXT>` resolved in Step 0 (never another automation's copy).

## What this skill is NOT

- **Not `/resume`.** The global `/resume` still reads handoffs (double-load). Use this instead until the global one is retired.
- **Not a full file dump.** It briefs from HOTcontext; it does not pre-load the allied files "just in case."
- **Not where work starts.** It orients, then waits for the user's go.
