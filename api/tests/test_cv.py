"""CV uyarlama testleri (API anahtarı ve embedding modeli gerekmez; model sahte istemciyle taklit edilir)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import cv
from app.cv import beceriler, okuyucu
from app.cv.cikti import docx_yaz, pdf_yaz
from app.cv.eslestirme import analiz_et, gereksinimleri_ayir
from app.cv.yazici import UyarlanmisCV, denetle, json_ayikla

ORNEK = Path(cv.__file__).parent / "ornekler"
CV = (ORNEK / "ornek_cv.txt").read_text(encoding="utf-8")
ILAN = (ORNEK / "ornek_ilan.txt").read_text(encoding="utf-8")


def test_beceri_esanlamlari_ve_turkce_ekler():
    assert beceriler.bul("Machine Learning ve PYTHON") == {"Makine Öğrenmesi", "Python"}
    assert "Makine Öğrenmesi" in beceriler.bul("makine öğrenmesinde 2 yıl")
    assert "Veri Analizi" in beceriler.bul("VERİ ANALİZLERİNDE deneyim")  # İ/ı katlama
    assert beceriler.bul("node ile rest of the team") == set()  # belirsiz kelimeler eşleşmez
    assert "C#" in beceriler.bul("C# ve .NET") and "Java" not in beceriler.bul("JavaScript")


def test_gereksinimler_ve_tercih_bolumu():
    g = gereksinimleri_ayir(ILAN)
    metinler = [x.metin for x in g]
    assert any("Python ile en az 2 yıl" in m for m in metinler)
    assert not any(m.startswith("Aranan Nitelikler") for m in metinler)
    docker = next(x for x in g if "Docker" in x.metin)
    python = next(x for x in g if "Python ile" in x.metin)
    assert docker.tercih and not python.tercih


def test_analiz_kelime_ortusmesiyle():
    a = analiz_et(CV, ILAN, gomucu=None)
    assert {"Python", "SQL", "scikit-learn", "Git"} <= a.eslesen_beceriler
    assert {"PyTorch", "Docker", "AWS"} <= a.eksik_beceriler
    # CV "makine öğrenmesi" demiyor ama scikit-learn modeli var; Power BI -> veri görselleştirme
    assert {"Makine Öğrenmesi", "Veri Görselleştirme"} <= a.ima_edilen_beceriler
    assert not a.ima_edilen_beceriler & a.eksik_beceriler
    assert 20 <= a.skor <= 90
    alakasiz = analiz_et("Aşçı. Türk mutfağı, pastacılık, menü planlama.", ILAN, gomucu=None)
    assert alakasiz.skor < a.skor


def test_baslik_cikarma():
    b = okuyucu.baslik_cikar(CV)
    assert b.ad == "Elif Kaya"
    assert "elif.kaya@ornek.com" in b.iletisim and "0532 111 22 33" in b.iletisim
    assert any("linkedin.com" in x for x in b.iletisim)


def test_docx_okuma():
    import docx

    belge = docx.Document()
    belge.add_paragraph("Ali Veli")
    belge.add_paragraph("Python geliştirici")
    tampon = io.BytesIO()
    belge.save(tampon)
    assert "Python geliştirici" in okuyucu.metne_cevir(tampon.getvalue(), "cv.docx")
    with pytest.raises(ValueError):
        okuyucu.metne_cevir(b"x", "cv.exe")


def test_json_ayikla():
    assert json_ayikla('Tamam:\n```json\n{"a": 1}\n```') == {"a": 1}


def test_denetim_uydurmayi_yakalar():
    yeni = UyarlanmisCV(ozet="Kubernetes ile 5 yıl deneyim", beceriler=["Python"],
                        deneyim=[{"sirket": "Hayali Ltd.", "maddeler": ["Raporlamayı %40 kısalttım"]}])
    supheler = denetle(CV, yeni)
    assert "Beceri: Kubernetes" in supheler and "Sayı: 5" in supheler
    assert "Şirket: Hayali Ltd." in supheler
    assert not any("40" in s or "Python" in s for s in supheler)  # CV'de var: şüphe değil


# ------------------------------------------------------------------ uçtan uca (sahte model)
class SahteIstemci:
    def __init__(self, cevap: dict) -> None:
        self.cevap, self.gelen = cevap, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, **_):
        self.gelen.append(messages)
        mesaj = SimpleNamespace(content="```json\n" + json.dumps(self.cevap, ensure_ascii=False) + "\n```")
        return SimpleNamespace(model="sahte-model", choices=[SimpleNamespace(message=mesaj)])


MODEL_CEVABI = {
    "unvan": "Makine Öğrenmesi Odaklı Veri Analisti",
    "ozet": "[AD_SOYAD], Python, SQL ve scikit-learn ile üretim verisinde makine öğrenmesi "
            "modelleri geliştiren bir endüstri mühendisidir. İletişim: [EPOSTA_1]",
    "beceriler": ["Python", "Makine Öğrenmesi", "scikit-learn", "SQL", "Power BI", "Git"],
    "deneyim": [{"pozisyon": "Veri Analisti", "sirket": "Anadolu Tekstil A.Ş.",
                 "tarih": "2023 - Günümüz",
                 "maddeler": ["scikit-learn ile makine arızası tahmin modeli geliştirdim.",
                              "Power BI panosuyla raporlama süresini %40 kısalttım."]}],
    "egitim": [{"okul": "Dokuz Eylül Üniversitesi", "bolum": "Endüstri Mühendisliği",
                "tarih": "2018 - 2022"}],
    "diger": [{"baslik": "Projeler", "maddeler": ["Türkçe duygu analizi (Hugging Face)"]},
              {"baslik": "Diller", "maddeler": ["İngilizce (B2)"]}],
    "degisiklikler": ["ML deneyimi öne alındı"],
    "oneriler": ["PyTorch ile küçük bir proje ekleyin"],
}


def test_uctan_uca_kisisel_veri_modele_gitmez():
    istemci = SahteIstemci(MODEL_CEVABI)
    s = cv.calistir(CV, ILAN, client=istemci, modeller=["sahte"], gomucu=None)

    giden = json.dumps(istemci.gelen[0], ensure_ascii=False)
    assert "elif.kaya@ornek.com" not in giden and "0532 111 22 33" not in giden
    assert "Elif Kaya" not in giden and "[AD_SOYAD]" in giden
    assert "elifkaya" not in giden.lower() and "[EPOSTA_1]" in giden  # bağlantı ve e-posta

    assert s.cv.ozet.startswith("Elif Kaya,") and "elif.kaya@ornek.com" in s.cv.ozet
    assert s.cv.model == "sahte-model"
    assert s.cv.uydurma_supheleri == []
    assert s.sonra.skor >= s.once.skor - 5  # yeniden yazım uyumu düşürmemeli


def test_docx_ve_pdf_cikti():
    s = cv.calistir(CV, ILAN, client=SahteIstemci(MODEL_CEVABI), modeller=["x"], gomucu=None)
    d = docx_yaz(s.baslik, s.cv)
    assert "Anadolu Tekstil" in okuyucu.metne_cevir(d, "c.docx")
    try:
        p = pdf_yaz(s.baslik, s.cv)
    except RuntimeError:
        pytest.skip("Unicode font yok")
    assert p.startswith(b"%PDF") and "Mühendisliği" in okuyucu.metne_cevir(p, "c.pdf")


def test_pozisyon_adi_ve_tanitim_gereksinim_sayilmaz():
    metinler = [g.metin for g in gereksinimleri_ayir(ILAN)]
    assert "Junior Makine Öğrenmesi Mühendisi" not in metinler
    assert not any("arıyoruz" in m for m in metinler)


def test_turkce_buyuk_harf_basliklar():
    s = cv.calistir(CV, ILAN, client=SahteIstemci(MODEL_CEVABI), modeller=["x"], gomucu=None)
    metin = okuyucu.metne_cevir(docx_yaz(s.baslik, s.cv), "c.docx")
    assert "BECERİLER" in metin and "DENEYİM" in metin and "BECERILER" not in metin
