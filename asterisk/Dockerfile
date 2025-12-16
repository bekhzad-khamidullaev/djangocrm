# Dockerfile for Asterisk 21 with WebRTC support (build from source)

# ==============================
# Builder stage
# ==============================
FROM debian:bookworm AS builder

# Base tools and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    git \
    gnupg \
    dirmngr \
    apt-transport-https \
    procps \
    build-essential \
    subversion \
    libssl-dev \
    libncurses5-dev \
    libxml2-dev \
    uuid-dev \
    libjansson-dev \
    libsqlite3-dev \
    libedit-dev \
    libcurl4-openssl-dev \
    libreadline-dev \
    libopus-dev \
    libsrtp2-dev \
    libspeex-dev \
    libspeexdsp-dev \
    unixodbc-dev \
    odbc-postgresql \
    pkg-config \
    python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src

# Clone Asterisk source (branch 21)
RUN git clone -b 21 https://github.com/asterisk/asterisk.git
WORKDIR /usr/src/asterisk

# Fetch optional codecs and install prerequisites
RUN contrib/scripts/get_mp3_source.sh || true
# Install detected prerequisites for Debian/Ubuntu
RUN contrib/scripts/install_prereq install || true

# Configure with bundled pjproject for compatibility
RUN ./configure --with-pjproject-bundled

# Enable codecs/modules via menuselect
RUN make menuselect.makeopts \
 && menuselect/menuselect \
    --enable format_mp3 \
    --enable codec_opus \
    --enable codec_g722 \
    --enable codec_gsm \
    --enable codec_ulaw \
    --enable codec_alaw \
    --enable format_wav \
    --enable format_wav_gsm \
    --enable format_pcm \
    --enable res_http_websocket \
    --enable res_pjsip \
    --enable res_pjsip_session \
    --enable res_pjsip_outbound_registration \
    --enable res_pjsip_endpoint_identifier_ip \
    --enable res_pjsip_acl \
    --enable res_pjsip_caller_id \
    --enable res_pjsip_nat \
    --enable res_pjsip_sdp_rtp \
    --enable res_pjsip_rfc3326 \
    --enable res_pjsip_transport_websocket \
    --enable res_rtp_asterisk \
    --enable res_srtp \
    --enable res_odbc \
    --enable res_config_odbc \
    --enable app_mixmonitor \
    --enable app_confbridge \
    --enable app_queue \
    --enable app_voicemail \
    --enable cdr_odbc \
    --enable cel_odbc \
    menuselect.makeopts

# Build and install
RUN make -j"$(nproc)" && make install
# Do not install sample configs; we provide our own configs via COPY
# RUN make samples

# ==============================
# Runtime stage
# ==============================
FROM debian:bookworm

# Runtime dependencies and clients
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    procps \
    gosu \
    wget \
    tar \
    msmtp \
    msmtp-mta \
    libssl3 \
    libncursesw6 \
    libxml2 \
    libjansson4 \
    libsqlite3-0 \
    libedit2 \
    libcurl4 \
    libopus0 \
    libsrtp2-1 \
    unixodbc \
    odbc-postgresql \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create Asterisk user and directories
RUN groupadd -r asterisk 2>/dev/null || true && \
    useradd -r -g asterisk asterisk 2>/dev/null || true && \
    mkdir -p /var/log/asterisk /var/lib/asterisk /var/spool/asterisk /etc/asterisk /var/run/asterisk && \
    chown -R asterisk:asterisk /var/log/asterisk /var/lib/asterisk /var/spool/asterisk /var/run/asterisk

# Fetch Asterisk sounds and MOH (en, ulaw/alaw/g722)
RUN set -e; \
    mkdir -p /var/lib/asterisk/sounds /var/lib/asterisk/moh; \
    cd /var/lib/asterisk/sounds; \
    for P in ulaw alaw g722; do \
      wget -q http://downloads.asterisk.org/pub/telephony/sounds/asterisk-core-sounds-en-${P}-current.tar.gz && \
      tar xzf asterisk-core-sounds-en-${P}-current.tar.gz && rm -f asterisk-core-sounds-en-${P}-current.tar.gz; \
    done; \
    cd /var/lib/asterisk/moh; \
    for P in ulaw alaw g722; do \
      wget -q http://downloads.asterisk.org/pub/telephony/sounds/asterisk-moh-opsound-${P}-current.tar.gz && \
      tar xzf asterisk-moh-opsound-${P}-current.tar.gz && rm -f asterisk-moh-opsound-${P}-current.tar.gz; \
    done; \
    chown -R asterisk:asterisk /var/lib/asterisk/sounds /var/lib/asterisk/moh

# Copy compiled Asterisk from builder
COPY --from=builder /usr/local/ /usr/local/

# Ensure expected runtime symlinks/paths
ENV PATH="/usr/local/sbin:/usr/local/bin:${PATH}"

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

# Run entrypoint as root to prepare configs, then it drops to 'asterisk' via gosu
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["asterisk", "-f", "-vvvg", "-c"]
