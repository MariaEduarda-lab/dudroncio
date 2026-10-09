CREATE TABLE client(
    id                              BIGSERIAL PRIMARY KEY,
    client_key                      UUID NOT NULL,
    person_type                     VARCHAR(2) NOT NULL,
    document_number                 VARCHAR(14) NOT NULL,
    full_name                       VARCHAR(255),
    birthdate                       DATE,
    password_hash                   VARCHAR(255),
    legal_name                      VARCHAR(255),
    trade_name                      VARCHAR(255),
    cnpj_status                     VARCHAR(30),
    primary_activity                VARCHAR(255),
    monthly_income_cents            BIGINT NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    phone_number                    VARCHAR(16) NOT NULL,
    address                         JSONB NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    CONSTRAINT uq_client_key UNIQUE(client_key),
    CONSTRAINT uq_client_document UNIQUE(document_number),
    CONSTRAINT uq_client_email UNIQUE(email),
    CONSTRAINT ck_client_person_type CHECK (person_type IN ('PF', 'PJ')),
    -- CPF com 11 digitos na PF; CNPJ com 12 caracteres [A-Z0-9] e 2
    -- digitos na PJ. Os digitos verificadores sao conferidos no codigo.
    CONSTRAINT ck_client_document CHECK (
        (person_type = 'PF' AND document_number ~ '^[0-9]{11}$')
        OR (person_type = 'PJ' AND document_number ~ '^[A-Z0-9]{12}[0-9]{2}$')
    ),
    -- Cada tipo so tem os proprios campos: a PF nao tem dados de empresa
    -- e a PJ nao tem senha (quem entra e o representante).
    CONSTRAINT ck_client_pf_fields CHECK (
        person_type <> 'PF' OR (
            full_name IS NOT NULL AND birthdate IS NOT NULL AND password_hash IS NOT NULL
            AND legal_name IS NULL AND trade_name IS NULL AND cnpj_status IS NULL AND primary_activity IS NULL
        )
    ),
    CONSTRAINT ck_client_pj_fields CHECK (
        person_type <> 'PJ' OR (
            legal_name IS NOT NULL AND cnpj_status IS NOT NULL AND primary_activity IS NOT NULL
            AND full_name IS NULL AND birthdate IS NULL AND password_hash IS NULL
        )
    ),
    CONSTRAINT ck_client_monthly_income CHECK (monthly_income_cents >= 0),
    CONSTRAINT ck_client_email_lowercase CHECK (email = LOWER(email))
);

CREATE TABLE legal_representative(
    id                              BIGSERIAL PRIMARY KEY,
    representative_key              UUID NOT NULL,
    client_id                       BIGINT NOT NULL REFERENCES client(id),
    cpf                             CHAR(11) NOT NULL,
    full_name                       VARCHAR(255) NOT NULL,
    birthdate                       DATE NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    phone_number                    VARCHAR(16) NOT NULL,
    role                            VARCHAR(100) NOT NULL,
    password_hash                   VARCHAR(255) NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    CONSTRAINT uq_legal_representative_key UNIQUE(representative_key),
    CONSTRAINT uq_legal_representative_cpf UNIQUE(cpf),
    CONSTRAINT uq_legal_representative_email UNIQUE(email),
    CONSTRAINT ck_legal_representative_cpf CHECK (cpf ~ '^[0-9]{11}$'),
    CONSTRAINT ck_legal_representative_email_lowercase CHECK (email = LOWER(email))
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

-- updated_at pertence ao estado persistido e deve ser confiavel mesmo
-- quando uma alteracao nao passa pelo ORM (script operacional, migracao ou
-- outro servico). O trigger tambem cobre as atualizacoes atomicas de saldo.
CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER tg_client_set_updated_at
    BEFORE UPDATE ON client
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER tg_legal_representative_set_updated_at
    BEFORE UPDATE ON legal_representative
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER tg_account_set_updated_at
    BEFORE UPDATE ON account
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- CLI-06: um e-mail nao se repete em lugar nenhum do banco, nem entre
-- clientes, nem entre representantes. UNIQUE so vale dentro de uma
-- tabela, entao todo e-mail cadastrado tambem entra aqui, pelos triggers
-- abaixo, na mesma transacao do cadastro. A chave primaria recusa o
-- repetido; com dois cadastros simultaneos, o segundo espera o primeiro
-- terminar e recebe o erro de unicidade (pk_registered_email).
CREATE TABLE registered_email(
    email                           VARCHAR(255) NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    CONSTRAINT pk_registered_email PRIMARY KEY(email)
);

CREATE FUNCTION register_email() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.email IS DISTINCT FROM OLD.email THEN
            RAISE EXCEPTION 'O e-mail do cadastro nao muda nesta fase' USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN NEW;
    END IF;

    INSERT INTO registered_email(email) VALUES (NEW.email);
    RETURN NEW;
END;
$$;

CREATE TRIGGER tg_client_register_email
    BEFORE INSERT OR UPDATE OF email ON client
    FOR EACH ROW EXECUTE FUNCTION register_email();

CREATE TRIGGER tg_legal_representative_register_email
    BEFORE INSERT OR UPDATE OF email ON legal_representative
    FOR EACH ROW EXECUTE FUNCTION register_email();

-- So PJ tem representante legal; a PF e o proprio titular.
CREATE FUNCTION legal_representative_only_for_pj() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM client WHERE id = NEW.client_id AND person_type = 'PJ') THEN
        RAISE EXCEPTION 'Representante legal so existe para cliente PJ' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER tg_legal_representative_only_for_pj
    BEFORE INSERT OR UPDATE OF client_id ON legal_representative
    FOR EACH ROW EXECUTE FUNCTION legal_representative_only_for_pj();

-- Toda PJ tem pelo menos um representante. A conferencia fica para o
-- COMMIT, porque a empresa e o representante nascem na mesma transacao.
CREATE FUNCTION pj_has_legal_representative() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.person_type = 'PJ'
        AND NOT EXISTS (SELECT 1 FROM legal_representative WHERE client_id = NEW.id) THEN
        RAISE EXCEPTION 'Cliente PJ precisa de pelo menos um representante legal' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER tg_pj_has_legal_representative
    AFTER INSERT ON client
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION pj_has_legal_representative();

-- Regras explicitas de tarifa, inclusive para PF e recebimentos gratuitos.
-- Uma nova vigencia gera outra linha; regras antigas permanecem auditaveis.
CREATE TABLE tariff_rule(
    id                              BIGSERIAL PRIMARY KEY,
    person_type                     VARCHAR(2) NOT NULL,
    transaction_type                VARCHAR(20) NOT NULL,
    direction                       VARCHAR(3) NOT NULL,
    monthly_free_quota              INTEGER,
    fee_after_quota_cents           BIGINT NOT NULL,
    valid_from                      TIMESTAMPTZ NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    CONSTRAINT uq_tariff_rule UNIQUE(person_type, transaction_type, direction, valid_from),
    CONSTRAINT ck_tariff_rule_person_type CHECK (person_type IN ('PF', 'PJ')),
    CONSTRAINT ck_tariff_rule_transaction_type CHECK (transaction_type IN ('PIX', 'TED')),
    CONSTRAINT ck_tariff_rule_direction CHECK (direction IN ('IN', 'OUT')),
    CONSTRAINT ck_tariff_rule_quota CHECK (monthly_free_quota IS NULL OR monthly_free_quota >= 0),
    CONSTRAINT ck_tariff_rule_fee CHECK (fee_after_quota_cents >= 0),
    CONSTRAINT ck_tariff_rule_unlimited CHECK (monthly_free_quota IS NOT NULL OR fee_after_quota_cents = 0),
    -- PF nunca paga (TAR-01) e receber e sempre gratis (TAR-02): so o envio
    -- de PJ pode ter preco, mesmo que alguem cadastre uma regra nova.
    CONSTRAINT ck_tariff_rule_only_pj_sends_pay CHECK (
        (person_type = 'PJ' AND direction = 'OUT') OR fee_after_quota_cents = 0
    )
);

-- Uma regra de tarifa nunca e editada nem apagada: o que foi cobrado
-- ontem precisa continuar explicavel hoje.
CREATE FUNCTION tariff_rule_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Uma regra de tarifa nunca e editada nem apagada' USING ERRCODE = 'restrict_violation';
END;
$$;

CREATE TRIGGER tg_tariff_rule_append_only
    BEFORE UPDATE OR DELETE ON tariff_rule
    FOR EACH ROW EXECUTE FUNCTION tariff_rule_append_only();

CREATE TRIGGER tg_tariff_rule_no_truncate
    BEFORE TRUNCATE ON tariff_rule
    FOR EACH STATEMENT EXECUTE FUNCTION tariff_rule_append_only();

INSERT INTO tariff_rule
    (person_type, transaction_type, direction, monthly_free_quota, fee_after_quota_cents, valid_from)
VALUES
    ('PF', 'PIX', 'IN',  NULL, 0,   '2026-01-01 00:00:00-03'),
    ('PF', 'PIX', 'OUT', NULL, 0,   '2026-01-01 00:00:00-03'),
    ('PF', 'TED', 'IN',  NULL, 0,   '2026-01-01 00:00:00-03'),
    ('PF', 'TED', 'OUT', NULL, 0,   '2026-01-01 00:00:00-03'),
    ('PJ', 'PIX', 'IN',  NULL, 0,   '2026-01-01 00:00:00-03'),
    ('PJ', 'PIX', 'OUT', 20,   99,  '2026-01-01 00:00:00-03'),
    ('PJ', 'TED', 'IN',  NULL, 0,   '2026-01-01 00:00:00-03'),
    ('PJ', 'TED', 'OUT', 2,    499, '2026-01-01 00:00:00-03');

-- Todo movimento de dinheiro: recebimentos (TED_IN, PIX_IN), avisados pelo
-- Banco Central, e envios (PIX_OUT, TED_OUT). Nesta etapa os envios sao so
-- entre contas do nosso banco; o envio para outro banco entra depois.
CREATE TABLE transaction(
    id                              BIGSERIAL PRIMARY KEY,
    transaction_key                 UUID NOT NULL,
    type                            VARCHAR(20) NOT NULL,
    direction                       VARCHAR(3) NOT NULL,
    amount_cents                    BIGINT NOT NULL,
    fee_cents                       BIGINT NOT NULL DEFAULT(0),
    tariff_rule_id                  BIGINT NOT NULL REFERENCES tariff_rule(id),
    source_account_id               BIGINT REFERENCES account(id),
    destination_account_id          BIGINT REFERENCES account(id),
    requested_by_client_id          BIGINT REFERENCES client(id),
    requested_by_representative_id  BIGINT REFERENCES legal_representative(id),
    idempotency_key                 VARCHAR(64),
    external_reference              VARCHAR(64),
    request_fingerprint             CHAR(64),
    counterparty_name               VARCHAR(255) NOT NULL,
    counterparty_document           VARCHAR(14) NOT NULL,
    counterparty_bank_code          CHAR(3) NOT NULL,
    counterparty_branch             VARCHAR(4) NOT NULL,
    counterparty_account_number     VARCHAR(20) NOT NULL,
    -- Chave Pix pela qual o recebimento chegou, ja normalizada.
    pix_key                         VARCHAR(255),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    CONSTRAINT uq_transaction_key UNIQUE(transaction_key),
    CONSTRAINT ck_transaction_type CHECK (type IN ('PIX', 'TED')),
    CONSTRAINT ck_transaction_direction CHECK (direction IN ('IN', 'OUT')),
    CONSTRAINT ck_transaction_amount CHECK (amount_cents BETWEEN 1 AND 100000000000),
    CONSTRAINT ck_transaction_fee CHECK (fee_cents >= 0),
    CONSTRAINT ck_transaction_incoming CHECK (
        direction <> 'IN'
        OR (
            destination_account_id IS NOT NULL AND external_reference IS NOT NULL AND fee_cents = 0
            AND source_account_id IS NULL AND idempotency_key IS NULL AND request_fingerprint IS NULL
        )
    ),
    CONSTRAINT ck_transaction_outgoing CHECK (
        direction <> 'OUT'
        OR (
            source_account_id IS NOT NULL AND idempotency_key IS NOT NULL
            AND request_fingerprint IS NOT NULL AND external_reference IS NULL
            AND requested_by_client_id IS NOT NULL
        )
    ),
    CONSTRAINT ck_transaction_not_to_itself CHECK (source_account_id IS DISTINCT FROM destination_account_id),
    CONSTRAINT ck_transaction_pix_key CHECK ((type = 'PIX') = (pix_key IS NOT NULL)),
    -- Um pedido de envio por chave de idempotencia em cada conta de origem.
    CONSTRAINT uq_transaction_idempotency UNIQUE(source_account_id, idempotency_key),
    CONSTRAINT ck_transaction_document CHECK (counterparty_document ~ '^([0-9]{11}|[A-Z0-9]{12}[0-9]{2})$')
);

-- O mesmo aviso de recebimento, chegando de novo, nao credita duas vezes.
-- A identificacao e unica por banco de origem: dois bancos podem usar o
-- mesmo texto sem um apagar o recebimento do outro.
CREATE UNIQUE INDEX ux_transaction_incoming_ref
    ON transaction (type, counterparty_bank_code, external_reference)
    WHERE direction = 'IN';

-- Contagem da cota de tarifa: envios de um tipo, de uma conta, no mes.
-- Uma transacao so existe se deu certo (TRA-09): todo envio gravado conta.
CREATE INDEX ix_transaction_sends
    ON transaction (source_account_id, type, created_at)
    WHERE direction = 'OUT';

-- O solicitante precisa ser o titular da conta. Para PJ, o representante
-- informado também precisa pertencer àquele cliente; para PF ele não existe.
CREATE FUNCTION validate_transaction_requester() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    account_client_id BIGINT;
    requester_person_type VARCHAR(2);
BEGIN
    IF NEW.direction = 'IN' THEN
        IF NEW.requested_by_client_id IS NOT NULL OR NEW.requested_by_representative_id IS NOT NULL THEN
            RAISE EXCEPTION 'Recebimento externo nao possui solicitante local' USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    SELECT a.client_id, c.person_type
      INTO account_client_id, requester_person_type
      FROM account a
      JOIN client c ON c.id = a.client_id
     WHERE a.id = NEW.source_account_id;

    IF NEW.requested_by_client_id IS DISTINCT FROM account_client_id THEN
        RAISE EXCEPTION 'O solicitante deve ser o titular da conta de origem' USING ERRCODE = 'check_violation';
    END IF;

    IF requester_person_type = 'PF' AND NEW.requested_by_representative_id IS NOT NULL THEN
        RAISE EXCEPTION 'Cliente PF nao opera por representante legal' USING ERRCODE = 'check_violation';
    END IF;

    IF requester_person_type = 'PJ' AND NOT EXISTS (
        SELECT 1 FROM legal_representative
         WHERE id = NEW.requested_by_representative_id
           AND client_id = account_client_id
    ) THEN
        RAISE EXCEPTION 'Saida PJ exige representante do cliente' USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER tg_transaction_validate_requester
    BEFORE INSERT OR UPDATE OF source_account_id, requested_by_client_id, requested_by_representative_id, direction
    ON transaction
    FOR EACH ROW EXECUTE FUNCTION validate_transaction_requester();

-- Cada movimento e uma linha imutavel do extrato. O valor e sempre
-- positivo; direction informa se ele entra ou sai da conta.
CREATE TABLE account_movement(
    id                              BIGSERIAL PRIMARY KEY,
    movement_key                    UUID NOT NULL,
    account_id                      BIGINT NOT NULL REFERENCES account(id),
    transaction_id                  BIGINT NOT NULL REFERENCES transaction(id),
    direction                       VARCHAR(10) NOT NULL,
    movement_type                   VARCHAR(10) NOT NULL,
    amount_cents                    BIGINT NOT NULL,
    balance_after_cents             BIGINT NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT(NOW()),
    CONSTRAINT uq_account_movement_key UNIQUE(movement_key),
    CONSTRAINT ck_account_movement_direction CHECK (direction IN ('DEBIT', 'CREDIT')),
    CONSTRAINT ck_account_movement_type CHECK (movement_type IN ('PRINCIPAL', 'FEE')),
    CONSTRAINT ck_account_movement_amount CHECK (amount_cents > 0),
    CONSTRAINT ck_account_movement_balance_after CHECK (balance_after_cents >= 0)
);

-- Transacoes e lancamentos nunca sao editados nem apagados.
-- A mensagem e montada no USING, sem o sinal de porcentagem: o
-- tests/utils/db_utils.py roda este arquivo pelo psycopg2, que leria esse
-- sinal como parametro (em qualquer lugar do arquivo, ate em comentario).
CREATE FUNCTION append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION USING
        MESSAGE = 'A tabela ' || TG_TABLE_NAME || ' so aceita INSERT',
        ERRCODE = 'restrict_violation';
END;
$$;

CREATE TRIGGER tg_transaction_append_only
    BEFORE UPDATE OR DELETE ON transaction
    FOR EACH ROW EXECUTE FUNCTION append_only();

CREATE TRIGGER tg_account_movement_append_only
    BEFORE UPDATE OR DELETE ON account_movement
    FOR EACH ROW EXECUTE FUNCTION append_only();

CREATE FUNCTION transaction_no_delete() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Uma transacao nunca e apagada' USING ERRCODE = 'restrict_violation';
END;
$$;

CREATE TRIGGER tg_transaction_no_delete
    BEFORE DELETE OR TRUNCATE ON transaction
    FOR EACH STATEMENT EXECUTE FUNCTION transaction_no_delete();

CREATE TRIGGER tg_account_movement_no_truncate
    BEFORE TRUNCATE ON account_movement
    FOR EACH STATEMENT EXECUTE FUNCTION append_only();

-- Extrato: movimentos de uma conta, do mais recente para o mais antigo,
-- em paginas que continuam a partir do id da ultima linha vista.
CREATE INDEX ix_account_movement_statement ON account_movement (account_id, id DESC);
