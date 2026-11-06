# KVKK Kalkanı: Değerlendirme Raporu

Otomatik üretildi: `python -m eval.kvkk_degerlendir`. P = precision (bulduklarımızın ne kadarı doğru), R = recall (gerçeklerin ne kadarını bulduk). Eşleşme katı: tür ve karakter aralığı birebir aynı olmalı.

### Sentetik set (500 örnek, tuzak sayılar içerir)

| Tür | Saf regex P / R / F1 | **KVKK Kalkanı** P / R / F1 | Kalkan TP / FP / FN |
|---|---|---|---|
| IBAN | 1.00 / 0.74 / 0.85 | **1.00 / 1.00 / 1.00** | 100 / 0 / 0 |
| EPOSTA | 1.00 / 1.00 / 1.00 | **1.00 / 1.00 / 1.00** | 140 / 0 / 0 |
| TCKN | 0.49 / 1.00 / 0.66 | **1.00 / 1.00 / 1.00** | 140 / 0 / 0 |
| KART | 0.48 / 1.00 / 0.65 | **1.00 / 1.00 / 1.00** | 80 / 0 / 0 |
| TELEFON | 1.00 / 0.64 / 0.78 | **1.00 / 1.00 / 1.00** | 180 / 0 / 0 |
| **TOPLAM** | 0.70 / 0.86 / 0.77 | **1.00 / 1.00 / 1.00** | 640 / 0 / 0 |

### Elle yazılmış zor set (22 örnek)

| Tür | Saf regex P / R / F1 | **KVKK Kalkanı** P / R / F1 | Kalkan TP / FP / FN |
|---|---|---|---|
| IBAN | 1.00 / 0.50 / 0.67 | **1.00 / 0.50 / 0.67** | 1 / 0 / 1 |
| EPOSTA | 1.00 / 0.67 / 0.80 | **1.00 / 0.67 / 0.80** | 2 / 0 / 1 |
| TCKN | 0.20 / 0.33 / 0.25 | **0.67 / 0.67 / 0.67** | 2 / 1 / 1 |
| KART | 0.50 / 0.50 / 0.50 | **1.00 / 1.00 / 1.00** | 2 / 0 / 0 |
| TELEFON | 0.40 / 0.33 / 0.36 | **0.83 / 0.83 / 0.83** | 5 / 1 / 1 |
| **TOPLAM** | 0.47 / 0.44 / 0.45 | **0.86 / 0.75 / 0.80** | 12 / 2 / 4 |

### KVKK Kalkanı'nın zor sette yaptığı hatalar

- `TC: 123 456 789 50` → kaçan: ["TCKN:'123 456 789 50'"], fazla: -
- `Ofis sabit hattı 212 345 67 89` → kaçan: ["TELEFON:'212 345 67 89'"], fazla: -
- `IBAN: TR33-0006-1005-1978-6457-8413-26` → kaçan: ["IBAN:'TR33-0006-1005-1978-6457-8413-26'"], fazla: -
- `mail: ali [at] ornek [dot] com` → kaçan: ["EPOSTA:'ali [at] ornek [dot] com'"], fazla: -
- `Kargo takip numaranız 10000000146` → kaçan: -, fazla: ["TCKN:'10000000146'"]
- `Stok kodu 5551234567 olan üründen 3 adet` → kaçan: -, fazla: ["TELEFON:'5551234567'"]

### Kapsam dışı (henüz)

Ad-soyad, adres, doğum tarihi, plaka. Bunlar kuralla güvenilir yakalanamaz; sonraki adım Türkçe NER modeliyle karşılaştırma.
