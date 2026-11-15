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
