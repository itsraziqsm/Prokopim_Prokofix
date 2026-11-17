# Membersihkan server dari Super App Prokopim

Panduan ini menghapus SEMUA yang dipasang oleh `deploy/README.md` (layanan, nginx, kode, data, pengguna `superapp`).
Jalankan berurutan. Perintah yang gagal karena bagiannya memang belum pernah dipasang boleh diabaikan.

> **Data ikut terhapus di langkah 5.** Bila server pernah dipakai sungguhan, unduh dulu cadangan terbaru
> (halaman Cadangan → Buat → Uji → Unduh) dan simpan di tempat aman.

## 1. Hentikan aplikasi yang dijalankan manual
```bash
sudo pkill -f "run.py|app.py|gunicorn"
```

## 2. Layanan systemd
```bash
sudo systemctl disable --now superapp superapp-cadangan.timer superapp-cadangan.service
```
```bash
sudo rm -f /etc/systemd/system/superapp.service /etc/systemd/system/superapp-cadangan.service /etc/systemd/system/superapp-cadangan.timer
```
```bash
sudo systemctl daemon-reload && sudo systemctl reset-failed
```

## 3. Konfigurasi nginx
```bash
sudo rm -f /etc/nginx/sites-enabled/superapp /etc/nginx/sites-available/superapp /etc/nginx/conf.d/superapp.conf
```
Kembalikan halaman bawaan nginx (bila dulu dihapus/dimatikan):
```bash
[ -f /etc/nginx/sites-available/default ] && sudo ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default; [ -f /etc/nginx/conf.d/default.conf.mati ] && sudo mv /etc/nginx/conf.d/default.conf.mati /etc/nginx/conf.d/default.conf; true
```
```bash
sudo nginx -t && sudo systemctl reload nginx
```
Bila nginx dipasang HANYA untuk aplikasi ini dan tidak dipakai situs lain, boleh dihapus sekalian:
```bash
sudo systemctl disable --now nginx && sudo apt purge -y nginx nginx-common && sudo rm -rf /etc/nginx
```

## 4. Sertifikat HTTPS (hanya bila pernah menjalankan certbot)
```bash
sudo certbot certificates
```
```bash
sudo certbot delete --cert-name DOMAIN
```

## 5. Kode, data, dan berkas rahasia
```bash
sudo rm -rf /opt/superapp /etc/superapp
```
Salinan repo/ZIP lain yang pernah dibuat (mis. clone pertama di folder home, ZIP cadangan yang disalin lewat scp).
Periksa dulu hasilnya, baru hapus yang memang milik aplikasi ini:
```bash
ls -d ~/Prokopim_Prokofix ~/cadangan-*.zip 2>/dev/null
```
```bash
rm -rf ~/Prokopim_Prokofix ~/cadangan-*.zip
```

## 6. Pengguna sistem `superapp`
```bash
sudo deluser --system superapp; sudo delgroup --system superapp 2>/dev/null; true
```

## 7. Firewall (hanya bila pernah menjalankan `ufw allow 'Nginx Full'`)
```bash
sudo ufw delete allow 'Nginx Full'
```

## 8. (Opsional) Paket sistem
Hapus HANYA bila tidak dipakai keperluan lain di server ini:
```bash
sudo apt purge -y libreoffice-writer libreoffice-common fonts-crosextra-carlito fonts-crosextra-caladea certbot python3-certbot-nginx && sudo apt autoremove -y
```
`python3-venv`, `python3-full`, dan `git` sebaiknya dibiarkan (umum dipakai).

## 9. Periksa
Semua baris harus kosong / "not found" / "No such file":
```bash
systemctl list-unit-files | grep superapp; ls /opt/superapp /etc/superapp 2>&1; id superapp 2>&1; sudo ss -ltnp | grep ':8000\b'
```
