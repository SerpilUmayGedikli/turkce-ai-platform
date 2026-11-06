"""Text-to-SQL testleri. API anahtarı gerekmez."""

from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import pytest

from app import agent
from app.veritabani.sorgu import sorgula, tr_lower
from eval import text2sql_degerlendir as degerlendir
from eval.text2sql_sorular import SORULAR

from .test_agent import _yanit


# ---------------------------------------------------------------- güvenlik
@pytest.mark.parametrize("sql", [
    "DELETE FROM musteriler",
    "UPDATE urunler SET fiyat = 0",
    "DROP TABLE urunler",
    "INSERT INTO kategoriler VALUES (99, 'x')",
    "ATTACH 'baska.db' AS b",
    "PRAGMA table_info(urunler)",
    "SELECT 1; DELETE FROM musteriler",
    "WITH RECURSIVE s(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM s) SELECT COUNT(*) FROM s",
])
def test_tehlikeli_sorgular_engellenir(sql):
    with pytest.raises(sqlite3.Error):
        sorgula(sql)
    assert sorgula("SELECT COUNT(*) FROM musteriler")[1][0][0] == 320  # veri sağlam


def test_satir_siniri():
    _, satirlar = sorgula("SELECT * FROM siparisler")
    assert len(satirlar) == 51  # 50 + "daha fazlası var" işareti


# ---------------------------------------------------------------- Türkçe
def test_tr_lower_ve_sqlite_farki():
    assert tr_lower("İSTANBUL") == "istanbul" and tr_lower("IĞDIR") == "ığdır"
    sqlite_lower = sorgula("SELECT LOWER('İSTANBUL')")[1][0][0]
    assert sqlite_lower != "istanbul"  # SQLite'ın kendi LOWER'ı Türkçeyi bilmez
    assert sorgula("SELECT COUNT(*) FROM musteriler WHERE ad LIKE 'ş%'")[1][0][0] == 0
    assert sorgula("SELECT COUNT(*) FROM musteriler WHERE tr_lower(ad) LIKE 'ş%'")[1][0][0] > 0


def test_tr_katla_modelin_isparta_hatasini_onler():
    # İlk ölçümde modelin yazdığı (yanlış) sorgu 0 buluyordu:
    hatali = "SELECT COUNT(*) FROM musteriler WHERE tr_lower(sehir) = 'isparta'"
    assert sorgula(hatali)[1][0][0] == 0
    # Katlama ile kullanıcının yazdığı her biçim aynı sonucu verir
    dogru = sorgula("SELECT COUNT(*) FROM musteriler WHERE sehir = 'Isparta'")[1][0][0]
    for yazim in ["ISPARTA", "isparta", "Isparta", "ısparta"]:
        sql = f"SELECT COUNT(*) FROM musteriler WHERE tr_katla(sehir) = tr_katla('{yazim}')"
        assert sorgula(sql)[1][0][0] == dogru > 0
    # Veri tarafındaki yazım tutarsızlığı da çözülür: 'Ismail' kaydı 'İsmail' aramasıyla bulunur
    assert sorgula("SELECT COUNT(*) FROM musteriler WHERE tr_katla(ad) = tr_katla('İsmail')")[1][0][0] > 0


# ---------------------------------------------------------------- test seti sağlığı
@pytest.mark.parametrize("ornek", SORULAR, ids=[s["soru"][:40] for s in SORULAR])
def test_altin_sql_calisir_ve_bos_degil(ornek):
    sutunlar, satirlar = sorgula(ornek["sql"])
    assert satirlar and satirlar[0][0] is not None


# ---------------------------------------------------------------- karşılaştırma
def test_karsilastir():
    k = degerlendir.karsilastir
    assert k([(1,), (2,)], [(2,), (1,)]) == (True, True)            # sıra önemsiz
    assert k([(250.004,)], [(250.0,)]) == (True, True)              # yuvarlama
    assert k([("Ali",)], [("Ali", 5)]) == (False, True)             # fazladan sütun: esnek doğru
    assert k([("Ali",), ("Can",)], [("Ali", 5)]) == (False, False)  # eksik satır
    assert k([(3,)], [(4,)]) == (False, False)


# ---------------------------------------------------------------- agent + KVKK + SQL
class SqlSahteIstemci:
    """Model gibi: önce etiketli SQL yazar, sonra sonucu cevaba koyar."""

    def __init__(self, sql: str) -> None:
        self.sql, self.modelin_gordugu = sql, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, tools=None):
        self.modelin_gordugu += [json.dumps(m, ensure_ascii=False, default=str) for m in messages]
        if not any(isinstance(m, dict) and m.get("role") == "tool" for m in messages):
            return _yanit({"role": "assistant", "content": None, "tool_calls": [{
                "id": "s1", "type": "function",
                "function": {"name": "sql_calistir", "arguments": json.dumps({"sorgu": self.sql})}}]})
        return _yanit({"role": "assistant", "content": messages[-1]["content"]})


def test_kvkk_etiketli_sql_gercek_degerle_calisir():
    istemci = SqlSahteIstemci("SELECT sehir FROM musteriler WHERE tckn = '[TCKN_1]'")
    sonuc = agent.calistir("TC kimlik numarası 40666836414 olan müşteri nerede?", model="t", client=istemci)
    assert "Ankara" in sonuc.cevap
    assert sonuc.adimlar[0]["calistirilan"]["sorgu"].endswith("'40666836414'")
    assert not any("40666836414" in m for m in istemci.modelin_gordugu)


def test_sorgu_sonucundaki_kisisel_veri_de_maskelenir():
    istemci = SqlSahteIstemci("SELECT ad, tckn, telefon FROM musteriler WHERE id = 42")
    sonuc = agent.calistir("42 numaralı müşteri kim?", model="t", client=istemci)
    arac_mesaji = [m for m in istemci.modelin_gordugu if '"role": "tool"' in m][0]
    assert "40666836414" not in arac_mesaji and "[TCKN_1]" in arac_mesaji
    assert "05424011878" not in arac_mesaji
    assert "40666836414" in sonuc.cevap  # kullanıcı gerçek değeri görür


def test_degerlendir_bir_dogru_ve_yanlis(monkeypatch):
    ornek = {"soru": "Kaç müşteri?", "etiket": ["kolay"], "sql": "SELECT COUNT(*) FROM musteriler"}
    for sql, beklenen in [("SELECT COUNT(id) FROM musteriler", "dogru"),
                          ("SELECT COUNT(*) FROM urunler", "yanlis")]:
        monkeypatch.setattr(agent, "istemci", lambda sql=sql: SqlSahteIstemci(sql))
        assert degerlendir.degerlendir_bir(ornek, "t")["durum"] == beklenen
