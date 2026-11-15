/* Super App Kerja — JS minimal: (1) alih tema, (2) sapaan & tanggal sesuai jam pengguna. */
(function () {
  "use strict";

  /* ---------- 1. Tema (pilihan ada di halaman Pengaturan) ----------
     Nilai di localStorage "tema": "light" | "dark" | (kosong = ikuti sistem).
     Tema awal sudah dipasang skrip kecil di <head> base.html. */
  var akar = document.documentElement;
  var mediaGelap = window.matchMedia("(prefers-color-scheme: dark)");

  function bacaPilihan() {
    try { return localStorage.getItem("tema"); } catch (e) { return null; }
  }
  function simpanPilihan(nilai) {
    try {
      if (nilai === "sistem") localStorage.removeItem("tema");
      else localStorage.setItem("tema", nilai);
    } catch (e) { /* localStorage bisa diblokir; abaikan */ }
  }
  function terapkanTema() {
    var p = bacaPilihan();
    // Matikan animasi warna sesaat agar pergantian tema langsung & serentak
    akar.classList.add("ganti-tema");
    akar.dataset.theme = (p === "light" || p === "dark") ? p : (mediaGelap.matches ? "dark" : "light");
    void akar.offsetWidth; // paksa browser menerapkan gaya baru dulu
    requestAnimationFrame(function () { akar.classList.remove("ganti-tema"); });
  }

  // Bila memilih "Ikuti sistem", ikut berubah saat tema Windows/perangkat berubah
  mediaGelap.addEventListener("change", terapkanTema);

  var grupTema = document.querySelector("[data-pilihan-tema]");
  if (grupTema) {
    var status = document.querySelector("[data-status-tema]");
    var pilihan = bacaPilihan();
    var nilaiAwal = (pilihan === "light" || pilihan === "dark") ? pilihan : "sistem";
    var radioAwal = grupTema.querySelector('input[value="' + nilaiAwal + '"]');
    if (radioAwal) radioAwal.checked = true;

    grupTema.addEventListener("change", function (e) {
      if (e.target.name !== "tema") return;
      simpanPilihan(e.target.value);
      terapkanTema();
      if (status) status.textContent = "Tema disimpan.";
    });
  }

  /* ---------- 2. Sidebar ringkas / lebar (md ke atas) ---------- */
  var tombolSidebar = document.getElementById("tombol-sidebar");
  function perbaruiTombolSidebar() {
    if (!tombolSidebar) return;
    var ringkas = akar.dataset.sidebar === "ringkas";
    var label = ringkas ? "Lebarkan sidebar" : "Ciutkan sidebar";
    tombolSidebar.setAttribute("aria-expanded", String(!ringkas));
    tombolSidebar.setAttribute("aria-label", label);
    tombolSidebar.title = label;
  }
  if (tombolSidebar) {
    tombolSidebar.addEventListener("click", function () {
      akar.dataset.sidebar = akar.dataset.sidebar === "ringkas" ? "lebar" : "ringkas";
      try { localStorage.setItem("sidebar", akar.dataset.sidebar); } catch (e) {}
      perbaruiTombolSidebar();
    });
    perbaruiTombolSidebar();
  }

  /* ---------- 3. Notifikasi pop-up (kanan atas) ----------
     - Pesan flash dari server ditampilkan otomatis.
     - Dari JS: window.notifikasi("Pesan", "sukses" | "info" | "galat")
     - Menutup sendiri (5 dtk; galat 8 dtk); berhenti saat disorot mouse / fokus keyboard. */
  var wadah = document.getElementById("wadah-notifikasi");
  var LAMA = { sukses: 5000, info: 5000, galat: 8000 };

  function tutup(el) {
    if (el.dataset.ditutup) return;
    el.dataset.ditutup = "1";
    el.classList.add("toast-keluar");
    var hapus = function () { if (el.parentNode) el.parentNode.removeChild(el); };
    el.addEventListener("transitionend", hapus);
    setTimeout(hapus, 300); // cadangan bila transisi dimatikan (reduced motion)
  }

  function pasang(el) {
    var sisa = LAMA[el.dataset.jenis] || 5000, mulai, timer;
    function jalan() { mulai = Date.now(); timer = setTimeout(function () { tutup(el); }, sisa); }
    function jeda() { clearTimeout(timer); sisa -= Date.now() - mulai; if (sisa < 1500) sisa = 1500; }
    el.addEventListener("mouseenter", jeda);
    el.addEventListener("mouseleave", jalan);
    el.addEventListener("focusin", jeda);
    el.addEventListener("focusout", jalan);
    el.querySelector("[data-toast-tutup]").addEventListener("click", function () { tutup(el); });
    wadah.appendChild(el);
    jalan();
  }

  window.notifikasi = function (pesan, jenis) {
    var cetakan = document.getElementById("cetakan-notifikasi-" + (jenis || "info"));
    if (!cetakan || !wadah) return;
    var el = cetakan.content.firstElementChild.cloneNode(true);
    el.querySelector("[data-toast-pesan]").textContent = pesan;
    pasang(el);
  };

  var awal = document.getElementById("notifikasi-awal");
  if (awal && wadah) {
    // Ditunda sedikit agar pembaca layar sempat mendaftarkan wadah aria-live
    setTimeout(function () {
      Array.prototype.forEach.call(awal.content.querySelectorAll("[data-toast]"), function (el) {
        pasang(document.importNode(el, true));
      });
    }, 150);
  }

  /* ---------- 4. Salin lokasi simpan terakhir ---------- */
  var tombolSalin = document.querySelector("[data-salin-lokasi]");
  if (tombolSalin) {
    tombolSalin.addEventListener("click", function () {
      var teks = document.querySelector("[data-lokasi]").textContent.trim();
      var berhasil = function () { window.notifikasi("Lokasi disalin ke clipboard.", "sukses"); };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(teks).then(berhasil, function () { window.notifikasi("Gagal menyalin lokasi.", "galat"); });
      } else {
        // Cadangan untuk browser lama
        var area = document.createElement("textarea");
        area.value = teks; area.style.position = "fixed"; area.style.opacity = "0";
        document.body.appendChild(area); area.select();
        try { document.execCommand("copy"); berhasil(); } catch (e) { window.notifikasi("Gagal menyalin lokasi.", "galat"); }
        document.body.removeChild(area);
      }
    });
  }

  /* ---------- 5. Sapaan & tanggal (batas jam sama dengan app/waktu.py) ---------- */
  var HARI = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
  var BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
               "Agustus", "September", "Oktober", "November", "Desember"];

  function sapaan(jam) {
    if (jam >= 4 && jam < 11) return "Selamat pagi";
    if (jam >= 11 && jam < 15) return "Selamat siang";
    if (jam >= 15 && jam < 18) return "Selamat sore";
    return "Selamat malam";
  }

  var elSapaan = document.querySelector("[data-sapaan]");
  var elTanggal = document.querySelector("[data-tanggal]");
  if (elSapaan || elTanggal) {
    var k = new Date();
    if (elSapaan) elSapaan.textContent = sapaan(k.getHours());
    if (elTanggal) elTanggal.textContent = HARI[k.getDay()] + ", " + k.getDate() + " " + BULAN[k.getMonth()] + " " + k.getFullYear();
  }
})();
