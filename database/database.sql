CREATE TABLE sample_entity_status(
    id		                        SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(enumerator)
);

INSERT INTO sample_entity_status (enumerator) VALUES
('created'),
('pending'),
('success'),
('failed');

CREATE TABLE sample_entity(
    id                              SERIAL PRIMARY KEY,
    sample_entity_key               CHAR(36) NOT NULL,
    status_id                       INTEGER NOT NULL REFERENCES sample_entity_status(id),
    sample_entity_data              JSONB NOT NULL,
    name                            VARCHAR(255) NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    document_number                 CHAR(14) NOT NULL,
    birthdate                       DATE NOT NULL,
    counter                         INTEGER NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(sample_entity_key),
    UNIQUE(document_number),
    UNIQUE(email)
);

CREATE TABLE sample_entity_status_event(
    id                              SERIAL PRIMARY KEY,
    sample_entity_id                INTEGER NOT NULL REFERENCES sample_entity(id),
    status_id                       INTEGER NOT NULL REFERENCES sample_entity_status(id),
    event_datetime                  TIMESTAMP NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW())
);

CREATE TABLE client(
    id                              BIGSERIAL PRIMARY KEY,
    client_key                      CHAR(36) NOT NULL,
    cnpj                            VARCHAR(14) NOT NULL,
    legal_name                      VARCHAR(255) NOT NULL,
    trade_name                      VARCHAR(255),
    client_type                     VARCHAR(10) NOT NULL,
    cnpj_status                     VARCHAR(30) NOT NULL,
    primary_activity                VARCHAR(255) NOT NULL,
    monthly_revenue_cents           BIGINT NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    phone_number                    VARCHAR(16) NOT NULL,
    address                         JSONB NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    CONSTRAINT uq_client_key UNIQUE(client_key),
    CONSTRAINT uq_client_cnpj UNIQUE(cnpj),
    CONSTRAINT uq_client_email UNIQUE(email),
    CONSTRAINT ck_client_type CHECK (client_type IN ('MEI', 'PJ')),
    CONSTRAINT ck_client_monthly_revenue CHECK (monthly_revenue_cents >= 0)
);

CREATE TABLE legal_representative(
    id                              BIGSERIAL PRIMARY KEY,
    representative_key              CHAR(36) NOT NULL,
    client_id                       BIGINT NOT NULL REFERENCES client(id),
    cpf                             CHAR(11) NOT NULL,
    full_name                       VARCHAR(255) NOT NULL,
    birthdate                       DATE NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    phone_number                    VARCHAR(16) NOT NULL,
    role                            VARCHAR(100) NOT NULL,
    password_hash                   VARCHAR(255) NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    CONSTRAINT uq_legal_representative_key UNIQUE(representative_key),
    CONSTRAINT uq_legal_representative_cpf UNIQUE(cpf),
    CONSTRAINT uq_legal_representative_email UNIQUE(email)
);
