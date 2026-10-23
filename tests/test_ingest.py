import os
import tempfile

from cardwise.db import get_engine, get_session
from cardwise.ingest import ingest_pdf


def test_ingest_real_pdf(pdf_path):
    """Ingest a real SBI PDF twice; second must be a no-op."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["CARDWISE_DATA"] = tmp
        db = os.path.join(tmp, "test.db")
        eng = get_engine(db)
        s = get_session(eng)

        r1 = ingest_pdf(pdf_path, s)
        assert r1["status"] == "ok"
        assert r1["inserted"] == r1["transactions"]

        r2 = ingest_pdf(pdf_path, s)
        assert r2["status"] == "skipped"
