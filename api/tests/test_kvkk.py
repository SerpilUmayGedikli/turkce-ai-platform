"""KVKK Kalkanı testleri. API anahtarı gerekmez."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import agent, main
from app.kvkk import Maskeleyici, bul
from app.kvkk.tespit import iban_gecerli, luhn_gecerli, tckn_gecerli

from .test_agent import _yanit

GERCEK_TCKN = "12345678950"  # algoritmaya uygun, rastgele bir örnek
IBAN = "TR33 0006 1005 1978 6457 8413 26"


@pytest.mark.parametrize("s,beklenen", [
    ("12345678950", True), ("10000000146", True),
    ("12345678901", False), ("02345678950", False), ("1234567895", False),
])
def test_tckn_algoritmasi(s, beklenen):
    assert tckn_gecerli(s) is beklenen


def test_iban_ve_luhn():
    assert iban_gecerli(IBAN) and iban_gecerli(IBAN.replace(" ", "").lower())
    assert not iban_gecerli(IBAN.replace("26", "27"))
    assert luhn_gecerli("4111 1111 1111 1111") and not luhn_gecerli("4111 1111 1111 1112")


@pytest.mark.parametrize("tel", [
    "0532 123 45 67", "05321234567", "+90 532 123 45 67", "(0532) 123 45 67",
    "0212-345-67-89", "532 123 45 67",
])
def test_telefon_bicimleri(tel):
    bulgular = bul(f"Tel: {tel}.")
    assert [(b.tur, b.metin) for b in bulgular] == [("TELEFON", tel)]


def test_tuzak_sayilar_maskelenmez():
    metin = "Sipariş no 12345678901, fatura 1234567812345678, tutar 1.250 TL"
    assert bul(metin) == []


def test_ayni_deger_ayni_etiket_ve_geri_yukleme():
    m = Maskeleyici()
    a = m.maskele(f"IBAN {IBAN}")
    b = m.maskele(f"Tekrar: {IBAN.replace(' ', '')}")  # biçim farklı, değer aynı
    assert a == "IBAN [IBAN_1]" and b == "Tekrar: [IBAN_1]"
    assert m.geri_yukle("[IBAN_1] onaylandı") == f"{IBAN} onaylandı"
    assert m.geri_yukle("[TCKN_9] bilinmiyor") == "[TCKN_9] bilinmiyor"  # uydurma etiket


class KvkkSahteIstemci:
    """Model gibi davranır: etiketi araca verir, sonra etiketle cevap yazar."""

    def __init__(self) -> None:
        self.modelin_gordugu: list[str] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, tools=None):
        self.modelin_gordugu += [json.dumps(m, ensure_ascii=False, default=str) for m in messages]
        if not any(m.get("role") == "tool" for m in messages if isinstance(m, dict)):
            return _yanit({
                "role": "assistant", "content": None,
                "tool_calls": [{
                    "id": "c1", "type": "function",
                    "function": {"name": "tckn_dogrula", "arguments": json.dumps({"tckn": "[TCKN_1]"})},
                }],
            })
        return _yanit({"role": "assistant", "content": f"[TCKN_1] numarası {messages[-1]['content']}."})


def test_model_gercek_veriyi_hic_gormez():
    istemci = KvkkSahteIstemci()
    sonuc = agent.calistir(
        f"TC numaram {GERCEK_TCKN}, telefonum 0532 123 45 67. Geçerli mi?",
        model="test", client=istemci,
    )
    # 1) Modele giden hiçbir mesajda gerçek değerler yok
    assert not any(GERCEK_TCKN in m or "0532 123 45 67" in m for m in istemci.modelin_gordugu)
    assert "[TCKN_1]" in sonuc.modele_giden_soru and "[TELEFON_1]" in sonuc.modele_giden_soru
    # 2) Yerel araç gerçek değerle çalıştı (etiketle değil)
    assert sonuc.adimlar[0]["sonuc"] == "geçerli"
    # 3) Kullanıcı gerçek değeri geri aldı
    assert sonuc.cevap == f"{GERCEK_TCKN} numarası geçerli."
    assert sonuc.maskelenen == {"TCKN": 1, "TELEFON": 1}


def test_kvkk_kapaliyken_maskeleme_yok():
    istemci = KvkkSahteIstemci()
    sonuc = agent.calistir(f"TC {GERCEK_TCKN}", model="test", client=istemci, kvkk=False)
    assert GERCEK_TCKN in sonuc.modele_giden_soru and sonuc.maskelenen == {}


def test_api_maskele_ucu():
    r = TestClient(main.app).post("/kvkk/maskele", json={"metin": f"TC {GERCEK_TCKN}"})
    assert r.json() == {"maskeli": "TC [TCKN_1]", "maskelenen": {"TCKN": 1}}
