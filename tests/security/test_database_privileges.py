from uuid import uuid4

import psycopg2
from psycopg2 import sql


def fetch_one(connection, statement: str, parameters=None):
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return cursor.fetchone()


def assert_permission_denied(connection, statement: str, parameters=None) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
    except psycopg2.errors.InsufficientPrivilege:
        return
    raise AssertionError(f"runtime executou operacao proibida: {statement}")


def test_runtime_role_is_unprivileged_and_not_owner_member(owner_connection):
    role = fetch_one(
        owner_connection,
        """
        SELECT rolsuper, rolcreatedb, rolcreaterole, rolinherit
          FROM pg_roles
         WHERE rolname = 'application_user'
        """,
    )
    assert role == (False, False, False, False)
    membership = fetch_one(
        owner_connection,
        """
        SELECT COUNT(*)
          FROM pg_auth_members membership
          JOIN pg_roles granted ON granted.oid = membership.roleid
          JOIN pg_roles member ON member.oid = membership.member
         WHERE granted.rolname = 'database_owner'
           AND member.rolname = 'application_user'
        """,
    )
    assert membership == (0,)


def test_objects_and_balance_functions_belong_to_owner(owner_connection):
    non_owner_objects = fetch_one(
        owner_connection,
        """
        SELECT COUNT(*)
          FROM pg_class object
          JOIN pg_namespace namespace ON namespace.oid = object.relnamespace
          JOIN pg_roles owner_role ON owner_role.oid = object.relowner
         WHERE namespace.nspname = 'public'
           AND object.relkind IN ('r', 'S', 'i')
           AND owner_role.rolname <> 'database_owner'
        """,
    )
    assert non_owner_objects == (0,)
    functions = fetch_one(
        owner_connection,
        """
        SELECT COUNT(*), BOOL_AND(prosecdef),
               BOOL_AND(proconfig = ARRAY['search_path=pg_catalog'])
          FROM pg_proc function
          JOIN pg_namespace namespace ON namespace.oid = function.pronamespace
          JOIN pg_roles owner_role ON owner_role.oid = function.proowner
         WHERE namespace.nspname = 'public'
           AND function.proname IN ('credit_account', 'debit_account')
           AND owner_role.rolname = 'database_owner'
        """,
    )
    assert functions == (2, True, True)


def test_public_and_runtime_database_schema_privileges_are_minimal(owner_connection):
    privileges = fetch_one(
        owner_connection,
        """
        SELECT
            has_database_privilege('public', current_database(), 'CREATE'),
            has_database_privilege('public', current_database(), 'TEMPORARY'),
            has_schema_privilege('public', 'public', 'CREATE'),
            has_database_privilege('application_user', current_database(), 'CONNECT'),
            has_schema_privilege('application_user', 'public', 'USAGE'),
            has_schema_privilege('application_user', 'public', 'CREATE')
        """,
    )
    assert privileges == (False, False, False, True, True, False)


def test_runtime_cannot_execute_ddl_or_destroy_data(runtime_connection):
    forbidden = [
        "CREATE TABLE runtime_probe(id integer)",
        "CREATE TEMP TABLE runtime_temp_probe(id integer)",
        "ALTER TABLE account ADD COLUMN runtime_probe integer",
        "DROP TABLE account",
        "TRUNCATE account",
        "TRUNCATE transaction",
        "TRUNCATE account_movement",
        "TRUNCATE tariff_rule",
        "DELETE FROM account",
        "DELETE FROM transaction",
        "DELETE FROM account_movement",
        "DELETE FROM tariff_rule",
    ]
    for statement in forbidden:
        assert_permission_denied(runtime_connection, statement)


def test_runtime_cannot_write_balance_identity_or_history(runtime_connection):
    forbidden = [
        "INSERT INTO account (balance_cents) VALUES (999999)",
        "INSERT INTO client (created_at) VALUES (NOW())",
        "UPDATE account SET balance_cents = 999999",
        "UPDATE account SET account_number = '99999999'",
        "UPDATE transaction SET amount_cents = 1",
        "UPDATE account_movement SET amount_cents = 1",
        "UPDATE tariff_rule SET fee_after_quota_cents = 0",
        "SELECT public.append_only()",
    ]
    for statement in forbidden:
        assert_permission_denied(runtime_connection, statement)


def test_runtime_allowed_flow_uses_defaults_and_guarded_balance_functions(runtime_connection):
    unique = uuid4().hex
    client_id, = fetch_one(
        runtime_connection,
        """
        INSERT INTO client (
            client_key, person_type, document_number, full_name, birthdate,
            password_hash, monthly_income_cents, email, phone_number, address
        ) VALUES (
            %s, 'PF', %s, 'Privilege Test', DATE '1990-01-01',
            'not-a-real-hash', 0, %s, '+5511999999999', '{}'::jsonb
        ) RETURNING id
        """,
        (str(uuid4()), f"{int(unique[:11], 16) % 100000000000:011d}", f"security.{unique}@example.test"),
    )
    account_id, initial_balance = fetch_one(
        runtime_connection,
        """
        INSERT INTO account (account_key, client_id, account_number, check_digit, status)
        VALUES (%s, %s, %s, '0', 'ACTIVE')
        RETURNING id, balance_cents
        """,
        (str(uuid4()), client_id, f"{int(unique[:8], 16) % 100000000:08d}"),
    )
    assert initial_balance == 0

    assert fetch_one(runtime_connection, "SELECT public.credit_account(%s, 100)", (account_id,)) == (100,)
    assert fetch_one(runtime_connection, "SELECT public.credit_account(%s, 0)", (account_id,)) == (None,)
    assert fetch_one(runtime_connection, "SELECT public.debit_account(%s, 101)", (account_id,)) == (None,)
    assert fetch_one(runtime_connection, "SELECT public.debit_account(%s, 40)", (account_id,)) == (60,)

    assert fetch_one(
        runtime_connection,
        "UPDATE account SET status = 'BLOCKED', status_reason = 'security test' WHERE id = %s RETURNING status",
        (account_id,),
    ) == ("BLOCKED",)
    assert fetch_one(runtime_connection, "SELECT public.credit_account(%s, 1)", (account_id,)) == (None,)
    assert fetch_one(runtime_connection, "SELECT balance_cents FROM account WHERE id = %s", (account_id,)) == (60,)


def test_owner_can_apply_a_versioned_schema_change(owner_connection):
    marker = f"security_owner_probe_{uuid4().hex}"
    with owner_connection.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE TABLE {} (id BIGINT PRIMARY KEY)").format(sql.Identifier(marker)))
        cursor.execute(sql.SQL("ALTER TABLE {} ADD COLUMN note TEXT").format(sql.Identifier(marker)))
        cursor.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(marker)))
