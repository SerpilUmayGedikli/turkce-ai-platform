"""Türkçe belge arama testleri. Model indirmez: embedding yerine sahte bir gömücü kullanılır."""

from __future__ import annotations

import numpy as np
import pytest

import app.rag as rag
from app import tools
from app.rag import Arama, parcala, rrf, yukle
from app.rag.bm25 import BM25
from app.rag.turkce import isle, kelimeler
from eval.rag_degerlendir import olc, sira_bul
from eval.rag_sorular import SORULAR


# ---------------------------------------------------------------- Türkçe ön işleme
def test_kelimeler_turkce_kurallarla():
    assert kelimeler("Anadolu Çarşı'dan İADE ve KVKK'nın") == ["anadolu", "çarşı", "iade", "kvkk"]
    assert kelimeler("IŞIK ISPARTA") == ["ışık", "ısparta"]  # İngilizce kuralla "isik" olmaz


def test_kok_bulma_ekleri_birlestirir():
    assert isle("iadelerde", "kok") == ["iade"]
    assert isle("iade", "kok") == ["ia"]  # bilinen Snowball hatası: kısa kökleri fazla kırpıyor
    assert isle("kargodaki siparişlerim", "kok") == isle("kargo siparişi", "kok")
    assert isle("kargodaki", "ham") != isle("kargo", "ham")  # ham yöntem birleştiremez
    assert isle("garantisi", "on5") == isle("garantiye", "on5") == ["garan"]
    with pytest.raises(ValueError):
        isle("x", "bilinmeyen")


# ---------------------------------------------------------------- parçalama
def test_parcala_basliklara_gore():
    p = parcala("deneme", "# Belge Adı\n\n## Bir\nmetin bir\n\n## İki\nmetin\niki\n## Boş\n")
    assert [x.kimlik for x in p] == ["deneme::Bir", "deneme::İki"]  # boş bölüm atlanır
    assert p[1].metin == "metin iki" and p[0].belge == "Belge Adı"
    assert p[0].tam_metin.startswith("Belge Adı - Bir.")


def test_belge_seti_ve_test_seti_tutarli():
    kimlikler = {p.kimlik for p in yukle()}
    assert len(kimlikler) == len(yukle()) >= 40  # kimlikler benzersiz
    for ornek in SORULAR:
        assert set(ornek["altin"]) <= kimlikler, ornek["soru"]
    assert {o["etiket"] for o in SORULAR} == {"dogrudan", "cekim", "esanlam"}
    assert len({o["soru"] for o in SORULAR}) == len(SORULAR)


# ---------------------------------------------------------------- sıralama
def test_bm25_ilgili_belgeyi_one_alir():
    bm = BM25([["kargo", "ücret"], ["iade", "süre", "gün"], ["kargo", "takip"]])
    skor = bm.skorlar(["iade", "gün"])
    assert skor.index(max(skor)) == 1 and skor[0] == skor[2] == 0


def test_rrf_iki_listede_de_ust_siradakini_one_alir():
    assert rrf([[1, 2, 3], [3, 1, 2]])[0] == 1  # 1: 1. ve 2. sıra; 3: 3. ve 1. sıra
    assert set(rrf([[1], [2]])) == {1, 2}


def _sahte_gomucu(metinler):
    """Harf sıklığı vektörü: gerçek anlam taşımaz ama vektör yolunu uçtan uca test eder."""
    v = np.array([[m.lower().count(h) for h in "abcçdefgğhıijklmnoöprsştuüvyz"] for m in metinler], float)
    return v / np.clip(np.linalg.norm(v, axis=1, keepdims=True), 1e-12, None)


def test_hibrit_ve_vektor_arama(tmp_path, monkeypatch):
    monkeypatch.setattr(rag.arama, "onbellekli", lambda g, metinler, ad: g(metinler))
    a = Arama(yukle(), _sahte_gomucu)
    for yontem in rag.YONTEMLER:
        assert a.ara("İadelerde kargo ücretini kim ödüyor?", 5, yontem), yontem
    assert a.ara("İadelerde kargo ücretini kim ödüyor?", 1, "bm25-kok")[0].baslik == "İade kargo ücreti"


def test_embedding_yoksa_hibrit_kelime_aramasina_duser():
    a = Arama(yukle())
    assert a.sirala("taksit", "hibrit-kok") == a.sirala("taksit", "bm25-kok")
    with pytest.raises(RuntimeError):
        a.sirala("taksit", "vektor")


# ---------------------------------------------------------------- araç ve ölçüm
def test_belge_ara_araci_kaynak_doner(monkeypatch):
    monkeypatch.setattr(rag, "varsayilan", lambda: Arama(yukle()))
    sonuc = tools.calistir("belge_ara", {"sorgu": "kapıda ödeme ücreti"})
    assert sonuc.startswith("[Ödeme ve Fatura › Kapıda ödeme]") and "29 TL" in sonuc


def test_olcumler():
    assert sira_bul(["a", "b", "c"], ["c", "x"]) == 3 and sira_bul(["a"], ["z"]) is None
    m = olc([1, 2, None, 6])
    assert m["R@1"] == 0.25 and m["R@5"] == 0.5 and m["MRR"] == pytest.approx((1 + 0.5 + 1 / 6) / 4)
