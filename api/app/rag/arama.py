"""Türkçe hibrit arama: BM25 (kelime) + embedding (anlam), RRF ile birleştirme.

Neden hibrit? BM25 "taksit", "IBAN", "48 saat" gibi kesin terimleri iyi bulur ama
"parayı ne zaman geri alırım" ile "para iadesi"ni eşleştiremez. Embedding anlamı yakalar ama
nadir terimlerde ve sayılarda zayıftır. RRF (Reciprocal Rank Fusion) iki sıralamayı skorları
ölçeklemeden, sadece sıralara bakarak birleştirir:  rrf(d) = Σ 1 / (k + sıra(d)),  k = 60.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from .belgeler import Parca, yukle
from .bm25 import BM25
from .turkce import isle
from .vektor import VARSAYILAN_MODEL, Gomucu, fastembed_gomucu, onbellekli

YONTEMLER = ["bm25-ham", "bm25-kok", "bm25-on5", "vektor", "hibrit-kok", "hibrit-on5"]
# eval/rag_degerlendir.py sonucuna göre seçildi (50 soruda en yüksek Recall@5). Aynı set üzerinde
# seçildiği için iyimserdir; ayrı bir doğrulama setiyle teyit edilmeli.
VARSAYILAN_YONTEM = "hibrit-on5"


def rrf(siralamalar: list[list[int]], k: int = 60) -> list[int]:
    skor: dict[int, float] = {}
    for siralama in siralamalar:
        for sira, i in enumerate(siralama, 1):
            skor[i] = skor.get(i, 0.0) + 1 / (k + sira)
    return sorted(skor, key=lambda i: -skor[i])


class Arama:
    def __init__(self, parcalar: list[Parca], gomucu: Gomucu | None = None,
                 model_adi: str = VARSAYILAN_MODEL) -> None:
        self.parcalar = parcalar
        metinler = [p.tam_metin for p in parcalar]
        self.bm25 = {y: BM25([isle(m, y) for m in metinler]) for y in ("ham", "kok", "on5")}
        self.gomucu = gomucu
        self.vektorler = onbellekli(gomucu, metinler, model_adi) if gomucu else None

    def _bm25_sirala(self, sorgu: str, yontem: str) -> list[int]:
        skorlar = self.bm25[yontem].skorlar(isle(sorgu, yontem))
        # Hiç ortak terimi olmayan parçalar sıralamaya girmez (0 skorlular arası sıra rastgele olurdu)
        return [i for i in np.argsort(skorlar)[::-1] if skorlar[i] > 0]

    def _vektor_sirala(self, sorgu: str) -> list[int]:
        if self.vektorler is None:
            raise RuntimeError("Embedding modeli yüklü değil")
        benzerlik = self.vektorler @ self.gomucu([sorgu])[0]
        return list(np.argsort(benzerlik)[::-1])

    def sirala(self, sorgu: str, yontem: str = VARSAYILAN_YONTEM) -> list[int]:
        tur, _, alt = yontem.partition("-")
        if tur == "bm25":
            return self._bm25_sirala(sorgu, alt)
        if tur == "vektor":
            return self._vektor_sirala(sorgu)
        if tur == "hibrit":
            if self.vektorler is None:  # embedding yoksa kelime aramasıyla devam et
                return self._bm25_sirala(sorgu, alt)
            return rrf([self._bm25_sirala(sorgu, alt), self._vektor_sirala(sorgu)])
        raise ValueError(f"Bilinmeyen yöntem: {yontem}")

    def ara(self, sorgu: str, n: int = 3, yontem: str = VARSAYILAN_YONTEM) -> list[Parca]:
        return [self.parcalar[i] for i in self.sirala(sorgu, yontem)[:n]]


@lru_cache(maxsize=1)
def varsayilan() -> Arama:
    """Uygulamanın kullandığı arama motoru. Embedding yüklenemezse BM25 ile çalışır."""
    parcalar = yukle()
    try:
        return Arama(parcalar, fastembed_gomucu())
    except Exception:  # paket yok, model indirilemedi vb.
        return Arama(parcalar)
