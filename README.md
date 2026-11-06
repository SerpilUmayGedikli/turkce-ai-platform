# Türkçe AI Platformu

Açık kaynak bileşenleri birleştiren, çok modelli ve araç kullanan bir **Türkçe agent ekosistemi**.
Hedef sohbet botu değil: kurumsal Türkçe kullanım senaryoları için ölçülebilir bir altyapı
(KVKK uyumlu veri maskeleme, Türkçe Text-to-SQL, Türkçe RAG, model karşılaştırma).

## Mimari

```
            ┌──────────── api (FastAPI) ────────────┐
 kullanıcı ─▶  /sohbet → agent döngüsü → araçlar     │
            └───────────────┬───────────────────────┘
                            │ OpenAI uyumlu istek
                  ┌─────────▼─────────┐
                  │ LiteLLM Gateway    │  takma adlar + yedekleme (fallback)
                  └──┬─────┬─────┬────┘
               Gemini  Groq  OpenRouter (Qwen, Kimi)   Ollama (yerel)
                            │
                  ┌─────────▼─────────┐
                  │ Postgres+pgvector  │  RAG belgeleri, agent kayıtları
                  └───────────────────┘
```

| Bileşen | Açık kaynak proje | Görevi |
|---|---|---|
| Gateway | [LiteLLM](https://github.com/BerriAI/litellm) | 100+ sağlayıcıya tek API, fallback, maliyet takibi |
| Yerel model | [Ollama](https://github.com/ollama/ollama) | Veriyi dışarı çıkarmadan model çalıştırma |
| Veritabanı | [pgvector](https://github.com/pgvector/pgvector) | SQL + vektör araması tek yerde |
| API | FastAPI | Agent servisi |

## Ücretsiz API anahtarları

| Sağlayıcı | Nereden | Neden |
|---|---|---|
| Google Gemini | https://aistudio.google.com/apikey | Cömert ücretsiz kota, araç çağırmada iyi → varsayılan |
| Groq | https://console.groq.com/keys | Çok hızlı açık modeller (Llama vb.) |
| OpenRouter | https://openrouter.ai/keys | Qwen, Kimi, DeepSeek'in `:free` sürümleri |

> Ücretsiz kotalar ve model adları sık değişir. Çalışmazsa `gateway/config.yaml` içindeki model adını
> sağlayıcının güncel listesiyle karşılaştır. Ücretsiz katmanlarda gönderdiğin veriler eğitim için
> kullanılabilir: gerçek kişisel veri gönderme (bu yüzden KVKK Kalkanı projesi var).

## Çalıştırma

```bash
cp .env.example .env          # anahtarlarını .env içine yaz
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5:7b   # isteğe bağlı, ~4.7 GB
```

- API dokümantasyonu: http://localhost:8000/docs
- Hızlı deneme:

```bash
curl -X POST localhost:8000/sohbet -H "Content-Type: application/json" -d '{"mesaj": "1250 TL nin %20 KDV si ne kadar, bugün hangi gün?"}'
```

Docker olmadan agent'ı komut satırından denemek (gateway çalışıyor olmalı):

```bash
cd api && pip install -r requirements.txt && python -m app.agent "250 * 1.2 kaç eder?"
```

Testler (API anahtarı gerekmez):

```bash
cd api && python -m pytest -q
```

## KVKK Kalkanı

Kişisel veriler modele **gitmeden önce** maskelenir, cevapta geri yüklenir:

```
Kullanıcı : "TC'm 12345678950, IBAN TR33 0006 1005 1978 6457 8413 26"
Modele    : "TC'm [TCKN_1], IBAN [IBAN_1]"
Araç      : tckn_dogrula("[TCKN_1]")  →  yerelde gerçek değerle çalışır  →  "geçerli"
Kullanıcıya: "12345678950 numarası geçerli."
```

- **Doğrulamalı tespit:** TCKN algoritması, IBAN mod-97, kart Luhn kontrolü. Sipariş/fatura
  numaraları gibi benzer sayılar maskelenmez.
- **Tutarlı etiketler:** Aynı değer, farklı biçimde yazılsa bile (`TR33 0006…` / `TR330006…`) aynı etiketi alır.
- **Uçtan uca koruma:** Soru, konuşma geçmişi ve araç sonuçları maskelenir. Test, gerçek değerin
  modele giden hiçbir mesajda bulunmadığını doğrular (`tests/test_kvkk.py`).

### Sonuçlar ([tam rapor](api/eval/sonuclar/kvkk_rapor.md))

| Veri seti | Saf regex F1 | KVKK Kalkanı F1 |
|---|---|---|
| Elle yazılmış zor örnekler (22) | 0.45 | **0.80** |
| Sentetik, tuzak sayılı (500) | 0.77 | 1.00\* |

\* Sentetik set bizim kurallarımıza yakın üretildiği için iyimserdir; asıl gösterge zor settir.
En büyük kazanç precision'da: saf regex, tuzak sayıların yarısını TCKN/kart sanıyor (TCKN P=0.49),
kalkan hiçbirini (P=1.00).

**Bilinen sınırlar:** Boşluklu TCKN, ön eksiz sabit hat, tireli IBAN, `[at]` ile gizlenmiş e-posta
kaçıyor; algoritmayı tesadüfen geçen takip numaraları maskeleniyor. Ad-soyad ve adres henüz
desteklenmiyor (sonraki adım: Türkçe NER modeli ile karşılaştırma).

```bash
cd api && python -m eval.kvkk_veri_uret && python -m eval.kvkk_degerlendir
```

## Yol haritası

- [x] **Hafta 1–2:** Gateway, sıfırdan agent döngüsü, araç sistemi, testler
- [ ] **Deney:** "Türkçe vergisi": aynı metnin Türkçede kaç kat fazla token tuttuğu (blog yazısı)
- [x] **Hafta 3–4:** KVKK Kalkanı v1: TCKN, IBAN, telefon, e-posta, kart; precision/recall ölçümü
- [ ] **KVKK v2:** Ad-soyad/adres için Türkçe NER, Presidio ile karşılaştırma, ayrı bir doğrulama seti
- [ ] **Hafta 5–6:** Türkçe Text-to-SQL aracı + 150 soruluk test seti (execution accuracy)
- [ ] **Hafta 7–8:** Türkçe hibrit arama (kök bulma + BM25 + embedding), Recall@5
- [ ] **Hafta 9–10:** Model router: soruya göre ucuz/güçlü model seçimi, maliyet ve doğruluk raporu
- [ ] **Hafta 11–12:** Gözlemlenebilirlik (Langfuse), canlı demo, değerlendirme raporu

## Neden agent döngüsü framework'süz?

`api/app/agent.py` bilerek LangGraph veya LangChain kullanmıyor. Döngüyü anlamak için önce sıfırdan
yazıldı; karmaşık akışlar (planlama, çoklu agent) geldiğinde framework'e geçiş ayrı bir karar olarak alınacak.
