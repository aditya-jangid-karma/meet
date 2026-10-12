---
name: resume
description: Use when starting a new session or resuming work on any project. Reads CLAUDE.md, memory, and the latest handoff note to catch you up on where things left off. Trigger whenever the user says "resume", "where did we leave off", "catch me up", "what were we working on", "let's continue", or starts a new conversation on a project that has handoff notes. Also trigger when the user says "read the handoff" or "read the claude.md".
---

# Resume — Pick Up Where You Left Off

Goal: In under 60 seconds of reading, the user knows exactly what this project is, where the last session ended, and what to do next.

## Step 1: Read Project Instructions (CLAUDE.md)

Read the CLAUDE.md file in the project root. This contains the project context, who the team is, folder structure, naming conventions, and hard rules. Always read this first — it orients you to the project and tells you how to behave.

If there are multiple CLAUDE.md files (e.g., in subfolders), read the root one first, then any subfolder ones relevant to the current work.

## Step 2: Read Memory

Read MEMORY.md from the user's memory directory. Then read each memory file it references. These contain:
- User profile (who they are, how to communicate)
- Feedback rules (things to always/never do)
- Project context (ongoing work, decisions, status)
- External references (where to find things)

Memory gives you the persistent context that carries across all sessions.

## Step 3: Find and Read the Latest Handoff

Search for handoff notes in these locations (check all, pick the most recent by date in the filename):
- `handoffs/` folder in project root or any subfolder
- Files matching `*handoff*` pattern anywhere in the project
- Files matching `YYYY-MM-DD_*.md` pattern in the project root or subfolders

Read the most recent one. If there are multiple projects with handoffs (e.g., AC_Automation and RSL_Automation in the same repo), identify which one is most relevant based on context, but mention all active projects briefly.

## Step 4: Present a Summary

Give the user a clear, plain-English summary with this structure:

1. **Project** — One line on what this project is (from CLAUDE.md)
2. **Last session** — What happened, when (from the handoff)
3. **Current state** — What's built, what's working, what's broken
4. **Next steps** — The immediate action items, ordered by priority
5. **Open items** — Anything unresolved or waiting on someone

Keep it concise — bullet points, not paragraphs. No jargon unless the user is technical. End by asking what the user wants to tackle.
