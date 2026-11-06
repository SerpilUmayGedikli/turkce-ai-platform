"""Türkçe Text-to-SQL değerlendirmesi: execution accuracy (çalıştırma doğruluğu).

Her soru agent'a sorulur. Agent'ın başarıyla çalıştırdığı SON sorgunun sonucu, altın SQL'in
sonucuyla karşılaştırılır. SQL metni değil SONUÇ karşılaştırılır: aynı cevaba farklı yollarla
ulaşan sorgular doğru sayılır.

İki ölçü:
  katı   : satırlar birebir aynı (sıra önemsiz, sayılar 2 basamağa yuvarlanır)
  esnek  : satır sayısı aynı ve altın sonucun her sütunu tahminde bir sütun olarak var
           (model fazladan sütun eklemişse, ör. ad + sipariş sayısı, yine doğru sayılır)

Çalıştır:
  cd api && python -m eval.text2sql_degerlendir --model gemini --limit 5
  cd api && python -m eval.text2sql_degerlendir --model gemini --bekle 4     # tüm set
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path

from app import agent
from app.veritabani.sorgu import sorgula

from .text2sql_sorular import SORULAR

SONUC_KLASORU = Path(__file__).parent / "sonuclar"


def _normal(deger):
    if isinstance(deger, (int, float)) and not isinstance(deger, bool):
        return round(float(deger), 2)
    return deger


def _satirlar(sql: str) -> list[tuple]:
    return sorgula(sql)[1]


def karsilastir(altin: list[tuple], tahmin: list[tuple]) -> tuple[bool, bool]:
    altin = [tuple(_normal(v) for v in s) for s in altin]
    tahmin = [tuple(_normal(v) for v in s) for s in tahmin]
    anahtar = lambda s: tuple(str(v) for v in s)  # noqa: E731  (None ile karışık sıralama için)
    kati = sorted(altin, key=anahtar) == sorted(tahmin, key=anahtar)
    if kati:
        return True, True
    if not altin or len(altin) != len(tahmin) or not tahmin[0]:
        return False, False
    sutun = lambda satirlar, i: sorted(map(str, (s[i] for s in satirlar)))  # noqa: E731
    tahmin_sutunlari = [sutun(tahmin, j) for j in range(len(tahmin[0]))]
    esnek = all(sutun(altin, i) in tahmin_sutunlari for i in range(len(altin[0])))
    return False, esnek


def son_sql(adimlar: list[dict]) -> str | None:
    for adim in reversed(adimlar):
        if adim["arac"] == "sql_calistir" and not adim["sonuc"].startswith("HATA"):
            return adim["calistirilan"].get("sorgu")
    return None


def degerlendir_bir(ornek: dict, model: str) -> dict:
    kayit = {"soru": ornek["soru"], "etiket": ornek["etiket"], "altin_sql": ornek["sql"]}
    try:
        sonuc = agent.calistir(ornek["soru"], model=model)
    except Exception as e:  # kota, ağ hatası vb.: soruyu "hata" olarak say, devam et
        return {**kayit, "durum": "api_hatasi", "hata": f"{type(e).__name__}: {str(e)[:200]}",
                "kati": False, "esnek": False}

    sql = son_sql(sonuc.adimlar)
    kayit.update({
        "tahmin_sql": sql, "cevap": sonuc.cevap, "model": sonuc.model, "sure_ms": sonuc.sure_ms,
        "sql_denemesi": sum(a["arac"] == "sql_calistir" for a in sonuc.adimlar),
        "sql_hatasi": sum(a["arac"] == "sql_calistir" and a["sonuc"].startswith("HATA")
                          for a in sonuc.adimlar),
        "maskelenen": sonuc.maskelenen,
    })
    if sql is None:
        return {**kayit, "durum": "sql_yok", "kati": False, "esnek": False}
    try:
        kati, esnek = karsilastir(_satirlar(ornek["sql"]), _satirlar(sql))
    except sqlite3.Error as e:
        return {**kayit, "durum": "calistirma_hatasi", "hata": str(e), "kati": False, "esnek": False}
    return {**kayit, "durum": "dogru" if esnek else "yanlis", "kati": kati, "esnek": esnek}


def rapor_yaz(kayitlar: list[dict], model: str) -> Path:
    def oran(liste, alan):
        return sum(k[alan] for k in liste) / len(liste) if liste else 0.0

    # API hatası (kota, ağ) modelin başarısızlığı değildir: doğruluk hesabından çıkarılır
    tum_kayitlar = kayitlar
    kayitlar = [k for k in tum_kayitlar if k["durum"] != "api_hatasi"]
    api_hatasi = len(tum_kayitlar) - len(kayitlar)
    gruplar: dict[str, list] = defaultdict(list)
    for k in kayitlar:
        for e in k["etiket"]:
            gruplar[e].append(k)
    sureler = [k["sure_ms"] for k in kayitlar if "sure_ms" in k]
    satirlar = [
        f"# Türkçe Text-to-SQL Raporu: `{model}`\n",
        f"{len(tum_kayitlar)} soru. Durumlar: {dict(Counter(k['durum'] for k in tum_kayitlar))}\n",
    ]
    if api_hatasi:
        satirlar.append(f"> ⚠️ {api_hatasi} soru API hatası (kota/ağ) nedeniyle cevapsız kaldı ve "
                        "doğruluk hesabına KATILMADI. Ölçüm eksik; tekrar çalıştırılmalı.\n")
    satirlar += [
        "| Grup | Soru | Katı doğruluk | Esnek doğruluk |",
        "|---|---|---|---|",
        f"| **Tümü** | {len(kayitlar)} | **{oran(kayitlar, 'kati'):.0%}** | **{oran(kayitlar, 'esnek'):.0%}** |",
    ]
    for etiket in ["kolay", "orta", "zor", "turkce", "kvkk"]:
        if gruplar[etiket]:
            g = gruplar[etiket]
            satirlar.append(f"| {etiket} | {len(g)} | {oran(g, 'kati'):.0%} | {oran(g, 'esnek'):.0%} |")
    if sureler:
        satirlar.append(f"\nOrtalama süre: {sum(sureler) / len(sureler) / 1000:.1f} sn/soru. "
                        f"Kendi kendini düzeltme: {sum(k.get('sql_hatasi', 0) for k in kayitlar)} "
                        "SQL hatası sonrası yeniden deneme.\n")
    satirlar.append("## Yanlışlar\n")
    for k in tum_kayitlar:
        if not k["esnek"] and k["durum"] != "api_hatasi":
            satirlar.append(f"- **{k['soru']}** ({k['durum']})\n  - altın: `{k['altin_sql']}`\n"
                            f"  - tahmin: `{k.get('tahmin_sql')}`" + (f"\n  - hata: {k['hata']}" if k.get("hata") else ""))
    SONUC_KLASORU.mkdir(parents=True, exist_ok=True)
    yol = SONUC_KLASORU / f"text2sql_{model}.md"
    yol.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    return yol


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="gemini")
    p.add_argument("--limit", type=int, default=0, help="ilk N soru (0 = hepsi)")
    p.add_argument("--etiket", default="", help="sadece bu etiketli sorular (ör. turkce)")
    p.add_argument("--bekle", type=float, default=0, help="sorular arası bekleme (sn), kota için")
    a = p.parse_args()

    sorular = [s for s in SORULAR if not a.etiket or a.etiket in s["etiket"]]
    if a.limit:
        sorular = sorular[: a.limit]
    SONUC_KLASORU.mkdir(parents=True, exist_ok=True)
    kayitlar = []
    for i, ornek in enumerate(sorular, 1):
        k = degerlendir_bir(ornek, a.model)
        kayitlar.append(k)
        print(f"[{i}/{len(sorular)}] {'✓' if k['esnek'] else '✗'} {k['durum']:17s} {ornek['soru']}", flush=True)
        if len(kayitlar) >= 2 and all("429" in k.get("hata", "") for k in kayitlar[-2:]):
            print("Kota doldu (art arda 429). Durduruluyor; kota yenilenince tekrar çalıştır.")
            break
        if a.bekle and i < len(sorular):
            time.sleep(a.bekle)

    (SONUC_KLASORU / f"text2sql_{a.model}.jsonl").write_text(
        "\n".join(json.dumps(k, ensure_ascii=False) for k in kayitlar) + "\n", encoding="utf-8")
    print(f"Rapor -> {rapor_yaz(kayitlar, a.model)}")


if __name__ == "__main__":
    main()
