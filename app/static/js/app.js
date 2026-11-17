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

  /* ---------- 5. Kirim sekali + tombol progres ----------
     a) <button type="submit" data-tombol-progres="Membuat Word…">: WAJIB untuk setiap tombol ekspor/proses.
        Saat diklik, tombol itu sendiri berubah menjadi bilah progres berjalan (tak tentu, karena server memproses
        dalam satu permintaan) dan terkunci; kiriman berikutnya dari formulir yang sama (klik ganda, Enter,
        tombol lain) ditolak sampai halaman berganti, sehingga ekspor tidak berjalan dua kali.
     b) <form data-kirim-sekali data-teks-proses="Memproses...">: versi lama untuk formulir biasa; semua tombol
        kirim dinonaktifkan dan labelnya diganti. */
  var jadikanProgres = function (tombol) {
    if (!tombol._asli) tombol._asli = tombol.innerHTML;
    var teks = tombol.dataset.tombolProgres || "Memproses…";
    tombol.classList.add("tombol-progres");
    tombol.setAttribute("aria-busy", "true");
    tombol.innerHTML = "";
    var bilah = document.createElement("span");
    bilah.className = "tombol-progres-bilah";
    bilah.setAttribute("aria-hidden", "true");
    var label = document.createElement("span");
    label.className = "relative";
    label.setAttribute("role", "status");
    label.textContent = teks;
    tombol.appendChild(bilah);
    tombol.appendChild(label);
    // Dinonaktifkan setelah formulir mulai terkirim (bila langsung, sebagian browser membatalkan kirimannya)
    setTimeout(function () { tombol.disabled = true; }, 0);
  };
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (e.defaultPrevented || !form.matches) return;
    var tombol = e.submitter && e.submitter.hasAttribute("data-tombol-progres") ? e.submitter : null;
    if (form.dataset.terkirim) { e.preventDefault(); return; }    // sudah terkirim: tolak kiriman ganda
    if (tombol) {
      form.dataset.terkirim = "1";
      jadikanProgres(tombol);
      return;
    }
    if (!form.matches("[data-kirim-sekali]")) return;
    form.dataset.terkirim = "1";
    // Ditunda sampai formulir mulai terkirim: tombol yang dinonaktifkan saat event submit tidak ikut mengirim
    // name/value-nya (mis. aksi="naik:<id>" pada formulir dengan banyak tombol aksi)
    setTimeout(function () {
      Array.prototype.forEach.call(form.querySelectorAll("button[type=submit]"), function (t) {
        t.disabled = true;
        t.setAttribute("aria-busy", "true");
        var label = t.querySelector("span:not(.sr-only)") || t.querySelector("span");
        if (label) label.textContent = form.dataset.teksProses || "Memproses...";
      });
    }, 0);
  });
  // Bila halaman dibuka lagi lewat tombol Kembali browser, kembalikan tombol & formulir seperti semula
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) return;
    Array.prototype.forEach.call(document.querySelectorAll("form[data-terkirim]"), function (form) {
      delete form.dataset.terkirim;
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-kirim-sekali] button[type=submit], [data-tombol-progres]"), function (t) {
      t.disabled = false;
      t.removeAttribute("aria-busy");
      t.classList.remove("tombol-progres");
      if (t._asli) { t.innerHTML = t._asli; delete t._asli; }
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

  /* ---------- 7. Nama berkas terpilih (input file bergaya tombol) ----------
     Satu berkas: namanya; beberapa (input multiple): "3 berkas: a.pdf, b.pdf, c.pdf".
     Tombol [data-butuh-berkas="<id input>"] aktif hanya bila input itu berisi berkas. */
  Array.prototype.forEach.call(document.querySelectorAll("[data-pilih-berkas]"), function (input) {
    var nama = input.parentNode.querySelector("[data-nama-berkas]");
    var awal = nama ? nama.textContent : "";
    var tombolButuh = input.id ? document.querySelectorAll('[data-butuh-berkas="' + input.id + '"]') : [];
    var perbarui = function () {
      var berkas = Array.prototype.map.call(input.files, function (f) { return f.name; });
      if (nama) nama.textContent = !berkas.length ? awal
        : berkas.length === 1 ? berkas[0] : berkas.length + " berkas: " + berkas.join(", ");
      Array.prototype.forEach.call(tombolButuh, function (t) { t.disabled = !berkas.length; });
    };
    input.addEventListener("change", perbarui);
    perbarui();
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

  /* ---------- 20. Zona seret-lepas berkas umum: <div data-seret-berkas> berisi <input type=file> ----------
     Berkas yang dilepas digabung dengan pilihan sebelumnya lalu dipasang ke input (event "change" agar nama
     berkas & tombol [data-butuh-berkas] ikut diperbarui). Hanya berkas yang cocok dengan atribut accept
     yang diambil. Berbeda dari [data-zona-unggah] yang khusus foto Arsip Liputan. */
  if (window.DataTransfer) {
    Array.prototype.forEach.call(document.querySelectorAll("[data-seret-berkas]"), function (zonaBerkas) {
      var input = zonaBerkas.querySelector("input[type=file]");
      if (!input) return;
      var akhiranBoleh = (input.accept || "").split(",").map(function (a) { return a.trim().toLowerCase(); })
        .filter(function (a) { return a.charAt(0) === "."; });
      var cocok = function (f) {
        if (!akhiranBoleh.length) return true;
        var nama = f.name.toLowerCase();
        return akhiranBoleh.some(function (a) { return nama.slice(-a.length) === a; });
      };
      ["dragenter", "dragover"].forEach(function (jenis) {
        zonaBerkas.addEventListener(jenis, function (e) { e.preventDefault(); zonaBerkas.dataset.seret = ""; });
      });
      ["dragleave", "drop"].forEach(function (jenis) {
        zonaBerkas.addEventListener(jenis, function () { delete zonaBerkas.dataset.seret; });
      });
      zonaBerkas.addEventListener("drop", function (e) {
        e.preventDefault();
        if (!e.dataTransfer || !e.dataTransfer.files.length) return;
        var kumpulan = new DataTransfer();
        Array.prototype.forEach.call(input.files, function (f) { kumpulan.items.add(f); });
        var ditolak = [];
        Array.prototype.forEach.call(e.dataTransfer.files, function (f) {
          if (cocok(f)) kumpulan.items.add(f); else ditolak.push(f.name);
        });
        if (ditolak.length) window.notifikasi(ditolak.join(", ") + ": bukan berkas " + akhiranBoleh.join("/").toUpperCase().replace(/\./g, "") + ".", "galat");
        input.files = kumpulan.files;
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
    });
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
    var pasangFokus = function () {
      var elFokus = document.getElementById(idFokus);
      if (elFokus && elFokus.disabled) {
        // Tombolnya kini nonaktif (sudah di ujung daftar): pindah ke tombol lain di baris yang sama
        var baris = elFokus.closest("tr, li, section");
        elFokus = baris ? baris.querySelector("button:not([disabled])") : null;
      }
      if (elFokus) elFokus.focus();
    };
    // Dipasang setelah halaman selesai dimuat: bila alamat memuat jangkar (#...), browser memindahkan fokus ke
    // jangkar itu saat memuat halaman dan akan menimpa fokus yang dipasang lebih awal.
    if (document.readyState === "complete") setTimeout(pasangFokus, 0);
    else window.addEventListener("load", function () { setTimeout(pasangFokus, 0); });
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


    /* ---------- 19. Editor fokus jawaban (layar penuh, ala aplikasi catatan) ----------
       Tombol [data-buka-editor="<id textarea>"] membuka <dialog id="editor-fokus">. Teks disalin langsung ke
       kolom jawaban asli (event "input") sehingga pratinjau di halaman, tanda "belum disimpan", dan
       "Tandai selesai" ikut diperbarui; tetap disimpan lewat tombol Simpan.
       Pratinjau di kanan bisa disembunyikan (localStorage["editor-pratinjau"]) dan lebarnya diseret 20–50%
       (localStorage["editor-lebar-pratinjau"]); pemisah juga bisa digeser dengan panah kiri/kanan. */
    var ef = document.querySelector("[data-editor-fokus]");
    if (ef && ef.showModal) {
      var efTeks = ef.querySelector("[data-ef-teks]");
      var efBadan = ef.querySelector("[data-ef-badan]");
      var efPemisah = ef.querySelector("[data-ef-pemisah]");
      var efInfo = ef.querySelector("[data-ef-info]");
      var efTombolPratinjau = ef.querySelector("[data-ef-pratinjau-tombol]");
      var LEBAR_MIN = 20, LEBAR_MAKS = 50;
      var asal = null, tombolAsal = null;
      efTeks.dataset.pratinjauSumber = "ef-hasil";

      var simpanPilihan = function (kunci, nilai) { try { localStorage.setItem(kunci, nilai); } catch (e) {} };
      var bacaPilihan = function (kunci) { try { return localStorage.getItem(kunci); } catch (e) { return null; } };

      var aturLebar = function (persen) {
        persen = Math.round(Math.min(LEBAR_MAKS, Math.max(LEBAR_MIN, persen)));
        efBadan.style.setProperty("--lebar-pratinjau", persen + "%");
        efPemisah.setAttribute("aria-valuenow", persen);
        efPemisah.setAttribute("aria-valuetext", "Pratinjau " + persen + "% lebar layar");
        return persen;
      };
      var aturPratinjau = function (tampil) {
        if (tampil) efBadan.removeAttribute("data-tanpa-pratinjau");
        else efBadan.setAttribute("data-tanpa-pratinjau", "");
        efTombolPratinjau.setAttribute("aria-pressed", tampil ? "true" : "false");
      };
      aturLebar(parseFloat(bacaPilihan("editor-lebar-pratinjau")) || LEBAR_MAKS);
      aturPratinjau(bacaPilihan("editor-pratinjau") !== "sembunyi");

      var perbaruiInfo = function () {
        var n = efTeks.value.length;
        efInfo.textContent = n.toLocaleString("id-ID") + " / " + Number(efTeks.maxLength).toLocaleString("id-ID") + " karakter";
      };
      // Salin ke kolom asli + jadwalkan pratinjau editor
      var sinkron = function () {
        if (!asal) return;
        asal.value = efTeks.value;
        asal.dispatchEvent(new Event("input", { bubbles: true }));
        clearTimeout(penunda.get(efTeks));
        penunda.set(efTeks, setTimeout(function () { muatPratinjau(efTeks); }, 250));
        perbaruiInfo();
      };

      // Ganti teks [awal, akhir) lewat execCommand agar Ctrl+Z tetap berfungsi; cadangan setRangeText
      var ganti = function (awal, akhir, teks, pilihAwal, pilihAkhir) {
        efTeks.focus();
        efTeks.setSelectionRange(awal, akhir);
        var ok = false;
        try { ok = document.execCommand("insertText", false, teks); } catch (e) {}
        if (!ok) efTeks.setRangeText(teks, awal, akhir, "end");
        efTeks.setSelectionRange(pilihAwal, pilihAkhir === undefined ? pilihAwal : pilihAkhir);
        sinkron();
      };
      // Rentang baris penuh yang tersentuh pilihan
      var rentangBaris = function () {
        var v = efTeks.value, a = efTeks.selectionStart, b = efTeks.selectionEnd;
        if (b > a && v[b - 1] === "\n") b--;
        var awal = v.lastIndexOf("\n", a - 1) + 1;
        var akhir = v.indexOf("\n", b);
        if (akhir < 0) akhir = v.length;
        return { awal: awal, akhir: akhir, baris: v.slice(awal, akhir).split("\n") };
      };
      var bungkus = function (tanda) {
        var a = efTeks.selectionStart, b = efTeks.selectionEnd, v = efTeks.value;
        // Spasi di tepi pilihan diletakkan di luar tanda, karena "**teks **" tidak terbaca tebal
        while (a < b && /\s/.test(v[a])) a++;
        while (b > a && /\s/.test(v[b - 1])) b--;
        ganti(a, b, tanda + v.slice(a, b) + tanda, a + tanda.length, b + tanda.length);
      };
      var ubahBaris = function (fungsi) {
        var a = efTeks.selectionStart, b = efTeks.selectionEnd, r = rentangBaris();
        var hasil = r.baris.map(fungsi).join("\n");
        if (a === b) {
          // Tanpa pilihan: kursor tetap di posisi yang sama relatif terhadap akhir baris
          var posisi = Math.max(r.awal, r.awal + hasil.length - (r.akhir - a));
          ganti(r.awal, r.akhir, hasil, posisi);
        } else {
          ganti(r.awal, r.akhir, hasil, r.awal, r.awal + hasil.length);
        }
      };
      var PENANDA = /^(\s*)(\d+\.\s+|-\s+)?/;
      var format = {
        tebal: function () { bungkus("**"); },
        miring: function () { bungkus("*"); },
        judul: function () {
          ubahBaris(function (b) { var t = b.trim(); return /^\*\*.+\*\*$/.test(t) ? t.slice(2, -2) : (t ? "**" + t + "**" : b); });
        },
        nomor: function () {
          var n = 0;
          ubahBaris(function (b) { var m = b.match(PENANDA); return b.trim() ? m[1] + (++n) + ". " + b.slice(m[0].length) : b; });
        },
        poin: function () {
          ubahBaris(function (b) { var m = b.match(PENANDA); return b.trim() ? m[1] + "- " + b.slice(m[0].length) : b; });
        },
        // Menjorok: butir bernomor yang masuk menjadi anak daftar dimulai lagi dari "1."
        masuk: function () {
          var satuBaris = rentangBaris().baris.length === 1;
          ubahBaris(function (b) { return "  " + (satuBaris ? b.replace(/^(\s*)\d+\.(\s+)/, "$11.$2") : b); });
        },
        keluar: function () { ubahBaris(function (b) { return b.replace(/^(\t| {1,2})/, ""); }); },
        tabel: function () {
          var a = efTeks.selectionStart, v = efTeks.value;
          var awal = a > 0 && v[a - 1] !== "\n" ? "\n" : "";
          var tabel = awal + "| Kolom 1 | Kolom 2 |\n|---|---|\n|  |  |\n";
          var sel = a + tabel.indexOf("Kolom 1");
          ganti(a, efTeks.selectionEnd, tabel, sel, sel + "Kolom 1".length);
        },
      };
      ef.querySelector("[role=toolbar]").addEventListener("click", function (e) {
        var t = e.target.closest("[data-format]");
        if (t && format[t.dataset.format]) format[t.dataset.format]();
      });

      efTeks.addEventListener("input", sinkron);
      efTeks.addEventListener("keydown", function (e) {
        var mod = e.ctrlKey || e.metaKey;
        if (mod && !e.shiftKey && (e.key === "b" || e.key === "B")) { e.preventDefault(); format.tebal(); return; }
        if (mod && !e.shiftKey && (e.key === "i" || e.key === "I")) { e.preventDefault(); format.miring(); return; }
        if (e.key === "Tab" && !mod && !e.altKey) { e.preventDefault(); (e.shiftKey ? format.keluar : format.masuk)(); return; }
        if (e.key === "Enter" && !e.shiftKey && !mod && efTeks.selectionStart === efTeks.selectionEnd) {
          // Lanjutkan daftar: "- " atau "N. " dengan indentasi yang sama; baris penanda kosong = akhiri daftar
          var v = efTeks.value, a = efTeks.selectionStart;
          var awalBaris = v.lastIndexOf("\n", a - 1) + 1, baris = v.slice(awalBaris, a);
          var m = baris.match(/^(\s*)(\d+)\.\s+(.*)$/) || baris.match(/^(\s*)(-)\s+(.*)$/);
          if (!m) return;
          e.preventDefault();
          if (!m[3].trim()) { ganti(awalBaris, a, "", awalBaris); return; }
          var lanjut = m[2] === "-" ? "- " : (parseInt(m[2], 10) + 1) + ". ";
          var sisip = "\n" + m[1] + lanjut;
          ganti(a, a, sisip, a + sisip.length);
        }
      });

      // Seret pemisah: lebar pratinjau = jarak dari pemisah ke tepi kanan, 20–50% lebar badan editor
      efPemisah.addEventListener("pointerdown", function (e) {
        e.preventDefault();
        efPemisah.setPointerCapture(e.pointerId);
        efBadan.setAttribute("data-menyeret", "");
      });
      efPemisah.addEventListener("pointermove", function (e) {
        if (!efPemisah.hasPointerCapture(e.pointerId)) return;
        var kotak = efBadan.getBoundingClientRect();
        aturLebar((kotak.right - e.clientX) / kotak.width * 100);
      });
      var selesaiSeret = function (e) {
        if (!efPemisah.hasPointerCapture(e.pointerId)) return;
        efPemisah.releasePointerCapture(e.pointerId);
        efBadan.removeAttribute("data-menyeret");
        simpanPilihan("editor-lebar-pratinjau", efPemisah.getAttribute("aria-valuenow"));
      };
      efPemisah.addEventListener("pointerup", selesaiSeret);
      efPemisah.addEventListener("pointercancel", selesaiSeret);
      efPemisah.addEventListener("dblclick", function () { simpanPilihan("editor-lebar-pratinjau", aturLebar(LEBAR_MAKS)); });
      efPemisah.addEventListener("keydown", function (e) {
        var kini = parseFloat(efPemisah.getAttribute("aria-valuenow")), baru = null;
        if (e.key === "ArrowLeft") baru = kini + 2;        // pemisah ke kiri = pratinjau melebar
        else if (e.key === "ArrowRight") baru = kini - 2;
        else if (e.key === "Home") baru = LEBAR_MIN;
        else if (e.key === "End") baru = LEBAR_MAKS;
        if (baru === null) return;
        e.preventDefault();
        simpanPilihan("editor-lebar-pratinjau", aturLebar(baru));
      });

      efTombolPratinjau.addEventListener("click", function () {
        var tampil = efTombolPratinjau.getAttribute("aria-pressed") !== "true";
        aturPratinjau(tampil);
        simpanPilihan("editor-pratinjau", tampil ? "tampil" : "sembunyi");
        if (tampil) muatPratinjau(efTeks);
      });
      ef.querySelector("[data-ef-tutup]").addEventListener("click", function () { ef.close(); });

      document.addEventListener("click", function (e) {
        var t = e.target.closest("[data-buka-editor]");
        if (!t) return;
        var baris = t.closest("[data-pertanyaan]");
        asal = document.getElementById(t.dataset.bukaEditor);
        if (!asal) return;
        tombolAsal = t;
        ef.querySelector("[data-ef-nomor]").textContent = baris ? baris.querySelector("h2").textContent.replace("Pertanyaan", "").trim() : "";
        ef.querySelector("[data-ef-pertanyaan]").textContent = baris ? baris.querySelector("textarea[name=teks]").value.trim() : "";
        efTeks.value = asal.value;
        perbaruiInfo();
        var hasil = document.getElementById("ef-hasil");
        var pratinjauAsal = document.getElementById(asal.dataset.pratinjauSumber);
        hasil.innerHTML = pratinjauAsal ? pratinjauAsal.innerHTML : "";
        ef.showModal();
        efTeks.focus();
        efTeks.setSelectionRange(asal.selectionStart || 0, asal.selectionEnd || 0);
      });
      ef.addEventListener("close", function () {
        if (asal) {
          // Pastikan pratinjau di halaman langsung sesuai isi terakhir
          clearTimeout(penunda.get(asal));
          muatPratinjau(asal);
        }
        if (tombolAsal) tombolAsal.focus();
        asal = null;
        tombolAsal = null;
      });
    }

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
