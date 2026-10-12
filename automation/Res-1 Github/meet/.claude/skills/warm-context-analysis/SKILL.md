---
name: warm-context-analysis
description: "Honest verdict on whether THIS session's accumulated context is still helping or has started hurting — and whether to save state and start fresh. Use when the user asks 'is my context helping or hurting', 'should I restart', 'is this session still good', 'am I degrading', 'fresh session?', 'should I keep going or start over', '/warm-context-analysis', or any time they're deciding whether to keep working in the current session vs. start clean. Also self-fire when you catch your OWN concrete degradation mid-session (you lost recall of something established earlier, the user corrected your analysis, you broke a standing rule you know). Reads the live context % AND the concrete degradation signals (not the number alone), gives a plain-English helping/hurting verdict, and — only if genuinely hurting — walks through saving state and restarting. It is equally a guard AGAINST restarting too early: a percentage under ~80% with no degradation is a 'keep going', not a 'restart'."
---

# /warm-context-analysis — Is This Session Helping or Hurting?

## What this skill is

A repeatable diagnostic for the question *"is my current context helping or hurting — should I save state and start fresh?"* It codifies the answer so the call is made on evidence, not on a gut feeling about how "full" the session looks.

It produces one of three verdicts — **HELPING** (keep going), **WATCH** (a signal or two, not yet time), **HURTING** (save state + restart now) — and, when the verdict is HURTING, it walks the user through saving the session's state into the context files before starting a fresh session, so nothing is lost.

## The one idea that makes this skill correct

**The context percentage is NOT the trigger. Concrete degradation is.**

A productive session can run well into the ~70% range — that is normal working territory, not a warning. The failure mode this skill prevents runs in *both* directions:

- **False HURTING** — recommending a restart at 60–75% just because the number "feels high." This throws away a warm, accurate, in-context session and forces a cold restart that has to re-learn everything. Expensive and wrong.
- **False HELPING** — pushing on at 90%+ while quietly producing degraded work (forgetting earlier decisions, getting corrected) because "we're not at 100% yet."

So the verdict leans on **what the session is actually doing**, with the percentage as a secondary modifier. A clean session at 78% keeps going. A session that just forgot a decision it made an hour ago should restart at 45%.

## When to fire

**Explicit (the user asks):**
- "is my context helping or hurting" / "should I restart"
- "is this session still good" / "am I degrading" / "fresh session?"
- "should I keep going or start over"
- "/warm-context-analysis"

**Self-fire (you catch your own degradation):** If mid-work you notice a concrete signal below — you couldn't recall something from earlier in this very session, the user corrected your analysis, you caught yourself breaking a standing rule (dropped plain English, skipped the WHY/WHAT/RISK/verify format, jumped ahead without confirmation) — run this diagnostic proactively and surface the verdict. Do not silently push through degradation. This is the one case where firing without being asked is correct, because a degrading session can't be trusted to notice on its own unless it's looking.

**Do NOT fire** on the percentage alone. A number ticking up is not a trigger. The user glancing at "73%" is not a trigger. Wait for them to ask, or for a concrete signal.

## The degradation signals (this is the evidence)

Walk these honestly. Each is a yes/no you can actually check against this conversation — not a feeling.

1. **Recall miss.** Did you recently fail to recall something established earlier *in this session* — a decision, a file path, a number the user gave you — and have to be reminded or re-derive it? This is the strongest single signal. One real recall miss outweighs any percentage.

2. **User correction.** Has the user (or a fresher session) had to correct your analysis because you were working from a stale or confused read? If less-loaded reasoning is catching your errors, your context has become a liability, not an asset.

3. **Quality slip / standing-rule violation.** Are you starting to break rules you know cold — explaining in jargon instead of plain English, skipping the WHY/WHAT/RISK/verify explanation, jumping ahead without waiting for confirmation, forgetting the "never read `.env`" rule? Rule-drift under load is an early degradation tell.

4. **Tool-result truncation / compression.** Are tool results coming back truncated, or is the harness visibly compressing/summarizing earlier messages? That's the harness telling you the window is genuinely full.

5. **Thread sprawl.** Has the session wandered across many unrelated topics so the *active* task is buried? Sprawl dilutes attention even when raw recall is intact.

**Counter-signals (evidence the session is still an asset — name these too):**
- Accurate recall of earlier decisions and file paths when you reach for them.
- Warm project context the session built up that a restart would have to rebuild.
- The active thread is coherent and on one task.
- Recent outputs were correct and uncorrected.

A restart throws the counter-signals away. That cost is real and goes in the verdict.

## The percentage band (secondary modifier, never the trigger)

Use the native context meter to *modulate* the verdict, not to make it:

| Band | Meaning for the verdict |
|---|---|
| **< 80%** | Working territory. Verdict rides almost entirely on the signals. No signals → HELPING, full stop. Never recommend restart here on the number alone. |
| **80–88%** | Soft zone. One real signal is enough to move from WATCH → HURTING. Still fine with zero signals. |
| **88–92%** | Pressure zone. Lean toward restarting on any signal; even sprawl alone justifies WATCH→HURTING. |
| **> 92%** | Force zone. Restart regardless — the window is near full and quality will degrade whether or not you've noticed yet. |

## Output format (target: < 250 words)

```
**Verdict: HELPING / WATCH / HURTING**

**Context:** {N}% used — {band: working / soft / pressure / force}

**Degradation signals:**
- {signal that fired, with the concrete evidence} — or "None observed."

**Counter-signals (what a restart would cost):**
- {warm context / accurate recall / coherent thread that would be lost}

**Why:** {1–2 sentences tying signals + band to the verdict — the honest call.}

**Recommendation:** {Keep going. / Keep going, but watch for {X}. / Save state and start fresh — steps below.}
```

If HELPING, stop after the block. Do not start a restart.
If HURTING, state that you're proceeding to the save-and-restart steps below, then do it.

## If the verdict is HURTING — carry it through

Don't just recommend it and wait. But respect the gate: saving state and restarting is a real move, so confirm once, then execute.

1. **Confirm once (single line).** `"Verdict is HURTING — {one-line why}. Save state and start a fresh session. Go?"` Wait for the user's go. (If they self-invoked with an explicit "yes, restart," skip the confirm.)

2. **Save the session's state.** Before anything closes, make sure what this session learned survives into the project's context files — update `context/HOTcontext.md` (current status, blockers, next step) and any allied file that changed (`decisions.md`, `todos.md`), or run the project's end-of-session flow. The goal: a fresh session can pick up exactly where this one left off with nothing lost.

3. **Start fresh and re-orient.** The user opens a new session and runs `/resume` so the fresh session loads the saved state. Confirm the new session came up with the right context before continuing the work.

## What this skill is NOT

- **Not a context-trimmer.** It doesn't compact or summarize to free space. It decides keep-vs-restart. (If staying, the session just keeps working as-is.)
- **Not a re-orientation tool.** If the user is *lost* ("where were we?") rather than the session being *degraded*, just re-read the context files — don't restart a healthy session.
- **Not an auto-restarter below the force band.** It never restarts a < 80% session on the number. Restarting is gated on signals (or > 92%) and the user's go.
- **Not a nag.** It does not fire on the percentage alone and does not nudge toward restart inside the working band. Silence is the correct output when nothing has degraded.

## Failure modes to avoid

- **Recommending restart on the number alone.** The cardinal error. Under 80% with no signals is always HELPING.
- **Pushing through real degradation because "we're only at 80%."** A recall miss at 45% still means restart. Signals beat the band downward as well as upward.
- **Padding the signal list.** If nothing degraded, write "None observed." Don't manufacture a signal to justify a verdict.
- **Recommending restart, then stopping.** If HURTING and the user says go, carry it through — save state, then confirm the fresh session came up right.
- **Restarting without saving state first.** A restart that skips step 2 loses everything the session learned. Save first, always.
- **Self-grading the session's *output quality* as a proxy for context health.** "The work has been good" is a counter-signal, not proof of health — recall misses can coexist with good recent output. Check the signals directly.

## Anti-pattern check before output

- [ ] Verdict is driven by concrete signals, not the percentage
- [ ] Both degradation signals AND counter-signals were weighed
- [ ] If verdict is HELPING, no restart is started
- [ ] If verdict is HURTING, state is saved into the context files BEFORE restarting
- [ ] Output is honest — no manufactured signals, no padding
