// İş ilanı siteleri ve kaydedilen ilanlar. app.js'teki yardımcıları ($, api, bildir, git, uyarla) kullanır.
// Masaüstünde her site kendi penceresinde (kalıcı oturumla) açılır; tarayıcıda yeni sekmede.
"use strict";

const masaustu = () => !!window.pywebview?.api?.site_ac;
const JSON_BASLIK = { "Content-Type": "application/json" };
let platformVerisi = null;

async function platformlariYukle() {
  try {
    platformVerisi = await (await api("/api/platformlar")).json();
    if (document.activeElement !== $("#arama-q")) $("#arama-q").value = platformVerisi.arama.q || "";
    if (document.activeElement !== $("#arama-konum")) $("#arama-konum").value = platformVerisi.arama.konum || "";
    platformlariCiz();
  } catch (e) { bildir(e.message, true); }
  $("#tarayici-notu").hidden = masaustu();
}

function platformlariCiz() {
  turCiz();
  $("#platformlar").innerHTML = platformVerisi.siteler.map((s) => `
    <div class="platform${s.secili ? " secili" : ""}" data-id="${kacis(s.id)}">
      <span class="p-logo" style="background:${kacis(s.renk)}">${kacis(s.ad[0])}</span>
      <div class="p-bilgi"><strong>${kacis(s.ad)}</strong><span>${kacis(s.bolge)}${s.anahtar_kelime_alir ? "" : " · aramayı sitede yap"}</span></div>
      <label class="p-sec" title="Seçili sitelerde ara'ya dahil et"><input type="checkbox" ${s.secili ? "checked" : ""}></label>
      <div class="p-eylem">
        <button class="ikincil kucuk" data-ac="tarayici" title="Kendi tarayıcında (Chrome, Edge...) aç">Sitede aç</button>
        ${masaustu() ? '<button class="baglanti" data-ac="adres" title="Uygulama penceresinde aç: sağ altta ＋ ilan ekle düğmesi olur">Pencerede aç</button>' : ""}
        <button class="baglanti" data-ac="giris">Giriş yap</button>
        ${s.ozel ? '<button class="baglanti sil" data-ac="sil">Kaldır</button>' : ""}
      </div>
    </div>`).join("");
  $$("#platformlar .platform").forEach((kart) => {
    const s = platformVerisi.siteler.find((x) => x.id === kart.dataset.id);
    kart.querySelector("input").addEventListener("change", async (e) => {
      s.secili = e.target.checked;
      kart.classList.toggle("secili", s.secili);
      turCiz();
      await api("/api/platformlar", { method: "POST", headers: JSON_BASLIK,
        body: JSON.stringify({ secili: platformVerisi.siteler.filter((x) => x.secili).map((x) => x.id) }) });
    });
    kart.querySelector('[data-ac="tarayici"]').addEventListener("click", () => tarayicidaAc(s.adres));
    kart.querySelector('[data-ac="adres"]')?.addEventListener("click", () => siteAc(s, s.adres));
    kart.querySelector('[data-ac="giris"]').addEventListener("click", () => siteAc(s, s.giris));
    kart.querySelector('[data-ac="sil"]')?.addEventListener("click", async () => {
      platformVerisi = await (await api("/api/platformlar", { method: "POST", headers: JSON_BASLIK, body: JSON.stringify({ ozel_sil: s.id }) })).json();
      platformlariCiz();
    });
  });
}

function siteAc(s, adres) {
  if (masaustu()) return window.pywebview.api.site_ac(s.id, adres, s.ad);
  return !!window.open(adres, "_blank", "noopener");
}

// Kendi tarayıcında aç (orada zaten girişliysen o oturum kullanılır)
function tarayicidaAc(adres) {
  if (window.pywebview?.api?.tarayicida_ac) return window.pywebview.api.tarayicida_ac(adres);
  return !!window.open(adres, "_blank", "noopener");
}

// ------------------------------------------------------------------ bugünkü tur
const yerelBugun = () => new Date().toLocaleDateString("sv"); // YYYY-MM-DD, yerel saat

function turCiz() {
  const v = platformVerisi;
  const liste = v.siteler.filter((s) => s.secili);
  const girilen = liste.filter((s) => s.bugun_girildi).length;
  const tarih = new Date(`${v.bugun}T12:00:00`);
  $("#tur-tarih").textContent = tarih.toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" });
  $("#tur-sayi").textContent = liste.length ? `${girilen}/${liste.length}` : "";
  $("#tur-seri").textContent = v.seri > 1 ? `${v.seri} gündür her gün` : v.seri === 1 ? "Seri başladı" : "";
  $("#tur-dolu").style.width = liste.length ? `${(100 * girilen) / liste.length}%` : "0";
  $("#tur").classList.toggle("tamam", liste.length > 0 && girilen === liste.length);
  $("#tur-liste").innerHTML = liste.map((s) => `
    <li class="${s.bugun_girildi ? "girildi" : ""}" data-id="${kacis(s.id)}">
      <label class="tur-tik"><input type="checkbox" ${s.bugun_girildi ? "checked" : ""}><span class="p-logo kucuk" style="background:${kacis(s.renk)}">${kacis(s.ad[0])}</span><strong>${kacis(s.ad)}</strong></label>
      <button class="ikincil kucuk" data-ac="tarayici">Sitede aç</button>
      ${masaustu() ? '<button class="baglanti" data-ac="pencere">Pencerede aç</button>' : ""}
    </li>`).join("") || '<li class="bos">Aşağıdaki platform kartlarından günlük turuna eklemek istediklerini işaretle.</li>';
  const enCok = Math.max(1, ...v.son7.map((g) => g.sayi));
  $("#son7").innerHTML = v.son7.map((g) => {
    const gun = new Date(`${g.tarih}T12:00:00`).toLocaleDateString("tr-TR", { weekday: "short" });
    return `<span class="gun${g.tarih === v.bugun ? " bugun" : ""}" title="${g.tarih}: ${g.sayi} site"><i style="height:${Math.round((g.sayi / enCok) * 100)}%"></i><b>${gun}</b></span>`;
  }).join("");

  $$("#tur-liste li[data-id]").forEach((li) => {
    const s = v.siteler.find((x) => x.id === li.dataset.id);
    li.querySelector("input").addEventListener("change", async (e) => {
      try {
        platformVerisi = await (await api("/api/platformlar/ziyaret", { method: "POST", headers: JSON_BASLIK,
          body: JSON.stringify({ id: s.id, girdim: e.target.checked }) })).json();
        turCiz();
        if (platformVerisi.bugun_tamam && e.target.checked) bildir("Bugünkü turu tamamladın.");
      } catch (err) { bildir(err.message, true); e.target.checked = !e.target.checked; }
    });
    li.querySelector('[data-ac="tarayici"]').addEventListener("click", () => tarayicidaAc(s.adres));
    li.querySelector('[data-ac="pencere"]')?.addEventListener("click", () => siteAc(s, s.adres));
  });
}

// Uygulama gece yarısını geçerek açık kalırsa ya da ertesi gün öne gelirse tur yenilensin
function gunDegistiyseYenile() {
  if (platformVerisi && platformVerisi.bugun !== yerelBugun() && !$("#ekran-ilanlar").hidden) platformlariYukle();
}
document.addEventListener("visibilitychange", () => { if (!document.hidden) gunDegistiyseYenile(); });
window.addEventListener("focus", gunDegistiyseYenile);
setInterval(gunDegistiyseYenile, 60_000);

$("#arama-formu").addEventListener("submit", async (e) => {
  e.preventDefault();
  const arama = { q: $("#arama-q").value.trim(), konum: $("#arama-konum").value.trim() };
  try {
    platformVerisi = await (await api("/api/platformlar", { method: "POST", headers: JSON_BASLIK, body: JSON.stringify({ arama }) })).json();
    platformlariCiz();
    const secili = platformVerisi.siteler.filter((s) => s.secili);
    if (!secili.length) return bildir("Önce aşağıdan en az bir site işaretle.", true);
    let acilan = 0;
    for (const s of secili) { if (await siteAc(s, s.adres)) acilan++; }
    bildir(masaustu() ? `${secili.length} site ayrı pencerelerde açıldı.`
      : acilan < secili.length ? `Tarayıcı ${secili.length - acilan} sekmeyi engelledi. Açılır pencerelere izin ver ya da siteleri tek tek aç.`
      : `${acilan} site yeni sekmelerde açıldı.`);
  } catch (err) { bildir(err.message, true); }
});

$("#site-formu").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    platformVerisi = await (await api("/api/platformlar", { method: "POST", headers: JSON_BASLIK,
      body: JSON.stringify({ ozel_ekle: { ad: $("#site-ad").value, adres: $("#site-adres").value } }) })).json();
    $("#site-ad").value = $("#site-adres").value = "";
    platformlariCiz();
    bildir("Site eklendi.");
  } catch (err) { bildir(err.message, true); }
});

// ------------------------------------------------------------------ kaydedilen ilanlar
const DURUMLAR = { yeni: "Yeni", uyarlandi: "CV uyarlandı", basvuruldu: "Başvurdum", gecildi: "İlgilenmiyorum" };

function sayaciGuncelle(n) {
  $("#ilan-sayac").hidden = !n;
  $("#ilan-sayac").textContent = n;
}

async function ilanlariYukle() {
  try {
    const { ilanlar } = await (await api("/api/ilanlar/liste", { method: "POST", headers: JSON_BASLIK, body: JSON.stringify({ cv: $("#cv").value.trim() }) })).json();
    ilanlariCiz(ilanlar);
  } catch (e) { bildir(e.message, true); }
}

function skorSinifi(s) { return s == null ? "yok" : s >= 70 ? "iyi" : s >= 50 ? "orta" : "dusuk"; }

function ilanlariCiz(liste) {
  const cvVar = $("#cv").value.trim().length >= 20;
  $("#ilan-sayisi").textContent = liste.length ? `(${liste.length})` : "";
  sayaciGuncelle(liste.length);
  $("#siralama-notu").textContent = !liste.length ? "" : cvVar ? "CV'ne uyuma göre sıralı (bilgisayarında hesaplandı)"
    : "Uyuma göre sıralamak için önce CV ve ilan ekranına CV'ni ekle";
  $("#nasil-kart").classList.toggle("daralt", liste.length > 0);
  $("#ilan-listesi").innerHTML = liste.map((i) => `
    <li class="ilan ${i.durum === "gecildi" ? "soluk" : ""}" data-id="${kacis(i.id)}">
      <div class="i-skor ${skorSinifi(i.skor)}" title="${i.skor == null ? "CV yok" : `Uyum ${i.skor}/100 · ATS anahtar kelime %${i.ats} · ${i.karsilanan}/${i.gereksinim} gereksinim karşılanıyor`}">
        ${i.skor == null ? "–" : i.skor}<small>${i.skor == null ? "" : "uyum"}</small></div>
      <div class="i-govde">
        <div class="i-ust"><strong>${kacis(i.baslik)}</strong><span class="i-site">${kacis(i.site)} · ${kacis(i.eklendi.slice(0, 10))}</span></div>
        <p class="i-onizleme">${kacis(i.onizleme)}…</p>
        ${i.eksik?.length ? `<div class="etiketler"><span class="i-etiket-baslik">CV'nde eksik:</span>${i.eksik.map((k) => `<span class="etiket pembe">${kacis(k)}</span>`).join("")}</div>` : ""}
      </div>
      <div class="i-eylem">
        <button class="birincil kucuk" data-ac="uyarla">CV'yi bu ilana uyarla</button>
        <div class="i-alt">
          <select data-ac="durum" aria-label="Başvuru durumu">${Object.entries(DURUMLAR).map(([k, v]) => `<option value="${k}" ${i.durum === k ? "selected" : ""}>${v}</option>`).join("")}</select>
          ${i.url ? '<button class="baglanti" data-ac="ac">İlanı aç</button>' : ""}
          <button class="baglanti sil" data-ac="sil">Sil</button>
        </div>
      </div>
    </li>`).join("") || '<li class="bos">Henüz kaydedilmiş ilan yok.</li>';

  $$("#ilan-listesi .ilan").forEach((li) => {
    const i = liste.find((x) => x.id === li.dataset.id);
    li.querySelector('[data-ac="uyarla"]').addEventListener("click", () => ilanaUyarla(i));
    li.querySelector('[data-ac="durum"]').addEventListener("change", (e) =>
      api(`/api/ilanlar/${i.id}`, { method: "PATCH", headers: JSON_BASLIK, body: JSON.stringify({ durum: e.target.value }) })
        .then(() => li.classList.toggle("soluk", e.target.value === "gecildi")));
    li.querySelector('[data-ac="ac"]')?.addEventListener("click", () => {
      const site = platformVerisi?.siteler.find((s) => s.ad === i.site) || { id: "ilan", ad: i.site };
      siteAc(site, i.url);
    });
    li.querySelector('[data-ac="sil"]').addEventListener("click", async () => {
      await api(`/api/ilanlar/${i.id}`, { method: "DELETE" });
      ilanlariYukle();
    });
  });
}

async function ilanaUyarla(i) {
  try {
    const tam = await (await api(`/api/ilanlar/${i.id}`)).json();
    $("#ilan").value = tam.metin;
    if (i.durum === "yeni") api(`/api/ilanlar/${i.id}`, { method: "PATCH", headers: JSON_BASLIK, body: JSON.stringify({ durum: "uyarlandi" }) });
    if ($("#cv").value.trim().length < 20) {
      git("girdiler");
      return bildir("İlan yüklendi. Şimdi CV'ni ekle ve \"CV'yi uyarla\"ya bas.");
    }
    uyarla(false);
  } catch (e) { bildir(e.message, true); }
}

$("#ilan-formu").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/ilanlar", { method: "POST", headers: JSON_BASLIK, body: JSON.stringify({
      baslik: $("#ilan-baslik").value, url: $("#ilan-url").value, metin: $("#ilan-metin").value }) });
    $("#ilan-baslik").value = $("#ilan-url").value = $("#ilan-metin").value = "";
    $("#elle-ekle").open = false;
    bildir("İlan eklendi.");
    ilanlariYukle();
  } catch (err) { bildir(err.message, true); }
});

async function sayaciYenile() {
  try {
    const { ilanlar } = await (await api("/api/ilanlar/liste", { method: "POST", headers: JSON_BASLIK, body: "{}" })).json();
    sayaciGuncelle(ilanlar.length);
  } catch { /* sunucu henüz hazır değil */ }
}

// Masaüstünde site penceresinden ilan eklenince çağrılır
window.ilanEklendi = (baslik) => {
  bildir(`İlan eklendi: ${baslik}`);
  if (!$("#ekran-ilanlar").hidden) ilanlariYukle(); else sayaciYenile();
};

// CV metni bu bilgisayarda hatırlanır: ilanlar her açılışta CV'ye uyuma göre sıralanabilsin
try { if (!$("#cv").value) $("#cv").value = localStorage.getItem("cv-metin") || ""; } catch { /* depolama kapalı */ }
$("#cv").addEventListener("input", () => { try { localStorage.setItem("cv-metin", $("#cv").value); } catch { /* yok say */ } });
sayaciYenile();
