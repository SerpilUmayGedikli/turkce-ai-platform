# API anahtarını .env dosyasına güvenle ekler (yazarken ekranda görünmez).
# Kullanım:  powershell -ExecutionPolicy Bypass -File .\anahtar-ekle.ps1

$dosya = Join-Path $PSScriptRoot ".env"
$secenekler = @{ "1" = "GEMINI_API_KEY"; "2" = "GROQ_API_KEY"; "3" = "OPENROUTER_API_KEY" }

Write-Host "Hangi anahtar?  1) Gemini   2) Groq   3) OpenRouter"
$secim = Read-Host "Seçim"
$ad = $secenekler[$secim]
if (-not $ad) { Write-Host "Geçersiz seçim."; exit 1 }

$gizli = Read-Host "$ad (yapıştır, Enter)" -AsSecureString
$deger = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($gizli)).Trim()
if (-not $deger) { Write-Host "Boş anahtar, değişiklik yapılmadı."; exit 1 }

$utf8 = New-Object System.Text.UTF8Encoding($false)
$satirlar = [IO.File]::ReadAllLines($dosya, $utf8)
$bulundu = $false
$satirlar = $satirlar | ForEach-Object {
    if ($_ -cmatch "^\s*$ad\s*=") { $bulundu = $true; "$ad=$deger" } else { $_ }
}
if (-not $bulundu) { $satirlar += "$ad=$deger" }
[IO.File]::WriteAllLines($dosya, [string[]]$satirlar, $utf8)

Write-Host "$ad kaydedildi ($($deger.Length) karakter). Bu pencereyi kapatabilirsin."
