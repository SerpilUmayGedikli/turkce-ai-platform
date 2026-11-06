"""Elle yazılmış ZOR örnekler: gerçek hayattaki dağınık yazım biçimleri.

Sentetik set kendi kurallarımızla üretildiği için iyimserdir. Bu set ise sistemin
nerede kırıldığını DÜRÜSTÇE göstermek için var; bazı örnekleri kaçırmamız bekleniyor.
Etiket = bir insanın kişisel veri olarak işaretleyeceği metin parçası.
"""

from __future__ import annotations

# (metin, [(tür, metnin içindeki parça), ...])
_HAM: list[tuple[str, list[tuple[str, str]]]] = [
    ("T.C. no'm 12345678950'dir.", [("TCKN", "12345678950")]),
    ("TCKN'm12345678950 olarak kayıtlı", [("TCKN", "12345678950")]),
    ("TC: 123 456 789 50", [("TCKN", "123 456 789 50")]),
    ("Beni 0532 1234567 numarasından arayın", [("TELEFON", "0532 1234567")]),
    ("05321234567'yi arayın lütfen", [("TELEFON", "05321234567")]),
    ("Yurtdışından: +90 (532) 123 45 67", [("TELEFON", "+90 (532) 123 45 67")]),
    ("Numaram 0 532 123 45 67", [("TELEFON", "0 532 123 45 67")]),
    ("Ofis sabit hattı 212 345 67 89", [("TELEFON", "212 345 67 89")]),
    ("IBAN'ım TR330006100519786457841326.", [("IBAN", "TR330006100519786457841326")]),
    ("IBAN: TR33-0006-1005-1978-6457-8413-26", [("IBAN", "TR33-0006-1005-1978-6457-8413-26")]),
    ("mail: ali [at] ornek [dot] com", [("EPOSTA", "ali [at] ornek [dot] com")]),
    ("İletişim: ayşe.yılmaz@şirket.com.tr", [("EPOSTA", "ayşe.yılmaz@şirket.com.tr")]),
    ("e-posta: Ali.Veli@Ornek.COM", [("EPOSTA", "Ali.Veli@Ornek.COM")]),
    ("Amex kartım 3782 822463 10005", [("KART", "3782 822463 10005")]),
    ("Kart: 4111-1111-1111-1111, son kullanma 12/28", [("KART", "4111-1111-1111-1111")]),
    ("Doğum tarihim 01.01.1990, telefonum 05551234567", [("TELEFON", "05551234567")]),
    # --- kişisel veri İÇERMEYENLER (yanlış pozitif tuzakları)
    ("Kargo takip numaranız 10000000146", []),  # TCKN algoritmasını tesadüfen geçen sayı
    ("Stok kodu 5551234567 olan üründen 3 adet", []),  # cep telefonuna benzeyen kod
    ("Vergi no 1234567890, sipariş 98765432101", []),
    ("Kartınızın son 4 hanesi 1111", []),
    ("Fiyat 1.250.000 TL, peşinat 250.000 TL", []),
    ("Müşteri hizmetleri: 444 1 444", []),
]


def ornekler() -> list[dict]:
    sonuc = []
    for metin, etiketler in _HAM:
        varliklar = []
        for tur, parca in etiketler:
            bas = metin.index(parca)
            varliklar.append({"tur": tur, "baslangic": bas, "bitis": bas + len(parca)})
        sonuc.append({"metin": metin, "varliklar": varliklar})
    return sonuc
