---
name: handoff
description: Use at the end of a work session to write a standardized handoff note that captures everything the next session needs to know. Trigger whenever the user says "handoff", "write a handoff", "save handoff", "session summary", "wrap up", "end session", "pause the session", "update the handoff", or "let's stop here". Also use when the user is clearly done working and needs a record of what happened.
---

# Handoff — End-of-Session Note

Goal: Write a note so complete that a brand-new session (or a different team member) can read it cold and pick up exactly where this session left off — no guessing, no re-reading code.

## Step 1: Gather Context

Before writing, collect this information:
- What was done in this session (files created, edited, bugs fixed, features added)
- Current state of all key project files (what works, what doesn't, what changed)
- Read CLAUDE.md for naming conventions and folder structure
- If a previous handoff exists, read it to get the session number and maintain continuity
- Any rules discovered or reinforced during this session

## Step 2: Write the Handoff

Use this template — every section matters, do not skip any:

```
# Handoff — [Short phrase describing the session's main outcome]

**Date:** YYYY-MM-DD (Session N)
**Session focus:** [One sentence — what was the main goal and was it achieved]

---

## 1. What happened this session

[For each significant change, use a subheading and 2-3 sentences explaining what changed and why. Include enough detail that someone reading this without any context understands the change. If a bug was fixed, explain what caused it and how it was fixed.]

## 2. Current state of files

| File | Status |
|---|---|
| `filename.py` | **CREATED** / **UPDATED** / Unchanged / Safe to delete — [brief note] |

[Include every file that's part of the project, not just ones that changed. This is the source of truth for what exists and what shape it's in.]

## 3. What still needs to happen

### Must do
- [Immediate next steps — things that block progress]

### Nice to have
- [Lower priority items, user requests that aren't urgent]

## 4. Important rules

- [List every hard rule that applies to this project]
- [Include rules from CLAUDE.md plus any discovered during sessions]
- [These protect the next session from making mistakes we already made]
```

## Step 3: Determine Session Number

Look at the previous handoff's session number and increment by 1. If no previous handoff exists, this is Session 1.

## Step 4: Save the File

Follow the project's naming convention:
- Filename format: `YYYY-MM-DD_session-N-handoff.md` (use today's date and the session number)
- Save to the project's `handoffs/` folder if one exists
- If no `handoffs/` folder exists, save to the project root
- If the project has subfolders (like `AC_Automation/`), save alongside the previous handoffs in whichever location they were stored

## Step 5: Confirm

Tell the user:
- Where the file was saved (exact path)
- A 1-2 sentence summary of what's in it
