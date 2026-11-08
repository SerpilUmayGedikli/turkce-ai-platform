"""İş ilanı siteleri ve kullanıcının kaydettiği ilanlar.

Siteler kullanıcının KENDİ oturumuyla açılır: uygulama hiçbir siteye kendisi giriş yapmaz, şifre
saklamaz, ilan toplamak için site taramaz (LinkedIn, Indeed, Kariyer.net gibi siteler bunu kullanım
koşullarıyla yasaklar ve bot korumasıyla engeller). Masaüstü uygulamasında her site ayrı bir
pencerede açılır, çerezler saklandığı için bir kez giriş yapmak yeter. Kullanıcı beğendiği ilanda
"CV Uyarlayıcı'ya ekle" düğmesine basınca ilan metni buraya kaydedilir ve CV'ye uyumuna göre
sıralanır.

Veriler bu bilgisayarda: %APPDATA%\\CVUyarlayici\\ilanlar.json ve platformlar.json
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote, quote_plus, urlparse

from . import ayarlar

# arama: {q} anahtar kelime, {l} konum (URL'ye kodlanmış), {slug} tireli küçük harf
SITELER: list[dict[str, Any]] = [
    {"id": "kariyernet", "ad": "Kariyer.net", "bolge": "Türkiye", "renk": "#7B2CBF",
     "giris": "https://www.kariyer.net/giris", "arama": "https://www.kariyer.net/is-ilanlari?kw={q}"},
    {"id": "linkedin", "ad": "LinkedIn", "bolge": "Global", "renk": "#0A66C2",
     "giris": "https://www.linkedin.com/login",
     "arama": "https://www.linkedin.com/jobs/search/?keywords={q}&location={l}"},
    {"id": "indeed", "ad": "Indeed", "bolge": "Türkiye", "renk": "#2557A7",
     "giris": "https://secure.indeed.com/auth", "arama": "https://tr.indeed.com/jobs?q={q}&l={l}"},
    {"id": "yenibiris", "ad": "Yenibiris", "bolge": "Türkiye", "renk": "#E4002B",
     "giris": "https://www.yenibiris.com/giris", "arama": "https://www.yenibiris.com/is-ilanlari?q={q}"},
    {"id": "secretcv", "ad": "Secretcv", "bolge": "Türkiye", "renk": "#F15A24",
     "giris": "https://www.secretcv.com/uye-girisi", "arama": "https://www.secretcv.com/is-ilanlari"},
    {"id": "elemannet", "ad": "Eleman.net", "bolge": "Türkiye", "renk": "#00A651",
     "giris": "https://www.eleman.net/giris", "arama": "https://www.eleman.net/is-ilanlari"},
    {"id": "glassdoor", "ad": "Glassdoor", "bolge": "Global", "renk": "#0CAA41",
     "giris": "https://www.glassdoor.com/profile/login_input.htm",
     "arama": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q}"},
    {"id": "techcareer", "ad": "Techcareer.net", "bolge": "Türkiye · teknoloji", "renk": "#5B2EFF",
     "giris": "https://www.techcareer.net/login", "arama": "https://www.techcareer.net/jobs"},
    {"id": "coderspace", "ad": "Coderspace", "bolge": "Türkiye · yazılım", "renk": "#1E1E2D",
     "giris": "https://coderspace.io/giris", "arama": "https://coderspace.io/is-ilanlari"},
    {"id": "youthall", "ad": "Youthall", "bolge": "Türkiye · genç yetenek", "renk": "#FF4D4D",
     "giris": "https://www.youthall.com/tr/login", "arama": "https://www.youthall.com/tr/jobs"},
    {"id": "toptalent", "ad": "Toptalent", "bolge": "Türkiye · genç yetenek", "renk": "#14213D",
     "giris": "https://toptalent.co/giris", "arama": "https://toptalent.co/is-ilanlari"},
    {"id": "anbean", "ad": "Anbean Kampüs", "bolge": "Türkiye · staj/yeni mezun", "renk": "#E85D04",
     "giris": "https://anbeankampus.co/giris", "arama": "https://anbeankampus.co/ilanlar"},
    {"id": "kariyerkapisi", "ad": "Kariyer Kapısı", "bolge": "Türkiye · kamu", "renk": "#C1121F",
     "giris": "https://kariyerkapisi.cbiko.gov.tr", "arama": "https://kariyerkapisi.cbiko.gov.tr/ilanlar"},
    {"id": "iskur", "ad": "İŞKUR", "bolge": "Türkiye · kamu", "renk": "#003F88",
     "giris": "https://esube.iskur.gov.tr", "arama": "https://esube.iskur.gov.tr/Istihdam/AramaKriter.aspx"},
    {"id": "jooble", "ad": "Jooble", "bolge": "Türkiye · toplayıcı", "renk": "#2D8CFF",
     "giris": "https://tr.jooble.org", "arama": "https://tr.jooble.org/SearchResult?ukw={q}&rgns={l}"},
    {"id": "wellfound", "ad": "Wellfound", "bolge": "Global · startup", "renk": "#111111",
     "giris": "https://wellfound.com/login", "arama": "https://wellfound.com/jobs"},
    {"id": "remoteok", "ad": "Remote OK", "bolge": "Global · uzaktan", "renk": "#FF4742",
     "giris": "https://remoteok.com", "arama": "https://remoteok.com/remote-{slug}-jobs"},
    {"id": "wwr", "ad": "We Work Remotely", "bolge": "Global · uzaktan", "renk": "#2E3192",
     "giris": "https://weworkremotely.com", "arama": "https://weworkremotely.com/remote-jobs/search?term={q}"},
]
VARSAYILAN_SECILI = ["kariyernet", "linkedin", "indeed", "yenibiris", "secretcv", "elemannet"]
MAKS_ILAN = 500

_kilit = threading.Lock()


def _dosya(ad: str):
    return ayarlar.klasor() / ad


def _oku(ad: str, varsayilan: Any) -> Any:
    try:
        return json.loads(_dosya(ad).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return varsayilan


def _yaz(ad: str, veri: Any) -> None:
    gecici = _dosya(ad + ".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    gecici.replace(_dosya(ad))


def _slug(metin: str) -> str:
    tablo = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return "-".join("".join(c if c.isalnum() else " " for c in metin.translate(tablo).lower()).split())


def arama_adresi(site: dict[str, Any], q: str = "", konum: str = "") -> str:
    """Sitenin arama sayfası; arama şablonu anahtar kelime almıyorsa ilan listesi açılır."""
    sablon = site.get("arama") or site.get("giris") or ""
    if not q.strip() and "{" in sablon:  # anahtar kelime yoksa sitenin ana ilan sayfası
        u = urlparse(sablon.split("?")[0].replace("{slug}", "").replace("remote--jobs", "remote-jobs"))
        return f"{u.scheme}://{u.netloc}{u.path}"
    return (sablon.replace("{q}", quote_plus(q.strip())).replace("{l}", quote_plus(konum.strip()))
            .replace("{slug}", quote(_slug(q))))


# ---------------------------------------------------------------- platform tercihleri
def platformlar() -> dict[str, Any]:
    tercih = _oku("platformlar.json", {})
    secili = set(tercih.get("secili", VARSAYILAN_SECILI))
    ozel = tercih.get("ozel", [])
    arama = tercih.get("arama", {"q": "", "konum": ""})
    siteler = [{**s, "ozel": False} for s in SITELER] + [{**s, "ozel": True} for s in ozel]
    bugun_girilen = set(tercih.get("ziyaretler", {}).get(_bugun(), []))
    for s in siteler:
        s["secili"] = s["id"] in secili
        s["adres"] = arama_adresi(s, arama.get("q", ""), arama.get("konum", ""))
        s["anahtar_kelime_alir"] = "{q}" in (s.get("arama") or "") or "{slug}" in (s.get("arama") or "")
        s["bugun_girildi"] = s["id"] in bugun_girilen
    return {"siteler": siteler, "arama": arama, **_gunluk_ozet(tercih.get("ziyaretler", {}), secili)}


# ---------------------------------------------------------------- günlük tur ("bugün buraya girdim")
def _bugun() -> str:
    return date.today().isoformat()


def _gunluk_ozet(ziyaretler: dict[str, list[str]], secili: set[str]) -> dict[str, Any]:
    """Bugünün tarihi, son 7 gün ve seri: art arda kaç gün en az bir siteye girildi.
    Bugün henüz girilmediyse seri dünden sayılır (gün bitmeden kırılmış sayılmaz)."""
    gun = date.today()
    if not ziyaretler.get(gun.isoformat()):
        gun -= timedelta(days=1)
    seri = 0
    while ziyaretler.get(gun.isoformat()):
        seri += 1
        gun -= timedelta(days=1)
    son7 = [{"tarih": (date.today() - timedelta(days=i)).isoformat(),
             "sayi": len(ziyaretler.get((date.today() - timedelta(days=i)).isoformat(), []))}
            for i in range(6, -1, -1)]
    return {"bugun": _bugun(), "seri": seri, "son7": son7,
            "bugun_tamam": bool(secili) and secili <= set(ziyaretler.get(_bugun(), []))}


def ziyaret_isaretle(kimlik: str, girdim: bool = True) -> dict[str, Any]:
    """Bugün bu siteye girildi/girilmedi. Ertesi gün liste kendiliğinden boş başlar."""
    with _kilit:
        tercih = _oku("platformlar.json", {})
        ziyaretler = tercih.setdefault("ziyaretler", {})
        bugun = set(ziyaretler.get(_bugun(), []))
        bugun.add(kimlik) if girdim else bugun.discard(kimlik)
        ziyaretler[_bugun()] = sorted(bugun)
        sinir = (date.today() - timedelta(days=120)).isoformat()  # eski günleri tutma
        tercih["ziyaretler"] = {g: v for g, v in ziyaretler.items() if g >= sinir and v}
        _yaz("platformlar.json", tercih)
    return platformlar()


def platformlari_kaydet(secili: list[str] | None = None, arama: dict[str, str] | None = None,
                        ozel_ekle: dict[str, str] | None = None, ozel_sil: str | None = None) -> dict:
    with _kilit:
        tercih = _oku("platformlar.json", {})
        if secili is not None:
            tercih["secili"] = list(dict.fromkeys(secili))
        if arama is not None:
            tercih["arama"] = {"q": arama.get("q", "")[:120], "konum": arama.get("konum", "")[:80]}
        ozel = tercih.setdefault("ozel", [])
        if ozel_ekle:
            adres = ozel_ekle["adres"].strip()
            ad = ozel_ekle.get("ad", "").strip() or urlparse(adres).netloc
            kimlik = "ozel-" + hashlib.sha1(adres.encode()).hexdigest()[:8]
            if not any(s["id"] == kimlik for s in ozel):
                ozel.append({"id": kimlik, "ad": ad[:40], "bolge": "Eklediğin site", "renk": "#5D6785",
                             "giris": adres, "arama": adres})
                tercih.setdefault("secili", VARSAYILAN_SECILI)
                tercih["secili"].append(kimlik)
        if ozel_sil:
            tercih["ozel"] = [s for s in ozel if s["id"] != ozel_sil]
        _yaz("platformlar.json", tercih)
    return platformlar()


# ---------------------------------------------------------------- kaydedilen ilanlar
def ilanlar() -> list[dict[str, Any]]:
    return _oku("ilanlar.json", [])


def _site_bul(url: str) -> str:
    alan = urlparse(url).netloc.lower().removeprefix("www.")
    for s in SITELER:
        if urlparse(s["giris"]).netloc.lower().removeprefix("www.").split(".")[-2:] == alan.split(".")[-2:]:
            return s["ad"]
    return alan or "Elle eklendi"


def ilan_ekle(metin: str, baslik: str = "", url: str = "", site: str = "", sirket: str = "") -> dict:
    metin = (metin or "").strip()
    if len(metin) < 40:
        raise ValueError("İlan metni çok kısa. İlan sayfasındayken ekle ya da açıklamayı seçip ekle.")
    baslik = " ".join((baslik or "").split())[:160] or metin.splitlines()[0][:120]
    kimlik = hashlib.sha1((url or metin[:500]).encode()).hexdigest()[:12]
    kayit = {"id": kimlik, "baslik": baslik, "sirket": sirket[:120], "url": url[:1000],
             "site": site or _site_bul(url), "metin": metin[:30000],
             "eklendi": datetime.now().isoformat(timespec="seconds"), "durum": "yeni"}
    with _kilit:
        liste = [i for i in ilanlar() if i["id"] != kimlik]  # aynı ilan tekrar eklenirse güncellenir
        liste.insert(0, kayit)
        _yaz("ilanlar.json", liste[:MAKS_ILAN])
    return kayit


def ilan_guncelle(kimlik: str, durum: str) -> None:
    with _kilit:
        liste = ilanlar()
        for i in liste:
            if i["id"] == kimlik:
                i["durum"] = durum
        _yaz("ilanlar.json", liste)


def ilan_sil(kimlik: str) -> None:
    with _kilit:
        _yaz("ilanlar.json", [i for i in ilanlar() if i["id"] != kimlik])


# Aynı CV + ilan için skor tekrar hesaplanmasın (embedding pahalı)
_skor_onbellek: dict[str, dict[str, Any]] = {}


def sirala(cv: str, gomucu=None) -> list[dict[str, Any]]:
    """Kaydedilen ilanları CV'ye uyuma göre sıralar (CV yoksa eklenme tarihine göre)."""
    from .eslestirme import analiz_et  # noqa: PLC0415

    liste = ilanlar()
    cv = (cv or "").strip()
    cv_ozet = hashlib.sha1(cv.encode()).hexdigest()[:12]
    for i in liste:
        i.pop("metin_kisa", None)
        i["onizleme"] = " ".join(i["metin"].split())[:220]
        if len(cv) < 20:
            i["skor"] = None
            continue
        anahtar = f"{cv_ozet}:{i['id']}:{hashlib.sha1(i['metin'].encode()).hexdigest()[:8]}"
        if anahtar not in _skor_onbellek:
            a = analiz_et(cv, i["metin"], gomucu)
            _skor_onbellek[anahtar] = {
                "skor": a.skor, "ats": a.ats_kapsama,
                "eksik": [k.ifade for k in a.anahtarlar if not k.var][:6],
                "karsilanan": sum(g.durum == "karşılanıyor" for g in a.gereksinimler),
                "gereksinim": len(a.gereksinimler), "zaman": time.time()}
        i.update(_skor_onbellek[anahtar])
    liste.sort(key=lambda i: (i.get("skor") is None, -(i.get("skor") or 0), i["eklendi"]), reverse=False)
    if len(cv) < 20:
        liste.sort(key=lambda i: i["eklendi"], reverse=True)
    return [{k: v for k, v in i.items() if k != "metin"} | {"metin_uzunluk": len(i["metin"])}
            for i in liste]


def ilan_metni(kimlik: str) -> dict[str, Any] | None:
    return next((i for i in ilanlar() if i["id"] == kimlik), None)
