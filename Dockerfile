# svcdesk image: Python 3.13, dependencies installed at build time (no network at run time, API.md section 9).
FROM python:3.13-slim

WORKDIR /app

# Dependencies first, so Docker caches this layer while the code changes.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/ /app/src/

# The SQLite file lives in /data, a named volume in docker-compose.yml, so tickets survive a restart.
RUN mkdir -p /data
ENV SVCDESK_DB=/data/svcdesk.db

EXPOSE 8080
CMD ["uvicorn", "svcdesk.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
