"""Sıfırdan yazılmış agent döngüsü (framework yok, bilerek).

Agent = döngü içinde çalışan bir model:
  1. Modele soruyu + araç listesini gönder
  2. Model araç çağırmak isterse aracı çalıştır, sonucu geri ver
  3. Model son cevabı verene kadar (ya da adım sınırına kadar) tekrarla

LangGraph gibi framework'lere geçmeden önce bunu kendin yazmış olman,
mülakatta "framework'ün içinde ne oluyor?" sorusunu cevaplayabilmeni sağlar.

Komut satırından dene:
    python -m app.agent "1250 TL'nin %20 KDV'si ne kadar, bugün hangi gün?"
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from . import tools
from .kvkk import Maskeleyici

SISTEM_MESAJI = (
    "Sen Türkçe düşünen ve Türkçe cevap veren yardımcı bir asistansın. "
    "Hesaplama gerektiğinde hesap_makinesi aracını, tarih/saat gerektiğinde "
    "simdiki_zaman aracını kullan; tahmin yürütme. Cevaplarını kısa ve net tut. "
    "Metinde [TCKN_1], [IBAN_1], [TELEFON_1] gibi etiketler görürsen bunlar gizlenmiş "
    "kişisel verilerdir: etiketleri aynen koru, değiştirme ve gerçek değeri tahmin etme. "
    "Bir araç gerçek değere ihtiyaç duyarsa etiketi argüman olarak ver."
)


@dataclass
class AgentSonucu:
    cevap: str
    model: str
    adimlar: list[dict[str, Any]] = field(default_factory=list)
    sure_ms: int = 0
    maskelenen: dict[str, int] = field(default_factory=dict)  # tür -> adet
    modele_giden_soru: str = ""  # modelin gerçekte gördüğü metin (şeffaflık için)


def istemci() -> OpenAI:
    # LiteLLM gateway OpenAI uyumlu olduğu için resmi openai paketiyle konuşuyoruz.
    return OpenAI(
        base_url=os.getenv("LLM_BASE_URL", "http://localhost:4000"),
        api_key=os.getenv("LITELLM_MASTER_KEY", "sk-degistir-beni"),
    )


def calistir(
    soru: str,
    model: str | None = None,
    gecmis: list[dict[str, Any]] | None = None,
    max_adim: int = 6,
    client: OpenAI | None = None,
    kvkk: bool = True,
) -> AgentSonucu:
    """kvkk=True iken modele giden HER metin maskelenir (soru, geçmiş, araç sonuçları);
    gerçek değerler sadece yerel araçlara ve kullanıcıya giden son cevaba geri yüklenir."""
    model = model or os.getenv("AGENT_MODEL", "gemini")
    client = client or istemci()
    baslangic = time.perf_counter()
    kalkan = Maskeleyici() if kvkk else None
    gizle = kalkan.maskele if kalkan else (lambda s: s)
    ac = kalkan.geri_yukle if kalkan else (lambda s: s)

    mesajlar: list[dict[str, Any]] = [{"role": "system", "content": SISTEM_MESAJI}]
    mesajlar += [{**m, "content": gizle(m["content"])} for m in (gecmis or [])]
    giden_soru = gizle(soru)
    mesajlar.append({"role": "user", "content": giden_soru})
    adimlar: list[dict[str, Any]] = []

    def sonuc_olustur(cevap: str, model_adi: str) -> AgentSonucu:
        return AgentSonucu(
            cevap=cevap,
            model=model_adi,
            adimlar=adimlar,
            sure_ms=int((time.perf_counter() - baslangic) * 1000),
            maskelenen=dict(kalkan.istatistik) if kalkan else {},
            modele_giden_soru=giden_soru,
        )

    for _ in range(max_adim):
        yanit = client.chat.completions.create(
            model=model, messages=mesajlar, tools=tools.semalar()
        )
        mesaj = yanit.choices[0].message

        if not mesaj.tool_calls:  # araç istemedi -> son cevap
            return sonuc_olustur(ac(mesaj.content or ""), yanit.model or model)

        mesajlar.append(mesaj.model_dump(exclude_none=True))
        for cagri in mesaj.tool_calls:
            try:
                argumanlar = json.loads(cagri.function.arguments or "{}")
            except json.JSONDecodeError:
                argumanlar = {}
            # Araç bizim makinemizde çalışır: gerçek değeri görebilir
            gercek_arg = kalkan.geri_yukle_derin(argumanlar) if kalkan else argumanlar
            sonuc = tools.calistir(cagri.function.name, gercek_arg)
            adimlar.append(
                {"arac": cagri.function.name, "argumanlar": argumanlar, "sonuc": sonuc}
            )
            # ...ama sonucu modele geri gönderirken yine maskeleriz
            mesajlar.append(
                {"role": "tool", "tool_call_id": cagri.id, "content": gizle(sonuc)}
            )

    return sonuc_olustur("Adım sınırına ulaşıldı, soruyu daha basit sorabilir misin?", model)


if __name__ == "__main__":
    soru = " ".join(sys.argv[1:]) or "1250 TL'nin %20 KDV'si ne kadar, bugün hangi gün?"
    sonuc = calistir(soru)
    if sonuc.maskelenen:
        print(f"  [kvkk] maskelenen: {sonuc.maskelenen}")
        print(f"  [kvkk] modelin gördüğü: {sonuc.modele_giden_soru}")
    for adim in sonuc.adimlar:
        print(f"  [araç] {adim['arac']}({adim['argumanlar']}) -> {adim['sonuc']}")
    print(f"\n[{sonuc.model}, {sonuc.sure_ms} ms]\n{sonuc.cevap}")
