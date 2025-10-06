# Streamlit Chatbot Learning - V1
StudyBuddy AI adalah aplikasi chatbot interaktif berbasis Streamlit dan Google Gemini yang dirancang sebagai teman belajar virtual. Aplikasi ini membantu siswa memahami materi pelajaran melalui tanya-jawab, kuis adaptif, dan review konsep yang sulit. Unggah file materi (PDF, TXT, MD) atau masukkan topik, lalu eksplorasi dengan cara yang menyenangkan dan efektif.

### Fitur Utama
- Mode Belajar (Chat): Tanya-jawab bebas tentang materi, dengan dukungan file konteks untuk jawaban yang akurat.
- Mode Kuis: Buat kuis pilihan ganda otomatis dengan tingkat kesulitan (mudah, sedang, sulit). Lacak progres akurasi dan riwayat jawaban.
- Mode Review: Ringkas konsep sulit berdasarkan jawaban salah sebelumnya, dengan tips dan latihan cepat.
- Upload File: Integrasi dengan Google Gemini File API untuk menganalisis PDF, TXT, atau Markdown sebagai konteks belajar.
- Progres Tracking: Metrik percobaan, akurasi, dan ringkasan 5 jawaban terakhir.
- Bahasa Indonesia: Semua interaksi ramah dan adaptif dalam bahasa Indonesia.
- Reset & Pengaturan: Mudah reset data dan sesuaikan mode serta level kesulitan.

### Persyaratan Sistem
- Python 3.8+
- Streamlit 1.36.0 atau lebih tinggi
- Akses ke Google AI Studio (untuk API Key Gemini)

### Instalasi
1. Kloning Repository:
```text
git clone https://github.com/andhiksu/studybuddy-ai.git
cd studybuddy-ai
```
2. Buat Environment Virtual (disarankan):
```text
python -m venv venv
source venv/bin/activate  # Linux/Mac
# atau
venv\Scripts\activate  # Windows
```
3. Instal Dependensi:
```text
pip install -r requirements.txt
```
File `requirements.txt` mencakup:
- `streamlit>=1.36.0`
- `google-genai>=1.0.0`
- `pypdf>=5.0.0`
4. Dapatkan API Key:
  - Dapatkan API Key [Google AI Studio](https://aistudio.google.com/app/api-keys)
  - Buat API Key baru dan simpan aman.
 
### Cara Menjalankan
1. Jalankan aplikasi:
```text
streamlit run streamlit_chatbot_learning.py
```
2. Buka browser di `http://localhost:8501`.
3. Di sidebar:
   - Masukkan API Key Gemini dan klik Set API Key.
   -  Unggah file materi atau masukkan topik (misalnya: "Fisika Kuantum").
   -  Pilih mode (Belajar, Kuis, Review) dan tingkat kesulitan.
   -  Klik Explore Topik untuk mulai.

Aplikasi akan otomatis memuat prompts dari `prompts_chatbot_learning.txt` untuk instruksi sistem dan kuis.

### Penggunaan
- API Key: Wajib untuk mengakses Gemini.
- Upload File: Dukung PDF/TXT/MD; file diunggah ke Gemini File API untuk konteks.
- Topik Manual: Jika tanpa file, masukkan deskripsi topik untuk eksplorasi.
- Mode & Level: Pilih interaksi (Belajar untuk chat, Kuis untuk tes, Review untuk ulasan).
- Reset: Hapus semua data dan mulai baru.

### Struktur Project
```text
studybuddy-ai/
├── streamlit_chatbot_learning.py  # Aplikasi utama Streamlit
├── prompts_chatbot_learning.txt   # Template prompts untuk sistem, kuis, dan review
├── requirements.txt               # Dependensi Python
└── README.md                      # Dokumen ini
```
- streamlit_chatbot_learning.py: Logika inti, termasuk upload file, generate respons, dan rendering UI.
- prompts_chatbot_learning.txt: Konfigurasi prompt Gemini (sistem role, instruksi JSON kuis, tips review).

### Troubleshooting
- Error API Key: Pastikan google-genai>=1.0.0 terinstal; restart app setelah update.
- Upload Gagal: Cek MIME type file; app otomatis deteksi PDF/TXT/MD.
- JSON Kuis Rusak: Model Gemini kadang output tidak sempurna; app coba parse otomatis.
- No Internet: App butuh akses Gemini API; pastikan koneksi stabil.
