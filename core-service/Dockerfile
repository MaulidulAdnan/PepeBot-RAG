# Menggunakan PHP 8.5 (Sesuai dengan versi lokal Anda)
FROM php:8.5-cli

# Install dependensi sistem yang dibutuhkan Laravel & ekstensi database PostgreSQL
RUN apt-get update && apt-get install -y \
    git curl libpng-dev libonig-dev libxml2-dev zip unzip libpq-dev \
    && docker-php-ext-install pdo_pgsql mbstring exif pcntl bcmath gd

# Membawa masuk Composer (Package Manager PHP)
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

# Install Node.js versi 26.x (Sesuai dengan Node 26.10.0 lokal Anda)
RUN curl -fsSL https://deb.nodesource.com/setup_26.x | bash - \
    && apt-get install -y nodejs

# Tentukan folder kerja utama di dalam container
WORKDIR /app

# Perintah yang dijalankan ketika container menyala
CMD bash -c "composer install && npm install && npm run dev"