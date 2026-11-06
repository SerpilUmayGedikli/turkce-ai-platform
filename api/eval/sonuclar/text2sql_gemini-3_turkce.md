# Türkçe Text-to-SQL Raporu: `gemini-3`

8 soru. Durumlar: {'dogru': 7, 'yanlis': 1}

Cevabı gerçekte veren model(ler): {'gemini-3': 8}

| Grup | Soru | Katı doğruluk | Esnek doğruluk |
|---|---|---|---|
| **Tümü** | 8 | **88%** | **88%** |
| kolay | 2 | 100% | 100% |
| orta | 6 | 83% | 83% |
| turkce | 8 | 88% | 88% |

Ortalama süre: 4.9 sn/soru. Kendi kendini düzeltme: 0 SQL hatası sonrası yeniden deneme.

## Yanlışlar

- **Soyadı ışık olan müşterilerin adları neler?** (yanlis)
  - altın: `SELECT DISTINCT ad FROM musteriler WHERE soyad = 'Işık'`
  - tahmin: `SELECT ad FROM musteriler WHERE tr_katla(soyad) = tr_katla('ışık')`
