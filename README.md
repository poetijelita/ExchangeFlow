# ExchangeFlow

Aplikasi web lokal untuk EP Tracker, IR Tracker, dashboard, dan tindak lanjut tim Outgoing Global Talent / Global Teacher. Aplikasi berjalan di satu komputer dan tidak terhubung dengan EXPA.

## Menjalankan aplikasi

1. Buka Terminal dan masuk ke folder proyek:
   ```bash
   cd /Users/poeti/ExchangeFlow
   ```
2. Jalankan aplikasi dengan Python 3:
   ```bash
   python3 app.py
   ```
3. Buka **http://127.0.0.1:8000** di browser. Biarkan Terminal terbuka saat aplikasi digunakan. Tekan `Ctrl+C` untuk menghentikannya.

Tidak perlu memasang paket tambahan. Jika folder dipindahkan, sesuaikan lokasi pada perintah `cd`.

## Penggunaan pertama dan akun

Pada penggunaan pertama, buat nama, username, dan password untuk akun **VP**. Password minimal 8 karakter; simpan dengan baik. Setelah masuk, VP dapat membuat akun tambahan di menu **Kelola Akun**. Setiap anggota masuk dengan username dan password masing-masing, dan dapat menggunakan tombol **Keluar** setelah selesai. Sesi masuk berakhir saat server dihentikan.

- **VP:** melihat dan mengelola seluruh EP, peluang, tugas, dan akun; dapat menunjuk EP Manager pada EP.
- **Team Leader:** melihat semua EP, peluang, dan tugas; dapat membuat atau mengubah data serta menunjuk EP Manager pada EP. Pembuatan akun hanya untuk VP.
- **EP Manager:** melihat dan memperbarui EP yang ditugaskan kepadanya, serta membuat dan mengelola tugas internal miliknya. Peluang pada IR Tracker dapat dilihat. Penugasan EP, akun, dan pengubahan peluang dikelola VP atau Team Leader.

Untuk menugaskan EP, VP atau Team Leader membuka **EP Tracker**, memilih **Lihat / Ubah**, memilih akun pada kolom **EP Manager**, lalu menyimpan. To-do list mencatat pekerjaan internal EP Manager dan tidak memerlukan peserta. VP dan Team Leader dapat menugaskan tugas kepada EP Manager; EP Manager dapat membuat dan mengelola tugasnya sendiri. Perubahan penugasan EP tidak memindahkan tugas antar anggota. Tugas bertenggat sebelum hari ini ditandai terlambat.

Status EP yang digunakan adalah Open, Applied, Accepted, Approved, Realized, Finished, dan Completted. Status lama tetap tersimpan dan dapat diubah secara bertahap. Tugas dari versi sebelumnya tetap tersedia dan ditugaskan ke EP Manager yang menangani EP pada saat migrasi. Jika EP belum memiliki EP Manager, VP atau Team Leader perlu menugaskan tugas tersebut secara manual.

Data EP dari versi sebelumnya tetap tersedia. Kolom PIC lama dipertahankan sebagai catatan; penugasan ke akun EP Manager perlu diatur satu per satu agar EP dapat muncul pada akun EP Manager yang tepat.

## Penyimpanan dan cadangan

Data dan akun tersimpan dalam `exchangeflow.db` di folder proyek. Sebelum memperbarui atau memindahkan aplikasi, hentikan server dengan `Ctrl+C`, lalu salin berkas database sebagai cadangan. Password tidak disimpan dalam bentuk teks biasa. Berkas database tetap dapat dibuka oleh orang yang memiliki akses langsung ke komputer atau berkas tersebut, jadi simpan dan bagikan cadangannya dengan hati-hati.

Aplikasi hanya mendengarkan di `127.0.0.1` dan dirancang untuk satu komputer, bukan untuk penggunaan bersama melalui internet. Login membatasi penggunaan melalui aplikasi, bukan akses langsung ke berkas komputer. Tidak ada sinkronisasi antar komputer atau fitur pemulihan password otomatis.

## Pengujian

```bash
python3 -m unittest discover -s tests -v
```
