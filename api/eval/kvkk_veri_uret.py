"""Sentetik, etiketli KVKK test seti üretir (tekrarlanabilir: seed sabit).

Tüm kimlik/IBAN/kart numaraları RASTGELE üretilir; gerçek kişilere ait değildir.
Setin içinde bilerek "tuzak" sayılar var: sipariş no, fatura no, takip no gibi
kişisel veri OLMAYAN ama kişisel veriye benzeyen sayılar. Yanlış pozitifi bunlar ölçer.

Çalıştır:  cd api && python -m eval.kvkk_veri_uret
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from app.kvkk.tespit import luhn_gecerli, tckn_gecerli

R = random.Random(42)
CIKTI = Path(__file__).parent / "veri" / "kvkk_sentetik.jsonl"


# ------------------------------------------------------------------ üreticiler
def tckn() -> str:
    d = [R.randint(1, 9)] + [R.randint(0, 9) for _ in range(8)]
    d.append(((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10)
    d.append(sum(d) % 10)
    return "".join(map(str, d))


def iban() -> str:
    bban = f"{R.randint(0, 99999):05d}0" + "".join(str(R.randint(0, 9)) for _ in range(16))
    kontrol = 98 - int(bban + "292700") % 97
    s = f"TR{kontrol:02d}{bban}"
    stil = R.choice(["bitisik", "bosluklu", "bosluklu", "kucuk"])
    if stil == "bitisik":
        return s
    bosluklu = " ".join(s[i : i + 4] for i in range(0, 26, 4))
    return bosluklu.lower() if stil == "kucuk" else bosluklu


def telefon() -> str:
    alan = R.choice(["532", "533", "542", "505", "555", "212", "216", "312", "232"])
    n = f"{R.randint(0, 999):03d}{R.randint(0, 99):02d}{R.randint(0, 99):02d}"
    a, b, c = n[:3], n[3:5], n[5:]
    cep = alan.startswith("5")
    bicimler = [
        f"0{alan} {a} {b} {c}",
        f"0{alan}{n}",
        f"+90 {alan} {a} {b} {c}",
        f"+90{alan}{n}",
        f"(0{alan}) {a} {b} {c}",
        f"0{alan}-{a}-{b}-{c}",
        f"0{alan} {a} {b}{c}",
    ]
    if cep:
        bicimler += [f"{alan} {a} {b} {c}", f"{alan}{n}"]
    return R.choice(bicimler)


ADLAR = ["ayse", "mehmet", "zeynep", "can", "elif", "burak", "selin", "emre", "şule", "oğuz"]
SOYADLAR = ["yilmaz", "kaya", "demir", "celik", "sahin", "ozturk", "aydin", "arslan"]
ALANLAR = ["gmail.com", "hotmail.com", "outlook.com", "sirket.com.tr", "ogr.edu.tr", "yahoo.com"]


def eposta() -> str:
    ad, soyad = R.choice(ADLAR), R.choice(SOYADLAR)
    yerel = R.choice([f"{ad}.{soyad}", f"{ad}{soyad}{R.randint(1, 99)}", f"{ad}_{soyad}", ad])
    return f"{yerel}@{R.choice(ALANLAR)}"


def kart() -> str:
    while True:
        s = R.choice(["4", "5", "9792"]) + "".join(str(R.randint(0, 9)) for _ in range(14))
        s = s[:15]
        for son in range(10):
            if luhn_gecerli(s + str(son)):
                s += str(son)
                break
        ayrac = R.choice([" ", "-", ""])
        return ayrac.join(s[i : i + 4] for i in range(0, 16, 4))


# Tuzaklar: kişisel veri değil ama benziyor
def siparis_no() -> str:  # 11 hane, TCKN algoritmasını GEÇMEYEN
    while True:
        s = str(R.randint(10**10, 10**11 - 1))
        if not tckn_gecerli(s):
            return s


def fatura_no() -> str:  # 16 hane, Luhn'u GEÇMEYEN
    while True:
        s = "".join(str(R.randint(0, 9)) for _ in range(16))
        if not luhn_gecerli(s):
            return s


def tutar() -> str:
    return f"{R.randint(100, 99999):,}".replace(",", ".") + R.choice([" TL", ",50 TL", " ₺"])


URETICILER = {
    "TCKN": tckn, "IBAN": iban, "TELEFON": telefon, "EPOSTA": eposta, "KART": kart,
    "SIPARIS": siparis_no, "FATURA": fatura_no, "TUTAR": tutar,
}
KISISEL = {"TCKN", "IBAN", "TELEFON", "EPOSTA", "KART"}

SABLONLAR = [
    "Merhaba, TC kimlik numaram {TCKN}, başvurumun durumunu öğrenebilir miyim?",
    "İadeyi {IBAN} numaralı hesaba yapar mısınız?",
    "Bana {TELEFON} numarasından ulaşabilirsiniz.",
    "E-posta adresim {EPOSTA}, faturayı oraya gönderin lütfen.",
    "Kartım {KART} ile ödeme yaptım ama {SIPARIS} numaralı sipariş görünmüyor.",
    "Sipariş numarası {SIPARIS}, toplam tutar {TUTAR}.",
    "{FATURA} numaralı faturanın tutarı {TUTAR} olarak görünüyor, hatalı değil mi?",
    "Adı soyadı belirtilen müşteri ({TCKN}) için {TELEFON} numarası kayıtlı.",
    "Kira bedeli {TUTAR}, ödeme {IBAN} hesabına yapılacak. İletişim: {EPOSTA}",
    "kimlik no:{TCKN} tel:{TELEFON}",
    "Müşteri {EPOSTA} adresinden yazdı, geri dönüş numarası {TELEFON}.",
    "Kredi kartı numarası {KART} olan müşterinin {TUTAR} tutarındaki işlemi iptal edilsin.",
    "Kargo takip no {SIPARIS}, alıcı telefonu {TELEFON}",
    "Lütfen {IBAN} IBAN'ına {TUTAR} gönderin, dekontu {EPOSTA} adresine iletin.",
    "{TCKN} TCKN'li personelin bordrosu {EPOSTA} adresine gönderildi.",
    "Faturanız: {FATURA}. Sorularınız için 444 0 444 veya {TELEFON}.",
    "Ödeme reddedildi. Kart: {KART}, sipariş: {SIPARIS}, tutar: {TUTAR}.",
    "Toplantı notları: bütçe {TUTAR}, sorumlu {EPOSTA}.",
    "Başvuru formu -> TC: {TCKN} | Tel: {TELEFON} | IBAN: {IBAN}",
    "Yeni tedarikçi kaydı: {IBAN}, irtibat {TELEFON}, fatura adresi e-postası {EPOSTA}.",
    "Referans kodu {SIPARIS} ile işlem yapıldı, kişisel veri içermez.",
    "Annemin TC'si {TCKN}, benimki {TCKN}. İkimizin de randevusu var mı?",
    "Sistemde {FATURA} ve {SIPARIS} numaralı iki kayıt var.",
    "WhatsApp: {TELEFON}",
    "Hesap özetimde {KART} kartından {TUTAR} çekim görünüyor.",
]


def ornek_uret(sablon: str) -> dict:
    metin, varliklar, i = "", [], 0
    while i < len(sablon):
        if sablon[i] == "{":
            j = sablon.index("}", i)
            tur = sablon[i + 1 : j]
            deger = URETICILER[tur]()
            if tur in KISISEL:
                varliklar.append({"tur": tur, "baslangic": len(metin), "bitis": len(metin) + len(deger)})
            metin += deger
            i = j + 1
        else:
            metin += sablon[i]
            i += 1
    return {"metin": metin, "varliklar": varliklar}


def main(adet: int = 500) -> None:
    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    with CIKTI.open("w", encoding="utf-8") as f:
        for k in range(adet):
            f.write(json.dumps(ornek_uret(SABLONLAR[k % len(SABLONLAR)]), ensure_ascii=False) + "\n")
    print(f"{adet} örnek yazıldı -> {CIKTI}")


if __name__ == "__main__":
    main()
