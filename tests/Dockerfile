# tests image (Stretch S3): standard library only, so nothing is installed; it reaches only SVCDESK_URL.
FROM python:3.13-slim

WORKDIR /tests
COPY run_tests.py /tests/run_tests.py

ENV SVCDESK_URL=http://svcdesk:8080
CMD ["python", "-u", "/tests/run_tests.py"]
