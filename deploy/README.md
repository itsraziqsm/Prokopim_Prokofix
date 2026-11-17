# Menjalankan Super App Prokopim di server Ubuntu (systemd + gunicorn + nginx)

```
Browser ──HTTPS──> nginx (port 80/443) ──> gunicorn 127.0.0.1:8000 (1 proses, 8 thread) ──> aplikasi Flask
                                            dijalankan systemd sebagai pengguna "superapp"
```

Berkas di folder ini:

| Berkas | Fungsi |
|---|---|
| `gunicorn.conf.py` | konfigurasi gunicorn (WAJIB `workers = 1`) |
| `superapp.service` | layanan systemd aplikasi |
| `nginx-superapp.conf` | reverse proxy nginx (batas unggahan, header keamanan) |
| `superapp-cadangan.service` + `.timer` | cadangan otomatis harian (opsional) |

Panduan ini mengasumsikan aplikasi di **`/opt/superapp`** dan pengguna sistem **`superapp`**. Bila memakai jalur
lain, sesuaikan jalur di `superapp.service` dan `superapp-cadangan.service`.

---

## 1. Paket sistem
```bash
sudo apt update
```
```bash
sudo apt install -y python3-venv python3-full git nginx libreoffice-writer fonts-dejavu fonts-crosextra-carlito fonts-crosextra-caladea
```
`libreoffice-writer` dipakai Pemecah SPT untuk membuat PDF. Fon Carlito/Caladea berukuran sama dengan Calibri/Cambria,
sehingga tata letak PDF hasil konversi tidak bergeser.

## 2. Pengguna layanan & kode aplikasi
```bash
sudo adduser --system --group --no-create-home --home /opt/superapp --shell /usr/sbin/nologin superapp
```
```bash
sudo git clone -b main https://github.com/itsraziqsm/Prokopim_Prokofix.git /opt/superapp
```
```bash
sudo chown -R superapp:superapp /opt/superapp
```
Wajib `-b main`. Branch lain berisi placeholder lama. Repo privat butuh token GitHub saat clone/pull.

## 3. Virtual environment & dependensi
```bash
sudo -u superapp python3 -m venv /opt/superapp/.venv
```
```bash
sudo -u superapp /opt/superapp/.venv/bin/pip install -r /opt/superapp/requirements-server.txt
```
```bash
sudo -u superapp mkdir -p /opt/superapp/instance/rumah-layanan
```
`requirements-server.txt` = `requirements.txt` + gunicorn. Folder `instance/` WAJIB sudah ada sebelum layanan dinyalakan
(systemd hanya mengizinkan layanan menulis di sana); `rumah-layanan` dipakai LibreOffice.

## 4. (Opsional) Pulihkan data dari komputer Windows
Di Windows: halaman **Cadangan** → buat cadangan **Semua data dan hasil** → **Uji** → **Unduh**. Salin ZIP-nya ke server
(mis. `scp`), lalu:
```bash
sudo install -o superapp -g superapp -m 600 cadangan-lengkap-*.zip /opt/superapp/instance/
```
```bash
cd /opt/superapp && sudo -u superapp env SUPERAPP_SERVER=1 .venv/bin/flask --app run cadangan periksa instance/cadangan-lengkap-NAMA.zip
```
```bash
cd /opt/superapp && sudo -u superapp env SUPERAPP_SERVER=1 .venv/bin/flask --app run cadangan pulihkan instance/cadangan-lengkap-NAMA.zip
```
Lakukan SEBELUM layanan dinyalakan (pemulihan menolak berjalan bila aplikasi sedang aktif). Jalur Windows di database
otomatis diubah ke jalur server. Kata sandi cadangan yang dipakai juga menjadi kata sandi cadangan di server.

## 5. Layanan systemd (gunicorn)
```bash
sudo cp /opt/superapp/deploy/superapp.service /etc/systemd/system/superapp.service
```
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now superapp
```
```bash
systemctl status superapp --no-pager && curl -sI http://127.0.0.1:8000/masuk | head -1
```
Baris terakhir harus `HTTP/1.1 200 OK` (atau `302` bila belum ada akun).

## 6. nginx
```bash
sudo cp /opt/superapp/deploy/nginx-superapp.conf /etc/nginx/sites-available/superapp
```
Ubah `server_name superapp.contoh.go.id;` menjadi domain atau alamat IP server:
```bash
sudo nano /etc/nginx/sites-available/superapp
```
```bash
sudo ln -sf /etc/nginx/sites-available/superapp /etc/nginx/sites-enabled/superapp && sudo rm -f /etc/nginx/sites-enabled/default
```
```bash
sudo nginx -t && sudo systemctl reload nginx
```
Bila firewall `ufw` aktif:
```bash
sudo ufw allow 'Nginx Full'
```
Port 8000 TIDAK perlu dibuka: gunicorn hanya mendengar dari mesin ini.

## 7. Akun pertama — segera!
Buka `http://DOMAIN/` di browser. Selama belum ada akun, halaman **/siapkan** bisa dibuka siapa pun yang menjangkau
server. Buat akun segera setelah layanan menyala (atau pulihkan cadangan lebih dulu, langkah 4).

## 8. HTTPS (sangat dianjurkan)
Dengan nama domain publik:
```bash
sudo apt install -y certbot python3-certbot-nginx
```
```bash
sudo certbot --nginx -d DOMAIN
```
Setelah situs terbuka lewat `https://`, aktifkan cookie khusus HTTPS:
```bash
sudo sed -i 's/SUPERAPP_HTTPS=0/SUPERAPP_HTTPS=1/' /etc/systemd/system/superapp.service
```
```bash
sudo systemctl daemon-reload && sudo systemctl restart superapp
```
Bila sudah stabil, hapus tanda `#` di baris `Strict-Transport-Security` pada konfigurasi nginx lalu `sudo systemctl
reload nginx`. Untuk server internal tanpa domain publik, minta sertifikat dari pengelola jaringan instansi.
**Jangan** mengisi `SUPERAPP_HTTPS=1` selama situs masih `http://`: login tidak akan bertahan.

## 9. (Opsional) Cadangan otomatis harian
Buat kata sandi cadangan dulu lewat halaman **Cadangan**. Simpan sandinya di berkas yang hanya bisa dibaca root & layanan:
```bash
sudo install -d -m 750 -o root -g superapp /etc/superapp
```
```bash
sudo install -m 640 -o root -g superapp /dev/null /etc/superapp/cadangan.env && sudo nano /etc/superapp/cadangan.env
```
Isi berkas itu satu baris: `SUPERAPP_SANDI_CADANGAN=kata-sandi-cadangan-anda`. Lalu:
```bash
sudo cp /opt/superapp/deploy/superapp-cadangan.service /opt/superapp/deploy/superapp-cadangan.timer /etc/systemd/system/
```
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now superapp-cadangan.timer
```
```bash
sudo systemctl start superapp-cadangan.service && journalctl -u superapp-cadangan -n 20 --no-pager
```
Cadangan tersimpan di `/opt/superapp/instance/cadangan/berkas/` dan tampil di halaman Cadangan. Cadangan lama tidak
dihapus otomatis: hapus lewat halaman Cadangan bila ruang disk menipis. Salin cadangan secara berkala ke tempat lain
(server cadangan / media terpisah) — cadangan di disk yang sama tidak melindungi dari kerusakan disk.

---

## Pekerjaan rutin

Memperbarui aplikasi (buat cadangan dulu):
```bash
cd /opt/superapp && sudo -u superapp git pull && sudo -u superapp .venv/bin/pip install -r requirements-server.txt
```
```bash
sudo systemctl restart superapp
```
CSS sudah di-commit, jadi server tidak butuh Node/npm.

Melihat log aplikasi:
```bash
journalctl -u superapp -f
```
Perintah terminal aplikasi selalu dijalankan sebagai pengguna `superapp` dari `/opt/superapp`, contoh:
```bash
cd /opt/superapp && sudo -u superapp env SUPERAPP_SERVER=1 .venv/bin/flask --app run cadangan buat
```
Pemulihan cadangan: matikan layanan dulu, pulihkan, lalu nyalakan lagi:
```bash
sudo systemctl stop superapp
```
```bash
cd /opt/superapp && sudo -u superapp env SUPERAPP_SERVER=1 .venv/bin/flask --app run cadangan pulihkan instance/cadangan/berkas/NAMA.zip
```
```bash
sudo systemctl start superapp
```

## Bila ada masalah

| Gejala | Penyebab umum |
|---|---|
| `502 Bad Gateway` | gunicorn tidak berjalan: `systemctl status superapp`, `journalctl -u superapp -n 50` |
| `413 Request Entity Too Large` | unggahan > `client_max_body_size` di nginx |
| Login selalu kembali ke halaman masuk | `SUPERAPP_HTTPS=1` padahal situs masih `http://` |
| `Permission denied` di log | berkas bukan milik `superapp`: `sudo chown -R superapp:superapp /opt/superapp` |
| PDF SPT tidak dibuat | `libreoffice-writer` belum terpasang, atau folder `instance/rumah-layanan` belum ada |
| `git pull`: "dubious ownership" | jalankan git sebagai `sudo -u superapp`, bukan sebagai root |

## Catatan
- **`workers = 1` jangan diubah.** Proses latar Pemecah SPT berjalan sebagai thread di dalam proses web. Gunicorn
  melayani banyak pengguna sekaligus lewat 8 thread.
- `SUPERAPP_SERVER=1` (di `superapp.service`) membuat aplikasi membaca header dari nginx (alamat, http/https) dan
  menyembunyikan tombol "Buka folder" (di server tombol itu membuka folder di mesin server, bukan komputer pengguna).
- Saat ini hanya akun pertama yang bisa dibuat lewat web. Akun tambahan untuk rekan kerja belum tersedia.
