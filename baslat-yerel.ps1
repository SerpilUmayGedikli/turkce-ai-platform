# Docker OLMADAN çalıştırma: gateway (4000) + API (8000)
# Kullanım:  powershell -ExecutionPolicy Bypass -File .\baslat-yerel.ps1
# Durdurmak: açılan iki pencereyi kapat.

$ErrorActionPreference = "Stop"
$kok = $PSScriptRoot
$venv = Join-Path $kok ".venv"
$py = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Sanal ortam kuruluyor (ilk seferde birkaç dakika sürer)..."
    python -m venv $venv
    & $py -m pip install -q -r (Join-Path $kok "api\requirements.txt") "litellm[proxy]"
}

if (-not (Test-Path (Join-Path $kok ".env"))) {
    Copy-Item (Join-Path $kok ".env.example") (Join-Path $kok ".env")
    Write-Host ".env oluşturuldu: anahtarlarını yazıp tekrar çalıştır."
    exit 1
}

# .env içindeki değişkenleri bu oturuma yükle (iki alt pencere de miras alır)
# DİKKAT: -cmatch (büyük/küçük harf duyarlı). Türkçe Windows'ta -match "I" harfini
# "ı"nın büyüğü sayar ve LITELLM, API gibi adları kaçırır ("Türkçe I sorunu").
Get-Content (Join-Path $kok ".env") -Encoding UTF8 | ForEach-Object {
    if ($_ -cmatch '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim())
    }
}
$env:PYTHONUTF8 = "1"

$litellm = Join-Path $venv "Scripts\litellm.exe"
$config = Join-Path $kok "gateway\config.yaml"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$litellm' --config '$config' --port 4000"
Start-Process powershell -WorkingDirectory (Join-Path $kok "api") -ArgumentList "-NoExit", "-Command", "& '$py' -m uvicorn app.main:app --port 8000 --reload"

Write-Host "Gateway: http://localhost:4000   API: http://localhost:8000/docs"
