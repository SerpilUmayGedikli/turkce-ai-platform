"""Türkçe AI Platformu: canlı demo (Gradio). Hugging Face Spaces'te veya yerelde çalışır.

Yerelde:   python demo/demo.py        → http://localhost:7860
Spaces:    python demo/hazirla.py ile paketlenip Space'e yüklenir (bkz. demo/README.md)
"""

from __future__ import annotations

import threading

import gradio as gr
import pandas as pd  # gradio'nun bağımlılığı

import servis

ACIKLAMA = """# 🇹🇷 Türkçe AI Platformu
Kurgusal **Anadolu Çarşı** mağazası için Türkçe bir agent: veritabanını SQL ile sorgular, politika
belgelerinde arama yapar ve kişisel verileri modele **göndermeden önce** maskeler.
Veriler sahtedir. Yine de buraya **gerçek kişisel veri yazma**."""

ORNEK_SORULAR = [
    "Geçen ay en çok ciro yapan kategori hangisi?",
    "ISPARTA'da kaç müşterimiz var?",
    "Kargodaki siparişimi iptal edebilir miyim?",
    "Paramı ne zaman geri alırım?",
    "TC'si 40666836414 olan müşteri hangi şehirde?",
    "1250 TL'nin %20 KDV'si ne kadar?",
]

ORNEK_KVKK = ("Merhaba, TC'm 10000000146, IBAN'ım TR33 0006 1005 1978 6457 8413 26. "
              "Sipariş no 20261104123 için 0532 123 45 67'den ya da ali.veli@ornek.com'dan ulaşabilirsiniz.")

ORNEK_SQL = [
    "SELECT COUNT(*) FROM musteriler WHERE ad LIKE 'Ş%'",
    "SELECT COUNT(*) FROM musteriler WHERE tr_lower(ad) LIKE 'ş%'",
    "SELECT sehir, COUNT(*) AS musteri FROM musteriler GROUP BY sehir ORDER BY musteri DESC LIMIT 5",
    "DELETE FROM musteriler",
    "SELECT * FROM sqlite_master; DROP TABLE siparisler",
]

ORNEK_BELGE = ["İadelerde kargo ücretini kim ödüyor?", "Evde yokken kurye gelirse ne olur?",
               "Paramı ne zaman geri alırım?", "Telefonum suya düştü, ücretsiz tamir edilir mi?"]


def sohbet(mesaj, gecmis):
    cevap, iz = servis.sor(mesaj, gecmis)
    if not cevap:
        return gecmis, "", gr.update()
    gecmis = gecmis + [{"role": "user", "content": mesaj}, {"role": "assistant", "content": cevap}]
    return gecmis, "", iz or "_Ayrıntı yok._"


def arayuz() -> gr.Blocks:
    with gr.Blocks(title="Türkçe AI Platformu", theme=gr.themes.Soft()) as d:
        gr.Markdown(ACIKLAMA)
        gr.Markdown(servis.model_durumu())

        with gr.Tab("🤖 Asistan"):
            gr.Markdown("Agent soruya göre aracı kendisi seçer: "
                        f"{', '.join(f'`{a}`' for a in servis.ARACLAR)}. Sağda arka planda olanlar görünür.")
            with gr.Row():
                with gr.Column(scale=3):
                    sohbet_kutusu = gr.Chatbot(type="messages", height=440, label="Sohbet")
                    with gr.Row():
                        soru = gr.Textbox(placeholder="Sorunu yaz ve Enter'a bas…", show_label=False,
                                          max_length=servis.MAKS_SORU, scale=5)
                        gonder = gr.Button("Gönder", variant="primary", scale=1)
                    ornek_sorular = ornek_listesi(soru, ORNEK_SORULAR, "Örnek sorular (tıkla, cevaplasın)")
                    temizle = gr.Button("Sohbeti temizle", size="sm")
                with gr.Column(scale=2):
                    iz = gr.Markdown("_Bir soru sor: modele giden metin, araç çağrıları ve SQL burada görünür._",
                                     label="Arka planda")
            cikti = [sohbet_kutusu, soru, iz]
            for olay in (soru.submit, gonder.click):
                olay(sohbet, [soru, sohbet_kutusu], cikti, concurrency_limit=2)
            # Örneğe tıklamak soruyu sadece kutuya yazmakla kalmaz, doğrudan gönderir
            ornek_sorular.click(lambda ornek, gecmis: sohbet(ornek[0], gecmis), [ornek_sorular, sohbet_kutusu],
                                cikti, concurrency_limit=2)
            temizle.click(lambda: ([], ""), None, [sohbet_kutusu, iz])

        with gr.Tab("🛡️ KVKK Kalkanı"):
            gr.Markdown("Kişisel veriler **doğrulamayla** bulunur (TCKN algoritması, IBAN mod-97, kart Luhn). "
                        "Örnekteki sipariş numarası 11 haneli ama TCKN algoritmasını geçmediği için maskelenmez. "
                        "Bu sekme modele hiçbir şey göndermez.")
            kvkk_girdi = gr.Textbox(ORNEK_KVKK, lines=3, label="Metin")
            kvkk_dugme = gr.Button("Maskele", variant="primary")
            vurgu = gr.HighlightedText(label="Bulunanlar", combine_adjacent=False)
            maskeli = gr.Textbox(label="Modele giden metin", interactive=False)
            ozet = gr.Markdown()
            kvkk_dugme.click(servis.kvkk_goster, kvkk_girdi, [vurgu, maskeli, ozet])
            kvkk_girdi.submit(servis.kvkk_goster, kvkk_girdi, [vurgu, maskeli, ozet])

        with gr.Tab("📄 Belge Arama"):
            gr.Markdown("Türkçe hibrit arama: BM25 + Türkçe ön işleme (kök/ilk 5 harf) + çok dilli embedding, "
                        "RRF ile birleştirme. 50 soruluk testte Recall@5: düz BM25 **%74** → hibrit **%94**. "
                        "Son örnek bilinen bir sınır: belgede \"sıvı teması\" yazıyor, soruyla ortak kelime yok.")
            with gr.Row():
                belge_sorgu = gr.Textbox(ORNEK_BELGE[0], label="Soru", scale=4)
                yontem = gr.Dropdown(servis_yontemleri(), value="hibrit-on5", label="Yöntem", scale=1)
            belge_ornekleri = ornek_listesi(belge_sorgu, ORNEK_BELGE, "Örnekler (tıkla, arasın)")
            belge_dugme = gr.Button("Ara", variant="primary")
            belge_sonuc = gr.Markdown()
            karsilastirma = gr.Dataframe(headers=["Yöntem", "1.", "2.", "3."], label="Yöntemler ne buldu?",
                                         interactive=False, wrap=True)
            for olay in (belge_dugme.click, belge_sorgu.submit):
                olay(servis.belge_ara, [belge_sorgu, yontem], [belge_sonuc, karsilastirma])
            belge_ornekleri.click(lambda ornek, y: (ornek[0], *servis.belge_ara(ornek[0], y)),
                                  [belge_ornekleri, yontem], [belge_sorgu, belge_sonuc, karsilastirma])

        with gr.Tab("🗄️ Güvenli SQL"):
            gr.Markdown("Modelin yazdığı SQL'e güvenilmez: salt okunur bağlantı, yalnızca SELECT'e izin veren "
                        "yetkilendirici, tek sorgu, 50 satır ve süre sınırı. Son iki örnek **saldırı denemesi**: "
                        "reddedilmeleri beklenen davranıştır. "
                        "Türkçe ayrıntı: SQLite'ın `LIKE`'ı `Ş` harfini tanımaz, `tr_lower()` tanır.")
            sql = gr.Code("SELECT COUNT(*) FROM musteriler WHERE tr_lower(ad) LIKE 'ş%'", language="sql",
                          label="SQL")
            sql_ornekleri = ornek_listesi(sql, ORNEK_SQL, "Örnekler (tıkla, çalışsın)")
            sql_dugme = gr.Button("Çalıştır", variant="primary")
            sql_durum = gr.Markdown()
            sql_tablo = gr.Dataframe(interactive=False, label="Sonuç")
            sql_dugme.click(sql_goster, sql, [sql_tablo, sql_durum])
            sql_ornekleri.click(lambda ornek: (ornek[0], *sql_goster(ornek[0])), sql_ornekleri,
                                [sql, sql_tablo, sql_durum])
    return d


def ornek_listesi(bilesen, ornekler: list[str], baslik: str) -> gr.Dataset:
    """gr.Examples tıklanınca sadece kutuyu doldurur; Dataset'in click olayına işlevi bağlarız."""
    return gr.Dataset(components=[bilesen], samples=[[o] for o in ornekler], label=baslik)


def sql_goster(s):
    sutunlar, satirlar, durum = servis.sql_calistir(s)
    if not sutunlar:  # reddedildi: önceki sorgunun tablosu ve başlıkları ekranda kalmasın
        # Boş tablo verince Gradio eski başlıkları tutuyor; açık bir satırla değiştiriyoruz
        return gr.update(value=pd.DataFrame({"Sonuç": ["Sorgu çalıştırılmadı"]})), durum
    return gr.update(value=satirlar, headers=sutunlar), durum


def servis_yontemleri() -> list[str]:
    from app.rag import YONTEMLER

    return YONTEMLER


if __name__ == "__main__":
    # Embedding modelini (~220 MB) arka planda yükle; ilk arama beklemesin.
    threading.Thread(target=lambda: servis.belge_ara("ısınma", "hibrit-on5"), daemon=True).start()
    arayuz().queue(default_concurrency_limit=4).launch()
