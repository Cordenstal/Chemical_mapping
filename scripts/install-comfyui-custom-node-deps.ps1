[CmdletBinding()]
param(
    [string]$CustomNodesRoot = '',
    [string]$PythonExe = '',
    [string]$LogPath = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptRoot = $PSScriptRoot
if (-not $CustomNodesRoot) {
    $CustomNodesRoot = Join-Path -Path $scriptRoot -ChildPath 'ComfyUI\custom_nodes'
}

function Write-Log {
    param(
        [string]$Message,
        [ValidateSet('INFO', 'WARN', 'ERROR')]
        [string]$Level = 'INFO'
    )

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[$timestamp] [$Level] $Message"
    Write-Host $line
    if ($script:LogPathResolved) {
        Add-Content -LiteralPath $script:LogPathResolved -Value $line -Encoding utf8
    }
}

function Resolve-PythonExe {
    param(
        [string]$RequestedPythonExe,
        [string]$RequestedCustomNodesRoot
    )

    if ($RequestedPythonExe -and (Test-Path -LiteralPath $RequestedPythonExe)) {
        return (Resolve-Path -LiteralPath $RequestedPythonExe).Path
    }

    $comfyRoot = Split-Path -Path $RequestedCustomNodesRoot -Parent
    $candidates = @(
        (Join-Path -Path $comfyRoot -ChildPath 'python_embeded\python.exe'),
        (Join-Path -Path $comfyRoot -ChildPath 'python.exe'),
        (Join-Path -Path $comfyRoot -ChildPath 'venv\Scripts\python.exe')
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        if ($pythonCommand.Path) {
            return $pythonCommand.Path
        }

        if ($pythonCommand.Source) {
            return $pythonCommand.Source
        }

        return 'python'
    }

    throw "Unable to find a Python executable. Pass -PythonExe explicitly."
}

function Invoke-DependencyInstall {
    param(
        [string]$PythonPath,
        [string]$TargetPath
    )

    $manifestDir = Split-Path -Path $TargetPath -Parent
    $manifestName = Split-Path -Path $TargetPath -Leaf

    Push-Location -LiteralPath $manifestDir
    try {
        if ($manifestName -like 'requirements*.txt') {
            Write-Log "Installing requirements from $TargetPath"
            & $PythonPath -m pip install --disable-pip-version-check --no-input -r $TargetPath
        }
        elseif ($manifestName -ieq 'install.py') {
            Write-Log "Running install script $TargetPath"
            & $PythonPath $TargetPath
        }
        else {
            Write-Log "Skipping unsupported manifest $TargetPath" 'WARN'
            return
        }
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path -LiteralPath $CustomNodesRoot)) {
    throw "Custom nodes root not found: $CustomNodesRoot"
}

$script:LogPathResolved = if ($LogPath) {
    $LogPath
}
else {
    Join-Path -Path $PSScriptRoot -ChildPath 'install-comfyui-custom-node-deps.log'
}

$logDirectory = Split-Path -Path $script:LogPathResolved -Parent
if ($logDirectory -and -not (Test-Path -LiteralPath $logDirectory)) {
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
}

Set-Content -LiteralPath $script:LogPathResolved -Value '' -Encoding utf8

$startedAt = Get-Date
Write-Log "Starting dependency scan"
Write-Log "Custom nodes root: $CustomNodesRoot"

$pythonPath = Resolve-PythonExe -RequestedPythonExe $PythonExe -RequestedCustomNodesRoot $CustomNodesRoot
Write-Log "Using Python executable: $pythonPath"

$manifests = @()
$manifests += Get-ChildItem -LiteralPath $CustomNodesRoot -Recurse -File -Filter 'requirements*.txt' | Sort-Object FullName
$manifests += Get-ChildItem -LiteralPath $CustomNodesRoot -Recurse -File -Filter 'install.py' | Sort-Object FullName

if (-not $manifests) {
    Write-Log 'No dependency manifests found.' 'WARN'
    exit 0
}

$total = $manifests.Count
$index = 0
$failures = @()

foreach ($manifest in $manifests) {
    $index++
    Write-Log "[$index/$total] Processing $($manifest.FullName)"

    try {
        Invoke-DependencyInstall -PythonPath $pythonPath -TargetPath $manifest.FullName
        Write-Log "[$index/$total] Completed $($manifest.FullName)"
    }
    catch {
        $message = $_.Exception.Message
        $failures += [pscustomobject]@{
            Path = $manifest.FullName
            Error = $message
        }
        Write-Log "[$index/$total] Failed $($manifest.FullName): $message" 'ERROR'
    }
}

$elapsed = New-TimeSpan -Start $startedAt -End (Get-Date)
Write-Log "Finished dependency scan in $([int]$elapsed.TotalSeconds) seconds"

if ($failures.Count -gt 0) {
    Write-Log "$($failures.Count) manifest(s) failed." 'ERROR'
    $failures | ForEach-Object {
        Write-Log "Failure: $($_.Path) :: $($_.Error)" 'ERROR'
    }
    exit 1
}

Write-Log 'All dependency manifests completed successfully.'
