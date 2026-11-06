"""KVKK Kalkanı değerlendirmesi: precision / recall / F1, baseline ile karşılaştırmalı.

Baseline = internette sık görülen "saf regex" yaklaşımı: kontrol hanesi doğrulaması yok,
her 11 haneli sayı TCKN, her 16 haneli sayı kart, her 10-11 haneli sayı telefon sayılır.

Eşleşme kuralı: tür + başlangıç + bitiş birebir aynı olmalı (katı ölçüm).

Çalıştır:  cd api && python -m eval.kvkk_veri_uret && python -m eval.kvkk_degerlendir
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from app.kvkk import TURLER, bul

from .kvkk_zor_ornekler import ornekler as zor_ornekler

KLASOR = Path(__file__).parent
SENTETIK = KLASOR / "veri" / "kvkk_sentetik.jsonl"
RAPOR = KLASOR / "sonuclar" / "kvkk_rapor.md"

# ------------------------------------------------------------------ baseline
_SAF = [
    ("IBAN", re.compile(r"TR\d{2}(?: ?\d{4}){5} ?\d{2}")),
    ("EPOSTA", re.compile(r"\S+@\S+\.\w+")),
    ("KART", re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b")),
    ("TCKN", re.compile(r"\b\d{11}\b")),
    ("TELEFON", re.compile(r"(?:\+90 ?)?\b0?\d{3}[ -]?\d{3}[ -]?\d{2}[ -]?\d{2}\b")),
]


def saf_regex(metin: str) -> list[tuple[str, int, int]]:
    bulunan: list[tuple[str, int, int]] = []
    for tur, desen in _SAF:
        for m in desen.finditer(metin):
            if all(m.end() <= b or m.start() >= e for _, b, e in bulunan):
                bulunan.append((tur, m.start(), m.end()))
    return bulunan


def kalkan(metin: str) -> list[tuple[str, int, int]]:
    return [(b.tur, b.baslangic, b.bitis) for b in bul(metin)]


# ------------------------------------------------------------------ ölçüm
def olc(veri: list[dict], tespit_et) -> tuple[dict, list[dict]]:
    tp, fp, fn = Counter(), Counter(), Counter()
    hatalar = []
    for ornek in veri:
        gercek = {(v["tur"], v["baslangic"], v["bitis"]) for v in ornek["varliklar"]}
        tahmin = set(tespit_et(ornek["metin"]))
        for t in tahmin & gercek:
            tp[t[0]] += 1
        for t in tahmin - gercek:
            fp[t[0]] += 1
        for t in gercek - tahmin:
            fn[t[0]] += 1
        if tahmin != gercek:
            m = ornek["metin"]
            hatalar.append({
                "metin": m,
                "kacan": [f"{t}:{m[b:e]!r}" for t, b, e in sorted(gercek - tahmin)],
                "fazla": [f"{t}:{m[b:e]!r}" for t, b, e in sorted(tahmin - gercek)],
            })

    def prf(a, b, c):
        p = a / (a + b) if a + b else 1.0
        r = a / (a + c) if a + c else 1.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        return p, r, f

    tablo = {t: (*prf(tp[t], fp[t], fn[t]), tp[t], fp[t], fn[t]) for t in TURLER}
    tablo["TOPLAM"] = (*prf(sum(tp.values()), sum(fp.values()), sum(fn.values())),
                       sum(tp.values()), sum(fp.values()), sum(fn.values()))
    return tablo, hatalar


def tablo_md(baslik: str, saf: dict, biz: dict) -> str:
    satirlar = [
        f"### {baslik}\n",
        "| Tür | Saf regex P / R / F1 | **KVKK Kalkanı** P / R / F1 | Kalkan TP / FP / FN |",
        "|---|---|---|---|",
    ]
    for tur in [*TURLER, "TOPLAM"]:
        s, b = saf[tur], biz[tur]
        ad = f"**{tur}**" if tur == "TOPLAM" else tur
        satirlar.append(
            f"| {ad} | {s[0]:.2f} / {s[1]:.2f} / {s[2]:.2f} "
            f"| **{b[0]:.2f} / {b[1]:.2f} / {b[2]:.2f}** | {b[3]} / {b[4]} / {b[5]} |"
        )
    return "\n".join(satirlar) + "\n"


def main() -> None:
    if not SENTETIK.exists():
        raise SystemExit("Önce veri üret:  python -m eval.kvkk_veri_uret")
    sentetik = [json.loads(s) for s in SENTETIK.read_text(encoding="utf-8").splitlines()]
    zor = zor_ornekler()

    sonuc = {}
    for ad, veri in [("sentetik", sentetik), ("zor", zor)]:
        sonuc[ad] = {"saf": olc(veri, saf_regex), "biz": olc(veri, kalkan)}

    rapor = [
        "# KVKK Kalkanı: Değerlendirme Raporu\n",
        "Otomatik üretildi: `python -m eval.kvkk_degerlendir`. "
        "P = precision (bulduklarımızın ne kadarı doğru), R = recall (gerçeklerin ne kadarını bulduk). "
        "Eşleşme katı: tür ve karakter aralığı birebir aynı olmalı.\n",
        tablo_md(f"Sentetik set ({len(sentetik)} örnek, tuzak sayılar içerir)",
                 sonuc["sentetik"]["saf"][0], sonuc["sentetik"]["biz"][0]),
        tablo_md(f"Elle yazılmış zor set ({len(zor)} örnek)",
                 sonuc["zor"]["saf"][0], sonuc["zor"]["biz"][0]),
        "### KVKK Kalkanı'nın zor sette yaptığı hatalar\n",
    ]
    for h in sonuc["zor"]["biz"][1]:
        rapor.append(f"- `{h['metin']}` → kaçan: {h['kacan'] or '-'}, fazla: {h['fazla'] or '-'}")
    rapor.append(
        "\n### Kapsam dışı (henüz)\n\n"
        "Ad-soyad, adres, doğum tarihi, plaka. Bunlar kuralla güvenilir yakalanamaz; "
        "sonraki adım Türkçe NER modeliyle karşılaştırma.\n"
    )
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text("\n".join(rapor), encoding="utf-8")

    for ad in ("sentetik", "zor"):
        s, b = sonuc[ad]["saf"][0]["TOPLAM"], sonuc[ad]["biz"][0]["TOPLAM"]
        print(f"{ad:9s} saf regex  P={s[0]:.3f} R={s[1]:.3f} F1={s[2]:.3f}")
        print(f"{'':9s} kalkan     P={b[0]:.3f} R={b[1]:.3f} F1={b[2]:.3f}")
    print(f"Rapor -> {RAPOR}")


if __name__ == "__main__":
    main()
