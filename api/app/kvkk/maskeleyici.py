"""Maskeleme ve geri yükleme.

    "TC'm 10000000146, IBAN TR33 0006 1005 1978 6457 8413 26"
 -> "TC'm [TCKN_1], IBAN [IBAN_1]"          (modele giden)
 <- "[TCKN_1] numaralı kaydınız bulundu"     (modelden gelen)
 -> "10000000146 numaralı kaydınız bulundu"  (kullanıcıya giden)

Aynı değer konuşma boyunca hep aynı etiketi alır, böylece model "bu iki mesajdaki TC aynı mı?"
sorusunu gerçek değeri görmeden cevaplayabilir. Eşleme tablosu sadece bu süreçte, bellekte durur.
"""

from __future__ import annotations

import re
from collections import Counter

from .tespit import bul

_ETIKET = re.compile(r"\[(?:TCKN|IBAN|TELEFON|EPOSTA|KART)_\d+\]")


def _normal(tur: str, deger: str) -> str:
    # "TR33 0006..." ile "TR330006..." aynı IBAN; aynı etiketi almalı
    if tur in ("IBAN", "KART", "TELEFON"):
        deger = re.sub(r"[^0-9A-Za-z]", "", deger).upper()
        if tur == "TELEFON":
            deger = deger[-10:]
    return deger.lower() if tur == "EPOSTA" else deger


class Maskeleyici:
    def __init__(self) -> None:
        self._etiketten: dict[str, str] = {}  # [TCKN_1] -> gerçek değer
        self._degerden: dict[tuple[str, str], str] = {}
        self._sayac: Counter[str] = Counter()
        self.istatistik: Counter[str] = Counter()  # tür -> kaç kez maskelendi

    def maskele(self, metin: str) -> str:
        parcalar, son = [], 0
        for b in bul(metin):
            anahtar = (b.tur, _normal(b.tur, b.metin))
            if anahtar not in self._degerden:
                self._sayac[b.tur] += 1
                etiket = f"[{b.tur}_{self._sayac[b.tur]}]"
                self._degerden[anahtar] = etiket
                self._etiketten[etiket] = b.metin
            parcalar += [metin[son : b.baslangic], self._degerden[anahtar]]
            son = b.bitis
            self.istatistik[b.tur] += 1
        parcalar.append(metin[son:])
        return "".join(parcalar)

    def geri_yukle(self, metin: str) -> str:
        return _ETIKET.sub(lambda m: self._etiketten.get(m.group(), m.group()), metin)

    def geri_yukle_derin(self, veri):
        """Araç argümanları gibi iç içe yapılarda (dict/list) etiketleri geri yükler."""
        if isinstance(veri, str):
            return self.geri_yukle(veri)
        if isinstance(veri, dict):
            return {k: self.geri_yukle_derin(v) for k, v in veri.items()}
        if isinstance(veri, list):
            return [self.geri_yukle_derin(v) for v in veri]
        return veri
