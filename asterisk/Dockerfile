# Dockerfile for Asterisk 21 with WebRTC support
FROM debian:bookworm-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    asterisk \
    asterisk-modules \
    asterisk-core-sounds-en \
    asterisk-core-sounds-ru \
    asterisk-moh-opsound-wav \
    asterisk-config \
    odbc-postgresql \
    unixodbc \
    postgresql-client \
    curl \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Create Asterisk user if not exists
RUN groupadd -r asterisk 2>/dev/null || true && \
    useradd -r -g asterisk asterisk 2>/dev/null || true

# Create necessary directories
RUN mkdir -p /var/log/asterisk \
    /var/lib/asterisk \
    /var/spool/asterisk \
    /etc/asterisk \
    /var/run/asterisk \
    && chown -R asterisk:asterisk /var/log/asterisk \
    /var/lib/asterisk \
    /var/spool/asterisk \
    /var/run/asterisk

# Copy configuration files
COPY config/ /etc/asterisk/

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose ports
# SIP: 5060/UDP, 5060/TCP
# RTP: 10000-10100/UDP
# AMI: 5038/TCP
# HTTP/WS: 8088/TCP
# HTTPS/WSS: 8089/TCP
EXPOSE 5060/udp 5060/tcp 5038/tcp 8088/tcp 8089/tcp
EXPOSE 10000-10100/udp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD asterisk -rx "core show version" || exit 1

WORKDIR /var/lib/asterisk

USER asterisk

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["asterisk", "-f", "-vvvg", "-c"]
