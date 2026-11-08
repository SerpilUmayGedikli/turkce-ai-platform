"""CV uyarlayıcı HTTP uç noktaları (site + masaüstü uygulamasının kullandığı API)."""

from __future__ import annotations

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.cv import web_api, yazici

from .test_cv import CV, ILAN, MODEL_CEVABI, SahteIstemci


@pytest.fixture
def istemci(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))  # ayarlar geçici klasöre yazılsın
    for k in ("LLM_BASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(web_api, "_gomucu", {"g": None})  # embedding indirme yok
    app = FastAPI()
    app.include_router(web_api.router)
    return TestClient(app)


def test_ornek_ve_analiz(istemci):
    ornek = istemci.get("/api/ornek").json()
    a = istemci.post("/api/cv/analiz", json=ornek).json()
    assert 0 < a["skor"] <= 100 and a["anahtarlar"] and 0 <= a["ats"] <= 100
    assert "Python" in a["eslesen"] and "PyTorch" in a["eksik"]
    assert all(g["durum"] in ("karşılanıyor", "kısmen", "eksik") for g in a["gereksinimler"])
    assert not any(g["en_yakin"] == "Elif Kaya" for g in a["gereksinimler"])  # ad satırı eşleşmez


def test_kisa_metin_reddedilir(istemci):
    assert istemci.post("/api/cv/analiz", json={"cv": "kısa", "ilan": ILAN}).status_code == 422


def test_dosya_okuma(istemci):
    import docx

    belge = docx.Document()
    for satir in CV.splitlines():
        belge.add_paragraph(satir)
    tampon = io.BytesIO()
    belge.save(tampon)
    j = istemci.post("/api/cv/oku", files={"dosya": ("cv.docx", tampon.getvalue())}).json()
    assert j["ad"] == "Elif Kaya" and "Anadolu Tekstil" in j["metin"]
    r = istemci.post("/api/cv/oku", files={"dosya": ("cv.exe", b"MZ" * 20)})
    assert r.status_code == 415


def test_model_yoksa_anlasilir_hata(istemci):
    r = istemci.post("/api/cv/uyarla", json={"cv": CV, "ilan": ILAN})
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]


def test_uyarla_ve_belge(istemci, monkeypatch):
    monkeypatch.setattr(yazici, "baglanti", lambda: (SahteIstemci(MODEL_CEVABI), ["sahte"]))
    s = istemci.post("/api/cv/uyarla", json={"cv": CV, "ilan": ILAN}).json()
    assert s["baslik"]["ad"] == "Elif Kaya" and s["cv"]["model"] == "sahte-model"
    assert s["sonra"]["skor"] >= s["once"]["skor"] - 5

    govde = {"baslik": s["baslik"], "cv": s["cv"]}
    d = istemci.post("/api/cv/belge?bicim=docx", json=govde)
    assert d.status_code == 200 and d.content[:2] == b"PK"  # docx = zip
    p = istemci.post("/api/cv/belge?bicim=pdf", json=govde)
    assert p.status_code in (200, 500) and (p.status_code == 500 or p.content.startswith(b"%PDF"))


def test_ayarlar_anahtari_geri_vermez(istemci):
    r = istemci.post("/api/ayarlar", json={"gemini_api_key": "test-anahtar-123"}).json()
    assert r["gemini_anahtari_var"] is True and r["model"]
    assert "test-anahtar-123" not in istemci.get("/api/ayarlar").text
    assert istemci.post("/api/ayarlar", json={"llm_base_url": "ftp://x"}).status_code == 422


def test_kapali_gateway_gemini_ye_duser(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9")  # kimse dinlemiyor
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    _, modeller = yazici.baglanti()
    assert modeller == yazici.GEMINI_MODELLERI
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")  # seçilen başa, yedekler arkaya
    _, modeller = yazici.baglanti()
    assert modeller[0] == "gemini-3.8-flash" and "gemini-3-flash-preview" in modeller[1:]
    monkeypatch.delenv("GEMINI_MODEL")
    monkeypatch.delenv("GEMINI_API_KEY")
    _, modeller = yazici.baglanti()  # yedek yoksa gateway'i dener (hata mesajı oradan gelir)
    assert modeller != yazici.GEMINI_MODELLERI


def test_model_secimi(istemci):
    d = istemci.get("/api/durum").json()
    assert any(s["id"] == d["gemini_varsayilan"] for s in d["gemini_secenekleri"])
    r = istemci.post("/api/ayarlar", json={"gemini_api_key": "x", "gemini_model": "gemini-3.8-flash"}).json()
    assert r["model"] == "gemini-3.8-flash" and r["gemini_model"] == "gemini-3.8-flash"
    assert istemci.post("/api/ayarlar", json={"gemini_model": "gpt-9"}).status_code == 422
    r = istemci.post("/api/ayarlar", json={"gemini_model": ""}).json()  # boş = önerilene dön
    assert r["model"] == d["gemini_varsayilan"]
