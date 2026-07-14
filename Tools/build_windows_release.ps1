param(
    [string]$Version = "0.1.0",
    [switch]$SkipInstall,
    [switch]$SkipExecutable
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$PythonApp = Join-Path $Root "Python_Control_Application"
$ReleaseRoot = Join-Path $Root "Releases"
$ReleaseDir = Join-Path $ReleaseRoot ("Building_Vibration_Analyzer_v{0}" -f $Version)
$Venv = Join-Path $PythonApp ".venv-release"
$Python = Join-Path $Venv "Scripts\python.exe"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Script
    )
    Write-Host "== $Name =="
    & $Script
}

Invoke-Step "Prepare release directory" {
    New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
}

if (-not $SkipInstall) {
    Invoke-Step "Create clean virtual environment" {
        if (Test-Path $Venv) {
            Remove-Item -LiteralPath $Venv -Recurse -Force
        }
        python -m venv $Venv
    }

    Invoke-Step "Install pinned dependencies" {
        & $Python -m pip install --upgrade pip
        & $Python -m pip install -r (Join-Path $PythonApp "requirements.txt")
    }
} else {
    $Python = "python"
}

Invoke-Step "Run Python tests" {
    Push-Location $Root
    try {
        & $Python -m unittest discover -s "Python_Control_Application\tests"
    } finally {
        Pop-Location
    }
}

Invoke-Step "Run firmware host tests" {
    Push-Location $Root
    try {
        & $Python -m unittest discover -s "Teensy_Firmware\tests"
    } finally {
        Pop-Location
    }
}

Invoke-Step "Compile Teensy firmware if Arduino CLI is available" {
    $ArduinoCli = Get-Command arduino-cli -ErrorAction SilentlyContinue
    if ($ArduinoCli) {
        Push-Location $Root
        try {
            arduino-cli compile --fqbn teensy:avr:teensy41 "Teensy_Firmware\BuildingVibrationLogger"
        } finally {
            Pop-Location
        }
    } else {
        "arduino-cli not found; firmware compile skipped." | Set-Content -Path (Join-Path $ReleaseDir "FIRMWARE_COMPILE_SKIPPED.txt")
    }
}

if (-not $SkipExecutable) {
    Invoke-Step "Build executable with PyInstaller" {
        Push-Location $PythonApp
        try {
            & $Python -m PyInstaller --noconfirm --clean --windowed `
                --name "BuildingVibrationAnalyzer" `
                --paths (Join-Path $PythonApp "src") `
                (Join-Path $PythonApp "src\building_vibration_analyzer\__main__.py")
        } finally {
            Pop-Location
        }
    }

    Invoke-Step "Copy executable artifacts" {
        $Built = Join-Path $PythonApp "dist\BuildingVibrationAnalyzer"
        if (Test-Path $Built) {
            Copy-Item -Path $Built -Destination $ReleaseDir -Recurse -Force
        } else {
            throw "PyInstaller output not found: $Built"
        }
    }
} else {
    "Executable build skipped by -SkipExecutable." | Set-Content -Path (Join-Path $ReleaseDir "EXECUTABLE_BUILD_SKIPPED.txt")
}

Invoke-Step "Copy release support files" {
    Copy-Item -Path (Join-Path $Root "README.md") -Destination (Join-Path $ReleaseDir "README.md") -Force
    Copy-Item -Path (Join-Path $PythonApp "sample_data") -Destination (Join-Path $ReleaseDir "sample_data") -Recurse -Force
    Copy-Item -Path (Join-Path $PythonApp "requirements.txt") -Destination (Join-Path $ReleaseDir "requirements.txt") -Force
    @"
Building Vibration Analyzer $Version

Portable use:
1. Connect the Teensy 4.1 logger by USB.
2. Run BuildingVibrationAnalyzer.exe if present.
3. Synchronize RTC before field logging.
4. Start and stop logging before removing power.
5. Analyze downloaded CSV sessions from the persistent append-only log.

Hardware validation is still required before field measurements.
"@ | Set-Content -Path (Join-Path $ReleaseDir "PORTABLE_USE.txt")
}

Invoke-Step "Generate SHA-256 checksums" {
    $ChecksumFile = Join-Path $ReleaseDir "SHA256SUMS.txt"
    Get-ChildItem -Path $ReleaseDir -File -Recurse |
        Where-Object { $_.FullName -ne $ChecksumFile } |
        ForEach-Object {
            $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName
            $relative = Resolve-Path -Relative $_.FullName
            "{0}  {1}" -f $hash.Hash, $relative
        } | Set-Content -Path $ChecksumFile
}

Write-Host "Release prepared at $ReleaseDir"
