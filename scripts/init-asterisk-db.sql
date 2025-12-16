-- Asterisk Realtime (PostgreSQL) initialization
-- This script is executed by the official postgres image on first DB init.
-- It will:
-- 1) Create role `asterisk` (if not exists)
-- 2) Create database `asterisk` owned by role `asterisk` (if not exists)
-- 3) Create PJSIP realtime tables inside `asterisk` database (if not exists)

-- 1) Create role `asterisk` if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'asterisk'
    ) THEN
        CREATE ROLE asterisk WITH LOGIN PASSWORD 'sP5CDu0vFMLZ5RJpgxcr46Ir';
    END IF;
END
$$;

-- 2) Create database `asterisk` if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_database WHERE datname = 'asterisk'
    ) THEN
        CREATE DATABASE asterisk OWNER asterisk;
    END IF;
END
$$;

-- 3) Create PJSIP realtime tables in `asterisk` database
\connect asterisk

-- ps_endpoints
CREATE TABLE IF NOT EXISTS ps_endpoints (
    id                      VARCHAR(80) PRIMARY KEY,
    transport               VARCHAR(80),
    aors                    VARCHAR(255),
    auth                    VARCHAR(80),
    context                 VARCHAR(80),
    disallow                VARCHAR(200) DEFAULT 'all',
    allow                   VARCHAR(200) DEFAULT 'ulaw,alaw,opus,g722',
    mailbox                 VARCHAR(80),
    dtmf_mode               VARCHAR(20) DEFAULT 'rfc4733',
    direct_media            VARCHAR(5)  DEFAULT 'no',
    connected_line_method   VARCHAR(20) DEFAULT 'invite',
    direct_media_glare_mitigation VARCHAR(20) DEFAULT 'none',
    disable_direct_media_on_nat VARCHAR(5) DEFAULT 'yes',
    ice_support             VARCHAR(5)  DEFAULT 'yes',
    force_rport             VARCHAR(5)  DEFAULT 'yes',
    rewrite_contact         VARCHAR(5)  DEFAULT 'yes',
    rtp_symmetric           VARCHAR(5)  DEFAULT 'yes',
    media_encryption        VARCHAR(20),
    webrtc                  VARCHAR(5)  DEFAULT 'yes',
    callerid                VARCHAR(80),
    from_user               VARCHAR(80),
    language                VARCHAR(20),
    t38_udptl               VARCHAR(5),
    rtp_timeout             INTEGER,
    rtp_timeout_hold        INTEGER,
    rtp_keepalive           INTEGER,
    deny                    VARCHAR(95),
    permit                  VARCHAR(95),
    transport_tls           VARCHAR(80),
    media_use_received_transport VARCHAR(5),
    outbound_auth           VARCHAR(80),
    outbound_proxy          VARCHAR(80),
    allow_subscribe         VARCHAR(5),
    subscribe_context       VARCHAR(80),
    trust_id_inbound        VARCHAR(5),
    trust_id_outbound       VARCHAR(5),
    device_state_busy_at    INTEGER,
    send_pai                VARCHAR(5),
    send_rpid               VARCHAR(5)
);

-- ps_auths
CREATE TABLE IF NOT EXISTS ps_auths (
    id              VARCHAR(80) PRIMARY KEY,
    auth_type       VARCHAR(20) DEFAULT 'userpass',
    username        VARCHAR(80),
    password        VARCHAR(80),
    realm           VARCHAR(80)
);

-- ps_aors
CREATE TABLE IF NOT EXISTS ps_aors (
    id                      VARCHAR(80) PRIMARY KEY,
    contact                 VARCHAR(255),
    default_expiration      INTEGER DEFAULT 3600,
    mailboxes               VARCHAR(80),
    max_contacts            INTEGER DEFAULT 1,
    minimum_expiration      INTEGER DEFAULT 60,
    remove_existing         VARCHAR(5) DEFAULT 'yes',
    qualify_frequency       INTEGER,
    authenticate_qualify    VARCHAR(5),
    support_path            VARCHAR(5) DEFAULT 'yes'
);

-- ps_contacts (runtime registrations)
CREATE TABLE IF NOT EXISTS ps_contacts (
    id                      VARCHAR(255) PRIMARY KEY,
    uri                     VARCHAR(255),
    expiration_time         TIMESTAMP,
    qualify_frequency       INTEGER,
    outbound_proxy          VARCHAR(255),
    path                    VARCHAR(255),
    user_agent              VARCHAR(255),
    endpoint                VARCHAR(80),
    reg_server              VARCHAR(255),
    via_addr                VARCHAR(255),
    via_port                INTEGER,
    call_id                 VARCHAR(255),
    prune_on_boot           VARCHAR(5),
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

-- ps_transports
CREATE TABLE IF NOT EXISTS ps_transports (
    id                          VARCHAR(80) PRIMARY KEY,
    type                        VARCHAR(20) DEFAULT 'transport',
    protocol                    VARCHAR(3)  DEFAULT 'udp',
    bind                        VARCHAR(50),
    external_media_address      VARCHAR(80),
    external_signaling_address  VARCHAR(80),
    external_signaling_port     INTEGER,
    local_net                   VARCHAR(255),
    tos                         VARCHAR(20),
    cos                         VARCHAR(20)
);

-- ps_endpoint_id_ips (IP-based endpoint identification)
CREATE TABLE IF NOT EXISTS ps_endpoint_id_ips (
    id          SERIAL PRIMARY KEY,
    endpoint    VARCHAR(80),
    ipaddr      INET,
    mask        INTEGER DEFAULT 32
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ps_contacts_endpoint ON ps_contacts (endpoint);
CREATE INDEX IF NOT EXISTS idx_ps_contacts_expiration ON ps_contacts (expiration_time);

-- Grant permissions to role asterisk
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO asterisk;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO asterisk;

-- 4) Create CDR/CEL tables for cdr_odbc and cel_odbc

-- cdr table
CREATE TABLE IF NOT EXISTS cdr (
    calldate        TIMESTAMP NOT NULL,
    clid            VARCHAR(80),
    src             VARCHAR(80),
    dst             VARCHAR(80),
    dcontext        VARCHAR(80),
    channel         VARCHAR(80),
    dstchannel      VARCHAR(80),
    lastapp         VARCHAR(80),
    lastdata        VARCHAR(255),
    duration        INTEGER,
    billsec         INTEGER,
    disposition     VARCHAR(45),
    amaflags        INTEGER,
    accountcode     VARCHAR(20),
    uniqueid        VARCHAR(32),
    userfield       VARCHAR(255),
    peeraccount     VARCHAR(80),
    linkedid        VARCHAR(32),
    sequence        INTEGER
);
CREATE INDEX IF NOT EXISTS idx_cdr_calldate ON cdr (calldate);
CREATE INDEX IF NOT EXISTS idx_cdr_src ON cdr (src);
CREATE INDEX IF NOT EXISTS idx_cdr_dst ON cdr (dst);

-- cel table
CREATE TABLE IF NOT EXISTS cel (
    id              SERIAL PRIMARY KEY,
    eventtype       VARCHAR(30),
    eventtime       TIMESTAMP,
    cid_name        VARCHAR(80),
    cid_num         VARCHAR(80),
    cid_ani         VARCHAR(80),
    cid_rdnis       VARCHAR(80),
    cid_dnid        VARCHAR(80),
    exten           VARCHAR(80),
    context         VARCHAR(80),
    channame        VARCHAR(80),
    appname         VARCHAR(80),
    appdata         VARCHAR(80),
    amaflag         INTEGER,
    accountcode     VARCHAR(20),
    uniqueid        VARCHAR(32),
    linkedid        VARCHAR(32),
    peer            VARCHAR(80),
    userdeftype     VARCHAR(255),
    eventextra      VARCHAR(255),
    userfield       VARCHAR(255)
);
CREATE INDEX IF NOT EXISTS idx_cel_eventtime ON cel (eventtime);
CREATE INDEX IF NOT EXISTS idx_cel_uniqueid ON cel (uniqueid);

GRANT ALL PRIVILEGES ON TABLE cdr TO asterisk;
GRANT ALL PRIVILEGES ON TABLE cel TO asterisk;
