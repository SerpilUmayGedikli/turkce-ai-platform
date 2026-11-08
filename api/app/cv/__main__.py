from __future__ import annotations

import argparse
import re
from pathlib import Path

from . import calistir
from .cikti import docx_yaz, pdf_yaz
from .okuyucu import dosyadan


def main() -> None:
    p = argparse.ArgumentParser(description="CV'yi iş ilanına göre uyarlar.")
    p.add_argument("cv", help="CV dosyası (PDF, DOCX, TXT)")
    p.add_argument("ilan", help="İlan metni dosyası (TXT)")
    p.add_argument("--ad", default="", help="Ad Soyad (boşsa CV'nin ilk satırı)")
    p.add_argument("--dil", default="ilan", choices=["ilan", "tr", "en"])
    p.add_argument("--cikti", default=".", help="Çıktı klasörü")
    a = p.parse_args()

    s = calistir(dosyadan(a.cv), Path(a.ilan).read_text(encoding="utf-8"), ad=a.ad, dil=a.dil)
    print(f"Uyum skoru: {s.once.skor} -> {s.sonra.skor}  (model: {s.cv.model})")
    print("Eksik beceriler:", ", ".join(sorted(s.once.eksik_beceriler)) or "-")
    for o in s.cv.oneriler:
        print("  öneri:", o)
    for u in s.cv.uydurma_supheleri:
        print("  ⚠ kontrol et:", u)

    klasor = Path(a.cikti)
    klasor.mkdir(parents=True, exist_ok=True)
    kok = re.sub(r"\W+", "_", f"{s.baslik.ad or 'cv'}_uyarlanmis").strip("_")
    (klasor / f"{kok}.docx").write_bytes(docx_yaz(s.baslik, s.cv))
    (klasor / f"{kok}.pdf").write_bytes(pdf_yaz(s.baslik, s.cv))
    print(f"Yazıldı: {klasor / kok}.docx / .pdf")


if __name__ == "__main__":
    main()
