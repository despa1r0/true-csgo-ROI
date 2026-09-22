from backend.app import database


def test_connection_settings_falls_back_to_database_url(monkeypatch):
    for name in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/catalogue")

    assert database.connection_settings() == {
        "conninfo": "postgresql://example.invalid/catalogue"
    }


def test_connection_settings_keep_password_out_of_url(monkeypatch):
    monkeypatch.setenv("PGHOST", "db")
    monkeypatch.setenv("PGPORT", "5433")
    monkeypatch.setenv("PGDATABASE", "true_roi")
    monkeypatch.setenv("PGUSER", "true_roi")
    monkeypatch.setenv("PGPASSWORD", "spaces and @:/#$ stay literal")

    assert database.connection_settings() == {
        "host": "db",
        "port": 5433,
        "dbname": "true_roi",
        "user": "true_roi",
        "password": "spaces and @:/#$ stay literal",
    }


def test_connection_settings_require_complete_pg_environment(monkeypatch):
    monkeypatch.setenv("PGHOST", "db")
    monkeypatch.delenv("PGDATABASE", raising=False)
    monkeypatch.delenv("PGUSER", raising=False)
    monkeypatch.delenv("PGPASSWORD", raising=False)

    try:
        database.connection_settings()
    except RuntimeError as error:
        assert "PGDATABASE, PGUSER, PGPASSWORD" in str(error)
    else:
        raise AssertionError("Incomplete PostgreSQL settings must fail fast")


class RecordingConnection:
    def __init__(self):
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((statement, params))
        return self


def test_schema_adds_and_safely_backfills_component_timestamps():
    connection = RecordingConnection()

    database.ensure_schema(connection)

    sql = "\n".join(statement for statement, _params in connection.statements)
    for component in ("listings", "sales", "buy_orders"):
        assert f"{component}_fetched_at TIMESTAMPTZ" in sql
        assert (
            f"WHERE {component}_fetched_at IS NULL AND {component}_error IS NULL"
            in sql
        )
