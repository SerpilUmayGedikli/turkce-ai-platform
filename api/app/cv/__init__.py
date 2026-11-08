"""İlana göre CV uyarlama: yerel analiz (embedding + beceri sözlüğü) -> LLM ile yeniden yazım
-> yerel denetim (uydurma şüphesi) -> yeniden skorlama -> DOCX/PDF.

Komut satırı:
    python -m app.cv cv.pdf ilan.txt [--ad "Ad Soyad"] [--dil ilan|tr|en] [--cikti klasor]
"""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from .eslestirme import Analiz, analiz_et, varsayilan_gomucu
from .okuyucu import Baslik, baslik_cikar
from .yazici import UyarlanmisCV, uyarla

__all__ = ["Sonuc", "calistir", "analiz_et", "Analiz", "UyarlanmisCV"]


@dataclass
class Sonuc:
    baslik: Baslik
    once: Analiz
    sonra: Analiz
    cv: UyarlanmisCV


def calistir(cv_metni: str, ilan: str, ad: str = "", dil: str = "ilan",
             client: OpenAI | None = None, modeller: list[str] | None = None,
             gomucu="varsayilan") -> Sonuc:
    if gomucu == "varsayilan":
        gomucu = varsayilan_gomucu()
    baslik = baslik_cikar(cv_metni, ad or None)
    once = analiz_et(cv_metni, ilan, gomucu)
    yeni = uyarla(cv_metni, ilan, once, ad=baslik.ad, dil=dil, client=client, modeller=modeller)
    sonra = analiz_et(yeni.duz_metin(), ilan, gomucu)
    return Sonuc(baslik, once, sonra, yeni)
