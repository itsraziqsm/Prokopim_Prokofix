/* Super App Kerja — JS minimal: (1) alih tema, (2) sapaan & tanggal sesuai jam pengguna. */
(function () {
  "use strict";

  /* ---------- 1. Alih tema terang/gelap ---------- */
  var akar = document.documentElement;
  var tombol = document.getElementById("tombol-tema");
  var mediaGelap = window.matchMedia("(prefers-color-scheme: dark)");

  // Tema yang sedang tampil: pilihan manual (data-theme) atau ikut sistem
  function temaAktif() {
    return akar.dataset.theme || (mediaGelap.matches ? "dark" : "light");
  }

  // Perbarui label tombol agar pembaca layar tahu aksi berikutnya
  function perbaruiTombol() {
    if (!tombol) return;
    var gelap = temaAktif() === "dark";
    tombol.setAttribute("aria-label", gelap ? "Ganti ke mode terang" : "Ganti ke mode gelap");
    tombol.title = tombol.getAttribute("aria-label");
  }

  if (tombol) {
    tombol.addEventListener("click", function () {
      var baru = temaAktif() === "dark" ? "light" : "dark";
      akar.dataset.theme = baru;
      try { localStorage.setItem("tema", baru); } catch (e) { /* localStorage bisa diblokir; abaikan */ }
      perbaruiTombol();
    });
    mediaGelap.addEventListener("change", perbaruiTombol);
    perbaruiTombol();
  }

  /* ---------- 2. Sapaan & tanggal (batas jam sama dengan app/waktu.py) ---------- */
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
