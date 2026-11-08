# CV uyarlayıcı web arayüzü: http://localhost:7861
# Kullanım:  powershell -ExecutionPolicy Bypass -File .\cv-baslat.ps1
# Gateway (baslat-yerel.ps1) açıksa onu kullanır; değilse .env'deki GEMINI_API_KEY ile doğrudan Gemini'ye bağlanır.

$ErrorActionPreference = "Stop"
$kok = $PSScriptRoot
$py = Join-Path $kok ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    python -m venv (Join-Path $kok ".venv")
    & $py -m pip install -q -r (Join-Path $kok "api\requirements.txt") "gradio>=5,<6"
}

# -cmatch: Türkçe Windows'ta -match "I" harfini "ı" sayar (bkz. baslat-yerel.ps1)
Get-Content (Join-Path $kok ".env") -Encoding UTF8 | ForEach-Object {
    if ($_ -cmatch '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(\S.*)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim())
    }
}
try {
    Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://localhost:4000/health/liveliness" | Out-Null
    $env:LLM_BASE_URL = "http://localhost:4000"
    Write-Host "Gateway bulundu: modeller gateway üzerinden."
} catch {
    Remove-Item Env:LLM_BASE_URL -ErrorAction SilentlyContinue
    Write-Host "Gateway kapalı: doğrudan Gemini kullanılacak."
}
$env:PYTHONUTF8 = "1"
& $py (Join-Path $kok "demo\cv_demo.py")
