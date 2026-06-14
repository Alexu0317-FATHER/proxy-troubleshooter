param(
    [string]$Target,
    [string]$Proxy,
    [string]$StateDir,
    [switch]$SaveProfile,
    [switch]$SaveRun
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "diagnose_proxy.py"

$argsList = @($pythonScript)
if ($Target) {
    $argsList += "--target"
    $argsList += $Target
}
if ($Proxy) {
    $argsList += "--proxy"
    $argsList += $Proxy
}
if ($StateDir) {
    $argsList += "--state-dir"
    $argsList += $StateDir
}
if ($SaveProfile) {
    $argsList += "--save-profile"
}
if ($SaveRun) {
    $argsList += "--save-run"
}

python @argsList
