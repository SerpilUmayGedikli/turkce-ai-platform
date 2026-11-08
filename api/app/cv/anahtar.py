"""İlanın ATS anahtar kelimelerini çıkarır ve CV'deki kapsamasını ölçer (yerel ML, LLM'siz).

Yöntem (KeyBERT yaklaşımı):
  1. Aday ifadeler: ilandaki 1-3 kelimelik n-gramlar (durak/genel kelimeyle başlayıp bitenler
     elenir) + beceri sözlüğünün ilanda bulduğu beceriler.
  2. Her aday ve ilanın tamamı çok dilli embedding ile vektöre çevrilir; aday-ilan kosinüs
     benzerliği "bu ifade ilanı ne kadar temsil ediyor" puanıdır. Sözlük becerilerine küçük bir
     bonus verilir (ATS'ler en çok somut beceri adına bakar).
  3. MMR (Maximal Marginal Relevance) ile birbirinin tekrarı olan ifadeler elenir
     ("makine öğrenmesi" ve "makine öğrenmesi modelleri" ikisi birden seçilmez).
  Embedding modeli yoksa ilandaki tekrar sıklığı ve ifade uzunluğuyla puanlanır.

Kapsama: ifadenin anlamlı kelimelerinin kökleri (ilk 5 harf) CV'de geçiyorsa ya da ifadedeki
sözlük becerisi CV'de (doğrudan/dolaylı) varsa "var" sayılır.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass

import numpy as np

from ..rag.turkce import DURAK, isle
from ..rag.vektor import Gomucu
from ..veritabani.sorgu import tr_katla, tr_lower
from . import beceriler

MAKS_ANAHTAR = 18
MMR_LAMBDA = 0.55
BECERI_BONUSU = 0.12

# İlanlarda sık geçen ama tek başına anahtar kelime olmayan sözcükler (TR + EN, ilk 5 harf)
_GENEL = set(isle("""
deneyim tecrübe tecrübeli bilgi bilgisi sahip olmak yıl yıllık iyi güçlü tercihen tercih aranan
aday adayların konusunda alanında ekip çalışma şirket pozisyon minimum en az derece derecede
kullanım kullanabilen yetkin yetkinlik beceri becerisi temel ileri seviye düzey ortam süreç
sorumluluk görev tanım nitelik nitelikler iş işe katkı fırsat uygun proje projeler model modeller
experience years strong knowledge ability skills skill good excellent working work preferred plus
required requirements familiarity understanding team company role position least level using
use proficiency proficient solid hands ability environment responsibilities qualifications
the and with for from into our you your will are have has able must nice
""", "on5"))
_EN_DURAK = {"the", "and", "or", "of", "in", "to", "for", "a", "an", "with", "on", "at", "by", "as",
             "is", "are", "be", "we", "you", "our", "your", "will", "from", "into", "this", "that"}
_KELIME = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9+#][A-Za-zÇĞİÖŞÜçğıöşü0-9+#.\-]*")
_PARCA = re.compile(r"[,;:.!?()\[\]/|•\n\t–]+")


@dataclass
class Anahtar:
    ifade: str
    puan: float
    var: bool = False


# Fiiller ("arıyoruz", "geliştirecek", "katılacak") ve iyelik ekiyle başlayan yarım tamlamalar
# ("öğrenmesi modelleri": başı "makine" olmadan anlamsız) anahtar kelime olamaz
_FIIL = re.compile(r"(?:[ae]cak|[ae]cek|[iıuü]yoruz|[iıuü]yor|m[ae]li|[ae]bilen|[ae]rak)$")
_IYELIK = re.compile(r"(?:s[ıiuü]|l[ae]r[ıi])$")
_BELIRTME = re.compile(r"(?:l[ae]r[ıi]n[ıi]|[ıiuü]n[ıiuü]|y[ıiuü])$")
_BASSIZ_SIFAT = {"yapay", "doğal", "büyük", "derin", "teknik", "olmayan", "iyi", "güçlü", "yeni"}


def _durak_mi(kelime: str) -> bool:
    k = tr_lower(kelime)
    return k in DURAK or k in _EN_DURAK or k[:5] in _GENEL or k.isdigit() or len(k) < 2


def _baglac_mi(kelime: str) -> bool:
    k = tr_lower(kelime)
    return k in DURAK or k in _EN_DURAK or bool(_FIIL.search(k)) or \
        (k.endswith("ing") and len(k) > 5)  # building, using, working


def adaylar(ilan: str) -> list[str]:
    """İlandaki aday anahtar ifadeler (görünen yazımıyla, tekrarsız)."""
    gorulen: dict[str, str] = {}
    satirlar = ilan.strip().splitlines()
    if satirlar and len(satirlar[0].split()) <= 6:  # ilk kısa satır pozisyon adıdır
        ilan = "\n".join(satirlar[1:])
    for parca in _PARCA.split(ilan):
        kelimeler = [k.strip(".-") for k in _KELIME.findall(parca)]
        kelimeler = [k for k in kelimeler if k]
        for n in (1, 2, 3):
            for i in range(len(kelimeler) - n + 1):
                grup = kelimeler[i : i + n]
                if _durak_mi(grup[0]) or _durak_mi(grup[-1]) or any(map(_baglac_mi, grup)):
                    continue
                kucuk = [tr_lower(k) for k in grup]
                if _IYELIK.search(kucuk[0]) or kucuk[-1] in _BASSIZ_SIFAT:
                    continue  # "mühendisi", "öğrenmesi modelleri", "... yapay" yarım kalır
                if any(_BELIRTME.search(k) for k in kucuk[:-1]):
                    continue  # "süreçlerini yapay": belirtme ekli kelime ifadenin ortasında olmaz
                if n == 1 and len(grup[0]) < 3 and not beceriler.bul(grup[0]):
                    continue
                ifade = " ".join(grup)
                gorulen.setdefault(tr_katla(ifade), ifade)
    for b in sorted(beceriler.bul(ilan)):  # sözlük becerileri her zaman aday
        gorulen.setdefault(tr_katla(b), b)
    return list(gorulen.values())


def _mmr(aday_vek: np.ndarray, alaka: np.ndarray, k: int) -> list[int]:
    secilen: list[int] = []
    kalan = list(range(len(alaka)))
    while kalan and len(secilen) < k:
        if secilen:
            benzerlik = (aday_vek[kalan] @ aday_vek[secilen].T).max(axis=1)
            puan = MMR_LAMBDA * alaka[kalan] - (1 - MMR_LAMBDA) * benzerlik
        else:
            puan = alaka[kalan]
        en_iyi = kalan[int(np.argmax(puan))]
        secilen.append(en_iyi)
        kalan.remove(en_iyi)
    return secilen


_ONBELLEK: dict[str, list[tuple[str, float]]] = {}


def cikar(ilan: str, gomucu: Gomucu | None = None, k: int = MAKS_ANAHTAR) -> list[tuple[str, float]]:
    """İlanı en iyi temsil eden k anahtar ifade ve puanları. Aynı ilan için önbelleklenir."""
    anahtar = hashlib.sha256(f"{bool(gomucu)}|{k}|{ilan}".encode()).hexdigest()
    if anahtar in _ONBELLEK:
        return _ONBELLEK[anahtar]
    aday = adaylar(ilan)
    if not aday:
        return []
    beceri_mi = np.array([1.0 if beceriler.bul(a) else 0.0 for a in aday])
    if gomucu:
        vek = gomucu(aday)
        alaka = (vek @ gomucu([ilan])[0]) + BECERI_BONUSU * beceri_mi
        secim = _mmr(vek, alaka, k)
        sonuc = [(aday[i], float(alaka[i])) for i in secim]
    else:
        terimler = Counter(isle(ilan, "on5"))
        def puan(i: int) -> float:
            koku = [t for t in isle(aday[i], "on5") if t not in _GENEL]
            return (sum(terimler[t] for t in koku) / max(len(koku), 1)) * len(koku) ** 0.5 \
                + 2 * beceri_mi[i]
        sirali = sorted(range(len(aday)), key=puan, reverse=True)
        sonuc, kullanilan = [], set()
        for i in sirali:  # basit tekrar eleme: kökleri öncekilerin alt kümesi olanı atla
            koku = frozenset(isle(aday[i], "on5")) - _GENEL
            if koku and not any(koku <= u for u in kullanilan):
                sonuc.append((aday[i], round(puan(i), 3)))
                kullanilan.add(koku)
            if len(sonuc) >= k:
                break
    # Başka bir seçili ifadenin içinde geçen tek kelime (beceri değilse) tekrar sayılır: "makine"
    katli = [tr_katla(i) for i, _ in sonuc]
    sonuc = [(i, p) for (i, p), k in zip(sonuc, katli)
             if " " in k or beceriler.bul(i)
             or not any(k != d and re.search(rf"(?<!\w){re.escape(k)}(?!\w)", d) for d in katli)]
    _ONBELLEK[anahtar] = sonuc
    return sonuc


def kapsama(anahtarlar: list[tuple[str, float]], cv: str, ek: str = "") -> list[Anahtar]:
    metin = f"{cv}\n{ek}"
    cv_terim = set(isle(metin, "on5"))
    cv_beceri = beceriler.genislet(beceriler.bul(metin))
    sonuc = []
    for ifade, puan in anahtarlar:
        koku = [t for t in isle(ifade, "on5") if t not in _GENEL] or isle(ifade, "on5")
        ifade_beceri = beceriler.bul(ifade)
        var = (bool(ifade_beceri) and ifade_beceri <= cv_beceri) or \
              (bool(koku) and all(t in cv_terim for t in koku))
        sonuc.append(Anahtar(ifade, round(puan, 3), var))
    return sonuc
