/* Super App Kerja — JS: tema, sidebar ringkas, notifikasi pop-up, tombol salin. */
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
    var pilihan = bacaPilihan();
    var nilaiAwal = (pilihan === "light" || pilihan === "dark") ? pilihan : "sistem";
    var radioAwal = grupTema.querySelector('input[value="' + nilaiAwal + '"]');
    if (radioAwal) radioAwal.checked = true;

    grupTema.addEventListener("change", function (e) {
      if (e.target.name !== "tema") return;
      simpanPilihan(e.target.value);
      terapkanTema();
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

  // Notifikasi yang dititipkan sebelum halaman dimuat ulang (lihat bagian progres)
  try {
    var titipan = sessionStorage.getItem("notifikasi-tertunda");
    if (titipan) {
      sessionStorage.removeItem("notifikasi-tertunda");
      titipan = JSON.parse(titipan);
      setTimeout(function () { window.notifikasi(titipan.pesan, titipan.jenis); }, 150);
    }
  } catch (e) { /* sessionStorage bisa diblokir; abaikan */ }

  var awal = document.getElementById("notifikasi-awal");
  if (awal && wadah) {
    // Ditunda sedikit agar pembaca layar sempat mendaftarkan wadah aria-live
    setTimeout(function () {
      Array.prototype.forEach.call(awal.content.querySelectorAll("[data-toast]"), function (el) {
        pasang(document.importNode(el, true));
      });
    }, 150);
  }

  /* ---------- 4. Tombol salin: <button data-salin="teks yang disalin"> ---------- */
  function salinCadangan(teks) {
    // Cara lama (execCommand) — dipakai bila Clipboard API tidak tersedia / ditolak
    var area = document.createElement("textarea");
    area.value = teks; area.setAttribute("readonly", ""); area.style.position = "fixed"; area.style.opacity = "0";
    document.body.appendChild(area); area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(area);
    return ok;
  }
  function salin(teks) {
    var lapor = function (ok) {
      window.notifikasi(ok ? "Lokasi disalin ke clipboard." : "Gagal menyalin lokasi.", ok ? "sukses" : "galat");
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(teks).then(function () { lapor(true); }, function () { lapor(salinCadangan(teks)); });
    } else {
      lapor(salinCadangan(teks));
    }
  }
  document.addEventListener("click", function (e) {
    var tombol = e.target.closest("[data-salin]");
    if (tombol) salin(tombol.getAttribute("data-salin"));
  });

  /* ---------- 5. Formulir kirim sekali ----------
     <form data-kirim-sekali data-teks-proses="Memproses...">: tombol kirim dinonaktifkan setelah diklik
     agar tidak terkirim ganda saat proses berjalan. */
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (e.defaultPrevented || !form.matches || !form.matches("[data-kirim-sekali]")) return;
    if (form.dataset.terkirim) { e.preventDefault(); return; }
    form.dataset.terkirim = "1";
    Array.prototype.forEach.call(form.querySelectorAll("button[type=submit]"), function (tombol) {
      tombol.disabled = true;
      tombol.setAttribute("aria-busy", "true");
      var label = tombol.querySelector("span") || tombol;
      label.textContent = form.dataset.teksProses || "Memproses...";
    });
  });
  // Bila halaman dibuka lagi lewat tombol Kembali browser, aktifkan ulang tombolnya
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) return;
    Array.prototype.forEach.call(document.querySelectorAll("[data-kirim-sekali]"), function (form) {
      delete form.dataset.terkirim;
      Array.prototype.forEach.call(form.querySelectorAll("button[type=submit]"), function (t) {
        t.disabled = false; t.removeAttribute("aria-busy");
      });
    });
  });

  /* ---------- 6. Pilih semua (tabel dengan kolom centang) ----------
     data-pilih-semua (kotak di kepala tabel), data-pilih-item (kotak per baris; yang disabled diabaikan),
     data-jumlah-dipilih (teks jumlah), data-perlu-pilihan (tombol yang nonaktif bila belum ada pilihan). */
  var induk = document.querySelector("[data-pilih-semua]");
  if (induk) {
    var anak = Array.prototype.filter.call(document.querySelectorAll("[data-pilih-item]"), function (c) { return !c.disabled; });
    var jumlahEl = document.querySelector("[data-jumlah-dipilih]");
    var tombolProses = document.querySelector("[data-perlu-pilihan]");
    var perbarui = function () {
      var n = anak.filter(function (c) { return c.checked; }).length;
      induk.checked = anak.length > 0 && n === anak.length;
      induk.indeterminate = n > 0 && n < anak.length;
      induk.disabled = anak.length === 0;
      if (jumlahEl) jumlahEl.textContent = n;
      if (tombolProses) tombolProses.disabled = n === 0;
    };
    induk.addEventListener("change", function () {
      anak.forEach(function (c) { c.checked = induk.checked; });
      perbarui();
    });
    anak.forEach(function (c) { c.addEventListener("change", perbarui); });
    perbarui();
  }

  /* ---------- 7. Nama berkas terpilih (input file bergaya tombol) ---------- */
  Array.prototype.forEach.call(document.querySelectorAll("[data-pilih-berkas]"), function (input) {
    var nama = input.parentNode.querySelector("[data-nama-berkas]");
    var awal = nama ? nama.textContent : "";
    input.addEventListener("change", function () {
      if (nama) nama.textContent = input.files.length ? input.files[0].name : awal;
    });
  });

  /* ---------- 8. Progres proses latar ----------
     <div data-pantau-progres="URL status JSON">: tanya progres tiap detik, perbarui bilah,
     lalu muat ulang halaman (dengan notifikasi) setelah selesai. */
  var pantau = document.querySelector("[data-pantau-progres]");
  if (pantau && window.fetch) {
    var urlStatus = pantau.getAttribute("data-pantau-progres");
    var elTahap = pantau.querySelector("[data-progres-tahap]");
    var elAngka = pantau.querySelector("[data-progres-angka]");
    var elBilah = pantau.querySelector("[data-progres-bilah]");
    var elIsi = pantau.querySelector("[data-progres-isi]");
    var elCatatan = pantau.querySelector("[data-progres-catatan]");
    var gagalBeruntun = 0;

    var tampilkan = function (d) {
      var tahap = d.selesai ? "Selesai" : d.tahap;
      if (tahap && elTahap.textContent !== tahap) elTahap.textContent = tahap;
      elAngka.textContent = d.persen + "%";
      elIsi.style.width = d.persen + "%";
      elBilah.setAttribute("aria-valuenow", d.persen);
    };

    var tanya = function () {
      fetch(urlStatus, { headers: { "Accept": "application/json" }, credentials: "same-origin", cache: "no-store" })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) {
          gagalBeruntun = 0;
          tampilkan(d);
          if (d.selesai) {
            try { sessionStorage.setItem("notifikasi-tertunda", JSON.stringify({ pesan: d.pesan, jenis: d.jenis })); } catch (e) {}
            setTimeout(function () { window.location.reload(); }, 400);
          } else {
            setTimeout(tanya, 1000);
          }
        })
        .catch(function () {
          gagalBeruntun += 1;
          if (gagalBeruntun < 30) {
            setTimeout(tanya, 2000);
          } else {
            elCatatan.textContent = "Progres tidak dapat dimuat. Muat ulang halaman ini secara manual.";
          }
        });
    };
    setTimeout(tanya, 500);
  }

  /* ---------- 9. Konfirmasi sebelum tindakan yang tidak bisa dibatalkan ----------
     <form data-konfirmasi="Hapus {n} riwayat?" data-konfirmasi-judul="Hapus riwayat" data-konfirmasi-tombol="Hapus">
     {n} diganti jumlah [data-pilih-item] yang dicentang di dalam form. Dialog memakai <dialog> bawaan browser:
     fokus terkunci di dalam dialog, Esc = batal. */
  var dialog = document.getElementById("dialog-konfirmasi");
  if (dialog && dialog.showModal) {
    var formMenunggu = null, tombolPengirim = null;
    document.addEventListener("submit", function (e) {
      var form = e.target;
      // Atribut boleh di tombol pengirim (mis. tombol Hapus di dalam form besar) atau di form
      var sumber = e.submitter && e.submitter.dataset.konfirmasi ? e.submitter : form;
      if (!sumber.dataset || !sumber.dataset.konfirmasi) return;
      if (form.dataset.dikonfirmasi === "1") { delete form.dataset.dikonfirmasi; return; }
      e.preventDefault();
      var n = form.querySelectorAll("[data-pilih-item]:checked").length;
      document.getElementById("dk-judul").textContent = sumber.dataset.konfirmasiJudul || "Konfirmasi";
      document.getElementById("dk-pesan").textContent = sumber.dataset.konfirmasi.replace("{n}", n);
      document.getElementById("dk-ya").textContent = sumber.dataset.konfirmasiTombol || "Ya";
      formMenunggu = form;
      tombolPengirim = e.submitter || null;
      dialog.returnValue = "";
      dialog.showModal();
    }, true);   // fase capture: berjalan sebelum handler lain
    dialog.addEventListener("close", function () {
      if (dialog.returnValue === "ya" && formMenunggu) {
        formMenunggu.dataset.dikonfirmasi = "1";
        if (formMenunggu.requestSubmit) formMenunggu.requestSubmit(tombolPengirim || undefined);
        else formMenunggu.submit();
      } else if (tombolPengirim) {
        tombolPengirim.focus();
      }
      formMenunggu = null;
      tombolPengirim = null;
    });
  }

  /* ---------- 10. Zona unggah foto: pilih, seret-lepas, atau tempel (Ctrl+V) ----------
     Semua berkas dikumpulkan di satu DataTransfer lalu dipasang ke <input type=file>, sehingga
     formulir dikirim seperti biasa. data-maks-berkas = batas byte per berkas, data-sisa = sisa kuota foto. */
  var zona = document.querySelector("[data-zona-unggah]");
  if (zona && window.DataTransfer) {
    var masukan = zona.querySelector("input[type=file]");
    var daftarPratinjau = document.querySelector("[data-pratinjau-unggah]");
    var tombolUnggah = document.querySelector("[data-tombol-unggah]");
    var maksByte = parseInt(zona.dataset.maksBerkas, 10);
    var sisaKuota = parseInt(zona.dataset.sisa, 10);
    var kumpulan = new DataTransfer();
    var TIPE = ["image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"];

    var gambarPratinjau = function () {
      Array.prototype.forEach.call(daftarPratinjau.querySelectorAll("img"), function (img) { URL.revokeObjectURL(img.src); });
      daftarPratinjau.textContent = "";
      Array.prototype.forEach.call(kumpulan.files, function (berkas, i) {
        var li = document.createElement("li");
        li.className = "grid gap-1 text-xs";
        var img = document.createElement("img");
        img.src = URL.createObjectURL(berkas);
        img.alt = "Pratinjau " + berkas.name;
        img.className = "aspect-square w-full rounded-md border border-garis bg-permukaan-2 object-cover";
        var nama = document.createElement("span");
        nama.className = "truncate text-redup";
        nama.textContent = berkas.name;
        var buang = document.createElement("button");
        buang.type = "button";
        buang.className = "tombol tombol-teks min-h-8 px-2 text-xs";
        buang.textContent = "Batalkan";
        buang.setAttribute("aria-label", "Batalkan " + berkas.name);
        buang.addEventListener("click", function () {
          var baru = new DataTransfer();
          Array.prototype.forEach.call(kumpulan.files, function (b, j) { if (j !== i) baru.items.add(b); });
          kumpulan = baru;
          masukan.files = kumpulan.files;
          gambarPratinjau();
        });
        li.appendChild(img); li.appendChild(nama); li.appendChild(buang);
        daftarPratinjau.appendChild(li);
      });
      if (tombolUnggah) tombolUnggah.disabled = kumpulan.files.length === 0;
    };

    var tambah = function (berkasBaru) {
      Array.prototype.forEach.call(berkasBaru, function (berkas) {
        if (TIPE.indexOf(berkas.type) === -1) {
          window.notifikasi(berkas.name + ": bukan foto JPG, PNG, WebP, GIF, atau BMP.", "galat");
        } else if (berkas.size > maksByte) {
          window.notifikasi(berkas.name + ": lebih dari " + Math.round(maksByte / 1048576) + " MB.", "galat");
        } else if (kumpulan.files.length >= sisaKuota) {
          window.notifikasi("Batas foto per kegiatan tercapai; " + berkas.name + " tidak ditambahkan.", "galat");
        } else {
          kumpulan.items.add(berkas);
        }
      });
      masukan.files = kumpulan.files;
      gambarPratinjau();
    };

    masukan.addEventListener("change", function () {
      var dipilih = Array.prototype.slice.call(masukan.files);
      masukan.files = kumpulan.files;      // pilihan sebelumnya tetap ada
      tambah(dipilih);
    });
    ["dragenter", "dragover"].forEach(function (jenis) {
      zona.addEventListener(jenis, function (e) { e.preventDefault(); zona.dataset.seret = ""; });
    });
    ["dragleave", "drop"].forEach(function (jenis) {
      zona.addEventListener(jenis, function () { delete zona.dataset.seret; });
    });
    zona.addEventListener("drop", function (e) {
      e.preventDefault();
      if (e.dataTransfer && e.dataTransfer.files.length) tambah(e.dataTransfer.files);
    });
    // Tempel gambar dari clipboard di mana pun pada halaman (teks biasa tetap ditempel seperti biasa)
    document.addEventListener("paste", function (e) {
      var item = e.clipboardData ? Array.prototype.slice.call(e.clipboardData.items) : [];
      var gambar = item.filter(function (it) { return it.kind === "file" && it.type.indexOf("image/") === 0; });
      if (!gambar.length) return;
      e.preventDefault();
      tambah(gambar.map(function (it, i) {
        var b = it.getAsFile();
        var akhiran = (b.type.split("/")[1] || "png").replace("jpeg", "jpg");
        return new File([b], "tempelan-" + Date.now() + "-" + (i + 1) + "." + akhiran, { type: b.type });
      }));
      window.notifikasi(gambar.length + " gambar ditempel. Klik Unggah foto untuk menyimpan.", "info");
    });
    gambarPratinjau();
  }

  /* ---------- 11. Saring daftar: <input data-saring="#wadah">, item [data-saring-teks] ---------- */
  Array.prototype.forEach.call(document.querySelectorAll("[data-saring]"), function (masukanSaring) {
    var wadah = document.querySelector(masukanSaring.dataset.saring);
    if (!wadah) return;
    var kosong = wadah.querySelector("[data-saring-kosong]");
    masukanSaring.addEventListener("input", function () {
      var kata = masukanSaring.value.trim().toLowerCase();
      var tampil = 0;
      Array.prototype.forEach.call(wadah.querySelectorAll("[data-saring-teks]"), function (el) {
        var cocok = !kata || el.dataset.saringTeks.toLowerCase().indexOf(kata) !== -1;
        el.hidden = !cocok;
        tampil += cocok ? 1 : 0;
      });
      if (kosong) kosong.classList.toggle("hidden", tampil > 0 || !kata);
    });
  });
})();
