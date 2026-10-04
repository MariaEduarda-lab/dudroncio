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

CREATE TABLE account(
    id                              BIGSERIAL PRIMARY KEY,
    account_key                     UUID NOT NULL,
    client_id                       BIGINT NOT NULL REFERENCES client(id),
    branch                          CHAR(4) NOT NULL DEFAULT('0001'),
    account_number                  CHAR(8) NOT NULL,
    check_digit                     CHAR(1) NOT NULL,
    balance_cents                   BIGINT NOT NULL DEFAULT(0),
    status                          VARCHAR(20) NOT NULL,
    status_reason                   VARCHAR(255),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    CONSTRAINT uq_account_key UNIQUE(account_key),
    CONSTRAINT uq_account_client UNIQUE(client_id),
    CONSTRAINT uq_account_number UNIQUE(branch, account_number),
    CONSTRAINT ck_account_number CHECK (account_number ~ '^[0-9]{8}$'),
    CONSTRAINT ck_account_check_digit CHECK (check_digit ~ '^[0-9]$'),
    CONSTRAINT ck_account_balance CHECK (balance_cents >= 0),
    CONSTRAINT ck_account_status CHECK (status IN ('CREATED', 'ACTIVE', 'BLOCKED', 'CLOSED'))
);

-- A conta nunca e apagada, e agencia, numero e digito nunca mudam. So
-- podem ser alterados o saldo e o status (com motivo e data da mudanca).
CREATE FUNCTION account_protected_columns() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Uma conta nunca e apagada' USING ERRCODE = 'restrict_violation';
    END IF;

    IF (NEW.id, NEW.account_key, NEW.client_id, NEW.branch, NEW.account_number, NEW.check_digit, NEW.created_at)
        IS DISTINCT FROM
       (OLD.id, OLD.account_key, OLD.client_id, OLD.branch, OLD.account_number, OLD.check_digit, OLD.created_at) THEN
        RAISE EXCEPTION 'Na conta, so o saldo e o status podem mudar' USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER tg_account_protected_columns
    BEFORE UPDATE OR DELETE ON account
    FOR EACH ROW EXECUTE FUNCTION account_protected_columns();

-- Tabela de precos da tarifa (TAR-14). Um preco novo e uma linha nova com
-- outro valid_from; a vigente e a de maior valid_from ate o instante do
-- envio. So envios tem preco: recebimentos e PF sao gratis no codigo.
CREATE TABLE fee_rule(
    id                              BIGSERIAL PRIMARY KEY,
    person_type                     VARCHAR(2) NOT NULL,
    transaction_type                VARCHAR(20) NOT NULL,
    free_monthly_quota              INTEGER NOT NULL,
    fee_cents                       BIGINT NOT NULL,
    valid_from                      TIMESTAMPTZ NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    CONSTRAINT uq_fee_rule UNIQUE(person_type, transaction_type, valid_from),
    CONSTRAINT ck_fee_rule_person_type CHECK (person_type IN ('PF', 'PJ')),
    CONSTRAINT ck_fee_rule_only_sends CHECK (transaction_type IN ('PIX_OUT', 'TED_OUT')),
    CONSTRAINT ck_fee_rule_quota CHECK (free_monthly_quota >= 0),
    CONSTRAINT ck_fee_rule_fee CHECK (fee_cents >= 0)
);

-- Uma regra de tarifa nunca e editada nem apagada: o que foi cobrado
-- ontem precisa continuar explicavel hoje.
CREATE FUNCTION fee_rule_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Uma regra de tarifa nunca e editada nem apagada' USING ERRCODE = 'restrict_violation';
END;
$$;

CREATE TRIGGER tg_fee_rule_append_only
    BEFORE UPDATE OR DELETE ON fee_rule
    FOR EACH ROW EXECUTE FUNCTION fee_rule_append_only();

CREATE TRIGGER tg_fee_rule_no_truncate
    BEFORE TRUNCATE ON fee_rule
    FOR EACH STATEMENT EXECUTE FUNCTION fee_rule_append_only();

-- Precos iniciais da PJ (05-tarifa.md), valendo desde o comeco de 2026 em
-- Brasilia. PF nao tem linha: nunca paga (TAR-01).
INSERT INTO fee_rule (person_type, transaction_type, free_monthly_quota, fee_cents, valid_from) VALUES
    ('PJ', 'PIX_OUT', 20, 99, '2026-01-01 00:00:00-03'),
    ('PJ', 'TED_OUT', 2, 499, '2026-01-01 00:00:00-03');
