# tests image (Stretch S3): pytest is installed at build time; at run time it reaches only SVCDESK_URL.
FROM python:3.13-slim

WORKDIR /tests
COPY requirements.txt /tests/requirements.txt
RUN pip install --no-cache-dir -r /tests/requirements.txt

COPY *.py /tests/

ENV SVCDESK_URL=http://svcdesk:8080
CMD ["python", "-u", "/tests/run_tests.py"]
