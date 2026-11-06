"""Türkçe metin ön işleme: küçük harf, kesme işareti, durak kelimeler, kök bulma.

Türkçe eklemeli bir dildir: "iade", "iadesi", "iadelerde", "iadenizin" aynı kelimedir ama
kelime eşleşmesine dayalı arama (BM25) bunları farklı sayar. Üç yöntem karşılaştırılır:

  ham  : sadece küçük harf (Türkçe kurallı) ve noktalama temizliği
  kok  : Snowball Türkçe kök bulucusu (sözlüksüz, ek kurallarıyla)
  on5  : kelimenin ilk 5 harfi. Türkçe bilgi erişimi literatüründe basit ama güçlü bir
         temel çizgi olarak bilinir (kökler çoğunlukla ilk harflerde durur).
"""

from __future__ import annotations

import re
from functools import lru_cache

from ..veritabani.sorgu import tr_lower

# Kesme işaretinden sonrası özel isme gelen ektir: "Çarşı'dan" -> "çarşı", "KVKK'nın" -> "kvkk"
_KESME = re.compile(r"['’`][a-zçğıöşü]+")
_KELIME = re.compile(r"[a-zçğıöşüâîû0-9]+")

DURAK = frozenset("""
acaba ama ancak artık aslında az bana bazı belki ben beni benim bile bir biraz birkaç biz bize
bizim bu buna bunda bundan bunu bunun burada çok çünkü da daha de defa diye en gibi hangi hangisi
hem hep hepsi her hiç için ile ise kaç kadar ki kim kimse mı mi mu mü nasıl ne neden nerede
nereye niçin niye o olan olarak oldu olduğu olur ona ondan onlar onu onun öyle sadece sanki
şey şu şuna şunu siz size sizin ve veya ya yani yoksa zaten mısınız misiniz mıyım miyim
""".split())


def kelimeler(metin: str) -> list[str]:
    """Türkçe kurallı küçük harf + kesme eki temizliği + durak kelime çıkarma."""
    metin = _KESME.sub("", tr_lower(metin))
    return [k for k in _KELIME.findall(metin) if k not in DURAK]


@lru_cache(maxsize=1)
def _kokbulucu():
    import snowballstemmer

    return snowballstemmer.stemmer("turkish")


@lru_cache(maxsize=50_000)
def _kok(kelime: str) -> str:
    return _kokbulucu().stemWord(kelime)


def isle(metin: str, yontem: str = "kok") -> list[str]:
    """Metni BM25 için terimlere çevirir. yontem: ham | kok | on5"""
    k = kelimeler(metin)
    if yontem == "ham":
        return k
    if yontem == "kok":
        return [_kok(w) for w in k]
    if yontem == "on5":
        return [w[:5] for w in k]
    raise ValueError(f"Bilinmeyen yöntem: {yontem}")
