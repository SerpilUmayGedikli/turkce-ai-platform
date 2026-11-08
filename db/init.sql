-- Veritabanı ilk açılışta bir kez çalışır.
CREATE EXTENSION IF NOT EXISTS vector;

-- RAG için belge parçaları. Şu an KULLANILMIYOR: arama bellekte (api/app/rag).
-- Belge sayısı büyüyünce buraya taşınacak. Boyut, kullanılan MiniLM modelinin çıktısı (384).
CREATE TABLE IF NOT EXISTS belge_parcalari (
    id          BIGSERIAL PRIMARY KEY,
    kaynak      TEXT NOT NULL,
    icerik      TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}'::jsonb,
    embedding   vector(384),
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
