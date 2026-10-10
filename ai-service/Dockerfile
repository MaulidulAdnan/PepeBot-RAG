# Menggunakan Python 3.12 versi ringan (Sesuai dengan Python 3.12.5 lokal Anda)
FROM python:3.12-slim

# Tentukan folder kerja utama di dalam container
WORKDIR /app

# Install compiler C dan dependensi Postgres (Wajib untuk library psycopg2 dan pgvector)
RUN apt-get update && apt-get install -y libpq-dev gcc

# Salin daftar library ke dalam container dan install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Menjalankan Uvicorn. Host 0.0.0.0 wajib agar bisa diakses dari luar container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]