"""Anlamsal arama için embedding (vektör) üretimi.

fastembed kullanılır: PyTorch gerektirmez, ONNX ile CPU'da çalışır (GPU'suz 16 GB RAM yeter).
Model ilk kullanımda Hugging Face'ten bir kez indirilir (~220 MB). Belge vektörleri diske
önbelleklenir; belge değişmedikçe yeniden hesaplanmaz.
"""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path
from typing import Callable

import numpy as np

VARSAYILAN_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# Masaüstü uygulaması (PyInstaller) paket klasörü geçici olduğu için ONBELLEK_DIZINI ile
# kalıcı bir kullanıcı klasörüne yönlendirilir; aksi halde model her açılışta yeniden iner.
# Kullanım anında okunur (import anında değil): masaüstü uygulaması değişkeni sonradan ayarlar.
def onbellek() -> Path:
    return Path(os.getenv("ONBELLEK_DIZINI") or
                Path(__file__).resolve().parents[2] / "data" / "rag_onbellek")

Gomucu = Callable[[list[str]], np.ndarray]  # metinler -> (n, boyut) birim vektörler


def _birimle(m: np.ndarray) -> np.ndarray:
    return m / np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-12, None)


@lru_cache(maxsize=2)
def fastembed_gomucu(model: str = VARSAYILAN_MODEL) -> Gomucu:
    from fastembed import TextEmbedding

    motor = TextEmbedding(model_name=model, cache_dir=str(onbellek() / "modeller"))
    return lambda metinler: _birimle(np.array(list(motor.embed(metinler)), dtype=np.float32))


def onbellekli(gomucu: Gomucu, metinler: list[str], ad: str) -> np.ndarray:
    """Belge vektörlerini metinlerin özetiyle (hash) diske kaydeder."""
    ozet = hashlib.sha256("\n".join(metinler).encode()).hexdigest()[:16]
    yol = onbellek() / f"{ad.replace('/', '_')}-{ozet}.npy"
    if yol.exists():
        return np.load(yol)
    vektorler = gomucu(metinler)
    onbellek().mkdir(parents=True, exist_ok=True)
    np.save(yol, vektorler)
    return vektorler
