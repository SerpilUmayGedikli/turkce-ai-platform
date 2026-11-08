"""CV dosyasını düz metne çevirir (PDF, DOCX, TXT/MD) ve başlık bilgisini (ad, iletişim) ayırır.

Başlık bilgisi modele hiç gönderilmez: uyarlanmış CV'nin başına yerelde geri konur.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..kvkk.tespit import bul

_URL = re.compile(r"(?:https?://|www\.)\S+|(?:linkedin\.com|github\.com)/\S+", re.I)


def metne_cevir(veri: bytes, ad: str) -> str:
    """Dosya içeriğini (bytes) uzantısına göre metne çevirir."""
    uzanti = Path(ad).suffix.lower()
    if uzanti == ".pdf":
        from pypdf import PdfReader

        sayfalar = PdfReader(io.BytesIO(veri)).pages
        metin = "\n".join((s.extract_text() or "") for s in sayfalar)
    elif uzanti == ".docx":
        import docx

        belge = docx.Document(io.BytesIO(veri))
        satirlar = [p.text for p in belge.paragraphs]
        for tablo in belge.tables:  # birçok CV şablonu iki sütunlu tablo kullanır
            for satir in tablo.rows:
                satirlar += [h.text for h in satir.cells]
        metin = "\n".join(satirlar)
    elif uzanti in (".txt", ".md", ""):
        metin = veri.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Desteklenmeyen dosya türü: {uzanti} (PDF, DOCX veya TXT yükleyin)")
    return temizle(metin)


def dosyadan(yol: str | Path) -> str:
    yol = Path(yol)
    return metne_cevir(yol.read_bytes(), yol.name)


def temizle(metin: str) -> str:
    metin = metin.replace("\r", "").replace(" ", " ").replace("\t", " ")
    metin = re.sub(r"[ ]{2,}", " ", metin)
    metin = re.sub(r"\n{3,}", "\n\n", metin)
    return metin.strip()


@dataclass
class Baslik:
    ad: str = ""
    iletisim: list[str] = field(default_factory=list)  # e-posta, telefon, bağlantılar


def baslik_cikar(metin: str, ad: str | None = None) -> Baslik:
    """Ad: kullanıcı vermediyse ilk dolu satır. İletişim: KVKK tespitçisinin bulduğu
    e-posta/telefon + bağlantılar."""
    if not ad:
        ilk = next((s.strip() for s in metin.splitlines() if s.strip()), "")
        # İlk satır bir cümle değil, 2-4 kelimelik bir isim gibi görünmeli
        if 1 < len(ilk.split()) <= 4 and not any(ch.isdigit() for ch in ilk) and "@" not in ilk:
            ad = ilk
    iletisim = [b.metin for b in bul(metin) if b.tur in ("EPOSTA", "TELEFON")]
    iletisim += [m.group().rstrip(".,;)") for m in _URL.finditer(metin)]
    tekil = list(dict.fromkeys(iletisim))
    return Baslik(ad=ad or "", iletisim=tekil)
