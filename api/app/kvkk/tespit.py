"""Türkçe kişisel veri (KVKK) tespit kuralları.

Fark yaratan nokta: sadece regex değil, DOĞRULAMA. Her 11 haneli sayı TC kimlik no değildir;
TCKN'nin, IBAN'ın ve kart numarasının matematiksel kontrol haneleri vardır. Bu sayede sipariş
numarası, fatura no gibi sayıları yanlışlıkla maskelemeyiz (yanlış pozitif azalır).

Desteklenen türler: TCKN, IBAN, TELEFON, EPOSTA, KART
Henüz desteklenmeyen: AD_SOYAD, ADRES (kurallarla zor; NER modeli gerekir -> sonraki adım)
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Bulgu:
    tur: str
    baslangic: int
    bitis: int
    metin: str


# ------------------------------------------------------------------ doğrulayıcılar
def tckn_gecerli(s: str) -> bool:
    """TC kimlik no algoritması: 11 hane, ilk hane 0 değil, 10. ve 11. hane kontrol hanesi."""
    if len(s) != 11 or not s.isdigit() or s[0] == "0":
        return False
    d = [int(c) for c in s]
    h10 = ((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10
    h11 = sum(d[:10]) % 10
    return d[9] == h10 and d[10] == h11


def iban_gecerli(s: str) -> bool:
    """ISO 13616 mod-97 kontrolü. TR IBAN: 'TR' + 24 hane = 26 karakter."""
    s = s.replace(" ", "").upper()
    if not re.fullmatch(r"TR\d{24}", s):
        return False
    yeniden = s[4:] + s[:4]
    sayi = "".join(str(int(c, 36)) for c in yeniden)  # T=29, R=27
    return int(sayi) % 97 == 1


def luhn_gecerli(s: str) -> bool:
    rakamlar = [int(c) for c in s if c.isdigit()]
    if not 13 <= len(rakamlar) <= 19:
        return False
    toplam = 0
    for i, r in enumerate(reversed(rakamlar)):
        if i % 2 == 1:
            r *= 2
            if r > 9:
                r -= 9
        toplam += r
    return toplam % 10 == 0


# ------------------------------------------------------------------ desenler
# (?<!\d) ve (?!\d): daha uzun bir sayının parçasını yakalamamak için.
_TCKN = re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")
_IBAN = re.compile(r"(?<![A-Za-z0-9])TR\d{2}(?:[ ]?\d{4}){5}[ ]?\d{2}(?!\d)", re.IGNORECASE)
_KART = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")
_EPOSTA = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# +90 / 0090 / 0 ile başlayan her numara; ön ek yoksa yalnızca 5xx cep numaraları
_TELEFON = re.compile(
    r"(?<![\d+])(?:"
    r"\(?(?:\+90|0090|0)[ .-]?\(?[2-5]\d{2}\)?"  # "(0532) ..." biçimi için baştaki \(?
    r"|\(?5\d{2}\)?"
    r")[ .-]?\d{3}[ .-]?\d{2}[ .-]?\d{2}(?!\d)"
)

# Öncelik: çakışmada önce gelen kazanır (IBAN içindeki rakamlar kart sanılmasın)
_KURALLAR = [
    ("IBAN", _IBAN, iban_gecerli),
    ("EPOSTA", _EPOSTA, None),
    ("TCKN", _TCKN, tckn_gecerli),
    ("KART", _KART, luhn_gecerli),
    ("TELEFON", _TELEFON, None),
]

TURLER = [ad for ad, _, _ in _KURALLAR]


def bul(metin: str) -> list[Bulgu]:
    adaylar: list[tuple[int, Bulgu]] = []
    for oncelik, (tur, desen, dogrula) in enumerate(_KURALLAR):
        for m in desen.finditer(metin):
            if dogrula is None or dogrula(m.group()):
                adaylar.append((oncelik, Bulgu(tur, m.start(), m.end(), m.group())))

    # Çakışmaları çöz: önce öncelik, sonra uzunluk
    adaylar.sort(key=lambda x: (x[0], -(x[1].bitis - x[1].baslangic)))
    secilen: list[Bulgu] = []
    for _, b in adaylar:
        if all(b.bitis <= s.baslangic or b.baslangic >= s.bitis for s in secilen):
            secilen.append(b)
    return sorted(secilen, key=lambda b: b.baslangic)
