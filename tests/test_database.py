from backend.app import database


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
