"""Demo veritabanı: Türkçe bir e-ticaret mağazası (SQLite, tekrarlanabilir).

Tüm kişiler, kimlik numaraları ve telefonlar RASTGELE üretilir; gerçek kişilere ait değildir.
Müşteri tablosunda bilerek kişisel veri (TCKN, telefon, e-posta) var: KVKK Kalkanı'nın sorgu
sonuçlarını da maskelediğini göstermek için.

Neden SQLite? Sunucu gerektirmez, tek dosyadır, Docker olmadan çalışır.
Sorgular standart SQL; ileride Postgres'e taşımak kolay.

Çalıştır:  cd api && python -m app.veritabani.olustur
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

VERI_YOLU = Path(__file__).resolve().parents[2] / "data" / "magaza.db"
BASLANGIC, BITIS = date(2025, 1, 1), date(2026, 10, 31)  # verinin kapsadığı dönem

SEMA_SQL = """
CREATE TABLE kategoriler (
    id INTEGER PRIMARY KEY,
    ad TEXT NOT NULL
);
CREATE TABLE urunler (
    id INTEGER PRIMARY KEY,
    ad TEXT NOT NULL,
    kategori_id INTEGER NOT NULL REFERENCES kategoriler(id),
    fiyat REAL NOT NULL,          -- TL
    stok INTEGER NOT NULL
);
CREATE TABLE musteriler (
    id INTEGER PRIMARY KEY,
    ad TEXT NOT NULL,
    soyad TEXT NOT NULL,
    sehir TEXT NOT NULL,
    tckn TEXT NOT NULL,
    telefon TEXT NOT NULL,
    eposta TEXT NOT NULL,
    kayit_tarihi TEXT NOT NULL    -- YYYY-MM-DD
);
CREATE TABLE siparisler (
    id INTEGER PRIMARY KEY,
    musteri_id INTEGER NOT NULL REFERENCES musteriler(id),
    tarih TEXT NOT NULL,          -- YYYY-MM-DD
    durum TEXT NOT NULL           -- 'teslim edildi' | 'kargoda' | 'iptal' | 'iade'
);
CREATE TABLE siparis_kalemleri (
    id INTEGER PRIMARY KEY,
    siparis_id INTEGER NOT NULL REFERENCES siparisler(id),
    urun_id INTEGER NOT NULL REFERENCES urunler(id),
    adet INTEGER NOT NULL,
    birim_fiyat REAL NOT NULL     -- satış anındaki fiyat, TL
);
"""

KATEGORILER = {
    "Elektronik": [("Kablosuz Kulaklık", 1899), ("Akıllı Saat", 4299), ("Bluetooth Hoparlör", 1299),
                   ("Laptop Çantası", 749), ("Powerbank 20000 mAh", 899), ("Oyuncu Faresi", 1149),
                   ("Mekanik Klavye", 2499), ("Tablet 10 inç", 8999)],
    "Giyim": [("Pamuklu Tişört", 349), ("Kot Pantolon", 899), ("Kapüşonlu Sweatshirt", 749),
              ("Kışlık Mont", 2799), ("Keten Gömlek", 649), ("Yün Kazak", 999), ("Deri Ceket", 4599)],
    "Ev & Yaşam": [("Seramik Kupa Seti", 399), ("Pamuk Nevresim Takımı", 1199), ("Türk Kahvesi Makinesi", 1799),
                   ("Çelik Tencere Seti", 2899), ("Dekoratif Yastık", 249), ("Bambu Kesme Tahtası", 199),
                   ("Çay Makinesi", 1599)],
    "Kitap": [("Roman: Kırmızı Saçlı Kadın", 189), ("Python ile Veri Bilimi", 449), ("Osmanlı Tarihi Atlası", 599),
              ("Çocuk Masalları Seti", 299), ("İstatistiğe Giriş", 379), ("Şiir Antolojisi", 159)],
    "Kozmetik": [("Nemlendirici Krem", 329), ("Güneş Kremi SPF50", 449), ("Parfüm 100 ml", 1899),
                 ("Doğal Zeytinyağlı Sabun", 89), ("Şampuan 500 ml", 159), ("Makyaj Fırçası Seti", 549)],
    "Spor": [("Yoga Matı", 499), ("Dambıl Seti 10 kg", 1299), ("Koşu Ayakkabısı", 2899),
             ("Spor Çantası", 699), ("Termos 750 ml", 449), ("Kamp Çadırı", 3499), ("Bisiklet Kaskı", 999)],
    "Oyuncak": [("Lego Seti", 1499), ("Peluş Ayı", 299), ("Ahşap Yapboz", 199), ("Uzaktan Kumandalı Araba", 899),
                ("Satranç Takımı", 449)],
    "Aksesuar": [("Deri Çanta", 1999), ("Sırt Çantası", 899), ("Güneş Gözlüğü", 1299), ("Deri Cüzdan", 599),
                 ("İpek Eşarp", 799), ("Çelik Kol Saati", 3299), ("Kartlık", 249)],
}

SEHIRLER = [("İstanbul", 30), ("Ankara", 12), ("İzmir", 10), ("Bursa", 6), ("Antalya", 6), ("Eskişehir", 4),
            ("Diyarbakır", 3), ("Şanlıurfa", 3), ("Muğla", 3), ("Çanakkale", 2), ("Isparta", 2), ("Iğdır", 2),
            ("Kırklareli", 2), ("Trabzon", 4), ("Gaziantep", 4), ("Konya", 5)]
ADLAR = ["Ayşe", "Mehmet", "Zeynep", "Can", "Elif", "Burak", "Selin", "Emre", "Şule", "Oğuz", "İrem", "Ömer",
         "Şeyma", "Ufuk", "Gizem", "Hakan", "Çağla", "Ismail", "Derya", "Kemal", "Büşra", "Şahin", "Ece", "Yusuf"]
SOYADLAR = ["Yılmaz", "Kaya", "Demir", "Çelik", "Şahin", "Öztürk", "Aydın", "Arslan", "Doğan", "Kılıç",
            "Aslan", "Çetin", "Koç", "Kurt", "Özdemir", "Işık", "Güneş", "Erdoğan"]
_ASCII = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def _tckn(r: random.Random) -> str:
    d = [r.randint(1, 9)] + [r.randint(0, 9) for _ in range(8)]
    d.append(((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10)
    d.append(sum(d) % 10)
    return "".join(map(str, d))


def _tarih(r: random.Random, bas: date, bit: date) -> date:
    return bas + timedelta(days=r.randint(0, (bit - bas).days))


def olustur(yol: Path = VERI_YOLU, seed: int = 7) -> Path:
    r = random.Random(seed)
    yol.parent.mkdir(parents=True, exist_ok=True)
    if yol.exists():
        yol.unlink()
    db = sqlite3.connect(yol)
    db.executescript(SEMA_SQL)

    urun_fiyat: dict[int, float] = {}
    uid = 0
    for kid, (kategori, urunler) in enumerate(KATEGORILER.items(), start=1):
        db.execute("INSERT INTO kategoriler VALUES (?, ?)", (kid, kategori))
        for ad, fiyat in urunler:
            uid += 1
            stok = 0 if r.random() < 0.12 else r.randint(1, 250)
            db.execute("INSERT INTO urunler VALUES (?, ?, ?, ?, ?)", (uid, ad, kid, float(fiyat), stok))
            urun_fiyat[uid] = float(fiyat)
    # popülerlik: bazı ürünler çok daha fazla satar
    urun_agirlik = {u: r.paretovariate(1.3) for u in urun_fiyat}

    sehirler, sehir_agirlik = zip(*SEHIRLER)
    musteri_sayisi = 320
    for mid in range(1, musteri_sayisi + 1):
        ad, soyad = r.choice(ADLAR), r.choice(SOYADLAR)
        tel = f"05{r.choice(['32', '33', '42', '05', '55', '44'])}{r.randint(0, 9999999):07d}"
        eposta = f"{ad.lower().translate(_ASCII)}.{soyad.lower().translate(_ASCII)}{mid}@ornekmail.com"
        db.execute(
            "INSERT INTO musteriler VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (mid, ad, soyad, r.choices(sehirler, sehir_agirlik)[0], _tckn(r), tel, eposta,
             _tarih(r, date(2024, 6, 1), BITIS).isoformat()),
        )
    # müşterilerin ~%12'si hiç sipariş vermez; diğerlerinin aktiflik düzeyi farklı
    aktiflik = {m: (0.0 if r.random() < 0.12 else r.paretovariate(1.6)) for m in range(1, musteri_sayisi + 1)}

    sid = kid_ = 0
    urunler_liste, agirliklar = list(urun_agirlik), list(urun_agirlik.values())
    musteriler_liste, m_agirlik = list(aktiflik), list(aktiflik.values())
    for _ in range(3200):
        sid += 1
        # büyüyen mağaza: 2026'da daha çok sipariş
        t = _tarih(r, BASLANGIC, BITIS)
        if t.year == 2025 and r.random() < 0.3:
            t = _tarih(r, date(2026, 1, 1), BITIS)
        if (BITIS - t).days < 7:
            durum = "kargoda"
        else:
            durum = r.choices(["teslim edildi", "iptal", "iade"], [88, 7, 5])[0]
        db.execute("INSERT INTO siparisler VALUES (?, ?, ?, ?)",
                   (sid, r.choices(musteriler_liste, m_agirlik)[0], t.isoformat(), durum))
        for urun in set(r.choices(urunler_liste, agirliklar, k=r.choice([1, 1, 1, 2, 2, 3, 4]))):
            kid_ += 1
            indirim = r.choice([1.0, 1.0, 1.0, 0.9, 0.85])
            db.execute("INSERT INTO siparis_kalemleri VALUES (?, ?, ?, ?, ?)",
                       (kid_, sid, urun, r.choice([1, 1, 1, 2, 3]), round(urun_fiyat[urun] * indirim, 2)))
    db.commit()
    db.close()
    return yol


if __name__ == "__main__":
    print(f"Veritabanı oluşturuldu -> {olustur()}")
