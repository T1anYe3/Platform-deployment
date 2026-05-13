FROM python:3.12-alpine

RUN pip install --no-cache-dir requests elasticsearch

# Install MinIO client
RUN wget -q https://dl.min.io/client/mc/release/linux-amd64/mc -O /usr/local/bin/mc && \
    chmod +x /usr/local/bin/mc

# Install curl for health checks
RUN apk add --no-cache curl openssl

WORKDIR /scripts

# Bridge scripts and state directory
COPY scripts/ /scripts/
RUN mkdir -p /state /tls

CMD ["python3", "/scripts/bridge-runner.py"]
