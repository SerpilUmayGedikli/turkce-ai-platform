# CV Uyarlayıcı'yı Windows masaüstü uygulaması olarak paketler (PyInstaller).
# Kullanım (proje kökünden):  powershell -ExecutionPolicy Bypass -File .\uygulama\paketle.ps1
# Çıktı: dist\CV Uyarlayici\CV Uyarlayici.exe  (klasörü olduğu gibi kopyalayıp dağıtabilirsin)
#
# Notlar:
# - Arayüz Windows'un WebView2 motoruyla açılır (Windows 10/11'de yüklü gelir).
# - API anahtarı pakete GİRMEZ: uygulama ilk açılışta Ayarlar ekranından ister ve
#   %APPDATA%\CVUyarlayici\ayarlar.json dosyasına yazar.
# - Anlam modeli (~220 MB) ilk kullanımda %APPDATA%\CVUyarlayici\onbellek altına bir kez iner.

$ErrorActionPreference = "Stop"
$kok = Split-Path $PSScriptRoot -Parent
Set-Location $kok
$py = Join-Path $kok ".venv\Scripts\python.exe"
& $py -m pip install -q pyinstaller pywebview

& $py -m PyInstaller --noconfirm --windowed `
    --name "CV Uyarlayici" `
    --icon "uygulama\simge.ico" `
    --paths "api" `
    --add-data "uygulama\web;web" `
    --add-data "uygulama\simge.ico;." `
    --add-data "uygulama\ilan_dugmesi.js;." `
    --add-data "api\app\cv\ornekler;app\cv\ornekler" `
    --collect-submodules app `
    --collect-data docx `
    --collect-all fastembed `
    --collect-all onnxruntime `
    --collect-all tokenizers `
    --collect-submodules uvicorn `
    --hidden-import multipart `
    --exclude-module gradio `
    --exclude-module pandas `
    --exclude-module litellm `
    --exclude-module matplotlib `
    --distpath "dist" --workpath "build" `
    "uygulama\masaustu.py"

if ($LASTEXITCODE -ne 0) { throw "Paketleme başarısız" }
Write-Host "Hazır: $kok\dist\CV Uyarlayici\CV Uyarlayici.exe"
