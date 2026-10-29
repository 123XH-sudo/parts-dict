from sqlalchemy import create_engine, inspect, text

from app.db import ensure_columns


def test_ensure_columns_adds_mpn_to_old_job_lines(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE job_lines (id INTEGER PRIMARY KEY, job_id INTEGER)")
        )

    ensure_columns(engine)
    ensure_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("job_lines")}
    assert "mpn" in columns
