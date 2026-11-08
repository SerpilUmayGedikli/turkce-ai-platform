// CV Uyarlayıcı arayüzü. Hem tarayıcıda (site) hem masaüstü penceresinde (pywebview) çalışır.
"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const MAKS_DENEME = 5;
// denemeler: her "uyarla" sonucu; sonuc: kullanıcının seçtiği deneme (indirilen o olur)
const durum = { analiz: null, sonuc: null, gorunum: "sonra", denemeler: [], secili: 0, girdi: null };
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
  return { cv: $("#cv").value.trim(), ilan: $("#ilan").value.trim(), ad: $("#ad").value.trim(), dil: $("#dil").value,
    mod: $("input[name=mod]:checked")?.value || "hedef", ek: $("#ek").value.trim() };
}

// Ek bilgiler (GitHub'da olmayan projeler) her ilanda aynıdır: bu tarayıcıda hatırlanır
try { $("#ek").value = localStorage.getItem("cv-ek") || ""; } catch { /* depolama kapalı */ }
$("#ek").addEventListener("input", () => { try { localStorage.setItem("cv-ek", $("#ek").value); } catch { /* yok say */ } });

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
  const anahtarlar = a.anahtarlar || [];
  $("#ats").textContent = anahtarlar.length ? `${anahtarlar.filter((k) => k.var).length}/${anahtarlar.length} · %${a.ats}` : "";
  $("#b-anahtar").innerHTML = anahtarlar.length
    ? anahtarlar.map((k) => `<span class="etiket ${k.var ? "yesil" : "pembe"}" title="${k.var ? "CV'nde geçiyor" : "CV'nde geçmiyor"}">${kacis(k.ifade)}</span>`).join("")
    : '<span class="bos">Anahtar kelime çıkarılamadı.</span>';
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
    durum.sonuc = null; durum.denemeler = [];
    olcer(); adimlariGuncelle(); eslesmeGoster(); git("eslesme");
  } catch (e) { bildir(e.message, true); } finally { bekle(false); }
});

// ------------------------------------------------------------------ uyarlama
// İlk "CV'yi uyarla" denemeleri sıfırlar; "Bir daha uyarla" seçili denemenin zayıf kalan
// gereksinimlerini modele geri verir ve yeni bir deneme ekler (en fazla MAKS_DENEME).
async function uyarla(tekrar = false) {
  if (!tekrar) { durum.girdi = girdiler(); durum.denemeler = []; }
  if (durum.denemeler.length >= MAKS_DENEME) return;
  const g = { ...durum.girdi };
  if (tekrar && durum.sonuc) {
    const s = durum.sonuc;
    g.onceki = {
      skor: s.sonra.skor,
      zayiflar: [
        ...s.sonra.gereksinimler.filter((x) => x.durum !== "karşılanıyor").map((x) => x.metin),
        ...[...new Set([...s.sonra.eksik, ...(s.sonra.anahtarlar || []).filter((k) => !k.var).map((k) => k.ifade)])]
          .map((x) => `CV'de geçmeyen ilan anahtar kelimesi (birebir geçir): ${x}`),
      ],
      projeler: (s.cv.projeler || []).filter((p) => p.yeni).map((p) => p.ad),
      cv: s.cv, // model bu sürümün ÜZERİNE çalışır: iyi olanı bırakır, zayıfı düzeltir
    };
  }
  const no = durum.denemeler.length + 1;
  bekle(true, g.mod === "hedef" ? `Deneme ${no}/${MAKS_DENEME}: model CV'yi uyarlıyor ve projeler tasarlıyor` : `Deneme ${no}/${MAKS_DENEME}: model CV'yi yeniden yazıyor`);
  try {
    const s = await (await api("/api/cv/uyarla", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(g) })).json();
    durum.denemeler.push(s);
    denemeSec(durum.denemeler.length - 1);
    adimlariGuncelle(); git("sonuc");
    if (tekrar) bildir(`Deneme ${no}: uyum ${s.sonra.skor} / 100`);
  } catch (e) {
    bildir(e.message, true);
    if (/bağlantı|anahtar|GEMINI/i.test(e.message)) git("ayarlar");
  } finally { bekle(false); denemeleriCiz(); }
}
$("#uyarla").addEventListener("click", () => uyarla(false));
$("#uyarla2").addEventListener("click", () => uyarla(false));
$("#tekrar").addEventListener("click", () => uyarla(true));

function denemeSec(i) {
  durum.secili = i;
  durum.sonuc = durum.denemeler[i];
  durum.gorunum = "sonra";
  olcer(); eslesmeGoster(); sonucCiz(); denemeleriCiz();
}

function denemeleriCiz() {
  const d = durum.denemeler;
  const enIyi = d.reduce((e, s, i) => (s.sonra.skor > d[e].sonra.skor ? i : e), 0);
  $("#denemeler").innerHTML = d.map((s, i) => `
    <button role="tab" data-i="${i}" aria-selected="${i === durum.secili}" class="deneme${i === enIyi && d.length > 1 ? " en-iyi" : ""}">
      <span class="d-no">Deneme ${i + 1}</span><span class="d-skor">${s.sonra.skor}</span>
      ${i === enIyi && d.length > 1 ? '<span class="d-rozet">en yüksek</span>' : ""}
    </button>`).join("");
  $$("#denemeler .deneme").forEach((b) => b.addEventListener("click", () => denemeSec(+b.dataset.i)));
  const kalan = MAKS_DENEME - d.length;
  const t = $("#tekrar");
  t.disabled = kalan <= 0 || !d.length;
  t.textContent = kalan > 0 ? `Bir daha uyarla (${kalan} hak kaldı)` : "Deneme hakkı bitti";
  t.title = "Seçili denemenin üzerine çalışır: iyi olan kısımlar aynen kalır, yalnızca zayıf kalan gereksinimler düzeltilir.";
}

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
  if (cv.beceriler.length) {
    // Kategorili satırlar ("Programlama: Python, SQL") alt alta, düz liste tek satırda
    const kategorili = cv.beceriler.some((b) => b.includes(":"));
    html += bolum("Beceriler", "Skills") + (kategorili
      ? cv.beceriler.map((b) => { const [k, ...d] = b.split(":"); return d.length ? `<p class="k-beceri"><strong>${kacis(k)}:</strong>${isaretle(d.join(":"))}</p>` : `<p class="k-beceri">${isaretle(b)}</p>`; }).join("")
      : `<p>${cv.beceriler.map(isaretle).join("  •  ")}</p>`);
  }
  if (cv.deneyim.length) {
    html += bolum("Deneyim", "Experience");
    for (const d of cv.deneyim) {
      html += `<div class="k-is"><strong>${isaretle([d.pozisyon, d.sirket].filter(Boolean).join(", "))}</strong><span class="k-tarih">${kacis(d.tarih)}</span></div>${maddeler(d.maddeler)}`;
    }
  }
  if (cv.projeler?.length) {
    html += bolum("Projeler", "Projects");
    for (const p of cv.projeler) {
      const tek = (p.teknolojiler || []).join(", ");
      const rozet = p.kaynak === "yeni" ? '<span class="k-rozet" title="Bu proje CV\'nde yoktu: yapıp GitHub\'a koyman gerekiyor">yapılacak</span>'
        : p.kaynak === "ek" ? '<span class="k-rozet ek" title="Ek bilgilerinden eklendi: GitHub\'a koy">GitHub\'a koy</span>' : "";
      html += `<div class="k-is${p.kaynak === "yeni" ? " k-yeni" : p.kaynak === "ek" ? " k-ek" : ""}"><strong>${isaretle(p.ad)}${tek ? ` <span class="k-tek">· ${kacis(tek)}</span>` : ""}</strong>${rozet}</div>${maddeler(p.maddeler)}`;
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
  $("#model-notu").textContent = `Yeniden yazan model: ${cv.model}` +
    (cv.tur > 1 ? " · Skor 90'ın altında kaldığı için otomatik ikinci turla iyileştirildi." : "");
  const sorular = cv.guclendirme_sorulari || [];
  $("#kutu-sorular").hidden = !sorular.length;
  $("#sorular").innerHTML = sorular.map((s) => `<li><strong>${kacis(s.soru)}</strong>${s.madde ? `<span class="s-madde">${kacis(s.madde)}</span>` : ""}</li>`).join("");

  const eklenen = cv.eklenen_beceriler || [];
  $("#kutu-eklenen").hidden = !eklenen.length;
  $("#eklenenler").innerHTML = eklenen.map((b) => `<span class="etiket sari">${kacis(b)}</span>`).join("");
  yapilacaklarCiz(cv.yapilacaklar || []);
  planCiz();
}

// Her ilan gereksinimi için: önce ne durumdaydı, sonra ne oldu, ne yapıldı
function planCiz() {
  const { once, sonra, cv } = durum.sonuc;
  const degisen = new Set(cv.degisen_korunan || []);
  const yeniProje = (cv.projeler || []).some((p) => p.yeni);
  const satirlar = once.gereksinimler.map((g, i) => {
    const s = sonra.gereksinimler[i] || g;
    let tur, metin;
    if (g.durum === "karşılanıyor") {
      [tur, metin] = degisen.has(g.en_yakin) ? ["ifade", "Zaten vardı, cümle yeniden ifade edildi"] : ["koru", "Zaten vardı, dokunulmadı"];
    } else if (s.durum === "karşılanıyor") {
      [tur, metin] = g.durum === "kısmen" ? ["guclu", "Kısmen vardı, güçlendirildi"] : ["ekle", yeniProje ? "Yoktu, projeyle eklendi" : "Yoktu, eklendi"];
    } else {
      [tur, metin] = ["zayif", s.durum === "kısmen" ? "Hâlâ kısmen karşılanıyor" : "Hâlâ eksik"];
    }
    return { tur, metin, g: g.metin };
  });
  const say = (t) => satirlar.filter((x) => x.tur === t).length;
  $("#plan-ozet").textContent = `${say("koru") + say("ifade")} zaten vardı · ${say("guclu")} güçlendirildi · ${say("ekle")} eklendi · ${say("zayif")} hâlâ zayıf`;
  const sira = { zayif: 0, ekle: 1, guclu: 2, ifade: 3, koru: 4 };
  $("#plan").innerHTML = satirlar.sort((a, b) => sira[a.tur] - sira[b.tur]).map((x) =>
    `<li class="plan-${x.tur}"><span class="p-etiket">${kacis(x.metin)}</span><span class="p-metin">${kacis(x.g)}</span></li>`).join("")
    || '<li class="bos">İlanda gereksinim bulunamadı.</li>';
}

function yapilacaklarCiz(liste) {
  $("#yapilacaklar-bolumu").hidden = !liste.length;
  $("#yapilacaklar").innerHTML = liste.map((y) => {
    const gh = y.github || {};
    const readme = (gh.readme || []).map((r) => `<li>${kacis(r)}</li>`).join("");
    const yayinla = y.tur === "yayinla";
    return `<li class="y-kart${yayinla ? " yayinla" : ""}">
      <div class="y-ust"><h3>${kacis(y.proje)}</h3><span class="y-tur">${yayinla ? "Bilgisayarında var · GitHub'a koy" : "Yap ve GitHub'a koy"}</span>${y.sure ? `<span class="y-sure">${kacis(y.sure)}</span>` : ""}</div>
      <p class="y-neden">${kacis(y.neden)}</p>
      ${(y.kapsadigi || []).length ? `<div class="etiketler">${y.kapsadigi.map((k) => `<span class="etiket yesil">${kacis(k)}</span>`).join("")}</div>` : ""}
      <div class="y-govde">
        <div><h4>${yayinla ? "Yayınlamadan önce" : "Nasıl yapacaksın"}</h4><ol>${(y.adimlar || []).map((a) => `<li>${kacis(a.replace(/^\d+[.)]\s*/, ""))}</li>`).join("")}</ol></div>
        <div><h4>Sonra GitHub'a koy</h4>
          ${gh.repo ? `<p class="y-repo"><code>github.com/&lt;kullanıcı-adın&gt;/${kacis(gh.repo)}</code></p>` : ""}
          ${readme ? `<p class="y-alt">README'de olsun:</p><ul>${readme}</ul>` : ""}
        </div>
      </div>
    </li>`;
  }).join("");
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
    const sec = $("#ayar-model");
    if (!sec.options.length || document.activeElement !== sec) {
      sec.replaceChildren(...d.gemini_secenekleri.map((m) => {
        const o = new Option(`${m.ad} · ${m.not}`, m.id);
        o.selected = m.id === (d.gemini_model || d.gemini_varsayilan);
        return o;
      }));
    }
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
  const govde = { llm_base_url: $("#ayar-url").value.trim(), gemini_model: $("#ayar-model").value };
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
