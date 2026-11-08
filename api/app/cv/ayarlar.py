"""Uygulama ayarları: model bağlantısı (gateway adresi ya da Gemini anahtarı).

Kullanıcının bilgisayarında saklanır (Windows: %APPDATA%\\CVUyarlayici\\ayarlar.json); hiçbir yere
gönderilmez. Anahtar API cevaplarında asla tam haliyle dönmez, yalnızca "tanımlı mı" bilgisi döner.
Ortam değişkeni ya da .env ile verilen değerler dosyadakinden önce gelir.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ALANLAR = ("LLM_BASE_URL", "LITELLM_MASTER_KEY", "GEMINI_API_KEY", "CV_MODEL")


def klasor() -> Path:
    kok = os.getenv("APPDATA") or os.path.expanduser("~/.config")
    yol = Path(kok) / "CVUyarlayici"
    yol.mkdir(parents=True, exist_ok=True)
    return yol


def _dosya() -> Path:
    return klasor() / "ayarlar.json"


def oku() -> dict[str, str]:
    try:
        return json.loads(_dosya().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


_DISARIDAN = {k for k in ALANLAR if os.getenv(k)}  # süreç başlarken ortamda olanlar


def uygula() -> None:
    """Dosyadaki ayarları ortam değişkenlerine yükler (ortamda zaten olanlara dokunmaz)."""
    for k, v in oku().items():
        if k in ALANLAR and k not in _DISARIDAN:
            if v:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def kaydet(yeni: dict[str, str | None]) -> None:
    """None gelen alan değiştirilmez, boş metin gelen alan silinir."""
    mevcut = oku()
    for k, v in yeni.items():
        if k in ALANLAR and v is not None:
            mevcut[k] = v.strip()
    _dosya().write_text(json.dumps(mevcut, ensure_ascii=False, indent=2), encoding="utf-8")
    uygula()


def env_dosyasi_yukle(yol: Path) -> None:
    """Geliştirme kolaylığı: proje kökündeki .env varsa ilgili alanları okur."""
    if not yol.exists():
        return
    for satir in yol.read_text(encoding="utf-8").splitlines():
        if "=" in satir and not satir.lstrip().startswith("#"):
            k, v = satir.split("=", 1)
            k, v = k.strip(), v.strip()
            if k in ALANLAR and v and not os.getenv(k):
                os.environ[k] = v
                _DISARIDAN.add(k)


def ozet() -> dict[str, object]:
    url = os.getenv("LLM_BASE_URL", "")
    return {
        "baglanti": "gateway" if url else ("gemini" if os.getenv("GEMINI_API_KEY") else "yok"),
        "llm_base_url": url,
        "gemini_anahtari_var": bool(os.getenv("GEMINI_API_KEY")),
        "disaridan": sorted(_DISARIDAN),  # .env/ortamdan gelenler arayüzden değiştirilemez
    }
