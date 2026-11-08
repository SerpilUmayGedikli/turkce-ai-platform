"""İlana göre CV uyarlayıcı: web arayüzü (Gradio).

Çalıştır (gateway açıkken ya da GEMINI_API_KEY tanımlıyken):
    python demo/cv_demo.py        → http://localhost:7861
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import gradio as gr

_KOK = Path(__file__).resolve().parent
sys.path.insert(0, str(_KOK.parent / "api"))

from app import cv  # noqa: E402
from app.cv.cikti import docx_yaz, pdf_yaz  # noqa: E402
from app.cv.eslestirme import Analiz, analiz_et, varsayilan_gomucu  # noqa: E402
from app.cv.okuyucu import dosyadan, temizle  # noqa: E402
from app.cv.yazici import baglanti  # noqa: E402

ORNEK = _KOK.parent / "api" / "app" / "cv" / "ornekler"
SIMGE = {"karşılanıyor": "✅", "kısmen": "🟡", "eksik": "❌"}

ACIKLAMA = """# 📄 İlana Göre CV Uyarlayıcı
CV'ni yükle, ilan metnini yapıştır. Önce **yerel model** CV'yi ilanla eşleştirip uyum skorunu ve
eksikleri çıkarır (embedding + beceri sözlüğü, hiçbir şey dışarı gitmez). Sonra LLM CV'yi ilana
göre yeniden yazar. **Ad ve iletişim bilgilerin modele gönderilmez.** Model CV'de olmayan bir şey
yazarsa "kontrol et" uyarısı çıkar."""


def _cv_metni(dosya, metin: str) -> str:
    if dosya:
        return dosyadan(dosya if isinstance(dosya, str) else dosya.name)
    return temizle(metin or "")


def _analiz_md(a: Analiz, baslik: str) -> str:
    satirlar = [f"### {baslik}: **{a.skor}/100**",
                f"_Yöntem: {'embedding + kelime + beceri' if a.embedding else 'kelime + beceri (embedding kapalı)'}_",
                f"**Eşleşen beceriler:** {', '.join(sorted(a.eslesen_beceriler)) or '-'}",
                f"**Dolaylı var, adıyla yazılmalı:** {', '.join(sorted(a.ima_edilen_beceriler)) or '-'}",
                f"**Eksik beceriler:** {', '.join(sorted(a.eksik_beceriler)) or '-'}", "",
                "| | Gereksinim | Skor | CV'deki en yakın ifade |", "|---|---|---|---|"]
    for g in a.gereksinimler:
        etiket = " _(tercihen)_" if g.tercih else ""
        yakin = (g.en_yakin[:80] + "…") if len(g.en_yakin) > 80 else g.en_yakin
        hucre = lambda s: s.replace("|", "/")  # noqa: E731 - tablo hücresini bozmasın
        satirlar.append(f"| {SIMGE[g.durum]} | {hucre(g.metin)}{etiket} | {g.skor:.2f} | "
                        f"{hucre(yakin) or '-'} |")
    return "\n".join(satirlar)


def analiz(dosya, cv_yazi, ilan):
    cv_metni = _cv_metni(dosya, cv_yazi)
    if not cv_metni or not (ilan or "").strip():
        return "CV ve ilan metni gerekli."
    return _analiz_md(analiz_et(cv_metni, ilan, varsayilan_gomucu()), "Uyum skoru")


def uyarla(dosya, cv_yazi, ilan, ad, dil):
    cv_metni = _cv_metni(dosya, cv_yazi)
    if not cv_metni or not (ilan or "").strip():
        raise gr.Error("CV ve ilan metni gerekli.")
    dil_kodu = {"İlanla aynı dil": "ilan", "Türkçe": "tr", "İngilizce": "en"}[dil]
    try:
        s = cv.calistir(cv_metni, ilan, ad=ad.strip(), dil=dil_kodu)
    except RuntimeError as e:
        raise gr.Error(str(e)) from e

    ozet = [f"## Uyum skoru: {s.once.skor} → **{s.sonra.skor}** / 100",
            f"_Cevabı veren model: `{s.cv.model}`_"]
    if s.cv.uydurma_supheleri:
        ozet += ["", "### ⚠️ Kontrol et: orijinal CV'de bulunamadı",
                 "Model bunları eklemiş olabilir. Doğru değilse CV'den sil:", ""]
        ozet += [f"- {u}" for u in s.cv.uydurma_supheleri]
    ozet += ["", "### Ne değişti"] + [f"- {d}" for d in s.cv.degisiklikler]
    ozet += ["", "### Eksikler için öneriler"] + [f"- {o}" for o in s.cv.oneriler]

    onizleme = [f"# {s.baslik.ad}" if s.baslik.ad else "", f"**{s.cv.unvan}**",
                " | ".join(s.baslik.iletisim), "", s.cv.ozet, "",
                "**Beceriler:** " + " • ".join(s.cv.beceriler)]
    for d in s.cv.deneyim:
        onizleme += ["", f"**{d.get('pozisyon', '')} · {d.get('sirket', '')}** _{d.get('tarih', '')}_"]
        onizleme += [f"- {m}" for m in d.get("maddeler", [])]

    klasor = Path(tempfile.mkdtemp(prefix="cv_"))
    kok = re.sub(r"\W+", "_", f"{s.baslik.ad or 'CV'}_uyarlanmis").strip("_")
    dosyalar = [klasor / f"{kok}.docx"]
    dosyalar[0].write_bytes(docx_yaz(s.baslik, s.cv))
    try:
        (klasor / f"{kok}.pdf").write_bytes(pdf_yaz(s.baslik, s.cv))
        dosyalar.append(klasor / f"{kok}.pdf")
    except RuntimeError:
        pass

    return ("\n".join(ozet), _analiz_md(s.once, "Önce"), _analiz_md(s.sonra, "Sonra"),
            "\n".join(onizleme), [str(d) for d in dosyalar],
            f"```\n{s.cv.modele_giden}\n```")


def ornek_yukle():
    return (None, (ORNEK / "ornek_cv.txt").read_text(encoding="utf-8"),
            (ORNEK / "ornek_ilan.txt").read_text(encoding="utf-8"))


def arayuz() -> gr.Blocks:
    client, modeller = baglanti()
    durum = (f"🟢 Model: `{modeller[0]}`" if client else
             "🔴 Model bağlantısı yok: gateway'i başlat ya da GEMINI_API_KEY tanımla. Analiz yine çalışır.")
    with gr.Blocks(title="CV Uyarlayıcı", theme=gr.themes.Soft()) as d:
        gr.Markdown(ACIKLAMA)
        gr.Markdown(durum)
        with gr.Row():
            with gr.Column():
                dosya = gr.File(label="CV (PDF, DOCX, TXT)", file_types=[".pdf", ".docx", ".txt", ".md"])
                cv_yazi = gr.Textbox(label="...ya da CV metnini yapıştır", lines=8)
                with gr.Row():
                    ad = gr.Textbox(label="Ad Soyad (boşsa CV'nin ilk satırı)", scale=2)
                    dil = gr.Dropdown(["İlanla aynı dil", "Türkçe", "İngilizce"],
                                      value="İlanla aynı dil", label="CV dili", scale=1)
            with gr.Column():
                ilan = gr.Textbox(label="İş ilanı metni", lines=16)
        with gr.Row():
            ornek = gr.Button("Örnekle doldur")
            analiz_btn = gr.Button("Sadece analiz et (modelsiz)")
            uyarla_btn = gr.Button("CV'yi uyarla", variant="primary")

        ozet = gr.Markdown()
        dosyalar = gr.File(label="İndir", file_count="multiple")
        with gr.Tab("Uyarlanmış CV"):
            onizleme = gr.Markdown()
        with gr.Tab("Analiz: önce"):
            once = gr.Markdown()
        with gr.Tab("Analiz: sonra"):
            sonra = gr.Markdown()
        with gr.Tab("Modele giden metin"):
            gr.Markdown("Modelin gerçekte gördüğü CV. Ad ve iletişim bilgileri etiketlenmiş olmalı.")
            giden = gr.Markdown()

        ornek.click(ornek_yukle, outputs=[dosya, cv_yazi, ilan])
        analiz_btn.click(analiz, [dosya, cv_yazi, ilan], once)
        uyarla_btn.click(uyarla, [dosya, cv_yazi, ilan, ad, dil],
                         [ozet, once, sonra, onizleme, dosyalar, giden])
    return d


if __name__ == "__main__":
    import os

    arayuz().launch(server_port=int(os.getenv("PORT", "7861")))
