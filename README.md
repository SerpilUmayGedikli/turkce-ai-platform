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
| OpenRouter | https://openrouter.ai/keys | Ücretsiz Nemotron/Gemma; kredi ile Qwen, Kimi (Kasım 2026'da ücretsiz Qwen/Kimi yok) |
| Alibaba Model Studio | https://modelstudio.console.alibabacloud.com | Qwen + Kimi tek anahtarla, yeni kullanıcıya model başına ~1M token (Singapur) |

> **İpucu:** Gemini'nin ücretsiz kotası **model başına** ayrı işler. Ana model dolunca
> `gemini-3` / `gemini-lite` takma adları aynı anahtarla çalışmaya devam eder.
>
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

## Türkçe Text-to-SQL

Agent, Türkçe soruları bir e-ticaret veritabanında SQL'e çevirip çalıştırır:

```
"Geçen ay en çok ciro yapan kategori hangisi?"
  → sql_calistir("SELECT c.ad FROM ... WHERE s.tarih BETWEEN '2026-10-01' AND '2026-10-31' ...")
  → "Spor"
```

- **Güvenlik (modelin yazdığı SQL'e güvenilmez):** salt okunur bağlantı, yalnızca SELECT'e izin veren
  SQLite yetkilendiricisi (DELETE/DROP/ATTACH/PRAGMA reddedilir), tek sorgu, 50 satır ve
  süre sınırı. Hata mesajı modele döner, model sorguyu kendisi düzeltir.
- **Türkçe sorun:** SQLite'ın `LOWER`/`LIKE` fonksiyonları Türkçe harfleri tanımaz:
  `ad LIKE 'ş%'` sorgusu **0** müşteri, Türkçe kurallı `tr_lower(ad) LIKE 'ş%'` sorgusu **26** müşteri bulur.
  Veritabanına Türkçe kurallı `tr_lower()` eklendi. İlk ölçümde Gemini'nin `tr_lower(sehir) = 'isparta'`
  yazdığı görüldü: model "ISPARTA"yı **kafasında İngilizce kuralla** küçültmüştü (doğrusu `ısparta`).
  Çözüm, dönüşümü modele bırakmamak oldu: `tr_katla()` iki tarafı da aynı şekilde normalleştirir
  (I/İ/ı/i farkını yok sayar), model sadece `tr_katla(sehir) = tr_katla('ISPARTA')` yazar.
- **KVKK ile birlikte:** "TC'si 40666836414 olan müşteri nerede?" sorusunda model yalnızca
  `[TCKN_1]` etiketini görür ve SQL'e etiketi yazar; sorgu yerelde gerçek değerle çalışır.
  Sorgu sonucundaki TCKN ve telefon da modele dönmeden önce maskelenir.
- **Ölçüm:** 36 Türkçe soru (kolay/orta/zor, Türkçe karakter, KVKK), altın SQL'ler.
  Execution accuracy: SQL metni değil, sorgunun **sonucu** karşılaştırılır.

### Sonuçlar: Türkçe karakter alt seti (8 soru)

| Ölçüm | Model | Doğruluk | Süre/soru | ISPARTA sorusu |
|---|---|---|---|---|
| v1 (`tr_lower`) | Gemini 3.8 Flash\* | %75 | 121 sn | ✗ `tr_lower(sehir) = 'isparta'` |
| v1.1 (`tr_katla`) | Gemini 3 Flash | **%88** | 4.9 sn | ✓ `tr_katla(sehir) = tr_katla('ISPARTA')` |

\* Cevabı gerçekte `gemini-3.6-flash` verdi: sağlayıcı istenen modeli arka planda değiştirebiliyor,
bu yüzden rapor cevabı **gerçekte veren modeli** de yazar. İki satırdaki modeller farklı olduğu için
artışın tamamı `tr_katla`'ya ait sayılmamalı. Isparta sorusu ise doğrudan bu düzeltmenin etkisini gösterir.
Kalan hata ("Soyadı ışık olan müşterilerin adları") bir Türkçe hatası değil: model aynı adı iki kez
listeledi, altın SQL `DISTINCT` kullanıyor. Altın cevap, sonuçlara bakılarak değiştirilmedi.
36 soruluk tam ölçüm ve model karşılaştırması ücretsiz kotalar nedeniyle parça parça (`--devam`) sürüyor.

```bash
cd api && python -m eval.text2sql_degerlendir --model gemini-3 --bekle 4
cd api && python -m eval.text2sql_degerlendir --model gemini-3 --bekle 4 --devam   # kota yarıda kestiyse
```

Demo veritabanı (`api/data/magaza.db`) ilk kullanımda otomatik üretilir: 320 müşteri, 3200 sipariş,
rastgele ve sahte kişisel verilerle.

## Türkçe Hibrit Belge Arama (RAG)

Agent, mağazanın politika belgelerinde (iade, kargo, iptal, ödeme, garanti, KVKK...) arama yapıp
cevabı kaynağıyla verir (`belge_ara` aracı). Aynı mağazanın veritabanı da bağlı olduğu için agent
"siparişim kargoda mı?" sorusuna SQL ile, "kargodaki siparişi iptal edebilir miyim?" sorusuna
belgeyle cevap verir.

**Türkçe sorun:** Türkçe eklemeli bir dil. "iade", "iadesi", "iadelerde", "iadenizin" aynı kelime ama
kelime eşleşmesine dayalı arama (BM25) bunları farklı sayar. Embedding anlamı yakalar ama
"taksit", "48 saat" gibi kesin terimlerde zayıf kalır.

**Çözüm:** BM25 (kütüphanesiz, `app/rag/bm25.py`) + Türkçe ön işleme (Türkçe kurallı küçük harf,
kesme işaretli ekler, kök/önek) + çok dilli embedding (fastembed, CPU, PyTorch'suz), RRF ile birleştirme.

### Sonuçlar ([tam rapor](api/eval/sonuclar/rag_rapor.md)): 50 soru, 47 parça

| Yöntem | Recall@1 | Recall@5 | MRR | cekim (16) | esanlam (18) |
|---|---|---|---|---|---|
| BM25, düz kelime | 50% | 74% | 0.59 | 69% | 56% |
| BM25 + Snowball kök | 64% | 80% | 0.70 | 94% | 50% |
| BM25 + ilk 5 harf | 74% | 86% | 0.80 | 94% | 67% |
| Embedding (MiniLM çok dilli) | 66% | 86% | 0.75 | 81% | 78% |
| **Hibrit (ilk 5 harf + embedding)** | 72% | **94%** | **0.80** | **100%** | **83%** |

*cekim: aynı kelime farklı ekle ("İadelerde kargo ücretini kim ödüyor?"); esanlam: farklı kelimeyle
("Paramı ne zaman geri alırım?"). İki sütun Recall@5. Belgedeki kelimelerle sorulan 16 soruyu tüm yöntemler buldu.*

**Bulgular:**
- Ek sorunu gerçek: düz BM25, ekli sorularda %69'da kalıyor; kök/önek ile **%94**.
- **Basit olan kazandı:** "ilk 5 harf" kesmesi, Snowball kök bulucusundan daha iyi (%86 / %80).
  Sebebi test olarak kayıtlı: Snowball `iadelerde`→`iade` yapıyor ama `iade`→`ia` yaparak kendi
  kökünü bozuyor.
- Kelime araması eş anlamlılarda çaresiz ("kurye" ≠ "kargo görevlisi"), embedding ise ekli kelimelerde
  ve nadir terimlerde kaçırıyor. İkisi birbirinin açığını kapatıyor: hibrit, iki türde de en iyisi.
- Hâlâ kaçanlar, kelime örtüşmesi hiç olmayan sorular: "Telefonum suya düştü" (belgede: "sıvı teması").

**Dürüstlük notları:** Sorular ve belgeler aynı kişi tarafından yazıldı (gerçek kullanıcı soruları daha
dağınık olur). Sorular sonuçlardan önce yazıldı ve değiştirilmedi. Varsayılan yöntem (`hibrit-on5`) bu
setteki sonuca bakılarak seçildi; bu yüzden %94 iyimser bir tahmin. Ayrı bir doğrulama seti gerekli.

```bash
cd api && python -m eval.rag_degerlendir     # API anahtarı gerekmez, model ilk seferde ~220 MB iner
```

## Yol haritası

- [x] **Hafta 1–2:** Gateway, sıfırdan agent döngüsü, araç sistemi, testler
- [ ] **Deney:** "Türkçe vergisi": aynı metnin Türkçede kaç kat fazla token tuttuğu (blog yazısı)
- [x] **Hafta 3–4:** KVKK Kalkanı v1: TCKN, IBAN, telefon, e-posta, kart; precision/recall ölçümü
- [ ] **KVKK v2:** Ad-soyad/adres için Türkçe NER, Presidio ile karşılaştırma, ayrı bir doğrulama seti
- [x] **Hafta 5–6:** Türkçe Text-to-SQL aracı + 36 soruluk test seti v1 (execution accuracy)
- [ ] **Text-to-SQL v2:** 150 soruya genişletme, modelleri (Gemini/Qwen/Kimi/yerel) karşılaştırma
- [x] **Hafta 7–8:** Türkçe hibrit arama (kök/önek + BM25 + embedding, RRF), 50 soruda Recall@5
- [ ] **RAG v2:** Ayrı doğrulama seti, gerçek kullanıcı soruları, reranker, cevap doğruluğu (faithfulness)
- [ ] **Canlı demo:** Hugging Face Spaces + Gradio (SQL + belge + KVKK tek sayfada)
- [ ] **Hafta 9–10:** Model router: soruya göre ucuz/güçlü model seçimi, maliyet ve doğruluk raporu
- [ ] **Hafta 11–12:** Gözlemlenebilirlik (Langfuse), canlı demo, değerlendirme raporu

## Neden agent döngüsü framework'süz?

`api/app/agent.py` bilerek LangGraph veya LangChain kullanmıyor. Döngüyü anlamak için önce sıfırdan
yazıldı; karmaşık akışlar (planlama, çoklu agent) geldiğinde framework'e geçiş ayrı bir karar olarak alınacak.
