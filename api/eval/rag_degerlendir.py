"""Türkçe belge arama değerlendirmesi: 6 yöntem x 50 soru. API anahtarı gerekmez.

Ölçüler:
  Recall@1 : doğru parça ilk sırada mı
  Recall@5 : doğru parça ilk 5'te mi (agent'a giden bağlam kabaca budur)
  MRR      : doğru parçanın sırasının tersi ortalaması (1. sıra = 1, 2. = 0.5, bulunamadı = 0)

Çalıştır:  cd api && python -m eval.rag_degerlendir
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from app.rag import YONTEMLER, varsayilan

from .rag_sorular import SORULAR

SONUC = Path(__file__).parent / "sonuclar" / "rag_rapor.md"
ETIKETLER = ["dogrudan", "cekim", "esanlam"]


def sira_bul(siralama: list[str], altin: list[str]) -> int | None:
    """Altın parçalardan herhangi birinin 1'den başlayan sırası; yoksa None."""
    for i, kimlik in enumerate(siralama, 1):
        if kimlik in altin:
            return i
    return None


def olc(siralar: list[int | None]) -> dict[str, float]:
    n = len(siralar) or 1
    return {
        "R@1": sum(s == 1 for s in siralar) / n,
        "R@5": sum(s is not None and s <= 5 for s in siralar) / n,
        "MRR": sum(1 / s for s in siralar if s) / n,
    }


def main() -> None:
    arama = varsayilan()
    yontemler = [y for y in YONTEMLER if arama.vektorler is not None or y.startswith("bm25")]
    sonuclar: dict[str, dict[str, list]] = {y: defaultdict(list) for y in yontemler}
    kayiplar: dict[str, list[str]] = defaultdict(list)

    for ornek in SORULAR:
        for y in yontemler:
            kimlikler = [arama.parcalar[i].kimlik for i in arama.sirala(ornek["soru"], y)]
            sira = sira_bul(kimlikler, ornek["altin"])
            sonuclar[y]["tumu"].append(sira)
            sonuclar[y][ornek["etiket"]].append(sira)
            if sira is None or sira > 5:
                kayiplar[y].append(f"{ornek['soru']} (sıra: {sira or 'yok'})")

    sayilar = {e: sum(o["etiket"] == e for o in SORULAR) for e in ETIKETLER}
    satirlar = [
        "# Türkçe Belge Arama Raporu\n",
        f"{len(SORULAR)} soru, {len(arama.parcalar)} parça (9 belge). "
        f"Soru türleri: {sayilar}\n",
        "## Genel\n",
        "| Yöntem | Recall@1 | Recall@5 | MRR |",
        "|---|---|---|---|",
    ]
    for y in yontemler:
        m = olc(sonuclar[y]["tumu"])
        satirlar.append(f"| {y} | {m['R@1']:.0%} | {m['R@5']:.0%} | {m['MRR']:.2f} |")

    satirlar += ["\n## Soru türüne göre Recall@5\n",
                 "| Yöntem | " + " | ".join(f"{e} ({sayilar[e]})" for e in ETIKETLER) + " |",
                 "|---|" + "---|" * len(ETIKETLER)]
    for y in yontemler:
        satirlar.append(f"| {y} | " + " | ".join(f"{olc(sonuclar[y][e])['R@5']:.0%}" for e in ETIKETLER) + " |")

    satirlar.append("\n## İlk 5'te bulunamayanlar\n")
    for y in yontemler:
        satirlar.append(f"**{y}** ({len(kayiplar[y])})\n")
        satirlar += [f"- {k}" for k in kayiplar[y]] + [""]

    SONUC.parent.mkdir(parents=True, exist_ok=True)
    SONUC.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    print("\n".join(satirlar[:12 + 2 * len(yontemler)]))
    print(f"\nRapor -> {SONUC}")


if __name__ == "__main__":
    main()
