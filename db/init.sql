-- Veritabanı ilk açılışta bir kez çalışır.
CREATE EXTENSION IF NOT EXISTS vector;

-- RAG için belge parçaları (3.-4. hafta)
CREATE TABLE IF NOT EXISTS belge_parcalari (
    id          BIGSERIAL PRIMARY KEY,
    kaynak      TEXT NOT NULL,
    icerik      TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}'::jsonb,
    embedding   vector(768),
    olusturulma TIMESTAMPTZ DEFAULT now()
);

-- Agent konuşma kayıtları: değerlendirme ve hata analizi için
CREATE TABLE IF NOT EXISTS agent_kayitlari (
    id          BIGSERIAL PRIMARY KEY,
    model       TEXT,
    soru        TEXT,
    cevap       TEXT,
    adimlar     JSONB,
    sure_ms     INTEGER,
    olusturulma TIMESTAMPTZ DEFAULT now()
);
