"""Güvenli SQL çalıştırma: modelin yazdığı sorguya ASLA güvenme.

Üç katman koruma:
  1. Salt okunur bağlantı (mode=ro): dosyaya yazılamaz
  2. Yetkilendirici (authorizer): SELECT dışındaki her işlem reddedilir (DELETE, ATTACH, PRAGMA...)
  3. Kaynak sınırı: en fazla 50 satır döner, çok uzun süren sorgu kesilir

Türkçe ayrıntı: SQLite'ın LOWER() ve LIKE'ı sadece ASCII harfleri tanır.
LOWER('İSTANBUL') 'istanbul' değil 'İstanbul' verir (İ olduğu gibi kalır), 'Ş' LIKE 'ş' eşleşmez.
Bu yüzden Türkçe kurallarla çalışan tr_lower() fonksiyonunu veritabanına ekliyoruz.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .olustur import VERI_YOLU, olustur

MAKS_SATIR = 50
MAKS_ADIM = 5_000_000  # SQLite sanal makine adımı; aşılırsa sorgu kesilir

_IZINLI = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
_RECURSIVE = getattr(sqlite3, "SQLITE_RECURSIVE", None)
if _RECURSIVE is not None:
    _IZINLI.add(_RECURSIVE)


def tr_lower(s):
    if s is None:
        return None
    return str(s).replace("I", "ı").replace("İ", "i").lower()


def tr_katla(s):
    """Karşılaştırma için katlama: Türkçe küçük harf + I/İ/ı/i farkını yok say.

    Neden? İlk ölçümde model tr_lower(sehir) = 'isparta' yazdı (doğrusu 'ısparta'):
    harf dönüşümünü kafasında İngilizce kuralla yaptı. tr_katla ile iki taraf da aynı
    fonksiyondan geçer, model dönüşüm yapmak zorunda kalmaz. Bonus: 'Ismail' = 'İsmail'.
    """
    if s is None:
        return None
    return tr_lower(s).replace("ı", "i")


def _yetki(eylem, *_):
    return sqlite3.SQLITE_OK if eylem in _IZINLI else sqlite3.SQLITE_DENY


def baglan(yol: Path = VERI_YOLU) -> sqlite3.Connection:
    if not yol.exists():
        olustur(yol)
    db = sqlite3.connect(f"file:{yol.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    db.create_function("tr_lower", 1, tr_lower, deterministic=True)
    db.create_function("tr_katla", 1, tr_katla, deterministic=True)
    db.set_authorizer(_yetki)
    sayac = {"n": 0}

    def ilerleme():
        sayac["n"] += 1
        return 1 if sayac["n"] * 1000 > MAKS_ADIM else 0  # 1 -> sorguyu kes

    db.set_progress_handler(ilerleme, 1000)
    return db


def sorgula(sql: str, yol: Path = VERI_YOLU) -> tuple[list[str], list[tuple]]:
    """Sütun adları ve satırları döner. Hata olursa sqlite3.Error fırlatır."""
    sql = sql.strip().rstrip(";")
    if ";" in sql:
        raise sqlite3.ProgrammingError("Tek seferde yalnızca bir sorgu çalıştırılabilir.")
    db = baglan(yol)
    try:
        imlec = db.execute(sql)
        sutunlar = [d[0] for d in imlec.description or []]
        return sutunlar, imlec.fetchmany(MAKS_SATIR + 1)
    finally:
        db.close()


def tablo_metni(sutunlar: list[str], satirlar: list[tuple]) -> str:
    """Modelin okuyacağı kısa tablo."""
    if not satirlar:
        return "Sonuç boş (0 satır)."
    kesik = len(satirlar) > MAKS_SATIR
    satirlar = satirlar[:MAKS_SATIR]
    bicim = lambda v: f"{v:.2f}" if isinstance(v, float) else str(v)  # noqa: E731
    metin = [" | ".join(sutunlar)] + [" | ".join(bicim(v) for v in s) for s in satirlar]
    if kesik:
        metin.append(f"... (ilk {MAKS_SATIR} satır gösterildi, sorguyu daralt)")
    return "\n".join(metin)


SEMA_ACIKLAMASI = """SQLite veritabanı (Türkçe e-ticaret mağazası). Tablolar:
- kategoriler(id, ad)  ad örnekleri: 'Elektronik','Giyim','Ev & Yaşam','Kitap','Kozmetik','Spor','Oyuncak','Aksesuar'
- urunler(id, ad, kategori_id -> kategoriler.id, fiyat REAL TL, stok INTEGER)
- musteriler(id, ad, soyad, sehir, tckn, telefon, eposta, kayit_tarihi 'YYYY-MM-DD')
  sehir değerleri Türkçe karakterle yazılır: 'İstanbul','İzmir','Iğdır','Isparta','Eskişehir','Şanlıurfa'...
  telefon '05321234567' biçiminde (boşluksuz)
- siparisler(id, musteri_id -> musteriler.id, tarih 'YYYY-MM-DD', durum)
  durum: 'teslim edildi' | 'kargoda' | 'iptal' | 'iade'
- siparis_kalemleri(id, siparis_id -> siparisler.id, urun_id -> urunler.id, adet, birim_fiyat REAL TL)
Kurallar:
- Veri 2025-01-01 ile 2026-10-31 arasını kapsar. 'Bugün' 2026-11-01 kabul edilir ('geçen ay' = Ekim 2026).
- Ciro/tutar = SUM(adet * birim_fiyat). Soru aksini söylemedikçe 'iptal' siparişleri ciroya katma.
- SQLite LOWER/LIKE Türkçe harfleri tanımaz. Metin karşılaştırırken İKİ TARAFI da tr_katla()
  ile sar ve kullanıcının yazdığı değeri olduğu gibi ver; büyük/küçük harf dönüşümünü kendin yapma:
  tr_katla(sehir) = tr_katla('ISPARTA'),  tr_katla(ad) LIKE '%' || tr_katla('Çanta') || '%'.
- Yalnızca tek bir SELECT sorgusu yazılabilir; en fazla 50 satır döner."""
