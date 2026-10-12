---
name: hybrid-explain
description: Use when explaining code, scripts, config, commands, or any technical mechanism to the CPA/bookkeeping team (Sachin, Abhilasha, Dhruv, Aditya). Produces plain-English meaning AND the real code side by side, never one without the other.
---

# Hybrid explanation

The audience is intelligent and non-engineer. They are not learning to code —
they are learning to **read, trust, and audit** what has been built for them.

Two failure modes, equally bad:

- **Too soft.** Analogies only. They come away with a feeling, not a fact, and
  cannot check the file themselves.
- **Too hard.** Code dumped with jargon. They skim, nod, and quietly stop
  verifying — which is the one thing this project cannot afford.

Aim between the two. Every claim about behaviour should be traceable to a line
they can open and look at.

## The shape

**1. Lead with the one-sentence meaning.** What does this thing DO, in words
that would survive being repeated to a client. No code yet.

**2. Show the real code.** Quote it from the actual file, unedited, in a fenced
block. Never paraphrase code into pseudo-code — the point is that they can
match what they read here against what is on disk.

**3. Break the syntax down.** A `| Piece | Meaning |` table when there are 3+
unfamiliar bits, prose when there are 1-2. Explain the punctuation too: `$`,
`|`, `-not`, `..`, backticks. Punctuation is where non-engineers stall, and
nobody explains it because engineers stopped seeing it years ago.

**4. Say why it is written this way.** The alternative that was rejected, and
what went wrong when it was tried. This is what turns explanation into
judgement. "Parse JSON, don't regex" means nothing; "regex stopped at the first
quote mark and a delete command slipped past the guard" is unforgettable.

**5. Give the failure mode.** What breaks if this line is wrong, deleted, or
edited carelessly. They maintain this after the session ends.

## Rules

- **Analogy once, then drop it.** One good image (a guard at the door, a
  visitor log) anchors the concept. Repeating it past that point replaces
  understanding instead of building it.
- **Cite `file.ps1:47`, not "the logging bit".** They need to navigate.
- **Never say "just" or "simply".** If it were simple it would not need
  explaining.
- **Expand every acronym and every unfamiliar verb on first use** — JSON,
  stdout, parse, pipe, append, exit code.
- **Explain the intentional-looking oddities.** Padded spacing, a variable
  renamed to dodge a collision, a value built from two pieces. Anything that
  looks like a typo but is not, gets a sentence — otherwise someone
  "corrects" it later.
- **Do not re-teach what `Learnings.md` already covers.** Reference it and
  build forward. Check before explaining a concept from scratch.
- **State the verification.** End a change with how they confirm it worked
  themselves, without taking your word for it.

## Applies to

Hooks, PowerShell, JSON config, git, terminal commands, file structure,
Claude Code's own behaviour, and any automation built for the firm's close
and reconciliation work.
