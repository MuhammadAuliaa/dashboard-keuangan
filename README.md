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
python app.py

### 3️⃣ Akses di Browser
http://127.0.0.1:5000/

## Fitur Dashboard

- **Total Tabungan** – balance utama dengan progress bar
- **3 Stat Cards** – Total / Active / Completed goals
- **Analytics Chart** – Area chart 8 bulan (Chart.js)
- **Recent Activity** – Tabel dengan filter Newest / Active
- **Monthly Goal** – Progress bulanan + avg daily + forecast
- **Upcoming Deadlines** – 3 goals terdekat deadline-nya
- **Add Funds Modal** – Form tambah dana via API `/api/add-funds`
- **Toast Notification** – Feedback sukses/gagal


> ⚠️ Hasil prediksi bersifat informatif dan **tidak menggantikan diagnosis dokter gigi**.

---

## 📸 Tampilan Aplikasi

### Halaman Utama
![Halaman Utama](screenshots/1.png)

### Upload Gambar Gigi
![Upload Gambar](screenshots/2.png)

### Hasil Prediksi
![Hasil Prediksi](screenshots/3.png)

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