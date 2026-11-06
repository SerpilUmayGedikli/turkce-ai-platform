"""Agent'ın kullanabileceği araçlar.

Yeni araç eklemek için: bir fonksiyon yaz, @arac ile işaretle. Bu kadar.
Model, açıklama ve parametre şemasına bakarak aracı ne zaman çağıracağına karar verir.
"""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo


@dataclass
class Arac:
    ad: str
    aciklama: str
    parametreler: dict[str, Any]  # JSON Schema
    fonksiyon: Callable[..., str]

    def openai_semasi(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.ad,
                "description": self.aciklama,
                "parameters": self.parametreler,
            },
        }


KAYIT: dict[str, Arac] = {}


def arac(ad: str, aciklama: str, parametreler: dict[str, Any]):
    def sar(fn: Callable[..., str]) -> Callable[..., str]:
        KAYIT[ad] = Arac(ad, aciklama, parametreler, fn)
        return fn

    return sar


# ---------------------------------------------------------------- hesap makinesi
_OPERATORLER = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _guvenli_hesapla(dugum: ast.AST) -> float:
    # eval() kullanmıyoruz: modelin ürettiği metni çalıştırmak güvenlik açığıdır.
    if isinstance(dugum, ast.Expression):
        return _guvenli_hesapla(dugum.body)
    if isinstance(dugum, ast.Constant) and isinstance(dugum.value, (int, float)):
        return dugum.value
    if isinstance(dugum, ast.BinOp) and type(dugum.op) in _OPERATORLER:
        sol, sag = _guvenli_hesapla(dugum.left), _guvenli_hesapla(dugum.right)
        if isinstance(dugum.op, ast.Pow) and abs(sag) > 100:
            raise ValueError("Üs çok büyük")
        return _OPERATORLER[type(dugum.op)](sol, sag)
    if isinstance(dugum, ast.UnaryOp) and type(dugum.op) in _OPERATORLER:
        return _OPERATORLER[type(dugum.op)](_guvenli_hesapla(dugum.operand))
    raise ValueError("Sadece sayılar ve + - * / // % ** kullanılabilir")


@arac(
    "hesap_makinesi",
    "Matematiksel bir ifadeyi kesin olarak hesaplar. Sayısal işlemlerde tahmin etme, bunu kullan.",
    {
        "type": "object",
        "properties": {
            "ifade": {"type": "string", "description": "Örn: (1250 * 0.18) + 40"}
        },
        "required": ["ifade"],
    },
)
def hesap_makinesi(ifade: str) -> str:
    ifade = ifade.replace(",", ".").replace("×", "*").replace("÷", "/")
    sonuc = _guvenli_hesapla(ast.parse(ifade, mode="eval"))
    return str(round(sonuc, 10))


# ---------------------------------------------------------------- tarih / saat
@arac(
    "simdiki_zaman",
    "Türkiye saatine göre bugünün tarihini, gününü ve saatini verir.",
    {"type": "object", "properties": {}},
)
def simdiki_zaman() -> str:
    gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    simdi = datetime.now(ZoneInfo("Europe/Istanbul"))
    return f"{simdi:%d.%m.%Y %H:%M}, {gunler[simdi.weekday()]}"


# ---------------------------------------------------------------- kimlik doğrulama
@arac(
    "tckn_dogrula",
    "Bir TC kimlik numarasının algoritmik olarak geçerli olup olmadığını kontrol eder. "
    "Numara gizlenmişse etiketi ([TCKN_1] gibi) aynen ver.",
    {
        "type": "object",
        "properties": {"tckn": {"type": "string"}},
        "required": ["tckn"],
    },
)
def tckn_dogrula(tckn: str) -> str:
    from .kvkk.tespit import tckn_gecerli

    temiz = "".join(c for c in tckn if c.isdigit())
    return "geçerli" if tckn_gecerli(temiz) else "geçersiz"


# ---------------------------------------------------------------- veritabanı (Text-to-SQL)
from .veritabani.sorgu import SEMA_ACIKLAMASI, sorgula, tablo_metni  # noqa: E402


@arac(
    "sql_calistir",
    "Mağaza veritabanında salt okunur bir SQL SELECT sorgusu çalıştırır ve sonucu tablo olarak döner. "
    "Satış, ürün, müşteri, sipariş sorularında kullan; sayıları asla tahmin etme. Hata alırsan "
    "hata mesajına göre sorguyu düzeltip tekrar dene.\n\n" + SEMA_ACIKLAMASI,
    {
        "type": "object",
        "properties": {"sorgu": {"type": "string", "description": "Tek bir SQLite SELECT sorgusu"}},
        "required": ["sorgu"],
    },
)
def sql_calistir(sorgu: str) -> str:
    return tablo_metni(*sorgula(sorgu))


# ---------------------------------------------------------------- belge arama (RAG)
@arac(
    "belge_ara",
    "Mağazanın politika belgelerinde (iade, değişim, kargo, iptal, ödeme, taksit, fatura, garanti, "
    "KVKK, üyelik, kupon, puan, müşteri hizmetleri) arama yapar ve en ilgili 3 bölümü kaynağıyla "
    "döner. Kural/süre/ücret sorularında kullan; cevabı yalnızca dönen metne dayandır ve kaynağı belirt. "
    "Metinde cevap yoksa bilmediğini söyle.",
    {
        "type": "object",
        "properties": {"sorgu": {"type": "string", "description": "Türkçe arama ifadesi, örn: iade kargo ücreti"}},
        "required": ["sorgu"],
    },
)
def belge_ara(sorgu: str) -> str:
    from .rag import varsayilan

    return "\n\n".join(f"[{p.belge} › {p.baslik}]\n{p.metin}" for p in varsayilan().ara(sorgu, 3))


def calistir(ad: str, argumanlar: dict[str, Any]) -> str:
    """Aracı çalıştırır. Hata olursa modeli düzeltebilmesi için hatayı metin olarak döner."""
    if ad not in KAYIT:
        return f"HATA: '{ad}' adında bir araç yok."
    try:
        return KAYIT[ad].fonksiyon(**argumanlar)
    except Exception as e:  # modele geri bildirim: kendini düzeltebilsin
        return f"HATA: {type(e).__name__}: {e}"


def semalar() -> list[dict[str, Any]]:
    return [a.openai_semasi() for a in KAYIT.values()]
