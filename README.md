# Financial Architect – Dashboard Tabungan (Flask)

Aplikasi ini merupakan **sistem deteksi dan klasifikasi penyakit gigi berbasis citra** menggunakan teknologi **Deep Learning**.  
Pengguna dapat mengunggah gambar gigi melalui web, kemudian sistem akan memprediksi jenis penyakit gigi beserta tingkat kepercayaannya (confidence).

Aplikasi ini dibangun menggunakan:
- **PyTorch** → training & inferensi model AI
- **Flask** → web backend
- **HTML + Bootstrap** → tampilan web

## Instalasi dan Menjalankan Aplikasi

Ikuti langkah-langkah berikut untuk menjalankan sistem di lokal:

### 1️⃣ Install Dependencies
pip install -r requirements.txt

### 2️⃣ Jalankan Aplikasi
Windows: python app.py

Mac: python3 app.py

### 3️⃣ Akses di Browser
http://127.0.0.1:5000/

## Fitur Aplikasi 

**Dashboard**
- Card ringkasan: total tabungan, target tabungan, pemasukan, pengeluaran
- Edit target maksimal tabungan
- Edit & reset "sudah ditabung bulan ini"
- Grafik analitik pemasukan & pengeluaran bulanan per tahun
- Filter tahun dinamis (relatif dari data yang ada)
- Histori transaksi terbaru (pagination, maks 5 rows, hanya kategori Tabungan)
- Tombol filter mode grafik: pemasukan / pengeluaran / keduanya

**Transaksi**
- Tabel transaksi dengan pagination (maks 20 rows per halaman)
- Input transaksi baru: period, category, subcategory, description, IDR, accounts, amount, income/expense, note
- Auto-fill field accounts, IDR, amount saat input nominal
- Edit data transaksi (pop up dengan tombol simpan)
- Hapus data transaksi (per baris)
- Filter tampilan: pemasukan / pengeluaran
- Data tersimpan otomatis ke file .xlsx lokal

**Target Tabungan (Savings Goals)**
- Daftar goals dengan progress bar
- Buat goal baru: nama, target nominal, opsional persentase dari tabungan
- Edit goal yang sudah ada
- Hapus goal
- Data goals tersimpan di file .xlsx tersendiri dan dinamis

---

## 📸 Tampilan Aplikasi

### Halaman Utama
![Halaman Utama](design/dashboard.png)

### Data Transaksi
![Data Transaksi](design/transaksi.png)

### Target Tabungan
![Target Tabungan](design/targetTabungan.png)

---

## 🎯 Tujuan Program

Program ini bertujuan untuk:
- Mengidentifikasi penyakit gigi secara otomatis dari gambar
- Menerapkan deep learning pada bidang kesehatan gigi
- Menyediakan sistem deteksi berbasis web yang mudah digunakan

---

## 🦠 Kelas Penyakit yang Dideteksi

Model AI mampu mengklasifikasikan gambar gigi ke dalam beberapa kategori berikut:

- Calculus
- Dental Caries
- Gingivitis
- Mouth Ulcer
- Tooth Discoloration
- Hypodontia

Jumlah kelas menyesuaikan dataset yang digunakan saat proses training.

---

## ⚙️ Cara Kerja Sistem

1. Pengguna mengunggah gambar gigi melalui website
2. Sistem melakukan preprocessing gambar:
   - Resize (224 × 224)
   - Normalisasi
3. Model deep learning melakukan inferensi
4. Sistem menampilkan:
   - Nama penyakit gigi
   - Confidence prediksi (%)

---

## 🧠 Arsitektur Model

- **Base Model**: ResNet18 (Transfer Learning)
- **Framework**: PyTorch
- **Loss Function**: CrossEntropyLoss
- **Optimizer**: Adam
- **Input Image Size**: 224 × 224

Lapisan fully connected (FC) dimodifikasi agar sesuai dengan jumlah kelas penyakit gigi.

---