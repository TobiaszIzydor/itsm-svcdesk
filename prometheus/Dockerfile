# My own Prometheus (observability profile): config baked in, no bind mount (house rule).
FROM prom/prometheus:v3.15.0
COPY prometheus.yml alerts.yml /etc/prometheus/
