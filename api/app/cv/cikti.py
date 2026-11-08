"""Uyarlanmış CV'yi DOCX ve PDF olarak yazar (ATS dostu: tek sütun, tablo/görsel yok)."""

from __future__ import annotations

import io
from pathlib import Path

from .okuyucu import Baslik
from .yazici import UyarlanmisCV

BOLUMLER = {
    "tr": {"ozet": "Profesyonel Özet", "beceri": "Beceriler", "deneyim": "Deneyim",
           "egitim": "Eğitim"},
    "en": {"ozet": "Professional Summary", "beceri": "Skills", "deneyim": "Experience",
           "egitim": "Education"},
}

# Türkçe karakterler için Unicode TTF gerekir (fpdf'in yerleşik fontları ş/ğ/ı basamaz)
_FONTLAR = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/calibrib.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]


def _ingilizce_mi(cv: UyarlanmisCV) -> bool:
    metin = f" {cv.ozet} ".lower()
    return sum(metin.count(f" {k} ") for k in ("the", "and", "with", "of")) > \
        sum(metin.count(f" {k} ") for k in ("ve", "ile", "bir", "için"))


def _bolum_adlari(cv: UyarlanmisCV) -> dict[str, str]:
    return BOLUMLER["en" if _ingilizce_mi(cv) else "tr"]


def _buyuk(metin: str, cv: UyarlanmisCV) -> str:
    # Python'un upper()'ı İngilizce kuralla çalışır: "Beceriler" -> "BECERILER" (doğrusu BECERİLER)
    if not _ingilizce_mi(cv):
        metin = metin.replace("i", "İ").replace("ı", "I")
    return metin.upper()


def _deneyim_basligi(d: dict) -> tuple[str, str]:
    sol = " · ".join(x for x in (d.get("pozisyon"), d.get("sirket")) if x)
    return sol, d.get("tarih") or ""


def _egitim_satiri(e: dict) -> str:
    return " · ".join(str(x) for x in (e.get("okul"), e.get("bolum"), e.get("not")) if x)


def docx_yaz(baslik: Baslik, cv: UyarlanmisCV) -> bytes:
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    b = _bolum_adlari(cv)
    belge = docx.Document()
    stil = belge.styles["Normal"]
    stil.font.name, stil.font.size = "Calibri", Pt(10.5)
    for bolum in belge.sections:
        bolum.left_margin = bolum.right_margin = bolum.top_margin = bolum.bottom_margin = Pt(50)

    def baslik_ekle(metin: str) -> None:
        p = belge.add_paragraph()
        p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(10), Pt(3)
        r = p.add_run(_buyuk(metin, cv))
        r.bold, r.font.size, r.font.color.rgb = True, Pt(11), RGBColor(0x1F, 0x3A, 0x5F)

    if baslik.ad:
        p = belge.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(baslik.ad)
        r.bold, r.font.size = True, Pt(18)
    if cv.unvan:
        p = belge.add_paragraph(cv.unvan)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if baslik.iletisim:
        p = belge.add_paragraph(" | ".join(baslik.iletisim))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    if cv.ozet:
        baslik_ekle(b["ozet"])
        belge.add_paragraph(cv.ozet)
    if cv.beceriler:
        baslik_ekle(b["beceri"])
        belge.add_paragraph(" • ".join(cv.beceriler))
    if cv.deneyim:
        baslik_ekle(b["deneyim"])
        for d in cv.deneyim:
            sol, tarih = _deneyim_basligi(d)
            p = belge.add_paragraph()
            p.paragraph_format.space_after = Pt(1)
            p.add_run(sol).bold = True
            if tarih:
                p.add_run(f"   {tarih}").italic = True
            for madde in d.get("maddeler", []):
                belge.add_paragraph(madde, style="List Bullet")
    if cv.egitim:
        baslik_ekle(b["egitim"])
        for e in cv.egitim:
            p = belge.add_paragraph()
            p.add_run(_egitim_satiri(e)).bold = True
            if e.get("tarih"):
                p.add_run(f"   {e['tarih']}").italic = True
    for blok in cv.diger:
        if blok.get("maddeler"):
            baslik_ekle(blok.get("baslik", ""))
            for madde in blok["maddeler"]:
                belge.add_paragraph(madde, style="List Bullet")

    tampon = io.BytesIO()
    belge.save(tampon)
    return tampon.getvalue()


def pdf_yaz(baslik: Baslik, cv: UyarlanmisCV) -> bytes:
    from fpdf import FPDF

    font = next(((n, k) for n, k in _FONTLAR if Path(n).exists() and Path(k).exists()), None)
    if font is None:
        raise RuntimeError("PDF için Unicode font bulunamadı (Arial/DejaVu). DOCX çıktısını kullanın.")

    b = _bolum_adlari(cv)
    pdf = FPDF(format="A4")
    pdf.set_margins(18, 16, 18)
    pdf.set_auto_page_break(True, 16)
    pdf.add_font("cv", "", font[0])
    pdf.add_font("cv", "B", font[1])
    pdf.add_page()
    genislik = pdf.w - pdf.l_margin - pdf.r_margin

    def yaz(metin: str, boyut: float = 10, kalin: bool = False, hiza: str = "L", h: float = 5) -> None:
        pdf.set_font("cv", "B" if kalin else "", boyut)
        pdf.multi_cell(genislik, h, metin, align=hiza, new_x="LMARGIN", new_y="NEXT")

    def bolum(metin: str) -> None:
        pdf.ln(3)
        pdf.set_text_color(31, 58, 95)
        yaz(_buyuk(metin, cv), 11, True, h=6)
        pdf.set_draw_color(31, 58, 95)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1.5)

    def madde(metin: str) -> None:
        pdf.set_font("cv", "", 10)
        pdf.set_x(pdf.l_margin + 3)
        pdf.multi_cell(genislik - 3, 5, f"•  {metin}", new_x="LMARGIN", new_y="NEXT")

    if baslik.ad:
        yaz(baslik.ad, 18, True, "C", 9)
    if cv.unvan:
        yaz(cv.unvan, 11, hiza="C", h=6)
    if baslik.iletisim:
        yaz(" | ".join(baslik.iletisim), 9, hiza="C")
    if cv.ozet:
        bolum(b["ozet"])
        yaz(cv.ozet)
    if cv.beceriler:
        bolum(b["beceri"])
        yaz(" • ".join(cv.beceriler))
    if cv.deneyim:
        bolum(b["deneyim"])
        for d in cv.deneyim:
            sol, tarih = _deneyim_basligi(d)
            yaz(f"{sol}   {tarih}".strip(), 10.5, True, h=6)
            for m in d.get("maddeler", []):
                madde(m)
            pdf.ln(1)
    if cv.egitim:
        bolum(b["egitim"])
        for e in cv.egitim:
            yaz(f"{_egitim_satiri(e)}   {e.get('tarih') or ''}".strip(), 10.5, True, h=6)
    for blok in cv.diger:
        if blok.get("maddeler"):
            bolum(blok.get("baslik", ""))
            for m in blok["maddeler"]:
                madde(m)
    return bytes(pdf.output())
