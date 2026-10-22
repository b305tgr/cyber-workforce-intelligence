# Midnight Signal - one-shot installer for Windows (PowerShell 5.1+ / 7).
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
# Checks Python + Ollama, builds a virtualenv, downloads the base model,
# builds the `midnight-signal` model from the Modelfile, then runs --doctor.
# (ASCII only on purpose: Windows PowerShell 5 mangles UTF-8 without a BOM.)

$ErrorActionPreference = "Continue"
$BaseModel   = "huihui_ai/qwen2.5-coder-abliterate:7b"
$CustomModel = "midnight-signal"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Step($t) { Write-Host ""; Write-Host "> $t" -ForegroundColor DarkYellow }
function Ok($t)   { Write-Host "  OK  $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  !   $t" -ForegroundColor Yellow }
function Die($t)  { Write-Host "  X   $t" -ForegroundColor Red; exit 1 }

function Test-Ollama { ollama list *> $null; return ($LASTEXITCODE -eq 0) }

# -- 1. Python -----------------------------------------------------------
Step "1/5  Python"
$Py = $null; $PyPre = @()
foreach ($cand in @("python", "py")) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    $pre = @(); if ($cand -eq "py") { $pre = @("-3") }
    & $cmd.Source @pre -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { $Py = $cmd.Source; $PyPre = $pre; break }
}
if (-not $Py) { Die "Python 3.9+ not found. Get it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH')." }
Ok (& $Py @PyPre --version)

# -- 2. Ollama -----------------------------------------------------------
Step "2/5  Ollama"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Warn "Ollama isn't installed."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $a = Read-Host "    Install it with winget now? [y/N]"
        if ($a -match '^[Yy]') { winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements }
    } else {
        Write-Host "    Download it from https://ollama.com/download"
    }
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Die "Install Ollama, open a NEW terminal window (so PATH refreshes), then re-run this script."
    }
}
Ok "found ollama"

if (-not (Test-Ollama)) {
    Warn "Ollama server isn't running - starting it in the background."
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    for ($i = 0; $i -lt 20; $i++) { if (Test-Ollama) { break }; Start-Sleep -Seconds 1 }
    if (-not (Test-Ollama)) { Die "Couldn't start Ollama. Open the Ollama app (or run 'ollama serve'), then re-run." }
}
Ok "server is running"

# -- 3. Python environment ----------------------------------------------
Step "3/5  Python environment"
if (-not (Test-Path ".venv")) {
    & $Py @PyPre -m venv .venv
    if ($LASTEXITCODE -ne 0) { Die "Couldn't create the virtualenv." }
}
$VPy = Join-Path $Root ".venv\Scripts\python.exe"
& $VPy -m pip install --quiet --upgrade pip
& $VPy -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) { Die "pip install failed." }
Ok "dependencies installed in .venv"

# -- 4. Models -----------------------------------------------------------
Step "4/5  Model"
$have = (ollama list) -match [regex]::Escape($BaseModel)
if ($have) {
    Ok "$BaseModel already downloaded"
} else {
    Write-Host "    downloading $BaseModel (about 4-5 GB) ..."
    ollama pull $BaseModel
    if ($LASTEXITCODE -ne 0) { Die "Download failed - check your connection and re-run." }
    Ok "downloaded $BaseModel"
}
ollama create $CustomModel -f Modelfile | Out-Null
if ($LASTEXITCODE -ne 0) { Die "'ollama create' failed." }
Ok "built '$CustomModel' from the Modelfile"

# -- 5. Health check -----------------------------------------------------
Step "5/5  Health check"
& $VPy midnight_signal.py --doctor
if ($LASTEXITCODE -ne 0) { Die "The health check found a problem. Fix the reported issue, then run .\run.ps1." }

Write-Host ""
Write-Host "> Done. Launch it with:  .\run.ps1" -ForegroundColor Green
Write-Host ""
