FROM python:3.12-slim

# WeasyPrint runtime deps — these are the C libraries the Python bindings call into.
# Without them, `import weasyprint` raises OSError: cannot load library 'pango-1.0-0'.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        fonts-liberation \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-seed demo data so the deployed instance has something to show on first load.
RUN python seed.py

EXPOSE 8080
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 60 'app:create_app()'"]
