"""CV'yi ilana göre LLM ile yeniden yazar ve yazılanı yerelde denetler.

İki mod:
  - "hedef" (varsayılan): uyumu ~90'a çıkarmak için ilanın istediği ama CV'de olmayan beceriler
    adayın yapabileceği PORTFÖY PROJELERİ olarak CV'ye eklenir; her yeni proje için "yapılacaklar"
    listesinde nasıl yapılacağı ve GitHub'a nasıl konacağı anlatılır. Mevcut iş deneyimlerine
    olmayan görev/şirket/tarih eklenmez; yeni beceriler yalnızca yeni projeler üzerinden girer.
  - "temkinli": CV'de OLMAYAN hiçbir şey eklenmez; sadece yeniden sıralama ve ifade.
Ortak kurallar:
  - Ad ve iletişim bilgisi modele gönderilmez. Metindeki e-posta/telefon/TCKN gibi veriler
    KVKK Kalkanı ile maskelenir, ad "[AD_SOYAD]" ile değiştirilir.
  - Modelin çıktısına güvenilmez: CV'de olmayan beceriler ve sayılar "uydurma şüphesi" olarak
    işaretlenir.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from ..kvkk import Maskeleyici
from ..veritabani.sorgu import tr_katla
from . import beceriler
from .eslestirme import Analiz, Gereksinim
from .okuyucu import _URL

AD_ETIKETI = "[AD_SOYAD]"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# Ücretsiz katmanda denenmiş modeller (Kasım 2026). Pro sürümleri ücretsiz katmanda kota vermez
# (faturalandırma gerekir); seçilebilir ama kota hatası verirse sıradaki ücretsiz modele düşülür.
GEMINI_SECENEKLERI = [
    {"id": "gemini-3.6-flash", "ad": "Gemini 3.6 Flash", "not": "Önerilen: daha temkinli yazar, uydurma riski düşük; ücretsiz"},
    {"id": "gemini-3.8-flash", "ad": "Gemini 3.8 Flash", "not": "En yeni, ücretsiz; şu an çok yavaş, zaman aşımına uğrayabilir"},
    {"id": "gemini-3.7-flash", "ad": "Gemini 3.7 Flash", "not": "Ücretsiz; şu an çok yavaş"},
    {"id": "gemini-3.5-flash", "ad": "Gemini 3.5 Flash", "not": "Ücretsiz"},
    {"id": "gemini-3-flash-preview", "ad": "Gemini 3 Flash", "not": "En hızlı, ilana daha çok uyarlar; ücretsiz"},
    {"id": "gemini-3.1-pro-preview", "ad": "Gemini 3.1 Pro", "not": "Ücretli: Google hesabında faturalandırma gerekir"},
]
GEMINI_VARSAYILAN = "gemini-3.6-flash"
GEMINI_YEDEKLER = ["gemini-3-flash-preview", "gemini-3.5-flash-lite"]  # kota/hata olursa
GEMINI_MODELLERI = [GEMINI_VARSAYILAN, *GEMINI_YEDEKLER]


def gemini_modelleri() -> list[str]:
    """Seçilen model (GEMINI_MODEL) başta, ardından ücretsiz yedekler."""
    secili = os.getenv("GEMINI_MODEL") or GEMINI_VARSAYILAN
    return [secili, *[m for m in GEMINI_MODELLERI if m != secili]]

_ORTAK = """[AD_SOYAD], [EPOSTA_1], [TELEFON_1] gibi etiketler gizlenmiş kişisel verilerdir; aynen koru.
Projeleri yalnızca "projeler" alanına yaz, "diger" alanına proje koyma. Sadece geçerli JSON döndür,
başka metin yazma."""

SISTEM_HEDEF = """Sen üst düzey bir teknik işe alım uzmanı, ATS (aday takip sistemi) uzmanı ve
kariyer koçusun. Amacın adayı bu ilan için EN YETKİN şekilde göstermek ve CV'nin ilana uyumunu 100
üzerinden EN AZ 90'a çıkarmak; bunu yaparken adayı yalancı duruma düşürmemek.

BİLGİ KAYNAKLARI (doğru kabul et):
- Adayın CV'si.
- "ADAYIN EK BİLGİLERİ": CV'ye yazmadığı ama gerçekten yaptığı projeler ve bildiği beceriler
  (çoğu GitHub'da değil, bilgisayarında). Bunları CV'ye "kaynak": "ek" olarak doğrudan ekle.
Bunlarla da kapanmayan her ilan gereksinimi için adayın 1-3 haftada yapabileceği gerçekçi bir
PORTFÖY PROJESİ tasarla ("kaynak": "yeni"). Aday bu projeyi yapıp GitHub'a koyacak. HİÇBİR
gereksinimi ihmal etme.

YAZIM KURALLARI (uzman CV yazımı):
1. Maddeler "eylem fiili + ne yaptı + hangi araçla + amaç/etki" formülüyle, tek cümle, en fazla
   ~25 kelime. "Sorumluydum, görev aldım, yardımcı oldum" gibi zayıf/pasif ifadeler yok.
2. ATS: "İLANIN ANAHTAR KELİMELERİ" listesindeki ifadeleri ilandaki yazımıyla birebir geçir (eş
   anlamlısını değil). Kısaltmayı ilk geçişte açılımıyla yaz: "Büyük Dil Modelleri (LLM)".
3. Özet 3 cümle: ilandaki rol başlığına yakın profil + en güçlü 3 eşleşme + bir farklılaştırıcı.
   Unvan satırı adayın gerçek unvanına dayanır, ilandaki unvanı adaya ait gibi yazma.
4. Beceriler: kategorili satırlar ("Programlama: Python, SQL", "Makine Öğrenmesi: scikit-learn,
   PyTorch", "Araçlar: Git, Docker"); her satırda ilanla en ilgili olanlar önce.
5. Bölüm ve madde sırası ilana göre: en ilgili deneyim ve projeler en üstte, ilgisizler kısalır.
6. Sayı uydurma. CV'de sayı yoksa maddeyi sayısız güçlü yaz ve "guclendirme_sorulari"na adaya
   o madde için somut bir soru ekle ("Bu panoyu kaç kişi kullanıyordu? Sayıyı eklersen madde
   güçlenir").

DOKUNULMAZLAR VE SINIRLAR:
7. GEREKSİNİM PLANI'na uy: "DOKUNMA" altındaki CV cümlelerini kelimesi kelimesine koru (yalnızca
   yerini değiştirebilirsin); "GÜÇLENDİR" altındakileri ilanın terimleriyle yeniden yaz; "EKLE"
   altındakileri ek bilgilerle ya da yeni projelerle kapsa. CV'de iyi olanı bozma.
8. Mevcut işlerin şirket, pozisyon ve tarihlerini değiştirme. Mevcut bir işe yalnızca o işin
   CV'deki görevlerinden makul şekilde çıkan bir ifade ekleyebilirsin (ör. Power BI raporu
   hazırlayan biri için "yöneticilere sundu"); her böyle eklemeyi "degisiklikler"de "Çıkarım:"
   diye başlatarak belirt. Mevcut işe yeni araç, teknoloji ya da sayı ekleme: bunlar projelerle gelir.
9. Projeler: "kaynak" alanı "cv" (CV'de zaten var), "ek" (ek bilgilerden) ya da "yeni" (yapılacak)
   olur; "yeni" alanı yalnızca "yeni" projelerde true'dur. Yeni proje maddelerinde gerçekleşmemiş
   sonuç sayısı yazma. En fazla 4 yeni proje; birkaç gereksinimi tek projede birleştir.
10. "yapilacaklar": her "yeni" proje için "tur": "yap" görevi (neden: adaya hitaben "CV'nde ...
   görünmüyor, bu ilan için şu projeyi ekledim"; adimlar: veri seti/kaynak, teknoloji, çıktı;
   github: repo adı + README içeriği; sure). Her "ek" proje için "tur": "yayinla" görevi (neden:
   "Bu proje bilgisayarında var, işe alımcı görebilsin diye GitHub'a koy"; github: repo adı + README;
   adimlar: yayınlamadan önce temizlenecekler; sure: genelde 1-2 gün).
""" + _ORTAK

SISTEM_TEMKINLI = """Sen deneyimli bir İK uzmanı ve CV editörüsün. Görevin, adayın CV'sini verilen iş
ilanına göre uyarlamak. KESİN KURALLAR:
1. CV'de olmayan hiçbir deneyim, beceri, araç, sertifika, proje, unvan, tarih veya sayı EKLEME.
   Sadece CV'deki bilgileri yeniden sırala, öne çıkar, kısalt ve ilanın terimleriyle yeniden ifade et.
2. İlanla ilgisiz bilgileri kısalt ya da çıkar, ilgili olanları en üste taşı.
3. Deneyim maddelerini eylem fiiliyle başlat; CV'de sayı/sonuç varsa koru ve öne çıkar.
4. İlanın istediği ama CV'de bulunmayan şeyleri CV'ye yazma, "oneriler" listesine yaz.
5. "projeler" alanına yalnızca CV'de zaten olan projeleri "yeni": false ile yaz; "yapilacaklar" boş
   liste olsun.
6. Maddeleri yeniden ifade ederken CV'de olmayan kapsam, etki veya sorumluluk ekleme.
7. GEREKSİNİM PLANI'na uy: "DOKUNMA" altındaki CV cümlelerini kelimesi kelimesine koru (yalnızca
   yerini değiştirebilirsin); "GÜÇLENDİR" altındakileri ilanın terimleriyle yeniden yaz.
""" + _ORTAK

SISTEMLER = {"hedef": SISTEM_HEDEF, "temkinli": SISTEM_TEMKINLI}

SEMA = """{
  "unvan": "adayın CV'deki gerçek unvanına dayalı tek satır (ör. 'Veri Analisti | Makine Öğrenmesi'); ilandaki unvanı adaya ait gibi yazma",
  "ozet": "3-4 cümlelik, ilana göre yazılmış profesyonel özet",
  "beceriler": ["ilanla en ilgili olanlar önce"],
  "deneyim": [{"pozisyon": "", "sirket": "", "tarih": "", "maddeler": ["..."]}],
  "projeler": [{"ad": "", "teknolojiler": ["..."], "maddeler": ["CV'de görünecek 1-3 madde"],
                "kaynak": "cv | ek | yeni", "yeni": true}],
  "egitim": [{"okul": "", "bolum": "", "tarih": "", "not": ""}],
  "diger": [{"baslik": "Sertifikalar / Diller vb.", "maddeler": ["..."]}],
  "yapilacaklar": [{"tur": "yap | yayinla", "proje": "projeler'deki adıyla aynı",
                    "neden": "adaya hitaben: CV'nde ... görünmüyor",
                    "kapsadigi": ["bu projenin karşıladığı ilan gereksinimleri"],
                    "adimlar": ["1. ...", "2. ..."],
                    "github": {"repo": "kucuk-harf-tireli-repo-adi", "readme": ["README'de olması gerekenler"]},
                    "sure": "ör. 1 hafta"}],
  "degisiklikler": ["CV'de neyi neden değiştirdiğinin kısa açıklaması"],
  "guclendirme_sorulari": [{"madde": "sorunun ilgili olduğu CV maddesi", "soru": "adaya somut soru"}],
  "oneriler": ["başvurudan önce adaya diğer öneriler"]
}"""

DILLER = {"ilan": "İlan hangi dilde yazılmışsa CV'yi o dilde yaz.",
          "tr": "CV'yi Türkçe yaz.", "en": "Write the CV in English."}


@dataclass
class UyarlanmisCV:
    unvan: str = ""
    ozet: str = ""
    beceriler: list[str] = field(default_factory=list)
    deneyim: list[dict[str, Any]] = field(default_factory=list)
    egitim: list[dict[str, Any]] = field(default_factory=list)
    diger: list[dict[str, Any]] = field(default_factory=list)
    projeler: list[dict[str, Any]] = field(default_factory=list)
    yapilacaklar: list[dict[str, Any]] = field(default_factory=list)
    guclendirme_sorulari: list[dict[str, Any]] = field(default_factory=list)
    degisiklikler: list[str] = field(default_factory=list)
    oneriler: list[str] = field(default_factory=list)
    uydurma_supheleri: list[str] = field(default_factory=list)
    eklenen_beceriler: list[str] = field(default_factory=list)  # yeni projelerle gelenler
    korunan: list[str] = field(default_factory=list)  # zaten karşılayan, aynen kalan cümleler
    degisen_korunan: list[str] = field(default_factory=list)  # korunması istenip değiştirilenler
    mod: str = "hedef"
    tur: int = 1  # kaç turda iyileştirildi (otomatik ikinci tur)
    model: str = ""
    modele_giden: str = ""  # şeffaflık: modelin gerçekte gördüğü CV metni

    def yeni_projeler_metni(self) -> str:
        return "\n".join(f"{p.get('ad', '')} {' '.join(p.get('teknolojiler') or [])} "
                         f"{' '.join(p.get('maddeler') or [])}" for p in self.projeler if p.get("yeni"))

    def duz_metin(self) -> str:
        """Yeniden skorlamak ve denetlemek için CV'nin düz metin hali."""
        satirlar = [self.unvan, self.ozet, ", ".join(self.beceriler)]
        for d in self.deneyim:
            satirlar += [f"{d.get('pozisyon', '')} {d.get('sirket', '')}", *d.get("maddeler", [])]
        for p in self.projeler:
            satirlar += [f"{p.get('ad', '')} {', '.join(p.get('teknolojiler') or [])}",
                         *p.get("maddeler", [])]
        for e in self.egitim:
            satirlar.append(" ".join(str(e.get(k, "")) for k in ("okul", "bolum", "not")))
        for b in self.diger:
            satirlar += [b.get("baslik", ""), *b.get("maddeler", [])]
        return "\n".join(s for s in satirlar if s)


def _ulasilabilir(url: str, zaman_asimi: float = 0.4) -> bool:
    """Gateway adresine TCP bağlantısı kurulabiliyor mu? (kapalı gateway'de 2 dk beklememek için)"""
    import socket  # noqa: PLC0415
    from urllib.parse import urlparse  # noqa: PLC0415

    u = urlparse(url)
    try:
        with socket.create_connection((u.hostname or "localhost",
                                       u.port or (443 if u.scheme == "https" else 80)), zaman_asimi):
            return True
    except OSError:
        return False


def baglanti() -> tuple[OpenAI | None, list[str]]:
    """Gateway (LLM_BASE_URL) açıksa onu, değilse GEMINI_API_KEY ile doğrudan Gemini'yi kullanır.
    .env'de gateway adresi olup gateway kapalıysa sessizce Gemini'ye düşer."""
    url = os.getenv("LLM_BASE_URL")
    if url and (_ulasilabilir(url) or not os.getenv("GEMINI_API_KEY")):
        istemci = OpenAI(base_url=url,
                         api_key=os.getenv("LITELLM_MASTER_KEY", "sk-degistir-beni"))
        return istemci, [os.getenv("CV_MODEL", os.getenv("AGENT_MODEL", "gemini"))]
    if os.getenv("GEMINI_API_KEY"):
        # Yeni Flash sürümleri yoğunlukta dakikalarca düşünebiliyor: sınırsız bekleme yerine
        # 4 dk sonra sıradaki modele geç; geçici 429/503 için bir kez yeniden dener.
        return (OpenAI(base_url=GEMINI_URL, api_key=os.environ["GEMINI_API_KEY"],
                       timeout=240, max_retries=1), gemini_modelleri())
    # Yerel model (Ollama) burada denenmez: işlemcide bir uyarlama 15 dakikayı bulabiliyor.
    # Yalnızca Ayarlar'da bilerek "yerel" seçilirse kullanılır; yoksa çevrimdışı motor çalışır.
    return None, []


def ollama_baglanti() -> tuple[OpenAI | None, list[str]]:
    """Anahtarsız ve internetsiz yerel model: bilgisayarda Ollama çalışıyorsa onu kullanır.
    Büyük modeller işlemcide yavaştır; bu yüzden zaman aşımı uzun tutulur."""
    ollama = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    if _ulasilabilir(ollama, 0.3):
        model = os.getenv("OLLAMA_MODEL") or _ollama_modeli(ollama)
        if model:
            return OpenAI(base_url=f"{ollama}/v1", api_key="ollama", timeout=900, max_retries=0), [model]
    return None, []


def _ollama_modeli(adres: str) -> str:
    """Ollama'da yüklü ilk sohbet modeli (embedding modelleri atlanır)."""
    import urllib.request  # noqa: PLC0415

    try:
        with urllib.request.urlopen(f"{adres}/api/tags", timeout=2) as yanit:
            modeller = [m["name"] for m in json.load(yanit).get("models", [])]
    except (OSError, ValueError, KeyError):
        return ""
    return next((m for m in modeller if "embed" not in m), "")


def _gizle(metin: str, kalkan: Maskeleyici, ad: str) -> str:
    # Sıra önemli: ad önce değiştirilirse "elif.kaya@..." e-posta olarak tanınmaz ve sızar.
    metin = kalkan.maskele(metin)
    metin = _URL.sub("[BAGLANTI]", metin)  # linkedin.com/in/ad-soyad gibi bağlantılar
    if ad:  # önce tam ad, sonra tek tek ad/soyad (ör. "Ayşe Hanım", "Yılmaz'ın")
        for parca in dict.fromkeys([ad, *ad.split()]):
            if len(parca) > 2:
                metin = re.sub(rf"(?<![\w\[]){re.escape(parca)}(?!\w)", AD_ETIKETI if parca == ad
                               else "[AD]", metin, flags=re.I)
    return metin


def _ac(veri: Any, kalkan: Maskeleyici, ad: str) -> Any:
    if isinstance(veri, str):
        return kalkan.geri_yukle(veri).replace(AD_ETIKETI, ad).replace("[AD]", ad.split()[0] if ad else "")
    if isinstance(veri, list):
        return [_ac(v, kalkan, ad) for v in veri]
    if isinstance(veri, dict):
        return {k: _ac(v, kalkan, ad) for k, v in veri.items()}
    return veri


def json_ayikla(metin: str) -> dict[str, Any]:
    """Model bazen JSON'u ```json bloğuna sarar ya da önüne açıklama ekler."""
    metin = re.sub(r"^```(?:json)?|```$", "", metin.strip(), flags=re.M).strip()
    bas, son = metin.find("{"), metin.rfind("}")
    if bas == -1 or son == -1:
        raise ValueError("Model JSON döndürmedi")
    return json.loads(metin[bas : son + 1])


_SAYI = re.compile(r"\d+(?:[.,]\d+)?")


def denetle(orijinal: str, uyarlanmis: UyarlanmisCV, ek: str = "") -> list[str]:
    """CV'de olmayan beceri ve sayıları bulur (modelin uydurmuş olabileceği şeyler).
    Yeni portföy projeleriyle gelen beceriler şüphe değildir; uyarlanmis.eklenen_beceriler'e yazılır."""
    yeni_metin = uyarlanmis.duz_metin()
    orijinal = f"{orijinal}\n{ek}"  # adayın ek bilgileri de doğru kaynaktır
    izinli = beceriler.genislet(beceriler.bul(orijinal))
    projeden = beceriler.genislet(beceriler.bul(uyarlanmis.yeni_projeler_metni())) - izinli
    yeni_beceriler = beceriler.bul(yeni_metin) - izinli
    uyarlanmis.eklenen_beceriler = sorted(yeni_beceriler & projeden)
    supheler = [f"Beceri: {b}" for b in sorted(yeni_beceriler - projeden)]
    orijinal_sayilar = {s.replace(",", ".") for s in _SAYI.findall(orijinal)}
    for s in dict.fromkeys(_SAYI.findall(yeni_metin)):
        if s.replace(",", ".") not in orijinal_sayilar:
            supheler.append(f"Sayı: {s}")
    # Unvan ve şirket adları da korunmalı
    katli = tr_katla(orijinal)
    for d in uyarlanmis.deneyim:
        sirket = (d.get("sirket") or "").strip()
        if sirket and tr_katla(sirket) not in katli:
            supheler.append(f"Şirket: {sirket}")
    return supheler


def _plan_notu(analiz: Analiz, mod: str, gizle) -> str:
    """Her gereksinim için ne yapılacağını söyler: zaten karşılanıyorsa DOKUNMA, kısmen ise
    GÜÇLENDİR, yoksa EKLE (hedef modunda projeyle, temkinli modda öneri olarak)."""
    def satir(g: Gereksinim) -> str:
        yakin = f' -> CV\'deki cümle: "{gizle(g.en_yakin)}"' if g.en_yakin else ""
        return f"- {g.metin}{' (tercihen)' if g.tercih else ''}{yakin}"

    gruplar = {d: [g for g in analiz.gereksinimler if g.durum == d]
               for d in ("karşılanıyor", "kısmen", "eksik")}
    ekle = ("CV'de yok, yeni portföy projeleriyle kapsa" if mod == "hedef"
            else "CV'de yok, CV'ye yazma, önerilere yaz")
    return ("## GEREKSİNİM PLANI (yerel analiz)\n"
            "### DOKUNMA: CV zaten karşılıyor, ilgili cümleyi aynen koru\n"
            + ("\n".join(map(satir, gruplar["karşılanıyor"])) or "- (yok)")
            + "\n### GÜÇLENDİR: kısmen karşılıyor, mevcut cümleyi ilanın terimleriyle yeniden yaz\n"
            + ("\n".join(map(satir, gruplar["kısmen"])) or "- (yok)")
            + f"\n### EKLE: {ekle}\n"
            + ("\n".join(f"- {g.metin}" for g in gruplar["eksik"]) or "- (yok)") + "\n\n")


def _ek_notu(ek: str, mod: str, gizle) -> str:
    if not ek.strip():
        return ""
    nasil = ("CV'ye 'kaynak': 'ek' projeler/beceriler olarak ekle"
             if mod == "hedef" else "yalnızca CV'deki bir bilgiyi destekliyorsa kullan")
    return (f"## ADAYIN EK BİLGİLERİ (CV'de yazmıyor ama gerçekten yaptı/biliyor; {nasil})\n"
            f"{gizle(ek.strip())}\n\n")


def _anahtar_notu(analiz: Analiz) -> str:
    if not analiz.anahtarlar:
        return ""
    var = [a.ifade for a in analiz.anahtarlar if a.var]
    yok = [a.ifade for a in analiz.anahtarlar if not a.var]
    return ("## İLANIN ANAHTAR KELİMELERİ (yerel ML, önem sırasıyla)\n"
            f"CV'de geçenler: {', '.join(var) or '-'}\n"
            f"CV'de geçmeyenler (ilandaki yazımıyla birebir geçir): {', '.join(yok) or '-'}\n\n")


_TEMEL_ALANLAR = ("unvan", "ozet", "beceriler", "deneyim", "projeler", "egitim", "diger",
                  "yapilacaklar", "guclendirme_sorulari")


def _onceki_notu(onceki: dict[str, Any] | None, gizle) -> str:
    """'Bir daha uyarla': seçili denemenin ÜZERİNE çalışılır. Model o sürümü temel alır, iyi olanı
    aynen bırakır, yalnızca hâlâ zayıf kalan gereksinimleri düzeltir."""
    if not onceki:
        return ""
    zayiflar = (onceki.get("zayiflar") or [])[:15]
    zayif = "\n".join(f"- {z}" for z in zayiflar) or "- (yok)"
    if not zayiflar:
        zayif += ("\nTüm gereksinimler zaten karşılanıyor: içeriğe, projelere ve yapılacaklara "
                  "dokunma; yalnızca dili, akışı ve sıralamayı iyileştir.")
    not_ = (f"## ÖNCEKİ DENEME\nSeçili denemenin uyum skoru: {onceki.get('skor', '?')}/100 "
            f"(hedef en az 90).\nHâlâ zayıf kalan ilan gereksinimleri:\n{zayif}\n")
    temel = {k: v for k, v in (onceki.get("cv") or {}).items() if k in _TEMEL_ALANLAR}
    if temel:
        not_ += ("### ÜZERİNE ÇALIŞILACAK SÜRÜM (JSON)\n"
                 f"{gizle(json.dumps(temel, ensure_ascii=False))}\n"
                 "Bu sürümü TEMEL AL: karşılanan gereksinimlere ait kısımları, iyi projeleri ve "
                 "yapılacakları AYNEN bırak. Yalnızca yukarıdaki zayıf gereksinimler için ilgili "
                 "maddeleri ilanın kelimeleriyle güçlendir ya da projeleri genişlet/yenisini ekle. "
                 "Tüm alanlarla eksiksiz JSON döndür.\n\n")
    else:
        projeler = ", ".join((onceki.get("projeler") or [])[:8]) or "-"
        not_ += (f"Önceki denemedeki projeler: {projeler}\nBu sefer bu gereksinimleri DOĞRUDAN ve "
                 f"ilanın kelimeleriyle karşılayan maddeler ve projeler yaz.\n\n")
    return not_


def _norm(metin: str) -> str:
    return re.sub(r"[^\w%]+", " ", tr_katla(metin)).strip()


def korunanlari_denetle(orijinal: str, analiz: Analiz, uyarlanmis: UyarlanmisCV) -> None:
    """Zaten karşılanan gereksinimlerin CV cümleleri yeni sürümde aynen duruyor mu?"""
    # Deneyim başlıkları (pozisyon - şirket (tarih)) yeni sürümde ayrı alanlara bölünür
    basliklar = [" ".join(str(d.get(k, "")) for k in ("pozisyon", "sirket", "tarih"))
                 for d in uyarlanmis.deneyim]
    yeni = f" {_norm(uyarlanmis.duz_metin())} {' '.join(_norm(b) for b in basliklar)} "
    cumleler = dict.fromkeys(g.en_yakin for g in analiz.gereksinimler
                             if g.durum == "karşılanıyor" and g.en_yakin)
    uyarlanmis.korunan = [c for c in cumleler if f" {_norm(c)} " in yeni]
    uyarlanmis.degisen_korunan = [c for c in cumleler if c not in uyarlanmis.korunan]


def uyarla(cv: str, ilan: str, analiz: Analiz, ad: str = "", dil: str = "ilan",
           client: OpenAI | None = None, modeller: list[str] | None = None,
           mod: str = "hedef", onceki: dict[str, Any] | None = None,
           ek: str = "") -> UyarlanmisCV:
    if client is None:
        client, modeller = baglanti()
    if client is None:
        raise RuntimeError("Model bağlantısı yok: gateway'i başlatın (LLM_BASE_URL) "
                           "ya da GEMINI_API_KEY tanımlayın.")
    modeller = modeller or ["gemini"]

    kalkan = Maskeleyici()
    gizli_cv = _gizle(cv, kalkan, ad)
    def gizle(metin: str) -> str:
        return _gizle(metin, kalkan, ad)
    kullanici = (
        f"{DILLER.get(dil, DILLER['ilan'])}\n\n"
        f"## İŞ İLANI\n{kalkan.maskele(ilan)}\n\n"
        f"## ADAYIN CV'Sİ\n{gizli_cv}\n\n"
        f"{_ek_notu(ek, mod, gizle)}"
        f"## ÖN ANALİZ (yerel model)\n"
        f"Uyum skoru: {analiz.skor}/100\n"
        f"CV'de de geçen ilan becerileri: {', '.join(sorted(analiz.eslesen_beceriler)) or '-'}\n"
        f"CV'de dolaylı olarak var, ilanın terimiyle AÇIKÇA yaz (ör. scikit-learn -> makine "
        f"öğrenmesi): {', '.join(sorted(analiz.ima_edilen_beceriler)) or '-'}\n"
        f"CV'de geçmeyen ilan becerileri "
        f"({'yeni projelerle kapsa' if mod == 'hedef' else 'CVye EKLEME, önerilere yaz'}): "
        f"{', '.join(sorted(analiz.eksik_beceriler)) or '-'}\n\n"
        f"{_anahtar_notu(analiz)}"
        f"{_plan_notu(analiz, mod, gizle)}"
        f"{_onceki_notu(onceki, gizle)}"
        f"Şu JSON şemasıyla cevap ver:\n{SEMA}"
    )
    mesajlar = [{"role": "system", "content": SISTEMLER.get(mod, SISTEM_HEDEF)},
                {"role": "user", "content": kullanici}]
    sicaklik = 0.8 if onceki else 0.4  # tekrar denemelerde farklı fikirler gelsin

    son_hata: Exception | None = None
    for model in modeller:
        try:
            yanit = client.chat.completions.create(model=model, messages=mesajlar,
                                                   temperature=sicaklik)
            veri = json_ayikla(yanit.choices[0].message.content or "")
            gercek_model = getattr(yanit, "model", None) or model
            break
        except Exception as e:  # noqa: BLE001 - kota/bağlantı/JSON hatası: sıradaki modeli dene
            son_hata = e
            print(f"[cv] {model} cevap veremedi, sıradaki deneniyor: {str(e)[:300]}", flush=True)
    else:
        raise RuntimeError(f"Model cevap veremedi: {son_hata}") from son_hata

    veri = _ac(veri, kalkan, ad)
    alanlar = UyarlanmisCV.__dataclass_fields__
    sonuc = UyarlanmisCV(**{k: v for k, v in veri.items() if k in alanlar and k not in
                            ("uydurma_supheleri", "eklenen_beceriler", "mod", "model", "tur",
                             "modele_giden", "korunan", "degisen_korunan")})
    for pr in sonuc.projeler:  # "kaynak" ve "yeni" tutarlı olsun
        pr["kaynak"] = pr.get("kaynak") if pr.get("kaynak") in ("cv", "ek", "yeni") else \
            ("yeni" if pr.get("yeni") else "cv")
        pr["yeni"] = pr["kaynak"] == "yeni"
    if mod != "hedef":  # temkinli modda yeni proje kabul edilmez
        sonuc.projeler = [p for p in sonuc.projeler if not p.get("yeni")]
        sonuc.yapilacaklar = []
    sonuc.model, sonuc.modele_giden, sonuc.mod = gercek_model, gizli_cv, mod
    sonuc.uydurma_supheleri = denetle(cv, sonuc, ek)
    korunanlari_denetle(cv, analiz, sonuc)
    return sonuc
