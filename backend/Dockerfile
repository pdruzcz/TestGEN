FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# tesseract-ocr + language packs (eng/pol) so scanned-PDF OCR (Epic 2,
# Story 2-pdf-ocr) and GUI screenshot OCR (Epic 3) work at runtime.
# libpango/libcairo/fontconfig — natywne zależności WeasyPrint (faktury VAT,
# Epic 7 Story 7.6 AC2); fonts-dejavu — polskie znaki w PDF.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-pol \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    fontconfig \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# --- Builder stage ---
FROM base AS builder

COPY pyproject.toml .
COPY app/ app/
# Install main deps + the optional imaging group (PyMuPDF/pytesseract/cv2/
# numpy/pillow) so the scanned-PDF and GUI OCR paths are active in production.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[imaging]"

# --- Production stage ---
FROM base AS production

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
