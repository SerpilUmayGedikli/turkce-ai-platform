"""CV uyarlayıcının HTTP uç noktaları. Hem web sitesi hem masaüstü uygulaması bunu kullanır.

    GET  /api/durum              model bağlantısı ve embedding durumu
    GET  /api/ayarlar            bağlantı ayarlarının özeti (anahtar dönmez)
    POST /api/ayarlar            bağlantı ayarlarını kaydet
    POST /api/cv/oku             CV dosyası (PDF/DOCX/TXT) -> metin + tahmini ad
    POST /api/cv/analiz          yerel uyum analizi (modelsiz)
    POST /api/cv/uyarla          analiz + LLM ile yeniden yazım + denetim + yeniden skor
    POST /api/cv/belge?bicim=    uyarlanmış CV -> DOCX ya da PDF
"""

from __future__ import annotations

import re
import threading
from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import ayarlar, calistir, ilanlar
from .cikti import docx_yaz, pdf_yaz
from .eslestirme import Analiz, analiz_et, varsayilan_gomucu
from .okuyucu import Baslik, baslik_cikar, metne_cevir
from .yazici import GEMINI_SECENEKLERI, GEMINI_VARSAYILAN, UyarlanmisCV, baglanti

router = APIRouter(prefix="/api")
MAKS_DOSYA = 10 * 1024 * 1024
MAKS_METIN = 30_000

_gomucu_kilit = threading.Lock()
_gomucu: dict[str, Any] = {}


def gomucu():
    """Embedding modeli ilk istekte bir kez yüklenir (ilk seferde ~220 MB indirilebilir)."""
    with _gomucu_kilit:
        if "g" not in _gomucu:
            _gomucu["g"] = varsayilan_gomucu()
        return _gomucu["g"]


def gomucu_isit() -> None:
    threading.Thread(target=gomucu, daemon=True).start()


def analiz_json(a: Analiz) -> dict[str, Any]:
    return {
        "skor": a.skor,
        "embedding": a.embedding,
        "eslesen": sorted(a.eslesen_beceriler),
        "dolayli": sorted(a.ima_edilen_beceriler),
        "eksik": sorted(a.eksik_beceriler),
        "gereksinimler": [asdict(g) for g in a.gereksinimler],
        "anahtarlar": [asdict(k) for k in a.anahtarlar],
        "ats": a.ats_kapsama,
    }


class AnalizIstegi(BaseModel):
    cv: str = Field(..., min_length=20, max_length=MAKS_METIN)
    ilan: str = Field(..., min_length=20, max_length=MAKS_METIN)


class UyarlaIstegi(AnalizIstegi):
    ad: str = ""
    dil: Literal["ilan", "tr", "en"] = "ilan"
    mod: Literal["hedef", "temkinli"] = "hedef"
    onceki: dict[str, Any] | None = None  # "bir daha uyarla": önceki skor, zayıflar, projeler
    ek: str = Field("", max_length=MAKS_METIN)  # GitHub'da olmayan projeler, bilinen beceriler


class BelgeIstegi(BaseModel):
    baslik: dict[str, Any]
    cv: dict[str, Any]


class AyarIstegi(BaseModel):
    llm_base_url: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str | None = None


@router.get("/durum")
def durum() -> dict[str, Any]:
    client, modeller = baglanti()
    return {
        "model": modeller[0] if client else None,
        "embedding": "hazir" if _gomucu.get("g") else ("yukleniyor" if "g" not in _gomucu else "yok"),
        **ayarlar.ozet(),
        "gemini_secenekleri": GEMINI_SECENEKLERI,
        "gemini_varsayilan": GEMINI_VARSAYILAN,
    }


@router.get("/ornek")
def ornek() -> dict[str, str]:
    """Denemek için sahte bir CV ve ilan."""
    from pathlib import Path  # noqa: PLC0415

    kok = Path(__file__).parent / "ornekler"
    return {"cv": (kok / "ornek_cv.txt").read_text(encoding="utf-8"),
            "ilan": (kok / "ornek_ilan.txt").read_text(encoding="utf-8")}


@router.get("/ayarlar")
def ayarlari_getir() -> dict[str, Any]:
    return ayarlar.ozet()


@router.post("/ayarlar")
def ayarlari_kaydet(istek: AyarIstegi) -> dict[str, Any]:
    if istek.llm_base_url and not re.match(r"^https?://", istek.llm_base_url.strip()):
        raise HTTPException(422, "Gateway adresi http:// ya da https:// ile başlamalı.")
    if istek.gemini_model and istek.gemini_model not in {s["id"] for s in GEMINI_SECENEKLERI}:
        raise HTTPException(422, "Bilinmeyen model.")
    ayarlar.kaydet({"LLM_BASE_URL": istek.llm_base_url, "GEMINI_API_KEY": istek.gemini_api_key,
                    "GEMINI_MODEL": istek.gemini_model})
    return durum()


@router.post("/cv/oku")
async def cv_oku(dosya: UploadFile = File(...)) -> dict[str, str]:
    veri = await dosya.read(MAKS_DOSYA + 1)
    if len(veri) > MAKS_DOSYA:
        raise HTTPException(413, "Dosya 10 MB'tan büyük.")
    try:
        metin = metne_cevir(veri, dosya.filename or "cv.txt")
    except ValueError as e:
        raise HTTPException(415, str(e)) from e
    except Exception as e:  # noqa: BLE001 - bozuk PDF/DOCX
        raise HTTPException(422, f"Dosya okunamadı: {e}") from e
    if len(metin) < 20:
        raise HTTPException(422, "Dosyadan metin çıkarılamadı. Taranmış (resim) PDF olabilir; "
                                 "CV metnini kopyalayıp yapıştırın.")
    return {"metin": metin[:MAKS_METIN], "ad": baslik_cikar(metin).ad}


@router.post("/cv/analiz")
def cv_analiz(istek: AnalizIstegi) -> dict[str, Any]:
    return analiz_json(analiz_et(istek.cv, istek.ilan, gomucu()))


@router.post("/cv/uyarla")
def cv_uyarla(istek: UyarlaIstegi) -> dict[str, Any]:
    try:
        s = calistir(istek.cv, istek.ilan, ad=istek.ad.strip(), dil=istek.dil, gomucu=gomucu(),
                     mod=istek.mod, onceki=istek.onceki, ek=istek.ek)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    return {"baslik": asdict(s.baslik), "once": analiz_json(s.once),
            "sonra": analiz_json(s.sonra), "cv": asdict(s.cv)}


@router.post("/cv/belge")
def cv_belge(istek: BelgeIstegi, bicim: Literal["docx", "pdf"] = Query("docx")) -> Response:
    baslik = Baslik(ad=str(istek.baslik.get("ad", "")), iletisim=list(istek.baslik.get("iletisim", [])))
    alanlar = UyarlanmisCV.__dataclass_fields__
    cv = UyarlanmisCV(**{k: v for k, v in istek.cv.items() if k in alanlar})
    try:
        veri = docx_yaz(baslik, cv) if bicim == "docx" else pdf_yaz(baslik, cv)
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e
    tur = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
           if bicim == "docx" else "application/pdf")
    return Response(veri, media_type=tur)


# ---------------------------------------------------------------- ilan siteleri ve kaydedilen ilanlar
class PlatformIstegi(BaseModel):
    secili: list[str] | None = None
    arama: dict[str, str] | None = None
    ozel_ekle: dict[str, str] | None = None  # {"ad": "...", "adres": "https://..."}
    ozel_sil: str | None = None


class IlanIstegi(BaseModel):
    metin: str = Field(..., max_length=60_000)
    baslik: str = ""
    url: str = ""
    site: str = ""
    sirket: str = ""


class ListeIstegi(BaseModel):
    cv: str = Field("", max_length=MAKS_METIN)


class DurumIstegi(BaseModel):
    durum: Literal["yeni", "uyarlandi", "basvuruldu", "gecildi"]


@router.get("/platformlar")
def platform_listesi() -> dict[str, Any]:
    return ilanlar.platformlar()


@router.post("/platformlar")
def platform_kaydet(istek: PlatformIstegi) -> dict[str, Any]:
    if istek.ozel_ekle and not re.match(r"^https?://\S+\.\S+", istek.ozel_ekle.get("adres", "").strip()):
        raise HTTPException(422, "Site adresi http:// ya da https:// ile başlamalı.")
    return ilanlar.platformlari_kaydet(istek.secili, istek.arama, istek.ozel_ekle, istek.ozel_sil)


class ZiyaretIstegi(BaseModel):
    id: str = Field(..., max_length=60)
    girdim: bool = True


@router.post("/platformlar/ziyaret")
def platform_ziyaret(istek: ZiyaretIstegi) -> dict[str, Any]:
    """Günlük tur: "bugün bu siteye girdim" işareti (ertesi gün sıfırlanır)."""
    return ilanlar.ziyaret_isaretle(istek.id, istek.girdim)


@router.post("/ilanlar/liste")
def ilan_listesi(istek: ListeIstegi) -> dict[str, Any]:
    return {"ilanlar": ilanlar.sirala(istek.cv, gomucu())}


@router.post("/ilanlar")
def ilan_kaydet(istek: IlanIstegi) -> dict[str, Any]:
    try:
        return ilanlar.ilan_ekle(istek.metin, istek.baslik, istek.url, istek.site, istek.sirket)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/ilanlar/{kimlik}")
def ilan_getir(kimlik: str) -> dict[str, Any]:
    ilan = ilanlar.ilan_metni(kimlik)
    if not ilan:
        raise HTTPException(404, "İlan bulunamadı.")
    return ilan


@router.patch("/ilanlar/{kimlik}")
def ilan_durum(kimlik: str, istek: DurumIstegi) -> dict[str, str]:
    ilanlar.ilan_guncelle(kimlik, istek.durum)
    return {"durum": istek.durum}


@router.delete("/ilanlar/{kimlik}")
def ilan_kaldir(kimlik: str) -> dict[str, bool]:
    ilanlar.ilan_sil(kimlik)
    return {"silindi": True}
