"""CV Uyarlayıcı: masaüstü uygulaması. Sunucuyu arka planda başlatır ve arayüzü Windows'un
yerleşik tarayıcı motoru (WebView2) ile kendi penceresinde açar. İnternet tarayıcısı gerekmez.

    python uygulama/masaustu.py
Paketleme (.exe): powershell -File uygulama/paketle.ps1
"""

from __future__ import annotations

import base64
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if getattr(sys, "frozen", False):
    # Pencereli .exe'de konsol yok: çıktı ve hatalar %APPDATA%\CVUyarlayici\uygulama.log'a gider.
    # Çökme olursa Python yığını da buraya yazılır (faulthandler).
    import faulthandler
    import os

    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

    _klasor = Path(os.getenv("APPDATA") or Path.home()) / "CVUyarlayici"
    _klasor.mkdir(parents=True, exist_ok=True)
    _log = open(_klasor / "uygulama.log", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = sys.stderr = _log
    faulthandler.enable(_log)

import uvicorn  # noqa: E402
import webview  # noqa: E402

from sunucu import uygulama_olustur  # noqa: E402


def _bos_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class KopruAPI:
    """Arayüzden çağrılan yerel işlemler (window.pywebview.api.*). WebView içinde tarayıcı
    indirmesi güvenilir çalışmadığı için dosyalar Windows'un Kaydet penceresiyle yazılır."""

    def __init__(self) -> None:
        # "_" önekli: pywebview js_api nesnesinin herkese açık alanlarını özyinelemeli tarar;
        # pencere nesnesi açık kalırsa log binlerce hata satırıyla dolar.
        self._pencere: webview.Window | None = None

    def kaydet(self, dosya_adi: str, base64_veri: str) -> str | None:
        uzanti = Path(dosya_adi).suffix.lstrip(".") or "dat"
        secim = self._pencere.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=dosya_adi,
            file_types=(f"{uzanti.upper()} dosyası (*.{uzanti})",))
        if not secim:
            return None
        yol = secim if isinstance(secim, str) else secim[0]
        Path(yol).write_bytes(base64.b64decode(base64_veri))
        return yol


def main() -> None:
    port = _bos_port()
    # Pencereli .exe'de konsol yok (sys.stderr None): uvicorn'un konsol log ayarı çökerdi
    sunucu = uvicorn.Server(uvicorn.Config(uygulama_olustur(), host="127.0.0.1", port=port,
                                           log_level="warning", log_config=None))
    threading.Thread(target=sunucu.run, daemon=True).start()
    for _ in range(200):  # sunucu hazır olana kadar bekle (en fazla ~10 sn)
        if sunucu.started:
            break
        time.sleep(0.05)

    kopru = KopruAPI()
    kopru._pencere = webview.create_window(
        "CV Uyarlayıcı", f"http://127.0.0.1:{port}/", js_api=kopru,
        width=1280, height=820, min_size=(960, 640), background_color="#E6E9EF")
    simge = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "simge.ico"
    webview.start(icon=str(simge) if simge.exists() else None)
    sunucu.should_exit = True


if __name__ == "__main__":
    main()
