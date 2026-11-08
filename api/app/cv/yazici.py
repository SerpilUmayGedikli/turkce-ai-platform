"""CV'yi ilana göre LLM ile yeniden yazar ve yazılanı yerelde denetler.

Kurallar:
  - Model CV'de OLMAYAN deneyim, beceri, sayı veya unvan EKLEMEZ. Sadece yeniden sıralar,
    vurgular, ilanın terimleriyle yeniden ifade eder. Eksikler ayrı bir "öneri" listesine gider.
  - Ad ve iletişim bilgisi modele gönderilmez. Metindeki e-posta/telefon/TCKN gibi veriler
    KVKK Kalkanı ile maskelenir, ad "[AD_SOYAD]" ile değiştirilir.
  - Modelin çıktısına güvenilmez: CV'de olmayan beceriler ve sayılar "uydurma şüphesi" olarak
    işaretlenir.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from ..kvkk import Maskeleyici
from ..veritabani.sorgu import tr_katla
from . import beceriler
from .eslestirme import Analiz
from .okuyucu import _URL

AD_ETIKETI = "[AD_SOYAD]"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODELLERI = ["gemini-3-flash-preview", "gemini-3.5-flash-lite"]

SISTEM = """Sen deneyimli bir İK uzmanı ve CV editörüsün. Görevin, adayın CV'sini verilen iş ilanına
göre uyarlamak. KESİN KURALLAR:
1. CV'de olmayan hiçbir deneyim, beceri, araç, sertifika, unvan, tarih veya sayı EKLEME. Uydurma
   yasaktır. Sadece CV'deki bilgileri yeniden sırala, öne çıkar, kısalt ve ilanın terimleriyle
   yeniden ifade et (CV "makine öğrenmesi" diyorsa ve ilan "machine learning" diyorsa ilanın
   terimini kullanabilirsin).
2. İlanla ilgisiz bilgileri kısalt ya da çıkar, ilgili olanları en üste taşı.
3. Deneyim maddelerini eylem fiiliyle başlat; CV'de sayı/sonuç varsa koru ve öne çıkar.
4. İlanın istediği ama CV'de bulunmayan şeyleri CV'ye yazma, "oneriler" listesine yaz.
5. [AD_SOYAD], [EPOSTA_1], [TELEFON_1] gibi etiketler gizlenmiş kişisel verilerdir; aynen koru.
6. Maddeleri yeniden ifade ederken CV'de olmayan kapsam, etki veya sorumluluk ekleme
   ("üretim planlamasına destek verdim" gibi CV'de geçmeyen iddialar yazma).
7. Sadece geçerli JSON döndür, başka metin yazma."""

SEMA = """{
  "unvan": "adayın CV'deki gerçek unvanına dayalı tek satır (ör. 'Veri Analisti | Makine Öğrenmesi'); ilandaki unvanı adaya ait gibi yazma",
  "ozet": "3-4 cümlelik, ilana göre yazılmış profesyonel özet",
  "beceriler": ["CV'de geçen beceriler, ilanla en ilgili olanlar önce"],
  "deneyim": [{"pozisyon": "", "sirket": "", "tarih": "", "maddeler": ["..."]}],
  "egitim": [{"okul": "", "bolum": "", "tarih": "", "not": ""}],
  "diger": [{"baslik": "Projeler / Sertifikalar / Diller vb.", "maddeler": ["..."]}],
  "degisiklikler": ["CV'de neyi neden değiştirdiğinin kısa açıklaması"],
  "oneriler": ["ilanın istediği ama CV'de olmayan şeyler için adaya öneri"]
}"""

DILLER = {"ilan": "İlan hangi dilde yazılmışsa CV'yi o dilde yaz.",
          "tr": "CV'yi Türkçe yaz.", "en": "Write the CV in English."}


@dataclass
class UyarlanmisCV:
    unvan: str = ""
    ozet: str = ""
    beceriler: list[str] = field(default_factory=list)
    deneyim: list[dict[str, Any]] = field(default_factory=list)
    egitim: list[dict[str, Any]] = field(default_factory=list)
    diger: list[dict[str, Any]] = field(default_factory=list)
    degisiklikler: list[str] = field(default_factory=list)
    oneriler: list[str] = field(default_factory=list)
    uydurma_supheleri: list[str] = field(default_factory=list)
    model: str = ""
    modele_giden: str = ""  # şeffaflık: modelin gerçekte gördüğü CV metni

    def duz_metin(self) -> str:
        """Yeniden skorlamak ve denetlemek için CV'nin düz metin hali."""
        satirlar = [self.unvan, self.ozet, ", ".join(self.beceriler)]
        for d in self.deneyim:
            satirlar += [f"{d.get('pozisyon', '')} {d.get('sirket', '')}", *d.get("maddeler", [])]
        for e in self.egitim:
            satirlar.append(" ".join(str(e.get(k, "")) for k in ("okul", "bolum", "not")))
        for b in self.diger:
            satirlar += [b.get("baslik", ""), *b.get("maddeler", [])]
        return "\n".join(s for s in satirlar if s)


def baglanti() -> tuple[OpenAI | None, list[str]]:
    """Gateway (LLM_BASE_URL) varsa onu, yoksa GEMINI_API_KEY ile doğrudan Gemini'yi kullanır."""
    if os.getenv("LLM_BASE_URL"):
        istemci = OpenAI(base_url=os.environ["LLM_BASE_URL"],
                         api_key=os.getenv("LITELLM_MASTER_KEY", "sk-degistir-beni"))
        return istemci, [os.getenv("CV_MODEL", os.getenv("AGENT_MODEL", "gemini"))]
    if os.getenv("GEMINI_API_KEY"):
        return OpenAI(base_url=GEMINI_URL, api_key=os.environ["GEMINI_API_KEY"]), GEMINI_MODELLERI
    return None, []


def _gizle(metin: str, kalkan: Maskeleyici, ad: str) -> str:
    # Sıra önemli: ad önce değiştirilirse "elif.kaya@..." e-posta olarak tanınmaz ve sızar.
    metin = kalkan.maskele(metin)
    metin = _URL.sub("[BAGLANTI]", metin)  # linkedin.com/in/ad-soyad gibi bağlantılar
    if ad:  # önce tam ad, sonra tek tek ad/soyad (ör. "Ayşe Hanım", "Yılmaz'ın")
        for parca in dict.fromkeys([ad, *ad.split()]):
            if len(parca) > 2:
                metin = re.sub(rf"(?<![\w\[]){re.escape(parca)}(?!\w)", AD_ETIKETI if parca == ad
                               else "[AD]", metin, flags=re.I)
    return metin


def _ac(veri: Any, kalkan: Maskeleyici, ad: str) -> Any:
    if isinstance(veri, str):
        return kalkan.geri_yukle(veri).replace(AD_ETIKETI, ad).replace("[AD]", ad.split()[0] if ad else "")
    if isinstance(veri, list):
        return [_ac(v, kalkan, ad) for v in veri]
    if isinstance(veri, dict):
        return {k: _ac(v, kalkan, ad) for k, v in veri.items()}
    return veri


def json_ayikla(metin: str) -> dict[str, Any]:
    """Model bazen JSON'u ```json bloğuna sarar ya da önüne açıklama ekler."""
    metin = re.sub(r"^```(?:json)?|```$", "", metin.strip(), flags=re.M).strip()
    bas, son = metin.find("{"), metin.rfind("}")
    if bas == -1 or son == -1:
        raise ValueError("Model JSON döndürmedi")
    return json.loads(metin[bas : son + 1])


_SAYI = re.compile(r"\d+(?:[.,]\d+)?")


def denetle(orijinal: str, uyarlanmis: UyarlanmisCV) -> list[str]:
    """CV'de olmayan beceri ve sayıları bulur (modelin uydurmuş olabileceği şeyler)."""
    yeni_metin = uyarlanmis.duz_metin()
    izinli = beceriler.genislet(beceriler.bul(orijinal))
    supheler = [f"Beceri: {b}" for b in sorted(beceriler.bul(yeni_metin) - izinli)]
    orijinal_sayilar = {s.replace(",", ".") for s in _SAYI.findall(orijinal)}
    for s in dict.fromkeys(_SAYI.findall(yeni_metin)):
        if s.replace(",", ".") not in orijinal_sayilar:
            supheler.append(f"Sayı: {s}")
    # Unvan ve şirket adları da korunmalı
    katli = tr_katla(orijinal)
    for d in uyarlanmis.deneyim:
        sirket = (d.get("sirket") or "").strip()
        if sirket and tr_katla(sirket) not in katli:
            supheler.append(f"Şirket: {sirket}")
    return supheler


def uyarla(cv: str, ilan: str, analiz: Analiz, ad: str = "", dil: str = "ilan",
           client: OpenAI | None = None, modeller: list[str] | None = None) -> UyarlanmisCV:
    if client is None:
        client, modeller = baglanti()
    if client is None:
        raise RuntimeError("Model bağlantısı yok: gateway'i başlatın (LLM_BASE_URL) "
                           "ya da GEMINI_API_KEY tanımlayın.")
    modeller = modeller or ["gemini"]

    kalkan = Maskeleyici()
    gizli_cv = _gizle(cv, kalkan, ad)
    eksikler = "\n".join(f"- {g.metin}" for g in analiz.eksik_gereksinimler[:15]) or "- (yok)"
    kullanici = (
        f"{DILLER.get(dil, DILLER['ilan'])}\n\n"
        f"## İŞ İLANI\n{kalkan.maskele(ilan)}\n\n"
        f"## ADAYIN CV'Sİ\n{gizli_cv}\n\n"
        f"## ÖN ANALİZ (yerel model)\n"
        f"Uyum skoru: {analiz.skor}/100\n"
        f"CV'de de geçen ilan becerileri: {', '.join(sorted(analiz.eslesen_beceriler)) or '-'}\n"
        f"CV'de dolaylı olarak var, ilanın terimiyle AÇIKÇA yaz (ör. scikit-learn -> makine "
        f"öğrenmesi): {', '.join(sorted(analiz.ima_edilen_beceriler)) or '-'}\n"
        f"CV'de geçmeyen ilan becerileri (CV'ye EKLEME, önerilere yaz): "
        f"{', '.join(sorted(analiz.eksik_beceriler)) or '-'}\n"
        f"CV'de karşılığı bulunamayan gereksinimler:\n{eksikler}\n\n"
        f"Şu JSON şemasıyla cevap ver:\n{SEMA}"
    )
    mesajlar = [{"role": "system", "content": SISTEM}, {"role": "user", "content": kullanici}]

    son_hata: Exception | None = None
    for model in modeller:
        try:
            yanit = client.chat.completions.create(model=model, messages=mesajlar, temperature=0.3)
            veri = json_ayikla(yanit.choices[0].message.content or "")
            gercek_model = getattr(yanit, "model", None) or model
            break
        except Exception as e:  # noqa: BLE001 - kota/bağlantı/JSON hatası: sıradaki modeli dene
            son_hata = e
    else:
        raise RuntimeError(f"Model cevap veremedi: {son_hata}") from son_hata

    veri = _ac(veri, kalkan, ad)
    alanlar = UyarlanmisCV.__dataclass_fields__
    sonuc = UyarlanmisCV(**{k: v for k, v in veri.items() if k in alanlar and k not in
                            ("uydurma_supheleri", "model", "modele_giden")})
    sonuc.model, sonuc.modele_giden = gercek_model, gizli_cv
    sonuc.uydurma_supheleri = denetle(cv, sonuc)
    return sonuc
