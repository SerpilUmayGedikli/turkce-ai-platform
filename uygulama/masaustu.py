"""CV Uyarlayıcı: masaüstü uygulaması. Sunucuyu arka planda başlatır ve arayüzü Windows'un
yerleşik tarayıcı motoru (WebView2) ile kendi penceresinde açar. İnternet tarayıcısı gerekmez.

    python uygulama/masaustu.py
Paketleme (.exe): powershell -File uygulama/paketle.ps1
"""

from __future__ import annotations

import base64
import json
import re
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


PAKET = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
ILAN_DUGMESI = (PAKET / "ilan_dugmesi.js").read_text(encoding="utf-8")


class SiteKopru:
    """İlan sitesi pencerelerine verilen TEK yetki: o anki ilanı uygulamaya göndermek.
    Sitenin kendi kodu da bu nesneyi görebildiği için dosya kaydetme, pencere açma gibi işlevler
    burada BİLEREK yoktur; gönderim de hız sınırlıdır."""

    def __init__(self, ana: KopruAPI) -> None:
        self._ana = ana
        self._son = 0.0

    def ilan_gonder(self, veri: dict) -> str:
        from app.cv import ilanlar  # noqa: PLC0415

        if time.time() - self._son < 1.5:
            return "Biraz bekle, az önce eklendi."
        self._son = time.time()
        veri = veri if isinstance(veri, dict) else {}
        try:
            kayit = ilanlar.ilan_ekle(str(veri.get("metin", ""))[:60000], str(veri.get("baslik", "")),
                                      str(veri.get("url", "")))
        except ValueError as e:
            return str(e)
        self._ana.ilan_eklendi(kayit)
        return f"Eklendi: {kayit['baslik'][:60]}. CV Uyarlayıcı'daki İlanlar listesinde."


class KopruAPI:
    """Arayüzden çağrılan yerel işlemler (window.pywebview.api.*). WebView içinde tarayıcı
    indirmesi güvenilir çalışmadığı için dosyalar Windows'un Kaydet penceresiyle yazılır."""

    def __init__(self) -> None:
        # "_" önekli: pywebview js_api nesnesinin herkese açık alanlarını özyinelemeli tarar;
        # pencere nesnesi açık kalırsa log binlerce hata satırıyla dolar.
        self._pencere: webview.Window | None = None
        self._siteler: dict[str, webview.Window] = {}
        self._site_kopru = SiteKopru(self)

    def site_ac(self, kimlik: str, adres: str, ad: str = "") -> bool:
        """İlan sitesini kendi penceresinde açar; açıksa öne getirip adresi yeniler. Oturum
        çerezleri kalıcıdır: kullanıcı bir kez giriş yapar."""
        if not re.match(r"^https?://", adres or ""):
            return False
        pencere = self._siteler.get(kimlik)
        if pencere is not None:
            try:
                pencere.load_url(adres)
                pencere.restore()
                pencere.show()
                return True
            except Exception:  # noqa: BLE001 - pencere kapatılmış
                self._siteler.pop(kimlik, None)
        pencere = webview.create_window(
            f"{ad or kimlik} · CV Uyarlayıcı", adres, js_api=self._site_kopru, width=1240, height=860,
            text_select=True, zoomable=True)
        pencere.events.loaded += lambda: self._dugme_ekle(pencere)
        pencere.events.closed += lambda: self._siteler.pop(kimlik, None)
        self._siteler[kimlik] = pencere
        return True

    @staticmethod
    def tarayicida_ac(adres: str) -> bool:
        """Siteyi kullanıcının kendi varsayılan tarayıcısında (Chrome, Edge...) açar; orada zaten
        girişli olduğu oturum kullanılır."""
        if not re.match(r"^https?://", adres or ""):
            return False
        import webbrowser  # noqa: PLC0415

        return webbrowser.open(adres)

    @staticmethod
    def _dugme_ekle(pencere: webview.Window) -> None:
        try:
            pencere.run_js(ILAN_DUGMESI)
        except Exception as e:  # noqa: BLE001 - sayfa erken kapandı vb.
            print(f"[ilan] düğme eklenemedi: {e}", flush=True)

    def ilan_eklendi(self, kayit: dict) -> None:
        if self._pencere is not None:
            self._pencere.run_js(f"window.ilanEklendi && window.ilanEklendi({json.dumps(kayit['baslik'])})")

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
    simge = PAKET / "simge.ico"
    # private_mode=False + storage_path: ilan sitelerindeki oturumlar (çerezler) kalıcı olur
    from app.cv import ayarlar  # noqa: PLC0415

    tarayici = ayarlar.klasor() / "tarayici"
    tarayici.mkdir(parents=True, exist_ok=True)
    webview.start(icon=str(simge) if simge.exists() else None, private_mode=False,
                  storage_path=str(tarayici))
    sunucu.should_exit = True


if __name__ == "__main__":
    main()
