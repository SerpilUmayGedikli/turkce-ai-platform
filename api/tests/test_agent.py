"""API anahtarı olmadan çalışan testler: modeli sahte bir istemciyle taklit ediyoruz.

Çalıştır:  cd api && python -m pytest -q
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletion

from app import agent, main, tools


def _yanit(mesaj: dict) -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "x",
            "object": "chat.completion",
            "created": 0,
            "model": "sahte-model",
            "choices": [{"index": 0, "finish_reason": "stop", "message": mesaj}],
        }
    )


class SahteIstemci:
    """İlk çağrıda hesap_makinesi ister, ikinci çağrıda araç sonucunu cevaba koyar."""

    def __init__(self) -> None:
        self.gelen_mesajlar: list[list[dict]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, tools=None):
        self.gelen_mesajlar.append(list(messages))
        if len(self.gelen_mesajlar) == 1:
            return _yanit(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "hesap_makinesi",
                                "arguments": json.dumps({"ifade": "1250 * 0,20"}),
                            },
                        }
                    ],
                }
            )
        arac_sonucu = messages[-1]["content"]
        return _yanit({"role": "assistant", "content": f"KDV {arac_sonucu} TL."})


def test_hesap_makinesi_guvenli():
    assert tools.calistir("hesap_makinesi", {"ifade": "(2+3)*4"}) == "20"
    assert tools.calistir("hesap_makinesi", {"ifade": "10 / 4"}) == "2.5"
    assert tools.calistir("hesap_makinesi", {"ifade": "__import__('os')"}).startswith("HATA")


def test_bilinmeyen_arac():
    assert tools.calistir("yok_boyle_arac", {}).startswith("HATA")


def test_agent_araci_kullanip_cevap_verir():
    istemci = SahteIstemci()
    sonuc = agent.calistir("1250 TL'nin KDV'si?", model="test", client=istemci)

    assert sonuc.cevap == "KDV 250.0 TL."
    assert sonuc.adimlar[0]["arac"] == "hesap_makinesi"
    # ikinci çağrıda model, araç sonucunu "tool" mesajı olarak görmeli
    ikinci = istemci.gelen_mesajlar[1]
    assert ikinci[-1] == {"role": "tool", "tool_call_id": "c1", "content": "250.0"}


def test_api_sohbet(monkeypatch):
    monkeypatch.setattr(agent, "istemci", SahteIstemci)
    cevap = TestClient(main.app).post("/sohbet", json={"mesaj": "KDV?"})
    assert cevap.status_code == 200
    assert cevap.json()["cevap"] == "KDV 250.0 TL."
