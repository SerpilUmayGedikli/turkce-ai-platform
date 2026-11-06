"""Demo sayfasının iş mantığı (arayüzden bağımsız, gradio gerektirmez; test edilebilir).

Model bağlantısı iki şekilde kurulur:
  1. LLM_BASE_URL tanımlıysa: projenin LiteLLM gateway'i (yerelde geliştirme)
  2. Değilse GEMINI_API_KEY ile doğrudan Gemini'nin OpenAI uyumlu uç noktası (Hugging Face Spaces)
Anahtar yoksa sadece Asistan sekmesi kapanır; KVKK, belge arama ve SQL sekmeleri modelsiz çalışır.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import date
from pathlib import Path
from typing import Any

# Yerelde: demo/ klasöründen api/ paketine eriş. Spaces'te app/ zaten bu klasörün yanında.
_KOK = Path(__file__).resolve().parent
for aday in (_KOK, _KOK.parent / "api"):
    if (aday / "app" / "__init__.py").exists():
        sys.path.insert(0, str(aday))
        break

from openai import APIConnectionError, NotFoundError, OpenAI, RateLimitError  # noqa: E402

from app import agent, tools  # noqa: E402
from app.kvkk import Maskeleyici  # noqa: E402
from app.kvkk.tespit import bul  # noqa: E402
from app.veritabani.sorgu import sorgula  # noqa: E402

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# Ücretsiz kota model başına ayrı işler: biri dolunca sıradakine geçilir.
GEMINI_MODELLERI = ["gemini-3-flash-preview", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
GUNLUK_SINIR = int(os.getenv("DEMO_GUNLUK_SINIR", "200"))  # herkese açık demoda kotayı korur
MAKS_SORU = 500


# ---------------------------------------------------------------- model bağlantısı
def baglanti() -> tuple[OpenAI | None, list[str]]:
    if os.getenv("LLM_BASE_URL"):
        return agent.istemci(), [os.getenv("AGENT_MODEL", "gemini")]
    anahtar = os.getenv("GEMINI_API_KEY")
    if anahtar:
        return OpenAI(base_url=GEMINI_URL, api_key=anahtar), GEMINI_MODELLERI
    return None, []


class Sayac:
    """Günlük soru sınırı (süreç belleğinde; yeniden başlatınca sıfırlanır, demo için yeterli)."""

    def __init__(self, sinir: int) -> None:
        self.sinir, self.gun, self.adet = sinir, date.today(), 0
        self._kilit = threading.Lock()

    def al(self) -> bool:
        with self._kilit:
            if date.today() != self.gun:
                self.gun, self.adet = date.today(), 0
            if self.adet >= self.sinir:
                return False
            self.adet += 1
            return True


SAYAC = Sayac(GUNLUK_SINIR)


def sor(soru: str, gecmis: list[dict[str, Any]], client: OpenAI | None = None,
        modeller: list[str] | None = None, sayac: Sayac = SAYAC) -> tuple[str, str]:
    """Agent'a sorar. (cevap, arka planda olanların markdown özeti) döner."""
    soru = (soru or "").strip()[:MAKS_SORU]
    if not soru:
        return "", ""
    if client is None:
        client, modeller = baglanti()
    if client is None:
        return ("Bu kurulumda model anahtarı tanımlı değil. KVKK, Belge Arama ve SQL sekmeleri "
                "modelsiz çalışır; Asistan için GEMINI_API_KEY gerekir.", "")
    if not sayac.al():
        return "Demonun günlük soru sınırı doldu (ücretsiz kota). Yarın tekrar dene.", ""

    gecmis = [{"role": m["role"], "content": m["content"]} for m in gecmis
              if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)]
    son_hata, atlanan = "", []
    for model in modeller or []:
        try:
            sonuc = agent.calistir(soru, model=model, gecmis=gecmis[-8:], client=client)
            yedek = f"\n\n_Kota dolu / kullanılamadığı için atlandı:{', '.join(atlanan)}_" if atlanan else ""
            return sonuc.cevap, iz(sonuc, istenen=model) + yedek
        except RateLimitError:
            son_hata = f"`{model}` kotası dolu"
            atlanan.append(f"`{model}`")
        except NotFoundError:
            son_hata = f"`{model}` bulunamadı"
            atlanan.append(f"`{model}`")
        except APIConnectionError:
            return "Model sağlayıcısına bağlanılamadı, biraz sonra tekrar dene.", ""
    return f"Şu an tüm ücretsiz modellerin kotası dolu ({son_hata}). Biraz sonra tekrar dene.", ""


def _kisalt(s: str, n: int = 700) -> str:
    return s if len(s) <= n else s[:n] + " …"


def iz(sonuc: agent.AgentSonucu, istenen: str) -> str:
    """Agent'ın arka planda yaptıklarını gösterir: modelin gördüğü metin, araçlar, SQL."""
    satirlar = [f"**Model:** `{sonuc.model}`" + (f" (istenen: `{istenen}`)" if istenen not in sonuc.model else "")
                + f" · {sonuc.sure_ms / 1000:.1f} sn"]
    if sonuc.maskelenen:
        turler = ", ".join(f"{t}: {n}" for t, n in sonuc.maskelenen.items())
        satirlar += [f"\n**KVKK:** maskelenen → {turler}\n", "Modelin gördüğü soru:",
                     f"```text\n{sonuc.modele_giden_soru}\n```"]
    if not sonuc.adimlar:
        satirlar.append("\nAraç kullanılmadı.")
    for i, a in enumerate(sonuc.adimlar, 1):
        satirlar.append(f"\n**{i}. `{a['arac']}`**")
        if a["arac"] == "sql_calistir":
            satirlar.append(f"```sql\n{a['argumanlar'].get('sorgu', '')}\n```")
        else:
            satirlar.append(f"`{json.dumps(a['argumanlar'], ensure_ascii=False)}`")
        if a["argumanlar"] != a["calistirilan"]:
            satirlar.append("_Etiketler yerelde gerçek değerle değiştirilerek çalıştırıldı._")
        satirlar.append(f"```text\n{_kisalt(a['sonuc'])}\n```")
    return "\n".join(satirlar)


# ---------------------------------------------------------------- KVKK
def kvkk_goster(metin: str) -> tuple[list[tuple[str, str | None]], str, str]:
    """(vurgulu parçalar, maskeli metin, özet). Model çağrılmaz."""
    metin = metin or ""
    parcalar, son = [], 0
    for b in bul(metin):
        parcalar += [(metin[son:b.baslangic], None), (b.metin, b.tur)]
        son = b.bitis
    parcalar.append((metin[son:], None))
    kalkan = Maskeleyici()
    maskeli = kalkan.maskele(metin)
    ozet = (", ".join(f"**{t}**: {n}" for t, n in kalkan.istatistik.items())
            if kalkan.istatistik else "Kişisel veri bulunamadı.")
    return [p for p in parcalar if p[0]], maskeli, ozet


# ---------------------------------------------------------------- belge arama
def belge_ara(sorgu: str, yontem: str) -> tuple[str, list[list[str]]]:
    """(seçilen yöntemle ilk 3 sonuç, tüm yöntemlerin ilk sonuçları karşılaştırması)."""
    from app.rag import YONTEMLER, varsayilan

    sorgu = (sorgu or "").strip()
    if not sorgu:
        return "", []
    a = varsayilan()
    if a.vektorler is None and not yontem.startswith("bm25"):
        not_ = "\n\n_Embedding modeli yüklenemedi; kelime aramasıyla gösteriliyor._"
    else:
        not_ = ""
    try:
        sonuclar = a.ara(sorgu, 3, yontem)
    except RuntimeError:
        sonuclar, not_ = [], "_Embedding modeli yüklenemedi; bu yöntem kullanılamıyor._"
    metin = "\n\n---\n\n".join(f"**{i}. {p.belge} › {p.baslik}**\n\n{p.metin}"
                               for i, p in enumerate(sonuclar, 1)) or "Sonuç yok."
    tablo = []
    for y in YONTEMLER:
        try:
            ilk = a.ara(sorgu, 3, y)
        except RuntimeError:
            continue
        tablo.append([y] + [f"{p.belge} › {p.baslik}" for p in ilk] + [""] * (3 - len(ilk)))
    return metin + not_, tablo


# ---------------------------------------------------------------- güvenli SQL
def sql_calistir(sql: str) -> tuple[list[str], list[list[Any]], str]:
    try:
        sutunlar, satirlar = sorgula(sql or "")
    except Exception as e:  # yetkilendirici reddi, sözdizimi hatası, süre aşımı
        return [], [], f"❌ Reddedildi / hata: `{type(e).__name__}: {e}`"
    return sutunlar, [list(s) for s in satirlar], f"✅ {len(satirlar)} satır (en fazla 50 gösterilir)"


def model_durumu() -> str:
    client, modeller = baglanti()
    if client is None:
        return "⚪ Model anahtarı yok: Asistan kapalı, diğer sekmeler çalışır."
    kaynak = "LiteLLM gateway" if os.getenv("LLM_BASE_URL") else "Gemini (ücretsiz katman)"
    return f"🟢 {kaynak}: {', '.join(modeller)}"


ARACLAR = list(tools.KAYIT)
