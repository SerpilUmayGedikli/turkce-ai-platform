"""CV Uyarlayıcı: web sitesi modu. Arayüzü (web/) ve API'yi (/api) aynı adresten sunar.

    python uygulama/sunucu.py            → http://localhost:8100
Masaüstü penceresi için: python uygulama/masaustu.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# PyInstaller paketinde dosyalar sys._MEIPASS altında; geliştirmede bu klasörün yanında
PAKET = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
PROJE = Path(__file__).resolve().parent.parent
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(PROJE / "api"))


def _ortam_hazirla() -> None:
    from app.cv import ayarlar  # noqa: PLC0415 - sys.path ayarından sonra

    os.environ.setdefault("ONBELLEK_DIZINI", str(ayarlar.klasor() / "onbellek"))
    if not getattr(sys, "frozen", False):
        ayarlar.env_dosyasi_yukle(PROJE / ".env")  # geliştirme: proje .env'i
    ayarlar.uygula()


def uygulama_olustur():
    _ortam_hazirla()  # ONBELLEK_DIZINI, embedding modülü import edilmeden önce ayarlanmalı
    from fastapi import FastAPI  # noqa: PLC0415
    from fastapi.staticfiles import StaticFiles  # noqa: PLC0415

    from app.cv.web_api import gomucu_isit, router  # noqa: PLC0415

    app = FastAPI(title="CV Uyarlayıcı", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.include_router(router)
    app.mount("/", StaticFiles(directory=PAKET / "web", html=True), name="web")
    app.add_event_handler("startup", gomucu_isit)
    return app


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8100"))
    print(f"CV Uyarlayıcı: http://localhost:{port}")
    uvicorn.run(uygulama_olustur(), host="127.0.0.1", port=port, log_level="warning")
