# PostToolUse logger — records every tool call that actually RAN.
# Blocked calls never reach PostToolUse, so each blocking hook writes its
# own BLOCKED line. See approval-hook.ps1 / protected-folders-hook.ps1.

$INPUT_JSON = [Console]::In.ReadToEnd()

# Parse the whole payload as JSON rather than picking fields out with a
# regex. A regex stops at the first quote mark and silently truncates any
# command containing one.
try {
    $DATA = $INPUT_JSON | ConvertFrom-Json
} catch {
    exit 0
}

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$LOG_DIR    = "$SCRIPT_DIR\..\logs"
$LOG_FILE   = "$LOG_DIR\$(Get-Date -Format 'yyyy-MM-dd').log"

if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}

$TIMESTAMP = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Short session id, so concurrent sessions can be told apart.
$SESSION = "--------"
if ($DATA.session_id) {
    $SESSION = $DATA.session_id.Substring(0, [Math]::Min(8, $DATA.session_id.Length))
}

$TOOL_NAME = $DATA.tool_name
if (-not $TOOL_NAME) { $TOOL_NAME = "unknown" }

# Terminal tools carry a command; file tools carry a path. Neither is an
# error — a missing field yields $null, not a stale previous value.
$DETAIL = $DATA.tool_input.command
if (-not $DETAIL) { $DETAIL = $DATA.tool_input.file_path }
if (-not $DETAIL) { $DETAIL = "" }

# Flatten newlines so one tool call is always exactly one log line.
$DETAIL = ($DETAIL -replace "`r?`n", " ")

$CWD = $DATA.cwd
if (-not $CWD) { $CWD = "" }

Add-Content -Path $LOG_FILE -Value "$TIMESTAMP | $SESSION | RAN     | $TOOL_NAME | $DETAIL | cwd=$CWD"

exit 0
