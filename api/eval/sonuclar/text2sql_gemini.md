# Türkçe Text-to-SQL Raporu: `gemini`

8 soru. Durumlar: {'dogru': 6, 'yanlis': 2}

| Grup | Soru | Katı doğruluk | Esnek doğruluk |
|---|---|---|---|
| **Tümü** | 8 | **75%** | **75%** |
| kolay | 2 | 100% | 100% |
| orta | 6 | 67% | 67% |
| turkce | 8 | 75% | 75% |

Ortalama süre: 121.5 sn/soru. Kendi kendini düzeltme: 0 SQL hatası sonrası yeniden deneme.

## Yanlışlar

- **ISPARTA ve ESKİŞEHİR'de toplam kaç müşteri var?** (yanlis)
  - altın: `SELECT COUNT(*) FROM musteriler WHERE sehir IN ('Isparta', 'Eskişehir')`
  - tahmin: `SELECT COUNT(*) as toplam FROM musteriler WHERE tr_lower(sehir) IN ('isparta', 'eskişehir');`
- **Soyadı ışık olan müşterilerin adları neler?** (yanlis)
  - altın: `SELECT ad FROM musteriler WHERE soyad = 'Işık'`
  - tahmin: `SELECT DISTINCT ad, soyad FROM musteriler WHERE tr_lower(soyad) = 'ışık'`
