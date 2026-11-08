"""CV ile ilan arasındaki uyumu ölçer. Bu kısım modelsiz çalışır (LLM gerekmez).

İki sinyal birleştirilir:
  1. Gereksinim kapsaması: ilanın her gereksinim cümlesi için CV'deki en yakın cümle bulunur.
     Yakınlık = embedding benzerliği (anlam) + Türkçe kelime örtüşmesi (ilk 5 harf; ekleri
     yutar). Embedding modeli kurulu değilse yalnızca kelime örtüşmesi kullanılır.
  2. Beceri kapsaması: ilanda geçen sözlük becerilerinin kaçı CV'de de geçiyor (ATS bakışı).

Eşik değerleri (KARSILANIYOR, KISMEN) elle seçildi, etiketli veriyle ayarlanmadı.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from ..rag.turkce import isle
from ..rag.vektor import Gomucu
from . import beceriler

KARSILANIYOR, KISMEN = 0.55, 0.35
TERCIH_AGIRLIGI = 0.5
MAKS_GEREKSINIM = 40

# İlan metinlerinde sık geçen, eşleşme sinyali taşımayan kelimeler (ilk 5 harfe kesilmiş)
_GENEL = set(isle("""
deneyim tecrübe tecrübeli bilgi bilgisi sahip olmak yıl yıllık iyi güçlü tercihen tercih
aranan aday adayların konusunda alanında experience years strong knowledge ability skills
skill good excellent working work preferred plus required requirements familiarity
understanding team ekip çalışma şirket company role pozisyon position minimum least
""", "on5"))
_TERCIH = re.compile(r"tercih|artı|avantaj|plus|nice to have|preferred|bonus|desired", re.I)
# İlanın tanıtım cümleleri gereksinim değildir ("Ekibimize ... arıyoruz", "We are looking for")
_TANITIM = re.compile(r"arıyoruz|arayışındayız|katılacak|we are (?:looking|hiring|seeking)|join our", re.I)
_MADDE = re.compile(r"^\s*(?:[-•*·▪●◦–]|\d+[.)])\s*")


@dataclass
class Gereksinim:
    metin: str
    tercih: bool = False  # "tercihen / nice to have" bölümünden mi?
    skor: float = 0.0  # 0-1
    en_yakin: str = ""  # CV'deki en yakın cümle
    durum: str = ""  # karşılanıyor | kısmen | eksik


@dataclass
class Analiz:
    skor: int  # 0-100 genel uyum
    gereksinimler: list[Gereksinim] = field(default_factory=list)
    ilan_becerileri: set[str] = field(default_factory=set)
    eslesen_beceriler: set[str] = field(default_factory=set)
    ima_edilen_beceriler: set[str] = field(default_factory=set)  # dolaylı var, adıyla yazılmalı
    eksik_beceriler: set[str] = field(default_factory=set)
    embedding: bool = False  # anlam benzerliği kullanıldı mı?

    @property
    def eksik_gereksinimler(self) -> list[Gereksinim]:
        return [g for g in self.gereksinimler if g.durum == "eksik"]


def _cumleler(metin: str, min_kelime: int = 3) -> list[str]:
    parcalar = []
    for satir in metin.splitlines():
        satir = _MADDE.sub("", satir).strip()
        # Uzun paragrafları cümlelere böl, kısa satırlar (madde) olduğu gibi kalsın
        for c in re.split(r"(?<=[.!?;])\s+", satir) if len(satir) > 160 else [satir]:
            c = c.strip(" .;")
            if len(c.split()) >= min_kelime or beceriler.bul(c):
                parcalar.append(c)
    return parcalar


def gereksinimleri_ayir(ilan: str) -> list[Gereksinim]:
    """İlanı gereksinim cümlelerine böler; 'Tercihen / Nice to have' başlığı altındakileri işaretler."""
    sonuc, tercih_bolumu, ilk = [], False, True
    for satir in ilan.splitlines():
        temiz = _MADDE.sub("", satir).strip()
        if not temiz:
            continue
        madde_mi = bool(_MADDE.match(satir))
        if ilk and not madde_mi and len(temiz.split()) <= 6:  # ilk kısa satır: pozisyon adı
            ilk = False
            continue
        ilk = False
        if not madde_mi and _TANITIM.search(temiz):
            continue
        # Başlık satırı: kısa, madde işareti yok, genelde ":" ile biter
        if not madde_mi and len(temiz.split()) <= 6 and (temiz.endswith(":") or temiz.isupper()):
            tercih_bolumu = bool(_TERCIH.search(temiz))
            continue
        for c in _cumleler(temiz):
            sonuc.append(Gereksinim(c, tercih=tercih_bolumu or bool(_TERCIH.search(c))))
    return sonuc[:MAKS_GEREKSINIM]


def _terimler(metin: str) -> set[str]:
    return {t for t in isle(metin, "on5") if t not in _GENEL and len(t) > 1}


def _kelime_ortusmesi(gereksinim: str, cv_terimleri: set[str]) -> float:
    g = _terimler(gereksinim)
    return len(g & cv_terimleri) / len(g) if g else 0.0


def _anlam_olcekle(benzerlik: np.ndarray) -> np.ndarray:
    # Çok dilli MiniLM'de ilgisiz cümleler ~0.2-0.3, aynı anlam ~0.7+ verir
    return np.clip((benzerlik - 0.30) / (0.75 - 0.30), 0.0, 1.0)


def analiz_et(cv: str, ilan: str, gomucu: Gomucu | None = None) -> Analiz:
    gereksinimler = gereksinimleri_ayir(ilan)
    from .okuyucu import baslik_cikar  # noqa: PLC0415

    ad = baslik_cikar(cv).ad  # ad satırı bir "deneyim cümlesi" değil, eşleşmeye girmesin
    cv_cumleleri = [c for c in _cumleler(cv, min_kelime=2) if c != ad] or [cv]
    cv_terimleri = _terimler(cv)
    cv_beceri = beceriler.bul(cv)
    cv_genis = beceriler.genislet(cv_beceri)

    anlam = None
    if gomucu and gereksinimler:
        g_vek = gomucu([g.metin for g in gereksinimler])
        c_vek = gomucu(cv_cumleleri)
        benzerlik = g_vek @ c_vek.T  # birim vektörler: iç çarpım = kosinüs
        anlam, en_yakin_idx = _anlam_olcekle(benzerlik.max(axis=1)), benzerlik.argmax(axis=1)

    for i, g in enumerate(gereksinimler):
        kelime = _kelime_ortusmesi(g.metin, cv_terimleri)
        g_beceri = beceriler.bul(g.metin)
        beceri = ((len(g_beceri & cv_beceri) + 0.5 * len(g_beceri & (cv_genis - cv_beceri)))
                  / len(g_beceri) if g_beceri else None)
        if anlam is not None:
            g.skor = 0.6 * float(anlam[i]) + 0.4 * kelime
            g.en_yakin = cv_cumleleri[int(en_yakin_idx[i])]
        else:
            g.skor = kelime
        if beceri is not None:  # cümlede somut bir beceri varsa onun karşılanması belirleyici
            g.skor = 0.5 * g.skor + 0.5 * beceri
        g.durum = ("karşılanıyor" if g.skor >= KARSILANIYOR
                   else "kısmen" if g.skor >= KISMEN else "eksik")

    ilan_beceri = beceriler.bul(ilan)
    eslesen = ilan_beceri & cv_beceri
    # CV'de adıyla geçmeyen ama alt becerilerle ima edilenler: ATS göremez, yarım puan
    ima = (ilan_beceri - cv_beceri) & cv_genis

    if gereksinimler:
        agirlik = np.array([TERCIH_AGIRLIGI if g.tercih else 1.0 for g in gereksinimler])
        gereksinim_skoru = float(np.average([g.skor for g in gereksinimler], weights=agirlik))
    else:
        gereksinim_skoru = 0.0
    if ilan_beceri:
        genel = 0.5 * gereksinim_skoru + 0.5 * (len(eslesen) + 0.5 * len(ima)) / len(ilan_beceri)
    else:
        genel = gereksinim_skoru

    return Analiz(
        skor=round(100 * genel),
        gereksinimler=gereksinimler,
        ilan_becerileri=ilan_beceri,
        eslesen_beceriler=eslesen,
        ima_edilen_beceriler=ima,
        eksik_beceriler=ilan_beceri - cv_beceri - ima,
        embedding=anlam is not None,
    )


def varsayilan_gomucu() -> Gomucu | None:
    """fastembed kuruluysa çok dilli embedding modeli, değilse None (kelime örtüşmesine düşer)."""
    try:
        from ..rag.vektor import fastembed_gomucu

        return fastembed_gomucu()
    except Exception:  # noqa: BLE001 - paket yok / model indirilemedi: sessizce kelimeye düş
        return None
