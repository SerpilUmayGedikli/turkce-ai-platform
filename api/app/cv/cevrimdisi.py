"""Çevrimdışı uyarlama motoru: API anahtarı ve internet olmadan çalışır.

Dil modeli yerine yerel kurallar ve yerel ML kullanır (çok dilli embedding, ATS anahtar kelime
çıkarımı, beceri sözlüğü):
  1. CV'yi bölümlere ayırır (özet, deneyim, eğitim, beceriler, projeler, diğer).
  2. Deneyim maddelerini ilana yakınlığına göre sıralar; ilanla hiç ilgisi olmayanları çıkarır.
     Maddelerin metnine dokunmaz: uydurma riski yoktur.
  3. Becerileri kategorili satırlara dizer, ilanla eşleşenleri öne alır, dolaylı becerileri
     (scikit-learn -> Makine Öğrenmesi) adıyla yazar.
  4. Özet ve unvanı şablonla, ilanın terimleriyle yazar.
  5. Ek bilgilerdeki projeleri ekler ("GitHub'a koy" görevi), hedef modunda eksik becerileri
     proje kataloğundan seçilen projelerle kapatır ("yap ve GitHub'a koy" görevi).
  6. Sayı içermeyen önemli maddeler için güçlendirme soruları üretir.
Dil modeli kadar akıcı yazmaz ve çeviri yapamaz; çıktı UyarlanmisCV ile aynı biçimdedir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..rag.vektor import Gomucu
from ..veritabani.sorgu import tr_katla, tr_lower
from . import beceriler
from .eslestirme import Analiz, _kelime_ortusmesi, _terimler
from .okuyucu import baslik_cikar
from .proje_katalogu import GENEL, KATALOG, SEKTORLER
from .yazici import UyarlanmisCV

MOTOR_ADI = "çevrimdışı motor (yerel kurallar + yerel ML)"
MAKS_YENI_PROJE = 3
ILGISIZ_ESIK = 0.12  # bu yakınlığın altındaki deneyim maddesi ilanla ilgisiz sayılır

BOLUMLER = {
    "ozet": r"özet|hakkımda|profil|kariyer hedefi|summary|profile|about me|objective",
    "deneyim": r"(?:iş )?deneyim(?:ler)?|tecrübe|iş geçmişi|(?:work |professional )?experience|employment",
    "egitim": r"eğitim(?: bilgileri)?|education",
    "beceri": r"beceriler|yetenekler|yetkinlikler|teknik beceriler|(?:technical )?skills",
    "proje": r"projeler|(?:kişisel )?projects?",
}
_MADDE = re.compile(r"^\s*(?:[-•*·▪●◦–]|\d+[.)])\s*")
_TARIH = re.compile(
    r"\(?\s*((?:[A-Za-zÇĞİÖŞÜçğıöşü]+\.?\s*)?\d{4}\s*[-–—]\s*(?:(?:[A-Za-zÇĞİÖŞÜçğıöşü]+\.?\s*)?\d{4}|"
    r"günümüz|halen|devam ediyor|present|current|now)|\d{4})\s*\)?", re.I)
_EN_IPUCU = re.compile(r"\b(?:the|and|with|experience|years|we are|you will|requirements)\b", re.I)

KATEGORILER = [
    ("Programlama", "Programming", {"Python", "Java", "JavaScript", "TypeScript", "C#", "C++", "Go", "Rust",
                                     "Kotlin", "Swift", "PHP", "R", "MATLAB", "SQL", "Bash"}),
    ("Makine Öğrenmesi ve Yapay Zeka", "Machine Learning & AI",
     {"Makine Öğrenmesi", "Derin Öğrenme", "Doğal Dil İşleme", "Bilgisayarlı Görü", "Büyük Dil Modelleri",
      "RAG", "Prompt Mühendisliği", "Yapay Zeka", "scikit-learn", "TensorFlow", "PyTorch", "Keras",
      "Hugging Face", "LangChain", "LangGraph", "MLOps", "MLflow"}),
    ("Veri", "Data", {"Veri Analizi", "Veri Bilimi", "Veri Mühendisliği", "İstatistik", "Veri Görselleştirme",
                      "ETL", "Pandas", "NumPy", "Spark", "Hadoop", "Kafka", "Airflow", "dbt", "Power BI",
                      "Tableau", "Excel", "Looker", "A/B Testi", "PostgreSQL", "MySQL", "MongoDB", "Redis",
                      "Elasticsearch", "Oracle", "SQL Server", "Vektör Veritabanı", "BigQuery", "Snowflake"}),
    ("Yazılım ve Web", "Software & Web",
     {"React", "Vue", "Angular", "Node.js", "Next.js", "HTML/CSS", "Django", "Flask", "FastAPI", "Spring",
      ".NET", "REST API", "GraphQL", "Mikroservis", "Nesne Yönelimli Programlama", "Tasarım Desenleri",
      "Birim Testi"}),
    ("Bulut ve Araçlar", "Cloud & Tools", {"Git", "AWS", "Azure", "Google Cloud", "Docker", "Kubernetes",
                                           "Terraform", "CI/CD", "Linux", "Jira", "AutoCAD", "SolidWorks",
                                           "SAP", "PLC", "Simulink"}),
    ("Yöntem ve Yetkinlikler", "Methods & Soft Skills",
     {"Agile", "Scrum", "Proje Yönetimi", "Ürün Yönetimi", "Takım Çalışması", "İletişim Becerisi",
      "Problem Çözme", "Liderlik"}),
    ("Diller", "Languages", {"İngilizce", "Almanca"}),
]


@dataclass
class Ayristirilmis:
    ust: list[str] = field(default_factory=list)  # ad, unvan, iletişim satırları
    ozet: list[str] = field(default_factory=list)
    deneyim: list[dict[str, Any]] = field(default_factory=list)
    egitim: list[dict[str, Any]] = field(default_factory=list)
    beceri: list[str] = field(default_factory=list)
    proje: list[str] = field(default_factory=list)
    diger: list[dict[str, Any]] = field(default_factory=list)


def _bolum_mu(satir: str) -> str | None:
    temiz = tr_lower(satir.strip().rstrip(":")).strip()
    if not temiz or len(temiz.split()) > 4:
        return None
    for ad, desen in BOLUMLER.items():
        if re.fullmatch(desen, temiz):
            return ad
    # Bilinmeyen ama başlık görünümlü satır (TAMAMI BÜYÜK, kısa): "diğer" bölümü
    if satir.strip().rstrip(":").isupper() and len(temiz) > 2:
        return "diger:" + satir.strip().rstrip(":").title()
    return None


def _deneyim_basligi(satir: str) -> dict[str, Any]:
    tarih = ""
    m = _TARIH.search(satir)
    if m:
        tarih = m.group(1).strip()
        satir = (satir[: m.start()] + satir[m.end():]).strip(" ,|-–—")
    parcalar = [p.strip() for p in re.split(r"\s+[-–—|@]\s+|\s*\|\s*|,\s+|\s+at\s+", satir) if p.strip()]
    return {"pozisyon": parcalar[0] if parcalar else satir, "sirket": " ".join(parcalar[1:2]),
            "tarih": tarih, "maddeler": []}


def ayristir(cv: str) -> Ayristirilmis:
    a = Ayristirilmis()
    bolum, diger_ad = "ust", ""
    for ham in cv.splitlines():
        satir = ham.strip()
        if not satir:
            continue
        b = _bolum_mu(satir)
        if b:
            bolum = "diger" if b.startswith("diger:") else b
            if bolum == "diger":
                diger_ad = b.split(":", 1)[1]
                a.diger.append({"baslik": diger_ad, "maddeler": []})
            continue
        madde = _MADDE.sub("", satir).strip()
        if bolum == "ust":
            a.ust.append(satir)
        elif bolum == "ozet":
            a.ozet.append(satir)
        elif bolum == "deneyim":
            if _MADDE.match(ham) and a.deneyim:
                a.deneyim[-1]["maddeler"].append(madde)
            elif a.deneyim and not a.deneyim[-1]["maddeler"] and not _TARIH.search(satir) \
                    and len(satir.split()) > 6:
                a.deneyim[-1]["maddeler"].append(satir)  # başlığın altındaki paragraf
            elif a.deneyim and a.deneyim[-1]["maddeler"] and len(satir.split()) > 8 and not _TARIH.search(satir):
                a.deneyim[-1]["maddeler"].append(satir)
            else:
                a.deneyim.append(_deneyim_basligi(satir))
        elif bolum == "egitim":
            m = _TARIH.search(satir)
            tarih = m.group(1).strip() if m else ""
            kalan = (satir[: m.start()] + satir[m.end():]) if m else satir
            parcalar = [p.strip() for p in re.split(r",|\s+[-–|]\s+", kalan) if p.strip()]
            a.egitim.append({"okul": parcalar[0] if parcalar else satir,
                             "bolum": parcalar[1] if len(parcalar) > 1 else "",
                             "tarih": tarih, "not": ", ".join(parcalar[2:])})
        elif bolum == "beceri":
            a.beceri += [p.strip(" -•") for p in re.split(r"[,;•|]|\s{2,}", madde) if p.strip(" -•")]
        elif bolum == "proje":
            a.proje.append(madde)
        elif bolum == "diger" and a.diger:
            a.diger[-1]["maddeler"].append(madde)
    return a


# ---------------------------------------------------------------- yardımcılar
def _ingilizce_mi(ilan: str) -> bool:
    return len(_EN_IPUCU.findall(ilan)) >= 3


def _slug(metin: str) -> str:
    tablo = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return "-".join(re.sub(r"[^a-z0-9]+", " ", metin.translate(tablo).lower()).split())[:40] or "proje"


def _sektor(ilan: str, cv: str, en: bool) -> str:
    for metin in (ilan, cv):
        k = tr_katla(metin)
        for kelimeler, tr, ing in SEKTORLER:
            if any(tr_katla(w) in k for w in kelimeler):
                return ing if en else tr
    return "real-world" if en else "gerçek dünya"


def _yakinlik(cumleler: list[str], analiz: Analiz, gomucu: Gomucu | None) -> np.ndarray:
    """Her cümlenin ilan gereksinimlerine en yüksek yakınlığı (0-1)."""
    gereksinim = [g.metin for g in analiz.gereksinimler] or [a.ifade for a in analiz.anahtarlar]
    if not cumleler or not gereksinim:
        return np.zeros(len(cumleler))
    kelime = np.array([[_kelime_ortusmesi(g, _terimler(c)) for g in gereksinim] for c in cumleler]).max(axis=1)
    if gomucu is None:
        return kelime
    benzerlik = (gomucu(cumleler) @ gomucu(gereksinim).T).max(axis=1)
    anlam = np.clip((benzerlik - 0.30) / (0.75 - 0.30), 0, 1)
    return 0.6 * anlam + 0.4 * kelime


def _ilan_yazimi(analiz: Analiz) -> dict[str, str]:
    """Kanonik beceri -> ilandaki yazımı (ATS birebir eşleşme için)."""
    yazim = {}
    for a in analiz.anahtarlar:
        bulunan = beceriler.bul(a.ifade)
        if len(bulunan) != 1:
            continue
        kanonik = next(iter(bulunan))
        if len(_terimler(a.ifade)) <= max(1, len(_terimler(kanonik))):
            # "scikit-learn" gibi küçük harfle yazılan beceriler büyütülmez
            yazim.setdefault(kanonik, a.ifade if kanonik[0].islower() else a.ifade[0].upper() + a.ifade[1:])
    return yazim


def _onem_sirasi(analiz: Analiz) -> dict[str, int]:
    """Kanonik beceri -> ilandaki önem sırası (ATS anahtar kelime listesindeki yeri)."""
    sira: dict[str, int] = {}
    for i, a in enumerate(analiz.anahtarlar):
        for b in beceriler.bul(a.ifade):
            sira.setdefault(b, i)
    return sira


ALAN_BECERILERI = ["Makine Öğrenmesi", "Veri Bilimi", "Yapay Zeka", "Derin Öğrenme", "Veri Mühendisliği",
                   "Doğal Dil İşleme", "Veri Analizi", "Veri Görselleştirme"]


def _liste(ogeler: list[str], en: bool) -> str:
    ogeler = list(dict.fromkeys(ogeler))
    if len(ogeler) <= 1:
        return "".join(ogeler)
    return ", ".join(ogeler[:-1]) + (" and " if en else " ve ") + ogeler[-1]


# ---------------------------------------------------------------- projeler
def _proje_sec(eksik: set[str]) -> list[tuple[dict, set[str]]]:
    """Eksik becerileri en çok kapsayan katalog projeleri (açgözlü küme örtüsü)."""
    kalan, secilen = set(eksik), []
    while kalan and len(secilen) < MAKS_YENI_PROJE:
        en_iyi = max(KATALOG, key=lambda p: len(p["beceriler"] & kalan))
        kapsanan = en_iyi["beceriler"] & kalan
        if not kapsanan:
            break
        secilen.append((en_iyi, kapsanan))
        kalan -= kapsanan
    if kalan and len(secilen) < MAKS_YENI_PROJE:  # katalogda karşılığı olmayanlar
        secilen.append((GENEL, set(sorted(kalan)[:3])))
    return secilen


def _proje_olustur(sablon: dict, kapsanan: set[str], yazim: dict[str, str], alan: str, en: bool,
                   cv_beceri: set[str]) -> tuple[dict, dict]:
    dil = "en" if en else "tr"
    # Projede kapsanan eksikler + adayın bildiği ilgili beceriler birlikte kullanılır
    kullanilan = sorted(kapsanan) + sorted((sablon.get("beceriler", set()) & cv_beceri) - kapsanan)[:2]
    adlar = [yazim.get(b, b) for b in kullanilan]
    yer = {"{B}": _liste(adlar[:4], en), "{alan}": alan}

    def doldur(metin: str, kisa: bool = False) -> str:
        for k, v in ({**yer, "{B}": _liste(adlar[:2], en)} if kisa else yer).items():
            metin = metin.replace(k, v)
        return metin[0].upper() + metin[1:] if metin else metin

    ad = doldur(sablon["ad"][dil], kisa=True)
    proje = {"ad": ad, "teknolojiler": adlar, "maddeler": [doldur(m) for m in sablon["maddeler"][dil]],
             "kaynak": "yeni", "yeni": True}
    repo = sablon["repo"].replace("{alan_slug}", _slug(alan)).replace("{beceri_slug}", _slug(" ".join(kullanilan[:2])))
    gorev = {
        "tur": "yap", "proje": ad, "kapsadigi": [yazim.get(b, b) for b in sorted(kapsanan)],
        "neden": (f"CV'nde {_liste([yazim.get(b, b) for b in sorted(kapsanan)], False)} kullandığını gösteren "
                  f"bir proje görünmüyor; bu ilan için bu projeyi ekledim."),
        "adimlar": [doldur(x) for x in sablon["adimlar"]],
        "github": {"repo": _slug(repo), "readme": sablon["readme"]}, "sure": sablon["sure"],
    }
    return proje, gorev


def _ek_projeler(ek: str) -> list[tuple[dict, dict]]:
    """Ek bilgilerdeki her madde bir proje (kaynak: ek) ve bir "GitHub'a koy" görevi olur."""
    sonuc = []
    for satir in ek.splitlines():
        metin = _MADDE.sub("", satir).strip()
        if len(metin.split()) < 3:
            continue
        ad = re.split(r"[,(;:]| - ", metin)[0].strip().rstrip(".")
        ad = re.sub(r"\s+\S+(?:d|t)[ıiuü]m$", "", ad).strip() or ad  # "... yazdım" -> "..."
        ad = ad[0].upper() + ad[1:] if ad else metin[:60]
        teknoloji = sorted(beceriler.bul(metin))
        proje = {"ad": ad[:80], "teknolojiler": teknoloji, "maddeler": [metin[0].upper() + metin[1:]],
                 "kaynak": "ek", "yeni": False}
        gorev = {"tur": "yayinla", "proje": proje["ad"],
                 "neden": "Bu proje bilgisayarında var; işe alımcı görebilsin diye GitHub'a koy.",
                 "kapsadigi": teknoloji,
                 "adimlar": ["Kodu tek klasörde topla, şifre/API anahtarı gibi gizli bilgileri sil (.env'i .gitignore'a ekle).",
                             "requirements.txt ya da package.json ekle, çalıştırma komutunu dene.",
                             "Kısa bir README ve bir ekran görüntüsü ekle, GitHub'da public repo olarak yayınla."],
                 "github": {"repo": _slug(ad), "readme": ["Ne yapıyor", "Kullanılan teknolojiler", "Nasıl çalıştırılır"]},
                 "sure": "1 gün"}
        sonuc.append((proje, gorev))
    return sonuc


def _cv_projeleri(satirlar: list[str]) -> list[dict]:
    projeler = []
    for s in satirlar:
        ad, _, ic = s.partition("(")
        projeler.append({"ad": ad.strip().rstrip(".,") or s, "teknolojiler": sorted(beceriler.bul(s)),
                         "maddeler": [ic.rstrip(")").strip()[0].upper() + ic.rstrip(")").strip()[1:]]
                         if ic.strip(") ") else [], "kaynak": "cv", "yeni": False})
    return projeler


# ---------------------------------------------------------------- güçlendirme soruları
def _soru(madde: str) -> str:
    k = tr_lower(madde)
    if re.search(r"model|tahmin|sınıflandır|predict|classif", k):
        return "Bu modelin doğruluk ya da F1 skoru neydi, kaç kayıtla çalıştın? Sayıyı eklersen madde güçlenir."
    if re.search(r"rapor|pano|dashboard|sunum|report", k):
        return "Bu raporu/panoyu kaç kişi kullanıyordu, ne kadar zaman kazandırdı? Sayıyı eklersen madde güçlenir."
    if re.search(r"sorgu|veri|data|sql|analiz", k):
        return "Kaç satır/tablo veriyle çalıştın ya da bu işin sonucu neydi (süre, oran, adet)?"
    return "Bu işin sonucunu bir sayıyla ifade edebilir misin (süre, oran, kişi, adet)?"


# ---------------------------------------------------------------- ana akış
def uyarla(cv: str, ilan: str, analiz: Analiz, ad: str = "", dil: str = "ilan", mod: str = "hedef",
           ek: str = "", gomucu: Gomucu | None = None) -> UyarlanmisCV:
    en = dil == "en" or (dil == "ilan" and _ingilizce_mi(ilan))
    a = ayristir(cv)
    yazim = _ilan_yazimi(analiz)
    alan = _sektor(ilan, cv, en)
    cv_beceri = beceriler.bul(cv)
    ek_beceri = beceriler.bul(ek)
    bilinen = beceriler.genislet(cv_beceri | ek_beceri)
    degisiklikler: list[str] = []

    # 1) Deneyim: maddeleri ilana yakınlığa göre sırala, ilgisizleri çıkar (metne dokunmadan)
    deneyim, cikarilan = [], []
    for d in a.deneyim:
        maddeler = d["maddeler"]
        if maddeler:
            puan = _yakinlik(maddeler, analiz, gomucu)
            sira = sorted(range(len(maddeler)), key=lambda i: -puan[i])
            anahtar_k = {tr_katla(k.ifade) for k in analiz.anahtarlar}
            def degerli(i: int) -> bool:
                return bool(beceriler.bul(maddeler[i])) or any(k in tr_katla(maddeler[i]) for k in anahtar_k)
            tut = [i for i in sira if puan[i] >= ILGISIZ_ESIK or degerli(i)] or sira[:1]
            cikarilan += [maddeler[i] for i in sira if i not in tut]
            d = {**d, "maddeler": [maddeler[i] for i in tut]}
        deneyim.append(d)
    if deneyim:
        degisiklikler.append("Deneyim maddeleri ilana en yakın olandan başlayarak sıralandı; cümlelerin metnine dokunulmadı.")
    for m in cikarilan:
        degisiklikler.append(f"İlanla ilgisi olmadığı için çıkarıldı: \"{m}\"")

    # 2) Projeler: CV'dekiler + ek bilgiler + (hedef modunda) eksikler için katalog projeleri
    projeler = _cv_projeleri(a.proje)
    yapilacaklar: list[dict] = []
    for proje, gorev in _ek_projeler(ek) if mod == "hedef" else []:
        projeler.append(proje)
        yapilacaklar.append(gorev)
    eksik = set()
    if mod == "hedef":
        eksik = set(analiz.eksik_beceriler)
        for g in analiz.gereksinimler:
            if g.durum != "karşılanıyor":
                eksik |= beceriler.bul(g.metin)
        for k in analiz.anahtarlar:
            if not k.var:
                eksik |= beceriler.bul(k.ifade)
        eksik -= bilinen
        yeni_projeler = []
        for sablon, kapsanan in _proje_sec(eksik):
            proje, gorev = _proje_olustur(sablon, kapsanan, yazim, alan, en, bilinen)
            yeni_projeler.append(proje)
            yapilacaklar.append(gorev)
        projeler = yeni_projeler + projeler  # ilanın aradığı projeler en üstte
        if yeni_projeler:
            degisiklikler.append(f"Eksik becerileri kapatmak için {len(yeni_projeler)} portföy projesi eklendi "
                                 f"({_liste(sorted(eksik), False)}); hepsi 'yapılacaklar' listesinde.")
    if ek.strip() and mod == "hedef":
        degisiklikler.append("Ek bilgilerindeki projeler CV'ye eklendi; GitHub'a koyman için görev oluşturuldu.")

    # 3) Beceriler: kategorili, ilanla eşleşenler önce; dolaylılar adıyla
    ilan_beceri = analiz.ilan_becerileri
    proje_beceri = {b for p in projeler if p["yeni"] for b in beceriler.bul(" ".join(p["teknolojiler"]))}
    tum = (cv_beceri | ek_beceri | (beceriler.genislet(cv_beceri) & ilan_beceri) | proje_beceri)
    satirlar = []
    for tr_ad, en_ad, kume in KATEGORILER:
        ogeler = sorted(tum & kume, key=lambda b: (b not in ilan_beceri, b))
        if ogeler:
            satirlar.append((sum(b in ilan_beceri for b in ogeler),
                             f"{en_ad if en else tr_ad}: {', '.join(yazim.get(b, b) for b in ogeler)}"))
    taninmayan = [x for x in a.beceri if not beceriler.bul(x)]
    if taninmayan:
        satirlar.append((0, f"{'Other' if en else 'Diğer'}: {', '.join(taninmayan)}"))
    beceri_satirlari = [s for _, s in sorted(satirlar, key=lambda x: -x[0])]
    dolayli = sorted((beceriler.genislet(cv_beceri) & ilan_beceri) - cv_beceri)
    if dolayli:
        degisiklikler.append(f"CV'nde dolaylı olarak var, ilanın terimiyle açıkça yazıldı: {_liste(dolayli, False)}.")

    # 4) Unvan ve özet (şablon; yalnızca CV'deki ve proje bilgileri)
    baslik = baslik_cikar(cv, ad or None)
    unvan_aday = [s for s in a.ust if s != baslik.ad and "@" not in s and not re.search(r"\d{3}", s)]
    temel_unvan = unvan_aday[0] if unvan_aday else (deneyim[0]["pozisyon"] if deneyim else "")
    onem = _onem_sirasi(analiz)
    cv_genis = beceriler.genislet(cv_beceri)
    alan_beceri = next((yazim.get(b, b) for b in ALAN_BECERILERI if b in ilan_beceri and b in cv_genis), "")
    unvan = f"{temel_unvan} | {alan_beceri}" if temel_unvan and alan_beceri and \
        tr_katla(alan_beceri) not in tr_katla(temel_unvan) else temel_unvan
    yil = re.search(r"(\d+)\+?\s*(?:yıllık|yıl|years?)", cv, re.I)
    eslesen = [yazim.get(b, b) for b in sorted(analiz.eslesen_beceriler, key=lambda b: (onem.get(b, 99), b))][:4]
    # Orijinal özetten: kısa unvan parçası ("Endüstri mühendisi.") ve tekrar etmeyen cümleler
    cumleler = [c.strip() for c in re.split(r"(?<=[.!?])\s+", " ".join(a.ozet)) if c.strip()]
    koken = next((c.rstrip(".") for c in cumleler if len(c.split()) <= 3), "")
    kalan = [c for c in cumleler if len(c.split()) > 3 and not re.search(r"\d+\s*(?:yıl|year)", c, re.I)
             and not re.search(r"\b(seviyorum|severim|love|passionate)\b", c, re.I)][:2]
    if en:
        ozet = (f"{temel_unvan or 'Professional'}" + (f" ({koken})" if koken else "")
                + (f" with {yil.group(1)} years of experience" if yil else "")
                + (f" in {_liste(eslesen, True)}" if eslesen else "") + ".")
    else:
        ozet = ((f"{_liste(eslesen, False)} alanlarında " if eslesen else "")
                + (f"{yil.group(1)} yıllık deneyime sahip " if yil else "")
                + f"{temel_unvan or 'profesyonel'}" + (f" ({tr_lower(koken)})" if koken else "") + ".")
        ozet = ozet[0].upper() + ozet[1:]
    if kalan:
        ozet += " " + " ".join(kalan)
    yeni_adlar = [yazim.get(b, b) for b in sorted(proje_beceri - cv_beceri)][:3]
    if yeni_adlar:
        ozet += (f" Recently building portfolio projects with {_liste(yeni_adlar, True)}." if en else
                 f" Son dönemde {_liste(yeni_adlar, False)} ile portföy projeleri geliştiriyor.")
    degisiklikler.append("Özet, ilanla eşleşen becerilerin öne çıkacağı şekilde yeniden kuruldu.")
    if en and re.search(r"[çğışöü]", " ".join(m for d in deneyim for m in d["maddeler"])):
        degisiklikler.append("Çevrimdışı motor çeviri yapamaz: deneyim maddeleri orijinal dilinde kaldı.")

    # 5) Güçlendirme soruları: sayı içermeyen, ilana en yakın maddeler
    tum_maddeler = [m for d in deneyim for m in d["maddeler"] if not re.search(r"\d", m)]
    puan = _yakinlik(tum_maddeler, analiz, gomucu) if tum_maddeler else np.array([])
    sorular = [{"madde": tum_maddeler[i], "soru": _soru(tum_maddeler[i])}
               for i in np.argsort(-puan)[:3]] if len(puan) else []

    # 6) Öneriler: projelerle de kapanmayan gereksinimler
    oneriler = []
    for g in analiz.gereksinimler:
        if g.durum == "eksik" and not (beceriler.bul(g.metin) & (bilinen | eksik)):
            oneriler.append(f"\"{g.metin}\" için CV'nde bir örnek yok; bunu bir deneyim maddesinde ya da projede göster.")
    if mod != "hedef" and analiz.eksik_beceriler:
        oneriler.append(f"CV'nde olmayan ilan becerileri: {_liste(sorted(analiz.eksik_beceriler), False)}. "
                        "Bunlar için küçük projeler yapıp CV'ne ekleyebilirsin ('Uyumu 90'a çıkar' modu bunu önerir).")
    oneriler.append("Daha akıcı ve ilana özel cümleler için Ayarlar'dan ücretsiz Gemini anahtarı ekleyebilirsin.")

    diger = a.diger
    return UyarlanmisCV(
        unvan=unvan, ozet=ozet.strip(), beceriler=beceri_satirlari, deneyim=deneyim, egitim=a.egitim,
        diger=diger, projeler=projeler, yapilacaklar=yapilacaklar, guclendirme_sorulari=sorular,
        degisiklikler=degisiklikler, oneriler=oneriler, mod=mod, model=MOTOR_ADI,
        modele_giden="(Çevrimdışı motor: CV bilgisayarından çıkmadı.)")
