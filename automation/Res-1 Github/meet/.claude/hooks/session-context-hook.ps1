# SessionStart hook — loads the live HOTcontext.md for whichever folder
# layout this project uses:
#
#   Root layout            <project>\context\HOTcontext.md          (the harness)
#   Per-automation layout  <project>\<automation>\context\HOTcontext.md   (e.g. Res1)
#
# Mirrors "Step 0" in the session-start / session-end skills. When several
# automations are found it prints only their NAMES, never their contents —
# loading every automation's context at startup is the waste this avoids.
#
# Always exits 0: a startup hook must never be able to block a session.

# The context files contain em dashes, arrows and ticks. Two separate encoding
# traps, and BOTH have to be handled or they arrive as mojibake ("â€”"):
#   reading  — PowerShell 5.1's Get-Content defaults to ANSI on a file with no
#              BOM, so every Get-Content below passes -Encoding UTF8.
#   writing  — stdout is emitted in the console codepage unless we force UTF-8.
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$INPUT_JSON = [Console]::In.ReadToEnd()

$PROJECT_DIR = $env:CLAUDE_PROJECT_DIR

if (-not $PROJECT_DIR) {
    # Fall back to the payload's cwd, then to wherever we were launched.
    try {
        $DATA = $INPUT_JSON | ConvertFrom-Json
        $PROJECT_DIR = $DATA.cwd
    } catch {
        $PROJECT_DIR = $null
    }
}
if (-not $PROJECT_DIR) { $PROJECT_DIR = (Get-Location).Path }

# Emits the loaded context wrapped in markers, followed by a short instruction
# block telling Claude how to brief the user WITHOUT anyone having typed
# /session-start. The context body between the markers is byte-for-byte the
# same file content the old hook printed; only the surrounding envelope is new
# (a deliberate, user-approved break from the S25 "byte-identical" rule). The
# briefing FORMAT is NOT restated here — this points at the session-start skill
# so the two can never drift.
function Write-BriefingBlock($HotPath, $ContextPath, $HeaderLine) {
    Write-Output "===== PROJECT CONTEXT (auto-loaded; /session-start was NOT required) ====="
    if ($HeaderLine) { Write-Output $HeaderLine }
    Write-Output "<<< BEGIN HOTcontext >>>"
    Get-Content -Raw -Encoding UTF8 $HotPath
    Write-Output "<<< END HOTcontext >>>"
    Write-Output ""
    Write-Output "HOW TO USE THIS ON YOUR FIRST REPLY:"
    Write-Output "- If the user's first message is a greeting or vague (e.g. 'hi', 'where were we?'),"
    Write-Output "  give the FULL briefing - follow the session-start skill exactly."
    Write-Output "- Otherwise: open with a 3-4 line orientation (last session + anything"
    Write-Output "  broken / blocked / awaiting a decision), then go straight to the task."
    Write-Output ""
    Write-Output "RULES:"
    Write-Output "- Never state status from memory - read the file or ask."
    Write-Output "- Context folder: $ContextPath"
    Write-Output "- Hook that produced this: $PSCommandPath"
    Write-Output "- On-demand only, do NOT auto-read: architecture.md, decisions.md, todos.md"
    Write-Output "  (in that folder) - open one only when the task needs it."
    Write-Output "========================================================================="
}

# 1. Root layout - load the file, then wrap it with the briefing instructions.
#
# WHERE IS "context"? Ask REPO_MAP.md first, fall back to the convention.
# REPO_MAP.md may carry a machine-readable marker line:
#     <!-- harness:context-dir = context -->
# so a repo whose context folder is named something else (notes\, docs\, ...)
# is still found, and the human-readable map and the hook cannot drift apart.
#
# NAME DELIBERATE: $CTX_HIT, not $MATCHES. PowerShell owns the automatic
# variable $Matches and refills it on every -match comparison - the same trap
# documented for $FOUND below and in Learnings.md. ($CTX_HIT.Matches is a
# PROPERTY of Select-String's MatchInfo object and is safe; the danger is only
# in naming one of OUR OWN variables $MATCHES.)
$CTX_NAME = "context"
$REPO_MAP = Join-Path $PROJECT_DIR "REPO_MAP.md"
if (Test-Path $REPO_MAP) {
    try {
        $CTX_HIT = Select-String -Path $REPO_MAP -Encoding UTF8 -Pattern 'harness:context-dir\s*=\s*([^\s>]+)' | Select-Object -First 1
        if ($CTX_HIT) {
            $CANDIDATE = $CTX_HIT.Matches[0].Groups[1].Value
            # Only trust the marker if that folder actually exists. A stale
            # marker must never be able to take the briefing down with it.
            if (Test-Path (Join-Path $PROJECT_DIR $CANDIDATE)) {
                $CTX_NAME = $CANDIDATE
            }
        }
    } catch {
        # Unreadable or malformed map: keep the convention. Fail open, always.
    }
}

$ROOT_HOT = Join-Path $PROJECT_DIR "$CTX_NAME\HOTcontext.md"
if (Test-Path $ROOT_HOT) {
    Write-BriefingBlock -HotPath $ROOT_HOT -ContextPath (Join-Path $PROJECT_DIR $CTX_NAME) -HeaderLine $null
    exit 0
}

# 2. Per-automation layout — look ONE level down only.
#
# NAME DELIBERATE: this list is $FOUND, not $MATCHES. PowerShell owns the
# automatic variable $Matches and refills it on every -match comparison; names
# are case-insensitive, so $MATCHES would be the SAME box. Any -match added
# above the checks below would silently replace the folder list with a
# hashtable, .Count would become 1, and the hook would load the wrong
# automation with no error. Same trap as $MATCH -> $MATCHED_PATTERN in
# Learnings.md. Do not rename this back.
$FOUND = @()
try {
    $FOUND = Get-ChildItem -Path $PROJECT_DIR -Directory -ErrorAction Stop |
        Where-Object { $_.Name -notlike ".*" -and $_.Name -ne "node_modules" } |
        Where-Object { Test-Path (Join-Path $_.FullName "context\HOTcontext.md") }
} catch {
    $FOUND = @()
}

if ($FOUND.Count -eq 1) {
    $AUTOMATION = $FOUND[0].Name
    $AUTO_HOT = Join-Path $FOUND[0].FullName "context\HOTcontext.md"
    Write-BriefingBlock -HotPath $AUTO_HOT -ContextPath (Join-Path $FOUND[0].FullName "context") -HeaderLine "HOT context for automation [$AUTOMATION] ($AUTO_HOT):"
    exit 0
}

if ($FOUND.Count -gt 1) {
    $NAMES = ($FOUND | ForEach-Object { $_.Name }) -join ", "
    Write-Output "This project uses the per-automation context layout. Automations with their own context: $NAMES"
    Write-Output "No HOTcontext has been loaded yet. ASK the user which automation they are working on, then read only that one: <automation>\context\HOTcontext.md"
    Write-Output "- Hook that produced this: $PSCommandPath"
    exit 0
}

# 3. Nothing found.
Write-Output "No context\HOTcontext.md was found in $PROJECT_DIR or one level below it. Tell the user plainly and ask before creating one."
Write-Output "- Hook that produced this: $PSCommandPath"
exit 0
