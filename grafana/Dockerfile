# My own Grafana (observability profile): provisioning and dashboards baked in, no bind mount (house rule).
FROM grafana/grafana:13.2.3
COPY provisioning /etc/grafana/provisioning
COPY dashboards /var/lib/grafana/dashboards
