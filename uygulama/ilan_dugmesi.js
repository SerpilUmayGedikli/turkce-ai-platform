// İş ilanı sitelerinin pencerelerine eklenen "CV Uyarlayıcı'ya ekle" düğmesi.
// Yalnızca kullanıcı düğmeye bastığında, o an açık olan ilanın metnini okur ve masaüstü
// uygulamasına gönderir. Site taramaz, arka planda hiçbir şey yapmaz.
(function () {
  if (window.__cvUyarlayici) return;
  window.__cvUyarlayici = true;

  // Sitelere göre ilan açıklaması alanları (öncelik sırasıyla); bulunamazsa sayfanın ana metni
  var ALANLAR = [
    ".jobs-description__content", ".jobs-search__job-details--container", ".jobs-description",
    ".job-view-layout", "#jobDescriptionText", ".jobsearch-JobComponent", ".jobsearch-ViewJobLayout",
    "[class*='job-detail']", "[class*='jobDetail']", "[class*='JobDetail']", "[class*='ilan-detay']",
    "[class*='job-description']", "[class*='jobDescription']", "[class*='description']",
    "article", "main", "[role='main']"
  ];

  function ilanMetni() {
    var secim = String(window.getSelection ? window.getSelection() : "").trim();
    if (secim.length > 120) return { metin: secim, kaynak: "seçim" };
    for (var i = 0; i < ALANLAR.length; i++) {
      var en = "", ogeler = document.querySelectorAll(ALANLAR[i]);
      for (var j = 0; j < ogeler.length; j++) {
        var t = (ogeler[j].innerText || "").trim();
        if (t.length > en.length && t.length < 40000) en = t;
      }
      // İlan açıklaması alanları kısa olabilir; genel alanlar (article/main) için daha uzun metin aranır
      var esik = ALANLAR[i] === "article" || ALANLAR[i] === "main" || ALANLAR[i] === "[role='main']" ? 300 : 150;
      if (en.length > esik) return { metin: en, kaynak: "sayfa" };
    }
    return { metin: (document.body.innerText || "").trim().slice(0, 20000), kaynak: "tüm sayfa" };
  }

  function baslik() {
    var h = document.querySelector(".job-details-jobs-unified-top-card__job-title, .jobsearch-JobInfoHeader-title, h1");
    return ((h && h.innerText) || document.title || "").trim().split("\n")[0];
  }

  var stil = document.createElement("style");
  stil.textContent =
    "#cvu-kutu{position:fixed;right:18px;bottom:18px;z-index:2147483647;font:14px/1.4 'Segoe UI',system-ui,sans-serif;display:flex;flex-direction:column;align-items:flex-end;gap:8px}" +
    "#cvu-dugme{background:#2F5BEA;color:#fff;border:0;border-radius:999px;padding:11px 18px;font-weight:600;cursor:pointer;box-shadow:0 6px 20px rgba(27,36,64,.3)}" +
    "#cvu-dugme:hover{background:#2348C4}" +
    "#cvu-not{background:#1B2440;color:#fff;border-radius:10px;padding:9px 13px;max-width:320px;box-shadow:0 6px 20px rgba(0,0,0,.25);display:none}" +
    "#cvu-ipucu{background:#fff;color:#5D6785;border-radius:8px;padding:5px 9px;font-size:12px;box-shadow:0 2px 8px rgba(0,0,0,.15)}";
  document.documentElement.appendChild(stil);

  var kutu = document.createElement("div");
  kutu.id = "cvu-kutu";
  kutu.innerHTML = '<div id="cvu-not"></div><div id="cvu-ipucu">İlanı açınca bas · istersen önce açıklamayı seç</div>' +
    '<button id="cvu-dugme" type="button">＋ CV Uyarlayıcı\'ya ekle</button>';
  document.documentElement.appendChild(kutu);

  var not = kutu.querySelector("#cvu-not"), zaman;
  function goster(metin) {
    not.textContent = metin; not.style.display = "block";
    clearTimeout(zaman); zaman = setTimeout(function () { not.style.display = "none"; }, 4500);
  }

  kutu.querySelector("#cvu-dugme").addEventListener("click", function () {
    var api = window.pywebview && window.pywebview.api;
    if (!api || !api.ilan_gonder) { goster("Uygulamaya bağlanılamadı, sayfayı yenileyip tekrar dene."); return; }
    var m = ilanMetni();
    api.ilan_gonder({ metin: m.metin, baslik: baslik(), url: location.href }).then(function (sonuc) {
      goster(sonuc || "Eklendi.");
    }).catch(function (e) { goster("Eklenemedi: " + e); });
  });
})();
