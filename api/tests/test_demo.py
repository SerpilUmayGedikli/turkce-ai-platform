"""Canlı demo iş mantığı testleri. Gradio ve API anahtarı gerekmez."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from openai import RateLimitError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "demo"))
import servis  # noqa: E402

from .test_agent import SahteIstemci, _yanit  # noqa: E402


def test_kvkk_vurgular_ve_maskeler():
    vurgu, maskeli, ozet = servis.kvkk_goster("TC 10000000146, sipariş 20261104123")
    assert ("10000000146", "TCKN") in vurgu
    assert maskeli == "TC [TCKN_1], sipariş 20261104123"  # algoritmayı geçmeyen sayı maskelenmez
    assert "TCKN" in ozet
    assert servis.kvkk_goster("")[2] == "Kişisel veri bulunamadı."


def test_sql_sekmesi_yazmayi_reddeder():
    sutunlar, satirlar, durum = servis.sql_calistir("SELECT COUNT(*) AS n FROM musteriler")
    assert sutunlar == ["n"] and satirlar[0][0] > 0 and durum.startswith("✅")
    assert servis.sql_calistir("DELETE FROM musteriler")[2].startswith("❌")


def test_anahtar_yoksa_asistan_kibarca_kapanir(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cevap, iz = servis.sor("merhaba", [])
    assert "anahtar" in cevap and iz == ""


def test_sor_arac_izini_gosterir():
    cevap, iz = servis.sor("1250'nin %20'si?", [], client=SahteIstemci(), modeller=["m1"],
                           sayac=servis.Sayac(5))
    assert "KDV" in cevap and "hesap_makinesi" in iz and "sahte-model" in iz


class KotaDoluIstemci(SahteIstemci):
    """İlk modelde kota hatası verir, sonrakinde normal çalışır."""

    def _create(self, model, messages, tools=None):
        if model == "dolu":
            import httpx
            yanit = httpx.Response(429, request=httpx.Request("POST", "http://x"))
            raise RateLimitError("kota", response=yanit, body=None)
        return _yanit({"role": "assistant", "content": f"cevap {model}"})


def test_kota_dolunca_siradaki_modele_gecer():
    cevap, _ = servis.sor("x", [], client=KotaDoluIstemci(), modeller=["dolu", "bos"],
                          sayac=servis.Sayac(5))
    assert cevap == "cevap bos"
    cevap, _ = servis.sor("x", [], client=KotaDoluIstemci(), modeller=["dolu"], sayac=servis.Sayac(5))
    assert "kota" in cevap


def test_gunluk_sinir():
    sayac = servis.Sayac(1)
    assert servis.sor("x", [], client=KotaDoluIstemci(), modeller=["bos"], sayac=sayac)[0] == "cevap bos"
    assert "sınır" in servis.sor("x", [], client=KotaDoluIstemci(), modeller=["bos"], sayac=sayac)[0]


def test_gecmis_temizlenir_ve_maskeli_gider():
    istemci = SahteIstemci()
    gecmis = [{"role": "user", "content": "TC'm 10000000146"}, {"role": "assistant", "content": "tamam"},
              {"role": "assistant", "content": None}]
    servis.sor("1250'nin %20'si?", gecmis, client=istemci, modeller=["m"], sayac=servis.Sayac(5))
    giden = json.dumps(istemci.gelen_mesajlar[0], ensure_ascii=False)
    assert "10000000146" not in giden and "[TCKN_1]" in giden


def test_belge_arama_sekmesi(monkeypatch):
    import app.rag as rag
    monkeypatch.setattr(rag, "varsayilan", lambda: rag.Arama(rag.yukle()))  # model indirmeden
    metin, tablo = servis.belge_ara("kapıda ödeme ücreti", "bm25-on5")
    assert "Kapıda ödeme" in metin and {r[0] for r in tablo} == {"bm25-ham", "bm25-kok", "bm25-on5",
                                                                    "hibrit-kok", "hibrit-on5"}
    assert "Embedding" in servis.belge_ara("kapıda ödeme", "hibrit-on5")[0]


def test_ornekler_tiklaninca_calisir():
    """Örnek listeleri sadece kutuyu doldurmamalı: her birinin click olayına bir işlev bağlı olmalı."""
    gr = pytest.importorskip("gradio")
    import demo

    d = demo.arayuz()
    listeler = [b for b in d.blocks.values() if isinstance(b, gr.Dataset)]
    assert len(listeler) == 3
    tetikleyiciler = {tuple(hedef) for dep in d.config["dependencies"] for hedef in dep["targets"]}
    for liste in listeler:
        assert (liste._id, "click") in tetikleyiciler


def test_space_paketi_gizli_dosya_icermez(tmp_path):
    pytest.importorskip("gradio")
    sys.path.insert(0, str(Path(servis.__file__).parent))
    import hazirla

    yol = hazirla.hazirla(tmp_path / "space")
    dosyalar = {p.relative_to(yol).as_posix() for p in yol.rglob("*") if p.is_file()}
    assert {"demo.py", "servis.py", "requirements.txt", "README.md", "app/agent.py"} <= dosyalar
    assert any(d.startswith("data/belgeler/") for d in dosyalar)
    assert not any(d.endswith((".env", ".db", ".npy")) or "__pycache__" in d for d in dosyalar)
    assert "app_file: demo.py" in (yol / "README.md").read_text(encoding="utf-8")
