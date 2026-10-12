Write an end-of-session handoff note. Gather what was done this session (files created, edited, bugs fixed), check the current state of project files, and read CLAUDE.md for naming conventions. If a previous handoff exists, read it for session number continuity.

Use this structure:

# Handoff — [Short phrase describing the session outcome]
**Date:** YYYY-MM-DD (Session N)
**Session focus:** [One sentence]

## 1. What happened this session
[Subheading per change, 2-3 sentences each with enough detail for someone reading cold]

## 2. Current state of files
[Table: File | Status (CREATED/UPDATED/Unchanged/Safe to delete)]

## 3. What still needs to happen
### Must do
### Nice to have

## 4. Important rules
[Every hard rule — from CLAUDE.md plus any discovered during sessions]

Save as `YYYY-MM-DD_session-N-handoff.md` in the project's `handoffs/` folder (or project root if no handoffs folder exists). Tell me where it was saved.
