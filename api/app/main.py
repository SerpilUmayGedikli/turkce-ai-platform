"""Platformun HTTP API'si.

Çalıştır (Docker dışında):  uvicorn app.main:app --reload
Dokümantasyon:             http://localhost:8000/docs
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from openai import APIError
from pydantic import BaseModel, Field

from . import agent, tools
from .kvkk import Maskeleyici

app = FastAPI(
    title="Türkçe AI Platformu",
    description="Çok modelli, araç kullanan Türkçe agent servisi",
    version="0.1.0",
)


class Mesaj(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class SohbetIstegi(BaseModel):
    mesaj: str = Field(..., min_length=1, examples=["250 * 1.2 kaç eder?"])
    model: str | None = Field(None, description="gateway takma adı: gemini, gemini-3, gemini-lite, qwen, kimi, nemotron, yerel")
    gecmis: list[Mesaj] = []
    kvkk: bool = Field(True, description="Kişisel verileri modele göndermeden önce maskele")


class SohbetCevabi(BaseModel):
    cevap: str
    model: str
    adimlar: list[dict[str, Any]]
    sure_ms: int
    maskelenen: dict[str, int]
    modele_giden_soru: str


class MaskeleIstegi(BaseModel):
    metin: str = Field(..., examples=["TC'm 10000000146, tel 0532 123 45 67"])


@app.post("/kvkk/maskele")
def kvkk_maskele(istek: MaskeleIstegi) -> dict[str, Any]:
    """Modele hiçbir şey göndermeden, sadece maskelemenin sonucunu gösterir."""
    kalkan = Maskeleyici()
    return {"maskeli": kalkan.maskele(istek.metin), "maskelenen": dict(kalkan.istatistik)}


@app.get("/saglik")
def saglik() -> dict[str, Any]:
    return {"durum": "ok", "araclar": list(tools.KAYIT)}


@app.post("/sohbet", response_model=SohbetCevabi)
def sohbet(istek: SohbetIstegi) -> SohbetCevabi:
    try:
        sonuc = agent.calistir(
            istek.mesaj,
            model=istek.model,
            gecmis=[m.model_dump() for m in istek.gecmis],
            kvkk=istek.kvkk,
        )
    except APIError as e:
        raise HTTPException(status_code=502, detail=f"Model hatası: {e}") from e
    return SohbetCevabi(**sonuc.__dict__)
