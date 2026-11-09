"""İlana göre CV uyarlama: yerel analiz (embedding + beceri sözlüğü) -> LLM ile yeniden yazım
-> yerel denetim (uydurma şüphesi) -> yeniden skorlama -> DOCX/PDF.

Komut satırı:
    python -m app.cv cv.pdf ilan.txt [--ad "Ad Soyad"] [--dil ilan|tr|en] [--cikti klasor]
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from openai import OpenAI

from . import cevrimdisi, yazici
from .eslestirme import Analiz, analiz_et, varsayilan_gomucu
from .okuyucu import Baslik, baslik_cikar
from .yazici import UyarlanmisCV, denetle, korunanlari_denetle, uyarla

__all__ = ["Sonuc", "calistir", "analiz_et", "Analiz", "UyarlanmisCV"]


@dataclass
class Sonuc:
    baslik: Baslik
    once: Analiz
    sonra: Analiz
    cv: UyarlanmisCV


HEDEF_SKOR = 90


def _zayiflar(a: Analiz) -> list[str]:
    """Hâlâ kapatılması gerekenler: zayıf gereksinimler + CV'de geçmeyen ilan becerileri ve
    ATS anahtar kelimeleri (skorun yarısı beceri kapsamasından gelir)."""
    eksik = list(dict.fromkeys([*sorted(a.eksik_beceriler),
                                *(k.ifade for k in a.anahtarlar if not k.var)]))
    return ([g.metin for g in a.gereksinimler if g.durum != "karşılanıyor"]
            + [f"CV'de geçmeyen ilan anahtar kelimesi (birebir geçir): {x}" for x in eksik])


def calistir(cv_metni: str, ilan: str, ad: str = "", dil: str = "ilan",
             client: OpenAI | None = None, modeller: list[str] | None = None,
             gomucu="varsayilan", mod: str = "hedef", onceki: dict | None = None,
             ek: str = "", oto_tur: bool = True) -> Sonuc:
    """Uyarlar ve yeniden skorlar. Hedef modunda skor 90'ın altında kalır ve zayıf gereksinim
    varsa, sonucun ÜZERİNE otomatik bir iyileştirme turu daha yapılır; iyi olan sürüm döner."""
    if gomucu == "varsayilan":
        gomucu = varsayilan_gomucu()
    baslik = baslik_cikar(cv_metni, ad or None)
    once = analiz_et(cv_metni, ilan, gomucu)

    # Motor seçimi: "cevrimdisi" ayarı ya da hiç model bağlantısı yoksa (anahtar yok, Ollama yok)
    # yerel kurallarla çalışan çevrimdışı motor; model hata verirse (kota, ağ) ona düşülür.
    def cevrimdisi_calistir(not_: str = "") -> Sonuc:
        yeni = cevrimdisi.uyarla(cv_metni, ilan, once, ad=baslik.ad, dil=dil, mod=mod, ek=ek, gomucu=gomucu)
        if not_:
            yeni.degisiklikler.insert(0, not_)
        yeni.uydurma_supheleri = denetle(cv_metni, yeni, ek)
        korunanlari_denetle(cv_metni, once, yeni)
        return Sonuc(baslik, once, analiz_et(yeni.duz_metin(), ilan, gomucu), yeni)

    motor = os.getenv("CV_MOTOR", "otomatik")  # otomatik | yerel | cevrimdisi
    if client is None and motor == "yerel":
        client, modeller = yazici.ollama_baglanti()
    elif client is None and motor != "cevrimdisi":
        client, modeller = yazici.baglanti()
    if motor == "cevrimdisi" or client is None:
        return cevrimdisi_calistir()
    try:
        yeni = uyarla(cv_metni, ilan, once, ad=baslik.ad, dil=dil, client=client, modeller=modeller,
                      mod=mod, onceki=onceki, ek=ek)
    except RuntimeError as e:
        return cevrimdisi_calistir(f"Model cevap veremedi ({str(e)[:120]}); CV çevrimdışı motorla uyarlandı.")
    sonra = analiz_et(yeni.duz_metin(), ilan, gomucu)

    if oto_tur and mod == "hedef" and sonra.skor < HEDEF_SKOR and _zayiflar(sonra):
        onceki2 = {"skor": sonra.skor, "zayiflar": _zayiflar(sonra), "cv": asdict(yeni)}
        try:
            yeni2 = uyarla(cv_metni, ilan, once, ad=baslik.ad, dil=dil, client=client,
                           modeller=modeller, mod=mod, onceki=onceki2, ek=ek)
            sonra2 = analiz_et(yeni2.duz_metin(), ilan, gomucu)
            if sonra2.skor >= sonra.skor:
                yeni, sonra = yeni2, sonra2
            yeni.tur = 2
        except RuntimeError:  # ikinci tur başarısızsa ilk sonuç yeterli
            pass
    return Sonuc(baslik, once, sonra, yeni)
