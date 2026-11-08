# CV Uyarlayıcı'yı bu bilgisayara kurar: paketlenmiş uygulamayı kalıcı bir klasöre kopyalar,
# Masaüstü'ne ve Başlat menüsüne simgeli kısayol koyar. Yönetici izni gerekmez.
# Kullanım (proje kökünden, önce paketle.ps1 çalışmış olmalı):
#   powershell -ExecutionPolicy Bypass -File .\uygulama\kur.ps1
# Kaldırmak için: powershell -ExecutionPolicy Bypass -File .\uygulama\kur.ps1 -Kaldir
param([switch]$Kaldir)

$ErrorActionPreference = "Stop"
$kok = Split-Path $PSScriptRoot -Parent
$kaynak = Join-Path $kok "dist\CV Uyarlayici"
$hedef = Join-Path $env:LOCALAPPDATA "Programs\CV Uyarlayici"
$exe = Join-Path $hedef "CV Uyarlayici.exe"
$kisayollar = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "CV Uyarlayıcı.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "CV Uyarlayıcı.lnk")
)

# Açık bir kopya varsa dosyalar kilitli olur
Get-Process "CV Uyarlayici" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

if ($Kaldir) {
    $kisayollar | Where-Object { Test-Path $_ } | Remove-Item -Force
    if (Test-Path $hedef) { Remove-Item $hedef -Recurse -Force }
    Write-Host "Kaldırıldı. Ayarlar ve model önbelleği $env:APPDATA\CVUyarlayici altında duruyor."
    return
}

if (-not (Test-Path (Join-Path $kaynak "CV Uyarlayici.exe"))) {
    throw "Paket bulunamadı: önce uygulama\paketle.ps1 çalıştır."
}

if (Test-Path $hedef) { Remove-Item $hedef -Recurse -Force }
New-Item -ItemType Directory -Force (Split-Path $hedef) | Out-Null
Copy-Item $kaynak $hedef -Recurse

$kabuk = New-Object -ComObject WScript.Shell
foreach ($yol in $kisayollar) {
    $k = $kabuk.CreateShortcut($yol)
    $k.TargetPath = $exe
    $k.WorkingDirectory = $hedef
    $k.IconLocation = "$exe,0"
    $k.Description = "CV'ni her iş ilanına göre uyarla"
    $k.Save()
}

Write-Host "Kuruldu: $exe"
$kisayollar | ForEach-Object { Write-Host "Kısayol: $_" }
