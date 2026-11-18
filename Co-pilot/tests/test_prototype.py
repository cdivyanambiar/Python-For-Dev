import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app.database import execute_read_only, initialize_database
from app.workflow import CopilotWorkflow


class FakeModel:
    def __init__(self, replies):
        self.replies = iter(replies)

    def generate(self, prompt, *, json_output=False):
        return next(self.replies)


class FakeIndex:
    def __init__(self, documents):
        self.documents = documents

    def search(self, question):
        return self.documents


class PrototypeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "switches.db"
        initialize_database(self.db)
        self.addCleanup(self.temp.cleanup)

    def test_select_and_reject_writes_and_private_tables(self):
        result = execute_read_only(self.db, "SELECT name FROM switches WHERE status = 'offline'")
        self.assertEqual(result["rows"], [["sw-lab-02"]])
        for query in ("DELETE FROM switches", "SELECT * FROM sqlite_master",
                      "SELECT name FROM switches; DELETE FROM switches",
                      "ATTACH DATABASE ':memory:' AS other"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                execute_read_only(self.db, query)
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM switches").fetchone()[0], 4)

    def test_sql_graph_returns_query_and_results(self):
        workflow = CopilotWorkflow(FakeModel([
            '{"route":"sql"}', '{"sql":"SELECT name FROM switches WHERE status = \'offline\'"}',
            "sw-lab-02 is offline in the sample snapshot.",
        ]), FakeIndex([]), self.db)
        result = workflow.run("Which switches are offline?")
        self.assertEqual(result["route"], "sql")
        self.assertEqual(result["sql_result"]["rows"], [["sw-lab-02"]])
        self.assertIn("sw-lab-02", result["answer"])

    def test_both_routes_include_evidence(self):
        docs = [{"source": "switch_runbook.md#Offline switch", "text": "Check power.", "score": 0.8}]
        workflow = CopilotWorkflow(FakeModel([
            '{"route":"both"}', '{"sql":"SELECT name FROM switches WHERE status = \'offline\'"}',
            "Check power [switch_runbook.md#Offline switch].",
        ]), FakeIndex(docs), self.db)
        result = workflow.run("Which switch is offline and how can I troubleshoot it?")
        self.assertEqual(result["documents"], docs)
        self.assertEqual(result["sql_result"]["rows"], [["sw-lab-02"]])

    def test_no_relevant_docs_does_not_generate_answer(self):
        workflow = CopilotWorkflow(FakeModel(['{"route":"docs"}']), FakeIndex([]), self.db)
        result = workflow.run("Unknown topic")
        self.assertIn("couldn't find", result["answer"])

    def test_api_submit_poll_and_failure(self):
        from fastapi.testclient import TestClient
        from app.main import app

        model = FakeModel(['{"route":"greeting"}', '{"route":"invalid"}'])
        with patch("app.main.DB_PATH", self.db), \
             patch("app.main.OllamaModel", return_value=model), \
             patch("app.main.DocumentIndex", return_value=FakeIndex([])), \
             TestClient(app) as client:
            response = client.post("/questions", json={"question": "hello"})
            self.assertEqual(response.status_code, 202)
            job_id = response.json()["job_id"]
            result = client.get(f"/questions/{job_id}").json()
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["result"]["route"], "greeting")
            self.assertEqual(client.post("/questions", json={"question": "  "}).status_code, 422)
            self.assertEqual(client.get("/questions/missing").status_code, 404)
            with self.assertLogs("app.main", level="ERROR"):
                failed = client.post("/questions", json={"question": "another question"})
            self.assertEqual(client.get(f"/questions/{failed.json()['job_id']}").json()["status"], "failed")


if __name__ == "__main__":
    unittest.main()
