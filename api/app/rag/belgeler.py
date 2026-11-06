"""Belgeleri okur ve parçalara (chunk) böler.

Parçalama stratejisi: her "## Başlık" bölümü bir parçadır. Politika belgeleri zaten konu
başlıklarıyla yazıldığı için sabit uzunlukta kesmekten daha anlamlı parçalar verir; başlık da
parçanın başına eklenir ki "İade kargo ücreti" gibi başlıklar aramada eşleşebilsin.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BELGE_KLASORU = Path(__file__).resolve().parents[2] / "data" / "belgeler"


@dataclass(frozen=True)
class Parca:
    kimlik: str      # "iade-ve-degisim::İade süresi"
    belge: str       # "İade ve Değişim Politikası"
    baslik: str      # "İade süresi"
    metin: str       # bölüm metni

    @property
    def tam_metin(self) -> str:
        return f"{self.belge} - {self.baslik}. {self.metin}"


def parcala(dosya_adi: str, icerik: str) -> list[Parca]:
    belge, parcalar, baslik, satirlar = dosya_adi, [], None, []

    def bitir():
        if baslik and "".join(satirlar).strip():
            metin = " ".join(s.strip() for s in satirlar if s.strip())
            parcalar.append(Parca(f"{dosya_adi}::{baslik}", belge, baslik, metin))

    for satir in icerik.splitlines():
        if satir.startswith("# "):
            belge = satir[2:].strip()
        elif satir.startswith("## "):
            bitir()
            baslik, satirlar = satir[3:].strip(), []
        else:
            satirlar.append(satir)
    bitir()
    return parcalar


def yukle(klasor: Path = BELGE_KLASORU) -> list[Parca]:
    parcalar: list[Parca] = []
    for yol in sorted(klasor.glob("*.md")):
        parcalar += parcala(yol.stem, yol.read_text(encoding="utf-8"))
    return parcalar
