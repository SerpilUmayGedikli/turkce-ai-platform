"""Türkçe Text-to-SQL test seti v1 (36 soru, altın SQL'li).

Etiketler:
  kolay / orta / zor : sorgunun yapısal zorluğu
  turkce             : Türkçe büyük/küçük harf veya karakter sorunu içerir (İ/ı, Ş/ş...)
  kvkk               : soruda kişisel veri var; model gerçek değeri görmeden sorgulamalı

Sorular bilerek belirsizlik içermeyecek şekilde yazıldı ("iptal hariç" gibi);
"ilk N" sorularında N. sırada eşitlik olmadığı veriden kontrol edildi.
"""

from __future__ import annotations

_CIRO = "SUM(k.adet * k.birim_fiyat)"
_KALEM = ("siparis_kalemleri k JOIN siparisler s ON s.id = k.siparis_id "
          "JOIN urunler u ON u.id = k.urun_id")

SORULAR: list[dict] = [
    # ---------------------------------------------------------------- kolay
    {"soru": "Kaç müşterimiz var?", "etiket": ["kolay"],
     "sql": "SELECT COUNT(*) FROM musteriler"},
    {"soru": "Mağazada kaç farklı kategori var?", "etiket": ["kolay"],
     "sql": "SELECT COUNT(*) FROM kategoriler"},
    {"soru": "En pahalı ürünün adı ne?", "etiket": ["kolay"],
     "sql": "SELECT ad FROM urunler ORDER BY fiyat DESC LIMIT 1"},
    {"soru": "Stoğu tükenmiş ürünlerin adlarını listele.", "etiket": ["kolay"],
     "sql": "SELECT ad FROM urunler WHERE stok = 0"},
    {"soru": "Kaç sipariş iptal edilmiş?", "etiket": ["kolay"],
     "sql": "SELECT COUNT(*) FROM siparisler WHERE durum = 'iptal'"},
    {"soru": "Şu anda kargoda olan kaç sipariş var?", "etiket": ["kolay"],
     "sql": "SELECT COUNT(*) FROM siparisler WHERE durum = 'kargoda'"},
    {"soru": "Fiyatı 1000 TL'den yüksek kaç ürün var?", "etiket": ["kolay"],
     "sql": "SELECT COUNT(*) FROM urunler WHERE fiyat > 1000"},
    {"soru": "Ürünlerin ortalama fiyatı kaç TL?", "etiket": ["kolay"],
     "sql": "SELECT AVG(fiyat) FROM urunler"},
    # ---------------------------------------------------------------- orta
    {"soru": "Elektronik kategorisinde kaç ürün var?", "etiket": ["orta"],
     "sql": "SELECT COUNT(*) FROM urunler u JOIN kategoriler c ON c.id = u.kategori_id WHERE c.ad = 'Elektronik'"},
    {"soru": "Her kategoride kaç ürün olduğunu göster.", "etiket": ["orta"],
     "sql": "SELECT c.ad, COUNT(*) FROM urunler u JOIN kategoriler c ON c.id = u.kategori_id GROUP BY c.id"},
    {"soru": "2026 yılında kaç sipariş verildi?", "etiket": ["orta"],
     "sql": "SELECT COUNT(*) FROM siparisler WHERE tarih BETWEEN '2026-01-01' AND '2026-12-31'"},
    {"soru": "Her şehirde kaç müşterimiz var?", "etiket": ["orta"],
     "sql": "SELECT sehir, COUNT(*) FROM musteriler GROUP BY sehir"},
    {"soru": "Hiç sipariş vermemiş kaç müşteri var?", "etiket": ["orta"],
     "sql": "SELECT COUNT(*) FROM musteriler WHERE id NOT IN (SELECT musteri_id FROM siparisler)"},
    {"soru": "Ekim 2026'daki toplam ciro ne kadar? İptal edilen siparişler hariç.", "etiket": ["orta"],
     "sql": f"SELECT {_CIRO} FROM {_KALEM} WHERE s.durum != 'iptal' "
            "AND s.tarih BETWEEN '2026-10-01' AND '2026-10-31'"},
    {"soru": "İade edilen siparişlerin toplam tutarı ne kadar?", "etiket": ["orta"],
     "sql": f"SELECT {_CIRO} FROM {_KALEM} WHERE s.durum = 'iade'"},
    {"soru": "En çok sipariş veren 5 müşterinin adı ve soyadı nedir?", "etiket": ["orta"],
     "sql": "SELECT m.ad, m.soyad FROM siparisler s JOIN musteriler m ON m.id = s.musteri_id "
            "GROUP BY m.id ORDER BY COUNT(*) DESC LIMIT 5"},
    {"soru": "İptal edilmeyen siparişlerde en çok adet satılan 3 ürün hangileri?", "etiket": ["orta"],
     "sql": f"SELECT u.ad FROM {_KALEM} WHERE s.durum != 'iptal' "
            "GROUP BY u.id ORDER BY SUM(k.adet) DESC LIMIT 3"},
    {"soru": "2026 yılında her ay kaç sipariş verildi?", "etiket": ["orta"],
     "sql": "SELECT substr(tarih, 1, 7), COUNT(*) FROM siparisler WHERE tarih LIKE '2026-%' "
            "GROUP BY substr(tarih, 1, 7)"},
    {"soru": "Kategori bazında 2025 yılı cirosu nedir? İptaller hariç.", "etiket": ["orta"],
     "sql": f"SELECT c.ad, {_CIRO} FROM {_KALEM} JOIN kategoriler c ON c.id = u.kategori_id "
            "WHERE s.durum != 'iptal' AND s.tarih BETWEEN '2025-01-01' AND '2025-12-31' GROUP BY c.id"},
    # ---------------------------------------------------------------- zor
    {"soru": "Geçen ay en çok ciro yapan kategori hangisi? İptaller hariç.", "etiket": ["zor"],
     "sql": f"SELECT c.ad FROM {_KALEM} JOIN kategoriler c ON c.id = u.kategori_id "
            "WHERE s.durum != 'iptal' AND s.tarih BETWEEN '2026-10-01' AND '2026-10-31' "
            f"GROUP BY c.id ORDER BY {_CIRO} DESC LIMIT 1"},
    {"soru": "Ortalama sipariş tutarı ne kadar? İptal edilen siparişleri sayma.", "etiket": ["zor"],
     "sql": f"SELECT AVG(t) FROM (SELECT {_CIRO} AS t FROM siparis_kalemleri k "
            "JOIN siparisler s ON s.id = k.siparis_id WHERE s.durum != 'iptal' GROUP BY s.id)"},
    {"soru": "Fiyatı ortalama ürün fiyatının üzerinde olan kaç ürün var?", "etiket": ["zor"],
     "sql": "SELECT COUNT(*) FROM urunler WHERE fiyat > (SELECT AVG(fiyat) FROM urunler)"},
    {"soru": "En az iki farklı kategoriden ürün almış kaç müşteri var?", "etiket": ["zor"],
     "sql": "SELECT COUNT(*) FROM (SELECT s.musteri_id FROM siparis_kalemleri k "
            "JOIN siparisler s ON s.id = k.siparis_id JOIN urunler u ON u.id = k.urun_id "
            "GROUP BY s.musteri_id HAVING COUNT(DISTINCT u.kategori_id) >= 2)"},
    {"soru": "Daha önce sipariş vermiş ama Ağustos-Ekim 2026 arasında hiç sipariş vermemiş kaç müşteri var?",
     "etiket": ["zor"],
     "sql": "SELECT COUNT(DISTINCT musteri_id) FROM siparisler WHERE musteri_id NOT IN "
            "(SELECT musteri_id FROM siparisler WHERE tarih BETWEEN '2026-08-01' AND '2026-10-31')"},
    {"soru": "2025'in ilk 10 ayında ve 2026'nın ilk 10 ayında kaçar sipariş verildi?", "etiket": ["zor"],
     "sql": "SELECT SUM(tarih BETWEEN '2025-01-01' AND '2025-10-31'), "
            "SUM(tarih BETWEEN '2026-01-01' AND '2026-10-31') FROM siparisler"},
    {"soru": "Toplam harcaması en yüksek 3 şehir hangileri? İptaller hariç.", "etiket": ["zor"],
     "sql": f"SELECT m.sehir FROM siparis_kalemleri k JOIN siparisler s ON s.id = k.siparis_id "
            "JOIN musteriler m ON m.id = s.musteri_id WHERE s.durum != 'iptal' "
            f"GROUP BY m.sehir ORDER BY {_CIRO} DESC LIMIT 3"},
    # ---------------------------------------------------------------- Türkçe karakter
    {"soru": "istanbul'da kaç müşterimiz var?", "etiket": ["kolay", "turkce"],
     "sql": "SELECT COUNT(*) FROM musteriler WHERE sehir = 'İstanbul'"},
    {"soru": "IĞDIR'DAKİ MÜŞTERİ SAYISI KAÇ?", "etiket": ["kolay", "turkce"],
     "sql": "SELECT COUNT(*) FROM musteriler WHERE sehir = 'Iğdır'"},
    {"soru": "izmirli müşteriler toplam kaç sipariş vermiş?", "etiket": ["orta", "turkce"],
     "sql": "SELECT COUNT(*) FROM siparisler s JOIN musteriler m ON m.id = s.musteri_id WHERE m.sehir = 'İzmir'"},
    {"soru": "ISPARTA ve ESKİŞEHİR'de toplam kaç müşteri var?", "etiket": ["orta", "turkce"],
     "sql": "SELECT COUNT(*) FROM musteriler WHERE sehir IN ('Isparta', 'Eskişehir')"},
    {"soru": "Adı ş harfiyle başlayan kaç müşteri var?", "etiket": ["orta", "turkce"],
     "sql": "SELECT COUNT(*) FROM musteriler WHERE ad LIKE 'Ş%'"},
    {"soru": "Adında 'çanta' geçen kaç ürün var?", "etiket": ["orta", "turkce"],
     "sql": "SELECT COUNT(*) FROM urunler WHERE tr_lower(ad) LIKE '%çanta%'"},
    {"soru": "Soyadı ışık olan müşterilerin adları neler?", "etiket": ["orta", "turkce"],
     # v1.1: DISTINCT eklendi. "adları neler" tekrarsız liste demek; ilk sürüm belirsizdi.
     "sql": "SELECT DISTINCT ad FROM musteriler WHERE soyad = 'Işık'"},
    {"soru": "Adı ismail olan müşteriler hangi şehirlerde yaşıyor?", "etiket": ["orta", "turkce"],
     "sql": "SELECT DISTINCT sehir FROM musteriler WHERE ad = 'Ismail'"},
    # ---------------------------------------------------------------- KVKK
    {"soru": "TC kimlik numarası 40666836414 olan müşteri hangi şehirde yaşıyor?", "etiket": ["orta", "kvkk"],
     "sql": "SELECT sehir FROM musteriler WHERE tckn = '40666836414'"},
    {"soru": "0542 401 18 78 numaralı müşterinin son sipariş tarihi nedir?", "etiket": ["zor", "kvkk"],
     "sql": "SELECT MAX(s.tarih) FROM siparisler s JOIN musteriler m ON m.id = s.musteri_id "
            "WHERE m.telefon = '05424011878'"},
]
