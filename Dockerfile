# PriceIQ — bundles the anti-bot scraper (Playwright/Chromium), the AI matcher
# (sentence-transformers), the Streamlit dashboard and the FastAPI service.
# Base image ships Chromium + all its system libs, so the scraper "just runs".
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 8501 = Streamlit dashboard, 8000 = FastAPI.
EXPOSE 8501 8000

# Default: the dashboard. Override `command` (compose) or CMD to run the API:
#   docker run ... uvicorn api:app --host 0.0.0.0 --port 8000
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
