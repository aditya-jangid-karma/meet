# PreToolUse guard - two tiers, both read from config/harness.config.json:
#
#   hardBlockPatterns        -> BLOCK the command with exit code 2. A narrow
#                               list of genuinely destructive commands. Claude
#                               Code documents exit 2 as the block that takes
#                               absolute precedence (a JSON "allow" cannot
#                               override it), so it is our best chance of biting
#                               even when Claude runs in bypassPermissions mode.
#   approvalRequiredPatterns -> ASK for confirmation (permissionDecision "ask").
#                               A broad list. In bypass / auto-accept modes an
#                               "ask" is auto-approved, so treat this tier as a
#                               convenience prompt in default mode, not a guard.
#
# The hard-block list is checked FIRST, so "rm -rf x" is blocked outright while
# a plain "rm x.txt" only asks.
#
# Parse the payload as JSON, never regex: a regex stops at the first quote, so
# 'Write-Output "hi"; Remove-Item x' would be read as 'Write-Output "hi"' and
# the dangerous half would never be inspected.

$INPUT_JSON = [Console]::In.ReadToEnd()

try {
    $DATA = $INPUT_JSON | ConvertFrom-Json
} catch {
    exit 0
}

$TOOL_NAME = $DATA.tool_name
$COMMAND   = $DATA.tool_input.command
if (-not $COMMAND) { exit 0 }

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$CONFIG     = Get-Content -Raw -Encoding UTF8 "$SCRIPT_DIR\..\config\harness.config.json" | ConvertFrom-Json
$HARD       = $CONFIG.hardBlockPatterns
$ASK        = $CONFIG.approvalRequiredPatterns

# Shared log setup. We log the decision here (not only in the PostToolUse
# logger) because a blocked or declined command never reaches PostToolUse:
#   BLOCKED         -> hard-blocked, never ran
#   ASKED then RAN  -> approved
#   ASKED, no RAN   -> declined
$LOG_DIR = "$SCRIPT_DIR\..\logs"
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}
$SESSION = "--------"
if ($DATA.session_id) {
    $SESSION = $DATA.session_id.Substring(0, [Math]::Min(8, $DATA.session_id.Length))
}
$FLAT     = ($COMMAND -replace "`r?`n", " ")
$STAMP    = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$LOG_FILE = "$LOG_DIR\$(Get-Date -Format 'yyyy-MM-dd').log"

# TIER 1 - hard block via exit code 2 (checked first). Patterns here are
# REGEX, matched with -match (case-insensitive, order-independent) - NOT
# literal substrings - so "Remove-Item x -Recurse" is caught no matter where
# the path and flags sit between the verb and the flag. NAME DELIBERATE:
# $pattern, never $MATCHES - PowerShell owns the automatic $Matches variable.
# The -match is wrapped so a malformed pattern skips instead of crashing the
# hook (the ASK tier below still backstops rm / Remove-Item / del).
foreach ($pattern in $HARD) {
    try { $HIT = ($COMMAND -match $pattern) } catch { $HIT = $false }
    if ($HIT) {
        Add-Content -Path $LOG_FILE `
            -Value "$STAMP | $SESSION | BLOCKED | $TOOL_NAME | $FLAT | matched=$pattern"
        [Console]::Error.WriteLine("Harness HARD-BLOCK: this command matches a hard-block rule in config/harness.config.json. It was NOT run - run it by hand if you truly intend to.")
        exit 2
    }
}

# TIER 2 - ask for confirmation via permissionDecision "ask". Patterns here are
# also REGEX now (matched with -match), anchored so a delete verb only triggers
# when it is actually being RUN (command start, or after a ; | & separator) -
# NOT when the word merely appears inside a quoted string being printed or
# searched. NAME DELIBERATE: $pattern / $ASKHIT, never $MATCHES.
foreach ($pattern in $ASK) {
    try { $ASKHIT = ($COMMAND -match $pattern) } catch { $ASKHIT = $false }
    if ($ASKHIT) {
        Add-Content -Path $LOG_FILE `
            -Value "$STAMP | $SESSION | ASKED   | $TOOL_NAME | $FLAT | matched=$pattern"
        $RESPONSE = @{
            hookSpecificOutput = @{
                hookEventName            = "PreToolUse"
                permissionDecision       = "ask"
                permissionDecisionReason = "Harness check: this command matches a delete/remove rule on the approval list in config/harness.config.json. Approve only if you meant to run it."
            }
        }
        $RESPONSE | ConvertTo-Json -Depth 5 -Compress
        exit 0
    }
}

exit 0