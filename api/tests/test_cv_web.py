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


def test_platformlar_ve_arama_adresleri(istemci):
    p = istemci.get("/api/platformlar").json()
    adlar = {s["ad"] for s in p["siteler"]}
    assert {"Kariyer.net", "LinkedIn", "Indeed", "Yenibiris", "Secretcv", "Eleman.net"} <= adlar
    p = istemci.post("/api/platformlar", json={"arama": {"q": "veri analisti", "konum": "İstanbul"},
                                               "secili": ["linkedin", "indeed"]}).json()
    s = {x["id"]: x for x in p["siteler"]}
    assert s["linkedin"]["adres"] == "https://www.linkedin.com/jobs/search/?keywords=veri+analisti&location=%C4%B0stanbul"
    assert s["indeed"]["adres"].startswith("https://tr.indeed.com/jobs?q=veri+analisti")
    assert s["remoteok"]["adres"] == "https://remoteok.com/remote-veri-analisti-jobs"
    assert s["linkedin"]["secili"] and not s["kariyernet"]["secili"]
    # özel site ekle / kaldır; geçersiz adres reddedilir
    p = istemci.post("/api/platformlar", json={"ozel_ekle": {"ad": "Şirketim", "adres": "https://ornek.com/kariyer"}}).json()
    ozel = next(x for x in p["siteler"] if x["ozel"])
    assert ozel["ad"] == "Şirketim" and ozel["secili"]
    assert istemci.post("/api/platformlar", json={"ozel_ekle": {"adres": "javascript:alert(1)"}}).status_code == 422
    p = istemci.post("/api/platformlar", json={"ozel_sil": ozel["id"]}).json()
    assert not any(x["ozel"] for x in p["siteler"])


def test_ilan_kaydet_sirala_ve_sil(istemci):
    from .test_cv import ILAN
    alakasiz = "Aşçı aranıyor\n- Restoran mutfağında 3 yıl deneyim\n- Türk mutfağı ve pasta bilgisi\n- Hijyen belgesi"
    a = istemci.post("/api/ilanlar", json={"metin": ILAN, "baslik": "ML Mühendisi", "url": "https://tr.indeed.com/viewjob?jk=1"}).json()
    assert a["site"] == "Indeed" and a["durum"] == "yeni"
    istemci.post("/api/ilanlar", json={"metin": alakasiz, "url": "https://www.kariyer.net/is-ilani/asci-1"})
    assert istemci.post("/api/ilanlar", json={"metin": "kısa"}).status_code == 422
    # aynı ilan tekrar eklenirse çoğalmaz
    istemci.post("/api/ilanlar", json={"metin": ILAN, "baslik": "ML Mühendisi", "url": "https://tr.indeed.com/viewjob?jk=1"})

    liste = istemci.post("/api/ilanlar/liste", json={"cv": CV}).json()["ilanlar"]
    assert len(liste) == 2 and liste[0]["baslik"] == "ML Mühendisi"  # CV'ye uyumlu olan üstte
    assert liste[0]["skor"] > liste[1]["skor"] and "metin" not in liste[0]
    assert liste[1]["site"] == "Kariyer.net"
    cvsiz = istemci.post("/api/ilanlar/liste", json={}).json()["ilanlar"]
    assert all(i["skor"] is None for i in cvsiz)

    assert istemci.get(f"/api/ilanlar/{a['id']}").json()["metin"] == ILAN.strip()
    istemci.patch(f"/api/ilanlar/{a['id']}", json={"durum": "basvuruldu"})
    assert istemci.patch(f"/api/ilanlar/{a['id']}", json={"durum": "x"}).status_code == 422
    istemci.delete(f"/api/ilanlar/{a['id']}")
    assert istemci.get(f"/api/ilanlar/{a['id']}").status_code == 404


def test_gunluk_tur_isaretleme_seri_ve_ertesi_gun_sifirlanma(istemci, monkeypatch):
    import datetime as dt

    from app.cv import ilanlar

    class SahteTarih(dt.date):
        bugun = dt.date(2026, 11, 9)

        @classmethod
        def today(cls):
            return cls.bugun

    monkeypatch.setattr(ilanlar, "date", SahteTarih)
    istemci.post("/api/platformlar", json={"secili": ["linkedin", "indeed"]})
    p = istemci.get("/api/platformlar").json()
    assert p["bugun"] == "2026-11-09" and p["seri"] == 0 and not p["bugun_tamam"]

    p = istemci.post("/api/platformlar/ziyaret", json={"id": "linkedin"}).json()
    s = {x["id"]: x for x in p["siteler"]}
    assert s["linkedin"]["bugun_girildi"] and not s["indeed"]["bugun_girildi"] and p["seri"] == 1
    p = istemci.post("/api/platformlar/ziyaret", json={"id": "indeed"}).json()
    assert p["bugun_tamam"] and p["son7"][-1] == {"tarih": "2026-11-09", "sayi": 2}
    p = istemci.post("/api/platformlar/ziyaret", json={"id": "indeed", "girdim": False}).json()  # tik geri alınır
    assert not p["bugun_tamam"]

    SahteTarih.bugun = dt.date(2026, 11, 10)  # ertesi gün: liste boş başlar, seri dünden sürer
    p = istemci.get("/api/platformlar").json()
    assert not any(x["bugun_girildi"] for x in p["siteler"]) and p["seri"] == 1
    p = istemci.post("/api/platformlar/ziyaret", json={"id": "linkedin"}).json()
    assert p["seri"] == 2

    SahteTarih.bugun = dt.date(2026, 11, 13)  # iki gün atlandı: seri kırılır
    assert istemci.get("/api/platformlar").json()["seri"] == 0
