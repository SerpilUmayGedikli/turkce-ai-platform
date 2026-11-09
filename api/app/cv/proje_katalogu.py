"""Çevrimdışı motorun proje kataloğu: eksik beceri -> adayın 1-3 haftada yapabileceği proje.

Her proje kapsadığı becerilerle (beceri sözlüğündeki kanonik adlar) eşleşir. Motor eksik
becerileri en çok kapsayan projeleri seçer (açgözlü küme örtüsü). Metinlerde:
  {alan}  ilanın/CV'nin sektörü ("üretim", "e-ticaret"...)
  {B}     projede kullanılan becerilerin ilandaki yazımıyla listesi
"""

from __future__ import annotations

KATALOG: list[dict] = [
    {
        "id": "sql-analitik", "sure": "1 hafta", "repo": "sql-{alan_slug}-analitigi",
        "beceriler": {"SQL", "PostgreSQL", "MySQL", "SQL Server", "Veri Analizi"},
        "ad": {"tr": "{B} ile {alan} verisi analitiği", "en": "{alan} data analytics with {B}"},
        "maddeler": {
            "tr": ["{B} kullanarak {alan} verisi için ilişkisel bir şema kurdum; JOIN, CTE ve pencere fonksiyonlarıyla analiz sorguları yazdım.",
                   "Veri temizleme ve kalite kontrol adımlarını SQL ile otomatikleştirip sonuçları raporladım."],
            "en": ["Designed a relational schema for {alan} data with {B}; wrote analytical queries using JOINs, CTEs and window functions.",
                   "Automated data cleaning and quality checks in SQL and reported the findings."]},
        "adimlar": ["Kaggle'dan ya da açık veri portalından {alan} ile ilgili bir veri seti indir.",
                    "PostgreSQL'i (ya da SQLite) kur, tabloları tasarla ve veriyi yükle.",
                    "En az 10 iş sorusunu SQL ile cevapla (JOIN, GROUP BY, CTE, pencere fonksiyonları).",
                    "Sorguları ve kısa yorumlarını bir notebook ya da .sql dosyalarında topla."],
        "readme": ["Veri seti ve şema (ER diyagramı)", "İş soruları ve SQL cevapları", "Önemli bulgular"],
    },
    {
        "id": "python-eda", "sure": "1 hafta", "repo": "{alan_slug}-veri-analizi",
        "beceriler": {"Python", "Pandas", "NumPy", "Veri Analizi", "İstatistik", "Veri Bilimi"},
        "ad": {"tr": "{B} ile {alan} verisi keşifsel analizi", "en": "Exploratory analysis of {alan} data with {B}"},
        "maddeler": {
            "tr": ["{B} ile {alan} verisini temizleyip keşifsel veri analizi yaptım; eksik ve aykırı değerleri ele aldım.",
                   "Bulguları istatistiksel testler ve grafiklerle destekleyen bir analiz raporu hazırladım."],
            "en": ["Cleaned and explored {alan} data with {B}, handling missing values and outliers.",
                   "Produced an analysis report backed by statistical tests and charts."]},
        "adimlar": ["{alan} ile ilgili açık bir veri seti seç.", "Pandas ile temizle, özellik türet.",
                    "Dağılımları ve ilişkileri görselleştir, en az bir hipotez testi yap.",
                    "Sonuçları Jupyter notebook'ta anlatı şeklinde yaz."],
        "readme": ["Soru ve veri seti", "Temizleme adımları", "Grafikler ve sonuçlar"],
    },
    {
        "id": "pano", "sure": "1 hafta", "repo": "{alan_slug}-pano",
        "beceriler": {"Power BI", "Tableau", "Looker", "Veri Görselleştirme", "Excel"},
        "ad": {"tr": "{B} ile {alan} yönetim panosu", "en": "{alan} management dashboard with {B}"},
        "maddeler": {
            "tr": ["{B} ile {alan} KPI'larını izleyen etkileşimli bir pano tasarladım.",
                   "Panodaki bulguları teknik olmayan paydaşlara yönelik kısa bir sunumla özetledim."],
            "en": ["Built an interactive {B} dashboard tracking {alan} KPIs.",
                   "Summarised the insights in a short presentation for non-technical stakeholders."]},
        "adimlar": ["{alan} için 5-6 KPI belirle.", "Veriyi modelle ve panoyu kur (filtreler, detay sayfaları).",
                    "Panonun ekran görüntülerini ve 1 sayfalık bulgu özetini hazırla."],
        "readme": ["KPI tanımları", "Pano ekran görüntüleri", "Bulgu özeti"],
    },
    {
        "id": "ml-model", "sure": "1-2 hafta", "repo": "{alan_slug}-ml-modeli",
        "beceriler": {"Makine Öğrenmesi", "scikit-learn", "Veri Bilimi", "Python"},
        "ad": {"tr": "{B} ile {alan} tahmin modeli", "en": "{alan} prediction model with {B}"},
        "maddeler": {
            "tr": ["{B} ile {alan} verisinde uçtan uca bir tahmin modeli geliştirdim ve çapraz doğrulamayla değerlendirdim.",
                   "Model sonuçlarını özellik önemleri ve hata analiziyle yorumlayıp raporladım."],
            "en": ["Developed and cross-validated an end-to-end {alan} prediction model with {B}.",
                   "Interpreted results through feature importance and error analysis."]},
        "adimlar": ["{alan} için bir sınıflandırma ya da regresyon problemi seç.",
                    "Veriyi hazırla, en az 3 modeli karşılaştır (ör. lojistik regresyon, random forest, XGBoost).",
                    "Doğruluk/F1 gibi metrikleri raporla, en iyi modeli kaydet."],
        "readme": ["Problem ve veri", "Model karşılaştırma tablosu", "Metrikler ve hata analizi"],
    },
    {
        "id": "derin-ogrenme", "sure": "2 hafta", "repo": "{alan_slug}-derin-ogrenme",
        "beceriler": {"PyTorch", "TensorFlow", "Keras", "Derin Öğrenme", "Bilgisayarlı Görü"},
        "ad": {"tr": "{B} ile {alan} için derin öğrenme modeli", "en": "Deep learning model for {alan} with {B}"},
        "maddeler": {
            "tr": ["{B} ile {alan} verisi üzerinde bir derin öğrenme modeli eğittim; eğitim ve doğrulama eğrilerini izledim.",
                   "Modeli klasik bir makine öğrenmesi yöntemiyle karşılaştırıp sonuçları belgeledim."],
            "en": ["Trained a deep learning model on {alan} data with {B}, monitoring training and validation curves.",
                   "Benchmarked it against a classical ML baseline and documented the results."]},
        "adimlar": ["{alan} ile ilgili görüntü, zaman serisi ya da metin veri seti seç.",
                    "PyTorch ile veri yükleyici ve model yaz, GPU yoksa Google Colab kullan.",
                    "Klasik bir modelle karşılaştır, eğitim grafiklerini kaydet."],
        "readme": ["Mimari", "Eğitim grafikleri", "Karşılaştırma ve sonuç"],
    },
    {
        "id": "llm-rag", "sure": "2 hafta", "repo": "{alan_slug}-llm-asistani",
        "beceriler": {"Büyük Dil Modelleri", "RAG", "LangChain", "LangGraph", "Hugging Face",
                      "Doğal Dil İşleme", "Prompt Mühendisliği", "Vektör Veritabanı", "Yapay Zeka"},
        "ad": {"tr": "{B} ile {alan} doküman asistanı", "en": "{alan} document assistant with {B}"},
        "maddeler": {
            "tr": ["{B} kullanarak {alan} dokümanları üzerinde soru cevaplayan bir asistan geliştirdim.",
                   "Cevap kalitesini örnek soru setiyle ölçüp istem ve arama ayarlarını iyileştirdim."],
            "en": ["Built a question-answering assistant over {alan} documents using {B}.",
                   "Evaluated answer quality on a sample question set and tuned prompts and retrieval."]},
        "adimlar": ["{alan} ile ilgili 20-30 açık doküman topla (kılavuz, rapor, SSS).",
                    "Metni parçala, embedding ile vektör veritabanına koy (ör. Chroma, FAISS).",
                    "Ücretsiz bir model (ör. Gemini ücretsiz katmanı ya da Ollama ile yerel model) ile RAG akışını kur.",
                    "20 soruluk bir değerlendirme seti hazırla ve sonuçları raporla."],
        "readme": ["Mimari şeması", "Kurulum ve çalıştırma", "Değerlendirme sonuçları"],
    },
    {
        "id": "api-docker", "sure": "1 hafta", "repo": "{alan_slug}-api",
        "beceriler": {"FastAPI", "Flask", "Django", "REST API", "Docker"},
        "ad": {"tr": "{B} ile {alan} tahmin servisi", "en": "{alan} prediction service with {B}"},
        "maddeler": {
            "tr": ["{B} ile bir modeli ya da veri işlemini REST uç noktası olarak sundum ve konteynerleştirdim.",
                   "Servise istek doğrulama, hata yönetimi ve otomatik testler ekledim."],
            "en": ["Exposed a model / data process as a REST endpoint with {B} and containerised it.",
                   "Added request validation, error handling and automated tests."]},
        "adimlar": ["Basit bir model ya da veri işlemi seç.", "FastAPI ile /tahmin uç noktası yaz.",
                    "Dockerfile ile konteynerleştir, docker run ile çalıştığını göster.", "pytest ile 3-5 test ekle."],
        "readme": ["Uç noktalar ve örnek istekler", "Docker ile çalıştırma", "Testler"],
    },
    {
        "id": "bulut", "sure": "1-2 hafta", "repo": "{alan_slug}-bulut-dagitimi",
        "beceriler": {"AWS", "Azure", "Google Cloud", "Terraform", "Linux", "CI/CD", "Docker"},
        "ad": {"tr": "{B} üzerinde {alan} uygulamasının dağıtımı", "en": "Deploying a {alan} application on {B}"},
        "maddeler": {
            "tr": ["{B} üzerinde konteynerleştirilmiş bir uygulamayı ücretsiz katman kaynaklarıyla yayına aldım.",
                   "Dağıtımı otomatik bir iş akışıyla tekrarlanabilir hale getirdim ve maliyet notlarını belgeledim."],
            "en": ["Deployed a containerised application on {B} using free-tier resources.",
                   "Made the deployment repeatable with an automated workflow and documented costs."]},
        "adimlar": ["AWS/Azure ücretsiz hesabı aç (harcama limiti koy).",
                    "Önceki bir projeni Docker ile paketle ve bulutta çalıştır (ör. App Service, ECS, Cloud Run).",
                    "GitHub Actions ile otomatik dağıtım ekle.", "Kaynakları kapatmayı unutma, adımları belgeleyip ekran görüntüsü al."],
        "readme": ["Mimari", "Dağıtım adımları", "Canlı adres ya da ekran görüntüleri"],
    },
    {
        "id": "kubernetes", "sure": "2 hafta", "repo": "{alan_slug}-mikroservis",
        "beceriler": {"Kubernetes", "Mikroservis", "Docker"},
        "ad": {"tr": "{B} ile {alan} mikroservis uygulaması", "en": "{alan} microservices on {B}"},
        "maddeler": {
            "tr": ["{B} kullanarak iki servisli bir uygulamayı yerel bir kümede çalıştırdım; ölçekleme ve sağlık kontrolleri ekledim."],
            "en": ["Ran a two-service application on a local {B} cluster with scaling and health checks."]},
        "adimlar": ["minikube ya da kind kur.", "İki küçük servis yaz ve Docker imajlarını oluştur.",
                    "Deployment, Service ve HPA tanımlarını yaz, ölçeklemeyi göster."],
        "readme": ["Mimari", "Kümede çalıştırma", "Ölçekleme denemesi"],
    },
    {
        "id": "etl", "sure": "2 hafta", "repo": "{alan_slug}-etl-hatti",
        "beceriler": {"ETL", "Airflow", "Veri Mühendisliği", "Spark", "dbt", "Kafka", "Snowflake",
                      "BigQuery", "Hadoop"},
        "ad": {"tr": "{B} ile {alan} veri hattı", "en": "{alan} data pipeline with {B}"},
        "maddeler": {
            "tr": ["{B} ile {alan} verisini kaynaktan alıp dönüştüren ve depoya yükleyen zamanlanmış bir veri hattı kurdum.",
                   "Hatta veri kalitesi kontrolleri ve hata bildirimleri ekledim."],
            "en": ["Built a scheduled pipeline with {B} that extracts, transforms and loads {alan} data.",
                   "Added data quality checks and failure alerts to the pipeline."]},
        "adimlar": ["Açık bir API ya da CSV kaynağı seç.", "Airflow'u Docker ile kur, günlük çalışan bir DAG yaz.",
                    "Veriyi dönüştürüp PostgreSQL'e (ya da bulut deposuna) yükle.", "Kalite kontrolleri ekle."],
        "readme": ["Veri akışı şeması", "DAG ekran görüntüsü", "Kurulum"],
    },
    {
        "id": "mlops", "sure": "1-2 hafta", "repo": "{alan_slug}-mlops",
        "beceriler": {"MLOps", "MLflow", "CI/CD"},
        "ad": {"tr": "{B} ile {alan} modelinin yaşam döngüsü", "en": "{alan} model lifecycle with {B}"},
        "maddeler": {
            "tr": ["{B} ile deneyleri, metrikleri ve model sürümlerini izledim; eğitim ve testleri otomatikleştirdim."],
            "en": ["Tracked experiments, metrics and model versions with {B}; automated training and tests."]},
        "adimlar": ["Önceki bir ML projeni al.", "MLflow ile deneyleri kaydet.", "GitHub Actions ile eğitim/test iş akışı ekle."],
        "readme": ["Deney karşılaştırması", "İş akışı", "Model kaydı"],
    },
    {
        "id": "frontend", "sure": "1-2 hafta", "repo": "{alan_slug}-web-arayuzu",
        "beceriler": {"React", "Vue", "Angular", "Next.js", "TypeScript", "JavaScript", "HTML/CSS"},
        "ad": {"tr": "{B} ile {alan} web uygulaması", "en": "{alan} web application with {B}"},
        "maddeler": {
            "tr": ["{B} ile bir API'den veri çeken, duyarlı ve erişilebilir bir web arayüzü geliştirdim.",
                   "Bileşen testleri yazıp uygulamayı ücretsiz bir barındırma servisinde yayınladım."],
            "en": ["Built a responsive, accessible web interface with {B} consuming a REST API.",
                   "Wrote component tests and deployed it on a free hosting service."]},
        "adimlar": ["{alan} ile ilgili küçük bir ürün fikri seç.", "Açık bir API'ye bağlan, 3-4 sayfa yap.",
                    "Testleri yaz, Vercel/Netlify'da yayınla."],
        "readme": ["Canlı adres", "Ekran görüntüleri", "Kurulum"],
    },
    {
        "id": "backend", "sure": "2 hafta", "repo": "{alan_slug}-backend",
        "beceriler": {"Node.js", "Spring", "Java", ".NET", "C#", "Go", "GraphQL", "MongoDB", "Redis",
                      "Nesne Yönelimli Programlama", "Tasarım Desenleri", "Birim Testi"},
        "ad": {"tr": "{B} ile {alan} arka uç servisi", "en": "{alan} backend service with {B}"},
        "maddeler": {
            "tr": ["{B} ile kimlik doğrulamalı, katmanlı mimaride bir arka uç servisi geliştirdim.",
                   "Birim ve entegrasyon testleriyle kritik akışları güvenceye aldım."],
            "en": ["Developed an authenticated, layered backend service with {B}.",
                   "Covered critical flows with unit and integration tests."]},
        "adimlar": ["{alan} için CRUD ağırlıklı bir senaryo seç.", "Katmanlı mimari ve JWT ile kimlik doğrulama kur.",
                    "Veritabanı bağlantısı ve testleri ekle, Docker ile çalıştır."],
        "readme": ["Mimari", "API dokümanı", "Testler"],
    },
    {
        "id": "ab-testi", "sure": "1 hafta", "repo": "{alan_slug}-ab-testi",
        "beceriler": {"A/B Testi", "İstatistik", "R"},
        "ad": {"tr": "{B} ile {alan} deney analizi", "en": "{alan} experiment analysis with {B}"},
        "maddeler": {
            "tr": ["{B} yaklaşımıyla örnek bir deneyin örneklem büyüklüğünü hesapladım ve sonuçlarını anlamlılık testleriyle yorumladım."],
            "en": ["Sized and analysed a sample experiment using {B}, interpreting results with significance tests."]},
        "adimlar": ["Açık bir A/B testi veri seti bul.", "Güç analizi ve hipotez testlerini uygula.", "Karar önerisi yaz."],
        "readme": ["Deney tasarımı", "Analiz", "Karar"],
    },
    {
        "id": "git-ci", "sure": "3-4 gün", "repo": "{alan_slug}-ci-ornegi",
        "beceriler": {"Git", "CI/CD", "Birim Testi", "Bash"},
        "ad": {"tr": "{B} ile otomatik test ve sürüm akışı", "en": "Automated testing and release flow with {B}"},
        "maddeler": {
            "tr": ["{B} ile dal stratejisi, kod incelemesi ve her değişiklikte çalışan otomatik testler kurdum."],
            "en": ["Set up branching, code review and automated tests on every change with {B}."]},
        "adimlar": ["Önceki bir projeni GitHub'a koy.", "Dal kuralları ve PR şablonu ekle.",
                    "GitHub Actions ile test ve lint iş akışı kur."],
        "readme": ["İş akışı rozeti", "Katkı rehberi"],
    },
]

GENEL = {
    "id": "genel", "sure": "1 hafta", "repo": "{alan_slug}-{beceri_slug}-projesi",
    "ad": {"tr": "{B} ile {alan} örnek projesi", "en": "{alan} sample project with {B}"},
    "maddeler": {"tr": ["{B} kullanarak {alan} odaklı, uçtan uca çalışan bir örnek proje geliştirdim ve belgeledim."],
                 "en": ["Built and documented an end-to-end {alan} project using {B}."]},
    "adimlar": ["{B} için resmi başlangıç rehberini bitir.", "{alan} ile ilgili küçük bir problem seç ve çöz.",
                "Kodu temiz bir yapıda düzenle, kısa bir demo videosu ya da ekran görüntüsü ekle."],
    "readme": ["Amaç", "Kullanılan teknolojiler", "Çalıştırma adımları"],
}

# Sektör sözcükleri (ilk eşleşen kullanılır; önce ilan, sonra CV aranır)
SEKTORLER = [
    (("üretim", "imalat", "fabrika", "manufactur"), "üretim", "manufacturing"),
    (("e-ticaret", "eticaret", "e-commerce", "perakende", "retail"), "e-ticaret", "e-commerce"),
    (("banka", "finans", "fintech", "sigorta", "finance", "banking", "insurance"), "finans", "finance"),
    (("sağlık", "hastane", "health", "medical", "ilaç"), "sağlık", "healthcare"),
    (("lojistik", "kargo", "tedarik", "logistic", "supply chain"), "lojistik", "logistics"),
    (("telekom", "telecom"), "telekom", "telecom"),
    (("enerji", "energy"), "enerji", "energy"),
    (("oyun", "gaming", "game"), "oyun", "gaming"),
    (("eğitim teknoloji", "edtech"), "eğitim", "education"),
    (("otomotiv", "automotive"), "otomotiv", "automotive"),
]
