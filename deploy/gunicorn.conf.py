"""Konfigurasi gunicorn untuk Super App Prokopim di server.

Dipakai oleh deploy/superapp.service:
    .venv/bin/gunicorn --config deploy/gunicorn.conf.py run:app
`run:app` = objek `app` di run.py (dibuat create_app() saat diimpor; bagian "python run.py" tidak dijalankan).
"""

# Hanya dari mesin ini; dunia luar masuk lewat nginx (lihat deploy/nginx-superapp.conf)
bind = "127.0.0.1:8000"

# WAJIB 1 proses: proses latar Pemecah SPT berjalan sebagai THREAD di dalam proses web dan progresnya ditanyakan
# ke proses yang sama. Lebih dari 1 worker = permintaan bisa jatuh ke proses lain. Konkurensi lewat thread.
workers = 1
worker_class = "gthread"
threads = 8

# Ekspor Word/PDF, gabung PDF, dan cadangan berjalan dalam satu permintaan; beri waktu cukup.
# (Untuk gthread, timeout = batas proses worker tidak memberi tanda hidup, bukan batas lama permintaan.)
timeout = 300
graceful_timeout = 60
keepalive = 5

# JANGAN pakai max_requests: worker yang dimulai ulang akan memutus thread pemrosesan SPT yang sedang jalan.

# Header X-Forwarded-* hanya dipercaya dari nginx di mesin yang sama
forwarded_allow_ips = "127.0.0.1"

# Log ke stdout/stderr -> ditangkap journald (lihat: journalctl -u superapp)
accesslog = "-"
errorlog = "-"
loglevel = "info"
