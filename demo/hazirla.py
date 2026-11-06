"""Hugging Face Space klasörünü hazırlar: demo + api/app paketi + belgeler, tek klasörde.

    python demo/hazirla.py            → demo/space/ (git'e girmez)

Sonra demo/space/ içeriğini Space deposuna yükle (bkz. demo/README.md). .env, veritabanı ve
embedding önbelleği kopyalanmaz: veritabanı ilk açılışta sahte veriyle üretilir, model iner.
"""

from __future__ import annotations

import shutil
from pathlib import Path

DEMO = Path(__file__).resolve().parent
KOK = DEMO.parent
HEDEF = DEMO / "space"

SPACE_README = """---
title: Türkçe AI Platformu
emoji: 🇹🇷
colorFrom: red
colorTo: gray
sdk: gradio
sdk_version: {surum}
app_file: demo.py
pinned: false
short_description: Türkçe agent - Text-to-SQL, hibrit RAG, KVKK maskeleme
---

Türkçe agent demosu: Text-to-SQL, Türkçe hibrit belge arama (BM25 + embedding) ve KVKK maskeleme.
Asistan sekmesi için Space ayarlarında `GEMINI_API_KEY` adlı bir **secret** tanımla.
"""

GEREKSINIMLER = """openai>=1.50
pydantic>=2.7
tzdata
numpy>=1.26
snowballstemmer>=2.2
fastembed>=0.4
"""


def hazirla(hedef: Path = HEDEF) -> Path:
    import gradio

    if hedef.exists():
        shutil.rmtree(hedef)
    yoksay = shutil.ignore_patterns("__pycache__", "*.pyc", "*.db", "rag_onbellek")
    shutil.copytree(KOK / "api" / "app", hedef / "app", ignore=yoksay)
    shutil.copytree(KOK / "api" / "data" / "belgeler", hedef / "data" / "belgeler")
    for dosya in ("demo.py", "servis.py"):
        shutil.copy2(DEMO / dosya, hedef / dosya)
    (hedef / "requirements.txt").write_text(GEREKSINIMLER, encoding="utf-8")
    (hedef / "README.md").write_text(SPACE_README.format(surum=gradio.__version__), encoding="utf-8")
    (hedef / ".gitignore").write_text("__pycache__/\ndata/*.db\ndata/rag_onbellek/\n", encoding="utf-8")
    return hedef


if __name__ == "__main__":
    yol = hazirla()
    dosyalar = sorted(p.relative_to(yol).as_posix() for p in yol.rglob("*") if p.is_file())
    print(f"{len(dosyalar)} dosya → {yol}")
    assert not any(d.endswith((".env", ".db")) for d in dosyalar), "gizli/veri dosyası kopyalanmamalı"
