# PreToolUse guard - blocks EDITS (Write/Edit/NotebookEdit) inside protected
# folders. "Protected" means look-but-don't-touch: Claude can still READ these
# files, it just cannot use its editing tools to change them.
#
# Matching is ROOT-ANCHORED. Each entry in protectedFolders is protected only:
#   - at the repo root          <repo>\<entry>
#   - and under the harness dir  <repo>\.claude\<entry>
# so a repo's OWN nested folders (e.g. src\config, data\logs) stay editable -
# only the harness's own config/logs and any top-level config/logs are frozen.
# This is a deliberate change from the old "folder of this name anywhere"
# match, which also froze dist\config, a repo's app logs, etc.
#
# Blocks via exit code 2 (reason on stderr). Claude Code documents exit 2 as the
# block that takes absolute precedence, so it is our best chance of holding even
# when Claude runs in bypassPermissions mode.

$INPUT_JSON = [Console]::In.ReadToEnd()

try {
    $DATA = $INPUT_JSON | ConvertFrom-Json
} catch {
    exit 0
}

$TOOL_NAME = $DATA.tool_name

$WRITE_TOOLS = @("Write", "Edit", "NotebookEdit")
if ($WRITE_TOOLS -notcontains $TOOL_NAME) { exit 0 }

$FILE_PATH = $DATA.tool_input.file_path
if (-not $FILE_PATH) { $FILE_PATH = $DATA.tool_input.notebook_path }
if (-not $FILE_PATH) { exit 0 }

# Locate ourselves: <repo>\.claude\hooks\this.ps1
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$CLAUDE_DIR = Split-Path -Parent $SCRIPT_DIR        # <repo>\.claude
$REPO_ROOT  = Split-Path -Parent $CLAUDE_DIR        # <repo>

$CONFIG    = Get-Content -Raw -Encoding UTF8 "$SCRIPT_DIR\..\config\harness.config.json" | ConvertFrom-Json
$PROTECTED = $CONFIG.protectedFolders

# Normalize to a comparable absolute form: full path, forward slashes,
# lower case (Windows is case-insensitive), no trailing slash.
function ConvertTo-Comparable($p) {
    try { $full = [System.IO.Path]::GetFullPath($p) } catch { $full = $p }
    return ($full -replace '\\', '/').TrimEnd('/').ToLowerInvariant()
}

# Edits arrive with absolute paths; guard the rare relative one anyway.
if (-not [System.IO.Path]::IsPathRooted($FILE_PATH)) {
    $FILE_PATH = Join-Path $REPO_ROOT $FILE_PATH
}
$FP = ConvertTo-Comparable $FILE_PATH

# Build the root-anchored protected targets.
$TARGETS = @()
foreach ($folder in $PROTECTED) {
    $NAME = ($folder -replace '\\', '/').Trim('/')
    if (-not $NAME) { continue }
    $TARGETS += (ConvertTo-Comparable (Join-Path $REPO_ROOT $NAME))
    $TARGETS += (ConvertTo-Comparable (Join-Path $CLAUDE_DIR $NAME))
}

foreach ($t in $TARGETS) {
    if ($FP -eq $t -or $FP.StartsWith("$t/")) {
        $LOG_DIR = "$SCRIPT_DIR\..\logs"
        if (-not (Test-Path $LOG_DIR)) {
            New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
        }
        $SESSION = "--------"
        if ($DATA.session_id) {
            $SESSION = $DATA.session_id.Substring(0, [Math]::Min(8, $DATA.session_id.Length))
        }
        $STAMP = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path "$LOG_DIR\$(Get-Date -Format 'yyyy-MM-dd').log" `
            -Value "$STAMP | $SESSION | BLOCKED | $TOOL_NAME | $FILE_PATH | matched=$t"
        [Console]::Error.WriteLine("Harness protected folder: [$FILE_PATH] is inside a protected location and was NOT changed. You can still READ it; edit it by hand if you truly intend to.")
        exit 2
    }
}

exit 0
