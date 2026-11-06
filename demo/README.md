# Canlı demo (Gradio)

Tek sayfada dört sekme:

| Sekme | Ne gösterir | Model gerekir mi? |
|---|---|---|
| 🤖 Asistan | Agent soruya göre SQL, belge arama veya hesap makinesi kullanır; sağda modele giden (maskeli) metin, araç çağrıları ve SQL görünür | Evet (`GEMINI_API_KEY`) |
| 🛡️ KVKK Kalkanı | Doğrulamalı kişisel veri tespiti ve maskeleme | Hayır |
| 📄 Belge Arama | 6 arama yönteminin aynı soruda ne bulduğu yan yana | Hayır |
| 🗄️ Güvenli SQL | Salt okunur, yalnızca SELECT; `DELETE` reddedilir; `tr_lower` farkı | Hayır |

## Yerelde çalıştırma

```bash
pip install -r api/requirements.txt "gradio>=5,<6"
python demo/demo.py            # http://localhost:7860
```

Model bağlantısı: `LLM_BASE_URL` tanımlıysa projenin LiteLLM gateway'i, değilse `GEMINI_API_KEY` ile
doğrudan Gemini kullanılır. Ücretsiz kota dolunca sıradaki Gemini modeline geçer
(`gemini-3-flash-preview` → `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite`).
Herkese açık demoda günlük soru sınırı vardır (`DEMO_GUNLUK_SINIR`, varsayılan 200).

## Hugging Face Spaces'e yükleme

```bash
python demo/hazirla.py         # demo/space/ klasörünü üretir (git'e girmez)
```

1. https://huggingface.co/new-space → SDK: **Gradio**, donanım: **CPU basic (ücretsiz)**
2. Space → **Settings → Variables and secrets → New secret**: `GEMINI_API_KEY`
   (anahtar koda veya dosyaya yazılmaz, sadece buraya)
3. `demo/space/` içeriğini Space'e yükle: sayfadaki **Files → Upload files** ya da
   `git clone https://huggingface.co/spaces/<kullanıcı>/<space>` ile klonlayıp kopyala ve gönder

İlk açılışta veritabanı sahte veriyle üretilir ve embedding modeli (~220 MB) iner; ilk arama
birkaç saniye sürebilir.

> Ücretsiz Gemini katmanında gönderilen metinler eğitim için kullanılabilir. Demo kişisel verileri
> maskeleyerek gönderir, yine de ziyaretçilere gerçek veri yazmamaları söylenir.
