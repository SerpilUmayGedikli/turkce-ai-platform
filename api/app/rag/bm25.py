"""BM25 (Okapi): kelime eşleşmesine dayalı klasik sıralama. Kütüphanesiz, ~30 satır.

skor(q, d) = Σ idf(t) * f(t,d) * (k1 + 1) / (f(t,d) + k1 * (1 - b + b * |d| / ort|d|))
"""

from __future__ import annotations

import math
from collections import Counter


class BM25:
    def __init__(self, belgeler: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.frekanslar = [Counter(d) for d in belgeler]
        self.uzunluklar = [len(d) for d in belgeler]
        self.ort = sum(self.uzunluklar) / max(len(belgeler), 1)
        df = Counter(t for d in belgeler for t in set(d))
        n = len(belgeler)
        self.idf = {t: math.log(1 + (n - s + 0.5) / (s + 0.5)) for t, s in df.items()}

    def skorlar(self, sorgu: list[str]) -> list[float]:
        sonuc = []
        for f, uzunluk in zip(self.frekanslar, self.uzunluklar):
            skor = 0.0
            for t in sorgu:
                if t in f:
                    pay = f[t] * (self.k1 + 1)
                    payda = f[t] + self.k1 * (1 - self.b + self.b * uzunluk / self.ort)
                    skor += self.idf[t] * pay / payda
            sonuc.append(skor)
        return sonuc
