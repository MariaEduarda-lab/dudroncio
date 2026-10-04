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
