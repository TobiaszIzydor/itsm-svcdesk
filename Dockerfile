# svcdesk image: Python 3.13, dependencies installed at build time (no network at run time, API.md section 9).
# Lab 5 triage (TRIAGE.md): the base image is pinned by digest (python:3.13-slim of 14 November 2026), the Debian
# packages are upgraded at build time, and pip is removed after the install - it is needed only to install, and its
# vendored copies of msgpack, urllib3 and pkg_resources carry fixed CVEs that no pip release ships yet. The service
# runs as an unprivileged user (Semgrep dockerfile missing-user), owner of /data where SQLite writes.
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so Docker caches this layer while the code changes.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && pip uninstall -y pip

COPY src/ /app/src/

# The SQLite file lives in /data, a named volume in docker-compose.yml, so tickets survive a restart.
RUN useradd --system --uid 10001 --no-create-home svcdesk && mkdir -p /data && chown svcdesk:svcdesk /data
ENV SVCDESK_DB=/data/svcdesk.db
USER svcdesk

EXPOSE 8080
CMD ["uvicorn", "svcdesk.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
