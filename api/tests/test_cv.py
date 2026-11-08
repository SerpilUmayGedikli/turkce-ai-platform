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


HEDEF_CEVABI = {
    **MODEL_CEVABI,
    "beceriler": [*MODEL_CEVABI["beceriler"], "PyTorch", "Docker", "Kubernetes"],
    "projeler": [
        {"ad": "PyTorch ile arıza tahmini", "teknolojiler": ["PyTorch", "Docker"],
         "maddeler": ["PyTorch ile derin öğrenme modeli eğittim ve Docker ile paketledim."], "yeni": True},
        {"ad": "Türkçe duygu analizi", "teknolojiler": ["Hugging Face"], "maddeler": ["..."], "yeni": False},
    ],
    "yapilacaklar": [{"proje": "PyTorch ile arıza tahmini", "neden": "CV'nde PyTorch projesi görünmüyor.",
                      "kapsadigi": ["PyTorch", "Docker"], "adimlar": ["1. Veri seti indir"],
                      "github": {"repo": "pytorch-ariza-tahmini", "readme": ["Kurulum"]}, "sure": "1 hafta"}],
}


def test_hedef_modu_projelerle_beceri_ekler():
    istemci = SahteIstemci(HEDEF_CEVABI)
    s = cv.calistir(CV, ILAN, client=istemci, modeller=["x"], gomucu=None)
    sistem = istemci.gelen[0][0]["content"]
    assert "90" in sistem and "PORTFÖY PROJESİ" in sistem
    # Projeyle gelen beceri "eklenen", projesiz gelen (Kubernetes) hâlâ şüpheli
    assert {"PyTorch", "Docker"} <= set(s.cv.eklenen_beceriler)
    assert "Beceri: Kubernetes" in s.cv.uydurma_supheleri
    assert not any("PyTorch" in x for x in s.cv.uydurma_supheleri)
    assert s.cv.yapilacaklar[0]["github"]["repo"] == "pytorch-ariza-tahmini"
    assert "PyTorch ile derin öğrenme" in s.cv.duz_metin()  # proje skora katılır
    metin = okuyucu.metne_cevir(docx_yaz(s.baslik, s.cv), "c.docx")
    assert "PROJELER" in metin and "PyTorch ile arıza tahmini" in metin


def test_temkinli_mod_yeni_proje_kabul_etmez():
    istemci = SahteIstemci(HEDEF_CEVABI)
    s = cv.calistir(CV, ILAN, client=istemci, modeller=["x"], gomucu=None, mod="temkinli")
    assert "EKLEME" in istemci.gelen[0][0]["content"]
    assert [p["ad"] for p in s.cv.projeler] == ["Türkçe duygu analizi"]
    assert s.cv.yapilacaklar == [] and s.cv.mod == "temkinli"
    assert "Beceri: PyTorch" in s.cv.uydurma_supheleri  # proje yoksa eklenen beceri şüphelidir


def test_bir_daha_uyarla_onceki_eksikleri_modele_verir():
    istemci = SahteIstemci(HEDEF_CEVABI)
    onceki = {"skor": 78, "zayiflar": ["AWS veya Azure deneyimi"], "projeler": ["PyTorch ile arıza tahmini"]}
    cv.calistir(CV, ILAN, client=istemci, modeller=["x"], gomucu=None, onceki=onceki)
    giden = istemci.gelen[0][1]["content"]
    assert "ÖNCEKİ DENEME" in giden and "78/100" in giden and "AWS veya Azure deneyimi" in giden


def test_gereksinim_plani_modele_gider_ve_korunanlar_denetlenir():
    istemci = SahteIstemci(HEDEF_CEVABI)
    s = cv.calistir(CV, ILAN, client=istemci, modeller=["x"], gomucu=None)
    giden = istemci.gelen[0][1]["content"]
    assert "GEREKSİNİM PLANI" in giden and "### DOKUNMA" in giden and "### EKLE" in giden
    assert "elif.kaya@ornek.com" not in giden  # plandaki CV cümleleri de maskeli
    # Zaten karşılanan gereksinimlerin cümleleri ya korunmuş ya da değişmiş olarak raporlanır
    karsilanan = {g.en_yakin for g in s.once.gereksinimler if g.durum == "karşılanıyor" and g.en_yakin}
    assert set(s.cv.korunan) | set(s.cv.degisen_korunan) == karsilanan


def test_korunan_cumle_aynen_kalinca_korunan_sayilir():
    from app.cv.eslestirme import Analiz, Gereksinim
    from app.cv.yazici import UyarlanmisCV, korunanlari_denetle

    a = Analiz(skor=50, gereksinimler=[
        Gereksinim("SQL bilgisi", en_yakin="SQL ile günlük raporlar hazırladım.", durum="karşılanıyor"),
        Gereksinim("Git kullanımı", en_yakin="Git ile sürüm kontrolü yaptım", durum="karşılanıyor"),
        Gereksinim("PyTorch", en_yakin="", durum="eksik")])
    a.gereksinimler.append(Gereksinim("Analist deneyimi", en_yakin="Veri Analisti - Anadolu (2023 - 2024)",
                                      durum="karşılanıyor"))
    y = UyarlanmisCV(deneyim=[{"pozisyon": "Veri Analisti", "sirket": "Anadolu", "tarih": "2023 - 2024",
                               "maddeler": ["SQL ile günlük raporlar hazırladım",  # nokta farkı önemsiz
                                            "Git tabanlı sürüm yönetimi uyguladım"]}])
    korunanlari_denetle("", a, y)
    assert y.korunan == ["SQL ile günlük raporlar hazırladım.", "Veri Analisti - Anadolu (2023 - 2024)"]
    assert y.degisen_korunan == ["Git ile sürüm kontrolü yaptım"]


def test_bir_daha_uyarla_secili_surumun_uzerine_calisir():
    ilk = cv.calistir(CV, ILAN, client=SahteIstemci(HEDEF_CEVABI), modeller=["x"], gomucu=None)
    from dataclasses import asdict
    istemci = SahteIstemci(HEDEF_CEVABI)
    onceki = {"skor": 80, "zayiflar": ["AWS deneyimi"], "cv": asdict(ilk.cv)}
    cv.calistir(CV, ILAN, client=istemci, modeller=["x"], gomucu=None, onceki=onceki)
    giden = istemci.gelen[0][1]["content"]
    assert "ÜZERİNE ÇALIŞILACAK SÜRÜM" in giden and "PyTorch ile arıza tahmini" in giden
    assert "elif.kaya@ornek.com" not in giden and "Elif Kaya" not in giden  # temel sürüm de maskeli
    assert "modele_giden" not in giden  # yalnızca CV alanları gider


def test_ats_anahtar_kelimeleri_ve_kapsama():
    from app.cv import anahtar

    ilan = ("Data Engineer\nRequirements:\n- Experience building ETL pipelines with Apache Airflow\n"
            "- Strong SQL skills and PostgreSQL\n- Familiarity with Docker and CI/CD\n")
    secilen = [i for i, _ in anahtar.cikar(ilan, None)]
    assert {"SQL", "Docker", "PostgreSQL"} <= set(secilen)
    assert "Data Engineer" not in secilen  # başlık satırı aday değil
    assert not any(i.lower().startswith(("building", "with", "and")) for i in secilen)
    k = {a.ifade: a.var for a in anahtar.kapsama(anahtar.cikar(ilan, None), "SQL ve PostgreSQL ile raporlar")}
    assert k["SQL"] and k["PostgreSQL"] and not k["Docker"]
    a = cv.analiz_et(CV, ILAN, None)
    assert a.anahtarlar and 0 < a.ats_kapsama < 100


def test_ek_bilgiler_dogru_kaynak_sayilir():
    ek_cevap = {**HEDEF_CEVABI,
                "beceriler": [*MODEL_CEVABI["beceriler"], "Flask", "PyTorch", "Docker"],
                "projeler": [*HEDEF_CEVABI["projeler"],
                             {"ad": "Flask stok API", "teknolojiler": ["Flask"], "maddeler": ["Flask ile REST API yazdım."],
                              "kaynak": "ek"}],
                "yapilacaklar": [*HEDEF_CEVABI["yapilacaklar"],
                                 {"tur": "yayinla", "proje": "Flask stok API", "neden": "Bilgisayarında var.",
                                  "github": {"repo": "flask-stok-api"}, "sure": "1 gün"}]}
    istemci = SahteIstemci(ek_cevap)
    ek = "- Flask ile stok takip API'si yazdım (bilgisayarımda)"
    s = cv.calistir(CV, ILAN, client=istemci, modeller=["x"], gomucu=None, ek=ek, oto_tur=False)
    giden = istemci.gelen[0][1]["content"]
    assert "ADAYIN EK BİLGİLERİ" in giden and "stok takip" in giden
    assert "İLANIN ANAHTAR KELİMELERİ" in giden
    assert not any("Flask" in x for x in s.cv.uydurma_supheleri)  # ek bilgide var: şüphe değil
    flask = next(p for p in s.cv.projeler if p["ad"] == "Flask stok API")
    assert flask["kaynak"] == "ek" and flask["yeni"] is False
    assert next(p for p in s.cv.projeler if p["ad"].startswith("PyTorch"))["kaynak"] == "yeni"


def test_hedefin_altinda_otomatik_ikinci_tur():
    istemci = SahteIstemci(MODEL_CEVABI)  # proje eklemeyen cevap: skor 90'ın altında kalır
    s = cv.calistir(CV, ILAN, client=istemci, modeller=["x"], gomucu=None)
    assert len(istemci.gelen) == 2 and s.cv.tur == 2
    assert "ÜZERİNE ÇALIŞILACAK SÜRÜM" in istemci.gelen[1][1]["content"]
    istemci = SahteIstemci(MODEL_CEVABI)
    cv.calistir(CV, ILAN, client=istemci, modeller=["x"], gomucu=None, oto_tur=False)
    assert len(istemci.gelen) == 1
    istemci = SahteIstemci(MODEL_CEVABI)
    cv.calistir(CV, ILAN, client=istemci, modeller=["x"], gomucu=None, mod="temkinli")
    assert len(istemci.gelen) == 1  # temkinli modda ikinci tur yok


def test_kategorili_beceriler_belgeye_satir_satir_yazilir():
    kat = {**MODEL_CEVABI, "beceriler": ["Programlama: Python, SQL", "Araçlar: Git, Power BI"]}
    s = cv.calistir(CV, ILAN, client=SahteIstemci(kat), modeller=["x"], gomucu=None, oto_tur=False)
    metin = okuyucu.metne_cevir(docx_yaz(s.baslik, s.cv), "c.docx")
    assert "Programlama: Python, SQL" in metin and "Araçlar: Git, Power BI" in metin
    assert "DENEYİM" in metin  # beceri döngüsü bölüm adlarını bozmamalı
    try:
        pdf = okuyucu.metne_cevir(pdf_yaz(s.baslik, s.cv), "c.pdf")
    except RuntimeError:  # bu makinede Unicode font yoksa PDF atlanır
        return
    assert "Programlama: Python, SQL" in pdf and "DENEY" in pdf
