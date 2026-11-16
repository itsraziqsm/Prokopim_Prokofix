/* Super App Prokopim — JS: tema, sidebar, notifikasi, konfirmasi, unggah foto, editor pertanyaan, mode baca. */
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
    var label = ringkas ? "Lebarkan menu" : "Ciutkan menu";
    tombolSidebar.setAttribute("aria-expanded", String(!ringkas));
    var teks = tombolSidebar.querySelector("[data-label-sidebar]");
    if (teks) teks.textContent = label;
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
  var formMenunggu = null, tombolPengirim = null, lanjutMenunggu = null, fokusSemula = null;
  function bukaKonfirmasi(judul, pesan, tombol) {
    document.getElementById("dk-judul").textContent = judul || "Konfirmasi";
    document.getElementById("dk-pesan").textContent = pesan;
    document.getElementById("dk-ya").textContent = tombol || "Ya";
    dialog.returnValue = "";
    dialog.showModal();
  }
  // Dari JS: window.konfirmasi("Pesan", { judul: "...", tombol: "Hapus" }, function () { ...bila Ya... })
  window.konfirmasi = function (pesan, opsi, lanjut) {
    if (!dialog || !dialog.showModal) { lanjut(); return; }
    opsi = opsi || {};
    lanjutMenunggu = lanjut;
    fokusSemula = document.activeElement;
    bukaKonfirmasi(opsi.judul, pesan, opsi.tombol);
  };
  if (dialog && dialog.showModal) {
    document.addEventListener("submit", function (e) {
      var form = e.target;
      // Atribut boleh di tombol pengirim (mis. tombol Hapus di dalam form besar) atau di form
      var sumber = e.submitter && e.submitter.dataset.konfirmasi ? e.submitter : form;
      if (!sumber.dataset || !sumber.dataset.konfirmasi) return;
      if (form.dataset.dikonfirmasi === "1") { delete form.dataset.dikonfirmasi; return; }
      e.preventDefault();
      var n = form.querySelectorAll("[data-pilih-item]:checked").length;
      formMenunggu = form;
      tombolPengirim = e.submitter || null;
      bukaKonfirmasi(sumber.dataset.konfirmasiJudul, sumber.dataset.konfirmasi.replace("{n}", n), sumber.dataset.konfirmasiTombol);
    }, true);   // fase capture: berjalan sebelum handler lain
    dialog.addEventListener("close", function () {
      var ya = dialog.returnValue === "ya";
      if (ya && formMenunggu) {
        formMenunggu.dataset.dikonfirmasi = "1";
        if (formMenunggu.requestSubmit) formMenunggu.requestSubmit(tombolPengirim || undefined);
        else formMenunggu.submit();
      } else if (ya && lanjutMenunggu) {
        lanjutMenunggu();
      } else if (tombolPengirim || fokusSemula) {
        (tombolPengirim || fokusSemula).focus();
      }
      formMenunggu = null;
      tombolPengirim = null;
      lanjutMenunggu = null;
      fokusSemula = null;
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

  /* ---------- 12. Panel kelengkapan: perbarui centang/silang langsung dari isian formulir ----------
     <li data-kelengkapan data-cek="isi:ID_ELEMEN | pilih:NAMA_RADIO | nilai:NAMA_RADIO=NILAI">.
     Butir tanpa data-cek (foto, Word) hanya mengikuti data yang sudah tersimpan. */
  var butirCek = document.querySelectorAll("[data-kelengkapan][data-cek]");
  if (butirCek.length) {
    var hitungParagraf = function (teks) {
      return teks.replace(/[\u200b-\u200d\u2060\ufeff]/g, "").split(/\r?\n|\r/)
        .filter(function (b) { return b.replace(/\s/g, "") !== ""; }).length;
    };
    var nilaiRadio = function (nama) {
      var el = document.querySelector('input[name="' + nama + '"]:checked');
      return el ? el.value : "";
    };
    var periksaButir = function (li) {
      var aturan = li.dataset.cek, jenis = aturan.split(":")[0], isi = aturan.slice(jenis.length + 1);
      var lengkap = false, detail = null;
      if (jenis === "isi") {
        var el = document.getElementById(isi);
        if (!el) return;
        if (li.dataset.kelengkapan === "isi") {
          var n = hitungParagraf(el.value);
          lengkap = n > 0;
          detail = n ? n + " paragraf" : "";
        } else {
          lengkap = el.value.trim() !== "";
        }
      } else if (jenis === "pilih") {
        lengkap = nilaiRadio(isi) !== "";
      } else if (jenis === "nilai") {
        var bagian = isi.split("=");
        lengkap = nilaiRadio(bagian[0]) === bagian[1];
      }
      li.dataset.lengkap = lengkap ? "1" : "0";
      li.querySelector("[data-tanda-lengkap]").hidden = !lengkap;
      li.querySelector("[data-tanda-belum]").hidden = lengkap;
      li.querySelector("[data-teks-status]").textContent = lengkap ? ": lengkap"
        : (li.hasAttribute("data-wajib") ? ": belum" : ": belum diisi (opsional)");
      var elDetail = li.querySelector("[data-detail]");
      if (detail !== null && elDetail) { elDetail.textContent = detail; elDetail.hidden = !detail; }
    };
    var perbaruiPanel = function () {
      Array.prototype.forEach.call(butirCek, periksaButir);
      var penghitung = document.querySelector("[data-jumlah-wajib-lengkap]");
      var wajibLengkap = document.querySelectorAll('[data-kelengkapan][data-wajib][data-lengkap="1"]').length;
      var semuaWajib = document.querySelectorAll("[data-kelengkapan][data-wajib]").length;
      if (penghitung) penghitung.textContent = wajibLengkap;
      // Tombol "Buat Word" hanya aktif bila semua butir wajib lengkap (server tetap memeriksa ulang)
      var kurang = wajibLengkap < semuaWajib;
      Array.prototype.forEach.call(document.querySelectorAll("[data-butuh-wajib]"), function (t) { t.disabled = kurang; });
      var syarat = document.querySelector("[data-syarat-word]");
      if (syarat) syarat.hidden = !kurang;
    };
    document.addEventListener("input", perbaruiPanel);
    document.addEventListener("change", perbaruiPanel);
  }

  /* ---------- 13. Klik butir Kelengkapan: gulir halus ke isiannya ----------
     Bukan lompatan mendadak: gulir halus (kecuali pengguna memilih "kurangi animasi"),
     isian difokus tanpa lompatan kedua, lalu disorot sesaat agar mudah ditemukan. */
  var kurangiGerak = window.matchMedia("(prefers-reduced-motion: reduce)");
  document.addEventListener("click", function (e) {
    var tautan = e.target.closest("[data-kelengkapan] a[href^='#']");
    if (!tautan) return;
    var tujuan = document.getElementById(tautan.getAttribute("href").slice(1));
    if (!tujuan) return;
    e.preventDefault();
    var halus = !kurangiGerak.matches;
    tujuan.scrollIntoView({ behavior: halus ? "smooth" : "auto", block: "center" });
    // Fokus isian (agar bisa langsung diketik) tanpa memicu lompatan gulir tambahan
    var bisaFokus = tujuan.matches("input, textarea, select, button, a[href]") ? tujuan
      : tujuan.querySelector("input:not([type=hidden]), textarea, select");
    if (bisaFokus && tujuan.id !== "bagian-foto") bisaFokus.focus({ preventScroll: true });
    // Sorot sesaat
    var disorot = tujuan;
    disorot.removeAttribute("data-sorot-pudar");
    disorot.setAttribute("data-sorot", "");
    setTimeout(function () { disorot.setAttribute("data-sorot-pudar", ""); }, halus ? 900 : 600);
    setTimeout(function () { disorot.removeAttribute("data-sorot"); disorot.removeAttribute("data-sorot-pudar"); }, halus ? 1600 : 700);
    if (history.replaceState) history.replaceState(null, "", "#" + tujuan.id);
  });

  /* ---------- 14. SPT terkait: "Tanpa SPT" menyembunyikan daftar, "Dengan SPT" menampilkannya ---------- */
  var wadahSpt = document.querySelector("[data-wadah-spt]");
  if (wadahSpt) {
    document.addEventListener("change", function (e) {
      if (!e.target || e.target.name !== "pakai_spt") return;
      var pakai = e.target.value === "ya";
      wadahSpt.hidden = !pakai;
      if (pakai) {
        var cari = wadahSpt.querySelector("input[type=search]");
        if (cari) cari.focus();
      } else {
        // Lepas pilihan SPT agar yang terkirim benar-benar tanpa SPT, lalu perbarui panel Kelengkapan
        Array.prototype.forEach.call(document.querySelectorAll('input[name="spt_id"]'), function (r) { r.checked = false; });
        document.dispatchEvent(new Event("change"));
      }
    });
  }

  /* ---------- 15. Fokus kembali setelah dialihkan: ?fokus=<id elemen> ----------
     Dipakai tombol Naik/Turun instansi agar pengguna keyboard tetap di tombol yang sama setelah halaman dimuat ulang. */
  var idFokus = new URLSearchParams(location.search).get("fokus");
  if (idFokus) {
    var elFokus = document.getElementById(idFokus);
    if (elFokus && elFokus.disabled) {
      // Tombolnya kini nonaktif (sudah di ujung daftar): pindah ke tombol lain di baris yang sama
      var baris = elFokus.closest("tr, li, section");
      elFokus = baris ? baris.querySelector("button:not([disabled])") : null;
    }
    if (elFokus) elFokus.focus();
    if (history.replaceState) history.replaceState(null, "", location.pathname + location.hash);
  }

  /* ---------- 16. Peringatan sebelum meninggalkan halaman bila ada perubahan belum disimpan ----------
     <form data-jaga-perubahan> ... <p data-tanda-berubah hidden>. Event "ubah-daftar" = perubahan dari JS. */
  Array.prototype.forEach.call(document.querySelectorAll("form[data-jaga-perubahan]"), function (form) {
    var berubah = false;
    var tanda = form.querySelector("[data-tanda-berubah]");
    function tandai() {
      if (berubah) return;
      berubah = true;
      if (tanda) tanda.hidden = false;
    }
    form.addEventListener("input", tandai);
    form.addEventListener("change", tandai);
    form.addEventListener("ubah-daftar", tandai);
    form.addEventListener("submit", function () { berubah = false; });
    window.addEventListener("beforeunload", function (e) {
      if (!berubah) return;
      e.preventDefault();
      e.returnValue = "";   // browser menampilkan pesan bawaannya sendiri
    });
  });

  /* ---------- 17. Editor pertanyaan (halaman instansi Materi Podcast) ----------
     Tambah / naik / turun / hapus pertanyaan di browser, penomoran ulang, pratinjau jawaban langsung
     (HTML dibuat server oleh pengurai yang sama dengan ekspor Word), dan kotak "Tandai selesai"
     yang hanya aktif bila semua pertanyaan sudah berjawaban. */
  var editor = document.querySelector("[data-editor-pertanyaan]");
  if (editor) {
    var daftarTanya = editor.querySelector("[data-daftar-pertanyaan]");
    var cetakanTanya = document.getElementById("cetakan-pertanyaan");
    var kosongTanya = editor.querySelector("[data-pertanyaan-kosong]");
    var pengumuman = editor.querySelector("[data-pengumuman]");
    var tombolTambah = editor.querySelector("[data-tambah-pertanyaan]");
    var kotakSelesai = editor.querySelector("[data-tanda-selesai]");
    var infoSelesai = editor.querySelector("[data-info-selesai]");
    var maksTanya = parseInt(editor.dataset.pertanyaanMaks || "150", 10);
    var csrfTanya = editor.querySelector("input[name=csrf_token]").value;
    var penghitung = 0;
    var KOSONG_PRATINJAU = '<p class="text-redup" data-pratinjau-kosong>Belum ada jawaban.</p>';

    var semuaBaris = function () { return daftarTanya.querySelectorAll("[data-pertanyaan]"); };
    var umumkan = function (teks) {
      pengumuman.textContent = "";
      setTimeout(function () { pengumuman.textContent = teks; }, 50);
    };
    var tandaiUbah = function () { editor.dispatchEvent(new Event("ubah-daftar")); };

    var perbaruiSelesai = function () {
      if (!kotakSelesai) return;
      var baris = semuaBaris(), terjawab = 0;
      Array.prototype.forEach.call(baris, function (b) {
        if (b.querySelector("textarea[name=jawaban]").value.trim()) terjawab++;
      });
      var boleh = baris.length > 0 && terjawab === baris.length;
      kotakSelesai.disabled = !boleh;
      if (!boleh) kotakSelesai.checked = false;
      infoSelesai.textContent = "Aktif bila semua pertanyaan sudah berjawaban (" + terjawab + " dari " + baris.length + " terjawab).";
      infoSelesai.hidden = boleh;   // petunjuk hanya perlu selama kotak belum bisa dicentang
    };

    var perbaruiNomor = function () {
      var baris = semuaBaris();
      Array.prototype.forEach.call(baris, function (b, i) {
        b.querySelector("[data-nomor]").textContent = i + 1;
        Array.prototype.forEach.call(b.querySelectorAll("[data-aksi-pertanyaan]"), function (tombol) {
          tombol.querySelector("[data-label-teks]").textContent = tombol.dataset.label + " " + (i + 1);
          if (tombol.dataset.aksiPertanyaan === "naik") tombol.disabled = i === 0;
          if (tombol.dataset.aksiPertanyaan === "turun") tombol.disabled = i === baris.length - 1;
        });
      });
      kosongTanya.hidden = baris.length > 0;
      tombolTambah.disabled = baris.length >= maksTanya;
      perbaruiSelesai();
    };

    var muatPratinjau = function (sumber) {
      var target = document.getElementById(sumber.dataset.pratinjauSumber);
      if (!target) return;
      if (!sumber.value.trim()) { target.innerHTML = KOSONG_PRATINJAU; return; }
      var data = new FormData();
      data.append("csrf_token", csrfTanya);
      data.append("teks", sumber.value);
      var nomor = (sumber._permintaan || 0) + 1;
      sumber._permintaan = nomor;
      fetch(editor.dataset.pratinjauUrl, { method: "POST", body: data, credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
        .then(function (html) {
          // HTML aman: dibuat server dari hasil penguraian, semua teks pengguna sudah di-escape
          if (sumber._permintaan === nomor) target.innerHTML = html;
        })
        .catch(function () {
          target.innerHTML = '<p class="text-bahaya-teks">Pratinjau gagal dimuat. Muat ulang halaman bila berlanjut.</p>';
        });
    };

    var penunda = new WeakMap();
    daftarTanya.addEventListener("input", function (e) {
      var sumber = e.target.closest("[data-pratinjau-sumber]");
      if (!sumber) return;
      clearTimeout(penunda.get(sumber));
      penunda.set(sumber, setTimeout(function () { muatPratinjau(sumber); }, 350));
      perbaruiSelesai();
    });

    tombolTambah.addEventListener("click", function () {
      penghitung++;
      var wadahBaru = document.createElement("div");
      wadahBaru.innerHTML = cetakanTanya.innerHTML.replace(/__KUNCI__/g, "b" + penghitung);
      var baru = wadahBaru.firstElementChild;
      daftarTanya.appendChild(baru);
      perbaruiNomor();
      tandaiUbah();
      baru.querySelector("textarea[name=teks]").focus();
      umumkan("Pertanyaan " + semuaBaris().length + " ditambahkan.");
    });

    daftarTanya.addEventListener("click", function (e) {
      var tombol = e.target.closest("[data-aksi-pertanyaan]");
      if (!tombol) return;
      var b = tombol.closest("[data-pertanyaan]");
      var aksi = tombol.dataset.aksiPertanyaan;
      if (aksi === "hapus") {
        var hapus = function () {
          var tetangga = b.nextElementSibling || b.previousElementSibling;
          b.remove();
          perbaruiNomor();
          tandaiUbah();
          umumkan("Pertanyaan dihapus. Tekan Simpan untuk menyimpan perubahan.");
          (tetangga ? tetangga.querySelector("textarea[name=teks]") : tombolTambah).focus();
        };
        var berisi = b.querySelector("textarea[name=teks]").value.trim() || b.querySelector("textarea[name=jawaban]").value.trim();
        if (berisi) {
          window.konfirmasi("Hapus pertanyaan " + b.querySelector("[data-nomor]").textContent +
            " beserta jawabannya? Penghapusan tersimpan setelah Anda menekan Simpan.",
            { judul: "Hapus pertanyaan", tombol: "Hapus" }, hapus);
        } else {
          hapus();
        }
        return;
      }
      if (aksi === "naik" && b.previousElementSibling) daftarTanya.insertBefore(b, b.previousElementSibling);
      else if (aksi === "turun" && b.nextElementSibling) daftarTanya.insertBefore(b.nextElementSibling, b);
      else return;
      perbaruiNomor();
      tandaiUbah();
      umumkan("Pertanyaan dipindah ke urutan " + b.querySelector("[data-nomor]").textContent + ".");
      // Tetap di tombol yang sama; bila kini di ujung (nonaktif), pindah ke tombol arah sebaliknya
      (tombol.disabled ? b.querySelector('[data-aksi-pertanyaan="' + (aksi === "naik" ? "turun" : "naik") + '"]') : tombol).focus();
      b.scrollIntoView({ block: "nearest", behavior: kurangiGerak.matches ? "auto" : "smooth" });
    });

    perbaruiNomor();
  }

  /* ---------- 18. Mode baca Materi Podcast ----------
     Filter status, pencarian dengan sorotan <mark>, ukuran huruf (localStorage["ukuran-baca"]), dan cetak.
     Semua di browser untuk satu materi; bagian yang disembunyikan filter juga tidak ikut dicetak. */
  var alatBaca = document.querySelector("[data-alat-baca]");
  if (alatBaca) {
    var wadahBaca = document.querySelector("[data-baca]");
    var bagianBaca = document.querySelectorAll("[data-instansi-baca]");
    var inputCari = alatBaca.querySelector("[data-cari-baca]");
    var hasilBaca = alatBaca.querySelector("[data-hasil-baca]");
    var kosongBaca = document.querySelector("[data-baca-kosong]");
    var statusPilih = "semua";
    var UKURAN = ["kecil", "sedang", "besar"];

    var aturUkuran = function (ukuran) {
      if (UKURAN.indexOf(ukuran) < 0) ukuran = "sedang";
      wadahBaca.dataset.ukuran = ukuran;
      Array.prototype.forEach.call(alatBaca.querySelectorAll("[data-ukuran-baca]"), function (t) {
        t.setAttribute("aria-pressed", t.dataset.ukuranBaca === ukuran ? "true" : "false");
      });
    };
    var ukuranTersimpan = null;
    try { ukuranTersimpan = localStorage.getItem("ukuran-baca"); } catch (e) {}
    aturUkuran(ukuranTersimpan);

    alatBaca.addEventListener("click", function (e) {
      var t = e.target.closest("[data-ukuran-baca]");
      if (t) {
        aturUkuran(t.dataset.ukuranBaca);
        try { localStorage.setItem("ukuran-baca", t.dataset.ukuranBaca); } catch (err) {}
      }
      if (e.target.closest("[data-cetak]")) window.print();
    });

    var hapusSorot = function () {
      Array.prototype.forEach.call(wadahBaca.querySelectorAll("mark[data-sorot-cari]"), function (m) {
        var induk = m.parentNode;
        induk.replaceChild(document.createTextNode(m.textContent), m);
        induk.normalize();
      });
    };
    // Bungkus setiap kemunculan kata (tanpa membedakan huruf besar/kecil) dengan <mark>; kembalikan jumlahnya
    var sorot = function (el, kata) {
      if (!el) return 0;
      var jumlah = 0, simpul = [], t, kecil = kata.toLowerCase();
      var penjelajah = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      while ((t = penjelajah.nextNode())) simpul.push(t);
      simpul.forEach(function (s) {
        var teks = s.nodeValue, rendah = teks.toLowerCase(), i = rendah.indexOf(kecil);
        if (i < 0) return;
        var potongan = document.createDocumentFragment(), posisi = 0;
        while (i >= 0) {
          potongan.appendChild(document.createTextNode(teks.slice(posisi, i)));
          var m = document.createElement("mark");
          m.setAttribute("data-sorot-cari", "");
          m.textContent = teks.slice(i, i + kata.length);
          potongan.appendChild(m);
          jumlah++;
          posisi = i + kata.length;
          i = rendah.indexOf(kecil, posisi);
        }
        potongan.appendChild(document.createTextNode(teks.slice(posisi)));
        s.parentNode.replaceChild(potongan, s);
      });
      return jumlah;
    };

    var terapkan = function () {
      hapusSorot();
      var kata = inputCari.value.trim();
      var cari = kata.length >= 2;
      var totalHasil = 0, instansiCocok = 0, tampil = 0;
      Array.prototype.forEach.call(bagianBaca, function (sec) {
        var cocokStatus = statusPilih === "semua" || sec.dataset.status === statusPilih;
        var nHasil = 0;
        var pertanyaan = sec.querySelectorAll("[data-pertanyaan-baca]");
        if (cocokStatus && cari) {
          var namaCocok = sorot(sec.querySelector("h2 [data-cari-isi]"), kata) > 0;
          nHasil += namaCocok ? 1 : 0;
          Array.prototype.forEach.call(pertanyaan, function (art) {
            var n = 0;
            Array.prototype.forEach.call(art.querySelectorAll("[data-cari-isi]"), function (el) { n += sorot(el, kata); });
            art.hidden = !(n > 0 || namaCocok);
            nHasil += n;
          });
        } else {
          Array.prototype.forEach.call(pertanyaan, function (art) { art.hidden = false; });
        }
        var terlihat = cocokStatus && (!cari || nHasil > 0);
        sec.hidden = !terlihat;
        Array.prototype.forEach.call(document.querySelectorAll('[data-isi-instansi="' + sec.dataset.instansiBaca + '"]'),
          function (li) { li.hidden = !terlihat; });
        if (terlihat) tampil++;
        totalHasil += nHasil;
        if (nHasil) instansiCocok++;
      });
      kosongBaca.hidden = tampil > 0;
      if (cari) {
        hasilBaca.textContent = totalHasil ? totalHasil + " hasil di " + instansiCocok + " instansi." : "Tidak ada hasil untuk “" + kata + "”.";
      } else if (kata) {
        hasilBaca.textContent = "Ketik minimal 2 huruf.";
      } else {
        hasilBaca.textContent = statusPilih === "semua" ? "" : "Menampilkan " + tampil + " dari " + bagianBaca.length + " instansi.";
      }
    };

    var penundaCari = null;
    inputCari.addEventListener("input", function () {
      clearTimeout(penundaCari);
      penundaCari = setTimeout(terapkan, 200);
    });
    alatBaca.addEventListener("change", function (e) {
      if (!e.target.matches("[data-saring-status]")) return;
      statusPilih = e.target.value;
      terapkan();
    });
  }
})();
