// CV Uyarlayıcı arayüzü. Hem tarayıcıda (site) hem masaüstü penceresinde (pywebview) çalışır.
"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const durum = { analiz: null, sonuc: null, gorunum: "sonra" };
const BASLIKLAR = { girdiler: "CV ve ilan", eslesme: "Eşleşme", sonuc: "Uyarlanmış CV", ayarlar: "Ayarlar" };

// ------------------------------------------------------------------ yardımcılar
function kacis(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(yol, secenek = {}) {
  const yanit = await fetch(yol, secenek);
  if (!yanit.ok) {
    let mesaj = `Sunucu hatası (${yanit.status})`;
    try {
      const j = await yanit.json();
      if (typeof j.detail === "string") mesaj = j.detail;
      else if (Array.isArray(j.detail)) mesaj = alanHatasi(j.detail[0]);
    } catch { /* gövde JSON değil */ }
    throw new Error(mesaj);
  }
  return yanit;
}

function alanHatasi(h) {
  const alan = h?.loc?.at(-1);
  const ad = { cv: "CV metni", ilan: "İlan metni" }[alan] || alan;
  if (h?.type === "string_too_short") return `${ad} çok kısa. En az birkaç satır gerekli.`;
  if (h?.type === "string_too_long") return `${ad} çok uzun (en fazla 30.000 karakter).`;
  return h?.msg || "Geçersiz istek";
}

let bildirimZaman;
function bildir(metin, hata = false) {
  const b = $("#bildirim");
  b.textContent = metin;
  b.classList.toggle("hata", hata);
  b.hidden = false;
  clearTimeout(bildirimZaman);
  bildirimZaman = setTimeout(() => (b.hidden = true), hata ? 7000 : 3500);
}

function bekle(acik, metin) {
  $("#perde").hidden = !acik;
  if (metin) $("#perde-metin").textContent = metin;
  $$("button.birincil, button.ikincil").forEach((b) => (b.disabled = acik));
}

// ------------------------------------------------------------------ gezinme
function git(ekran) {
  $$(".ekran").forEach((e) => (e.hidden = e.id !== `ekran-${ekran}`));
  $$(".adim").forEach((a) => a.classList.toggle("aktif", a.dataset.ekran === ekran));
  $("#baslik").textContent = BASLIKLAR[ekran];
  $(".ekran:not([hidden])").scrollTop = 0;
}

function adimlariGuncelle() {
  const [, eslesme, sonuc] = $$(".adimlar .adim");
  eslesme.disabled = !durum.analiz && !durum.sonuc;
  sonuc.disabled = !durum.sonuc;
  $$(".adimlar .adim")[0].classList.toggle("bitti", !!(durum.analiz || durum.sonuc));
  eslesme.classList.toggle("bitti", !!durum.sonuc);
}

$$(".adim").forEach((a) => a.addEventListener("click", () => git(a.dataset.ekran)));
$$("[data-git]").forEach((b) => b.addEventListener("click", () => git(b.dataset.git)));

// ------------------------------------------------------------------ CV dosyası
const birak = $("#birak");
async function dosyaOku(dosya) {
  if (!dosya) return;
  const form = new FormData();
  form.append("dosya", dosya);
  $("#birak-metin").textContent = "Okunuyor…";
  try {
    const j = await (await api("/api/cv/oku", { method: "POST", body: form })).json();
    $("#cv").value = j.metin;
    if (j.ad && !$("#ad").value) $("#ad").value = j.ad;
    birak.classList.add("yuklendi");
    $("#birak-metin").textContent = `${dosya.name} okundu. Metni aşağıda düzeltebilirsin.`;
  } catch (e) {
    birak.classList.remove("yuklendi");
    $("#birak-metin").innerHTML = "<strong>Dosyayı buraya bırak</strong> ya da seçmek için tıkla";
    bildir(e.message, true);
  }
}
$("#dosya").addEventListener("change", (e) => dosyaOku(e.target.files[0]));
birak.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("#dosya").click(); } });
["dragenter", "dragover"].forEach((t) => birak.addEventListener(t, (e) => { e.preventDefault(); birak.classList.add("uzerinde"); }));
["dragleave", "drop"].forEach((t) => birak.addEventListener(t, () => birak.classList.remove("uzerinde")));
birak.addEventListener("drop", (e) => { e.preventDefault(); dosyaOku(e.dataTransfer.files[0]); });

$("#ornek").addEventListener("click", async () => {
  const j = await (await api("/api/ornek")).json();
  $("#cv").value = j.cv;
  $("#ilan").value = j.ilan;
  $("#ad").value = "";
  bildir("Örnek CV ve ilan yüklendi. Kişiler ve şirketler hayalidir.");
});

function girdiler() {
  return { cv: $("#cv").value.trim(), ilan: $("#ilan").value.trim(), ad: $("#ad").value.trim(), dil: $("#dil").value };
}

// ------------------------------------------------------------------ ölçer
function olcer() {
  const once = durum.sonuc?.once.skor ?? durum.analiz?.skor;
  const sonra = durum.sonuc?.sonra.skor;
  if (once == null) return;
  $("#olcer").hidden = false;
  $("#olcer-once").style.width = `${once}%`;
  $("#olcer-sonra").style.width = `${sonra ?? once}%`;
  $("#olcer-sonra").style.opacity = sonra == null ? ".0" : "1";
  $("#olcer-once").style.opacity = sonra == null ? "1" : ".45";
  $("#olcer-once").style.background = sonra == null ? "var(--kalem)" : "";
  $("#olcer-sayi").innerHTML = sonra == null ? `${once} / 100` : `<del>${once} →</del>${sonra} / 100`;
  $("#olcer").title = sonra == null ? "Mevcut CV'nin ilanla uyumu" : `Uyarlamadan önce ${once}, sonra ${sonra}`;
}

// ------------------------------------------------------------------ eşleşme ekranı
function eslesmeCiz(a) {
  $("#gereksinimler").innerHTML = a.gereksinimler.map((g) => `
    <li class="gereksinim ${g.durum}">
      <span class="g-metin"><mark>${kacis(g.metin)}</mark>${g.tercih ? '<span class="g-tercih">tercihen</span>' : ""}</span>
      <span class="g-skor" title="0-1 arası benzerlik">${g.skor.toFixed(2)}</span>
      ${g.durum === "eksik" ? '<span class="g-yakin">CV\'de karşılığı bulunamadı.</span>'
        : g.en_yakin ? `<span class="g-yakin">CV'de en yakın: <q>${kacis(g.en_yakin)}</q></span>` : ""}
    </li>`).join("") || '<li class="bos">İlanda gereksinim cümlesi bulunamadı. Madde madde yazılmış nitelikler gerekir.</li>';

  const etiketler = (liste, sinif, bos) => liste.length
    ? liste.map((b) => `<span class="etiket ${sinif}">${kacis(b)}</span>`).join("") : `<span class="bos">${bos}</span>`;
  $("#b-eslesen").innerHTML = etiketler(a.eslesen, "yesil", "Yok");
  $("#b-dolayli").innerHTML = etiketler(a.dolayli, "sari", "Yok");
  $("#b-eksik").innerHTML = etiketler(a.eksik, "pembe", "Eksik beceri yok");
  $("#yontem").textContent = a.embedding
    ? "Benzerlik, anlam (çok dilli embedding) ve kelime örtüşmesiyle bilgisayarında hesaplandı."
    : "Anlam modeli henüz hazır değil; benzerlik yalnızca kelime örtüşmesiyle hesaplandı.";
}

function eslesmeGoster() {
  const a = durum.sonuc ? durum.sonuc[durum.gorunum] : durum.analiz;
  $("#once-sonra").hidden = !durum.sonuc;
  $$("#once-sonra button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.gorunum === durum.gorunum)));
  $("#eslesme-eylem").hidden = !!durum.sonuc;
  eslesmeCiz(a);
}
$$("#once-sonra button").forEach((b) => b.addEventListener("click", () => { durum.gorunum = b.dataset.gorunum; eslesmeGoster(); }));

$("#olc").addEventListener("click", async () => {
  const g = girdiler();
  bekle(true, "Uyum ölçülüyor");
  try {
    durum.analiz = await (await api("/api/cv/analiz", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(g) })).json();
    durum.sonuc = null;
    olcer(); adimlariGuncelle(); eslesmeGoster(); git("eslesme");
  } catch (e) { bildir(e.message, true); } finally { bekle(false); }
});

// ------------------------------------------------------------------ uyarlama
async function uyarla() {
  const g = girdiler();
  bekle(true, "Model CV'yi yeniden yazıyor");
  try {
    durum.sonuc = await (await api("/api/cv/uyarla", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(g) })).json();
    durum.gorunum = "sonra";
    olcer(); adimlariGuncelle(); eslesmeGoster(); sonucCiz(); git("sonuc");
  } catch (e) {
    bildir(e.message, true);
    if (/bağlantı|anahtar|GEMINI/i.test(e.message)) git("ayarlar");
  } finally { bekle(false); }
}
$("#uyarla").addEventListener("click", uyarla);
$("#uyarla2").addEventListener("click", uyarla);

function sonucCiz() {
  const { baslik, cv } = durum.sonuc;
  // Uydurma şüphesi taşıyan ifadeler kâğıtta da pembe ile işaretlenir
  const supheler = cv.uydurma_supheleri.map((s) => s.split(": ").slice(1).join(": ")).filter(Boolean);
  const isaretle = (metin) => {
    let html = kacis(metin);
    for (const s of supheler) {
      const desen = new RegExp(`(?<![\\p{L}\\d])(${kacis(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})(?![\\p{L}\\d])`, "giu");
      html = html.replace(desen, '<span class="supheli" title="Orijinal CV\'de yok">$1</span>');
    }
    return html;
  };
  const tr = !/\b(the|and|with)\b/i.test(cv.ozet);
  const bolum = (t, e) => `<h4>${tr ? t : e}</h4>`;
  const maddeler = (l) => l?.length ? `<ul>${l.map((m) => `<li>${isaretle(m)}</li>`).join("")}</ul>` : "";

  let html = "";
  if (baslik.ad) html += `<h3 class="k-ad">${kacis(baslik.ad)}</h3>`;
  if (cv.unvan) html += `<p class="k-unvan">${isaretle(cv.unvan)}</p>`;
  if (baslik.iletisim.length) html += `<p class="k-iletisim">${baslik.iletisim.map(kacis).join("  |  ")}</p>`;
  if (cv.ozet) html += bolum("Profesyonel Özet", "Professional Summary") + `<p>${isaretle(cv.ozet)}</p>`;
  if (cv.beceriler.length) html += bolum("Beceriler", "Skills") + `<p>${cv.beceriler.map(isaretle).join("  •  ")}</p>`;
  if (cv.deneyim.length) {
    html += bolum("Deneyim", "Experience");
    for (const d of cv.deneyim) {
      html += `<div class="k-is"><strong>${isaretle([d.pozisyon, d.sirket].filter(Boolean).join(", "))}</strong><span class="k-tarih">${kacis(d.tarih)}</span></div>${maddeler(d.maddeler)}`;
    }
  }
  if (cv.egitim.length) {
    html += bolum("Eğitim", "Education");
    for (const e of cv.egitim) {
      html += `<div class="k-is"><strong>${kacis([e.okul, e.bolum, e.not].filter(Boolean).join(", "))}</strong><span class="k-tarih">${kacis(e.tarih)}</span></div>`;
    }
  }
  for (const b of cv.diger) if (b.maddeler?.length) html += `<h4>${kacis(b.baslik)}</h4>${maddeler(b.maddeler)}`;
  $("#kagit").innerHTML = html;

  const liste = (sec, l, bos) => ($(sec).innerHTML = l.length ? l.map((x) => `<li>${kacis(x)}</li>`).join("") : `<li class="bos">${bos}</li>`);
  $("#kutu-uyari").hidden = !cv.uydurma_supheleri.length;
  liste("#uyarilar", cv.uydurma_supheleri, "");
  liste("#degisiklikler", cv.degisiklikler, "Model değişiklik açıklaması vermedi.");
  liste("#oneriler", cv.oneriler, "Öneri yok.");
  $("#model-notu").textContent = `Yeniden yazan model: ${cv.model}`;
}

// ------------------------------------------------------------------ indirme
function dosyaAdi(bicim) {
  const ad = (durum.sonuc.baslik.ad || "CV").replace(/[^\p{L}\d]+/gu, "_").replace(/^_|_$/g, "");
  return `${ad}_uyarlanmis.${bicim}`;
}

$$("[data-bicim]").forEach((b) => b.addEventListener("click", async () => {
  const bicim = b.dataset.bicim;
  const { baslik, cv } = durum.sonuc;
  try {
    const blob = await (await api(`/api/cv/belge?bicim=${bicim}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ baslik, cv }) })).blob();
    const ad = dosyaAdi(bicim);
    if (window.pywebview?.api?.kaydet) {
      // Masaüstü: Windows'un Kaydet penceresi
      const veri = await new Promise((ok) => { const r = new FileReader(); r.onload = () => ok(r.result.split(",")[1]); r.readAsDataURL(blob); });
      const yol = await window.pywebview.api.kaydet(ad, veri);
      if (yol) bildir(`Kaydedildi: ${yol}`);
    } else {
      const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: ad });
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      bildir(`${ad} indirildi.`);
    }
  } catch (e) { bildir(e.message, true); }
}));

// ------------------------------------------------------------------ ayarlar ve durum
async function durumYenile() {
  try {
    const d = await (await api("/api/durum")).json();
    const el = $("#durum");
    const embed = { hazir: "", yukleniyor: " · anlam modeli yükleniyor", yok: " · anlam modeli yok" }[d.embedding];
    el.className = `durum ${d.model ? "iyi" : "kotu"}`;
    $("#durum-metin").textContent = d.model ? `Model: ${d.model}${embed}` : "Model bağlı değil";
    el.title = d.model ? "" : "CV'yi uyarlamak için Ayarlar'dan bir model bağla. Uyum ölçümü modelsiz çalışır.";
    $("#model-uyari").hidden = !!d.model;
    $("#ayar-url").value = d.llm_base_url || "";
    $("#anahtar-durum").textContent = d.gemini_anahtari_var ? "· Şu an bir anahtar tanımlı." : "";
    const dis = d.disaridan.length;
    $("#ayar-disaridan").hidden = !dis;
    $("#ayar-disaridan").textContent = dis ? `${d.disaridan.join(", ")} .env dosyasından geliyor; buradaki değer onu geçersiz kılmaz.` : "";
    if (d.embedding === "yukleniyor") setTimeout(durumYenile, 3000);
  } catch {
    $("#durum").className = "durum kotu";
    $("#durum-metin").textContent = "Sunucuya ulaşılamıyor";
  }
}

$("#ayara-git").addEventListener("click", () => { git("ayarlar"); $("#ayar-anahtar").focus(); });

$("#ayar-formu").addEventListener("submit", async (e) => {
  e.preventDefault();
  const govde = { llm_base_url: $("#ayar-url").value.trim() };
  const anahtar = $("#ayar-anahtar").value.trim();
  if (anahtar) govde.gemini_api_key = anahtar;
  try {
    await api("/api/ayarlar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(govde) });
    $("#ayar-anahtar").value = "";
    $("#ayar-sonuc").textContent = "Ayarlar kaydedildi.";
    durumYenile();
  } catch (err) { $("#ayar-sonuc").textContent = err.message; }
});

durumYenile();
