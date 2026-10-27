"""Meaningful state, provenance, session and HTTP boundary checks. No external calls."""
import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from core import DEFAULTS, TASKS, Nebius, Ollama, Problem, Rehearsal, Store, active, assemble_artifact, artifact_checks, generate_artifact, resolve
from server import AppServer


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "test.sqlite3")
        self.app = Rehearsal(self.store)
        self.owner = "owner-one"

    def tearDown(self):
        self.temp.cleanup()

    def candidate(self, text="For Aster Ops, do not round numbers.", **kwargs):
        return self.app.candidate(self.owner, {"text": text, "project": "aster", "task": "ops-report",
                                               "source": "sample:user-feedback", "mode": "offline", **kwargs})

    def adopt(self, candidate=None, **kwargs):
        c = candidate or self.candidate()
        c = self.app.preview(self.owner, c["id"], {"mode": "offline", **kwargs})
        return self.app.adopt(self.owner, c["id"], {"expected_version": c["preview"]["version"]})

    def test_candidate_is_never_automatically_adopted(self):
        c = self.candidate()
        self.assertEqual(c["status"], "candidate")
        self.assertEqual(self.app.state(self.owner)["policies"], [])
        with self.assertRaises(Problem) as e:
            self.app.adopt(self.owner, c["id"], {"expected_version": 0})
        self.assertEqual(e.exception.status, 409)

    def test_before_after_are_useful_work_with_fixture_evidence(self):
        c = self.candidate()
        preview = self.app.preview(self.owner, c["id"], {"mode": "offline"})["preview"]
        self.assertIn("12.7k transactions", preview["before"]["body"])
        self.assertIn("12,743 transactions", preview["after"]["body"])
        self.assertIn("Next action:", preview["after"]["body"])
        self.assertFalse(preview["after"]["provenance"]["actual_ai_call"])
        self.assertTrue(preview["other_project"]["policy_unchanged"])
        self.assertIn("12.7k people", preview["other_project"]["artifact"]["body"])

    def test_adoption_changes_aster_but_not_bloom(self):
        self.adopt()
        aster = self.app.run(self.owner, "ops-report", {"mode": "offline"})
        bloom = self.app.run(self.owner, "launch-copy", {"mode": "offline"})
        self.assertEqual(aster["policy"]["number_format"], "exact")
        self.assertEqual(bloom["policy"]["number_format"], "compact")
        self.assertEqual(aster["policy_version"], 1)

    def test_once_exception_is_not_consumed_by_preview_then_restores_project(self):
        self.adopt()
        c = self.candidate("For this task only, use compact numbers.")
        preview = self.app.preview(self.owner, c["id"], {"mode": "offline"})
        self.assertEqual(preview["rule"]["scope"], "task")
        self.assertEqual(self.app.state(self.owner)["version"], 1)
        self.app.adopt(self.owner, c["id"], {"expected_version": 1})
        once = self.app.run(self.owner, "ops-report", {"mode": "offline"})
        next_report = self.app.run(self.owner, "ops-report", {"mode": "offline"})
        self.assertEqual(once["policy"]["number_format"], "compact")
        self.assertEqual(next_report["policy"]["number_format"], "exact")
        self.assertTrue(any(r.get("consumed_by_artifact") == once["id"] for r in self.app.state(self.owner)["policies"]))

    def test_expired_policy_does_not_apply(self):
        rule = {"id": "expired", "key": "tone", "value": "friendly", "scope": "project", "project": "aster",
                "task": "ops-report", "expires_at": "2020-01-01T00:00:00+00:00"}
        policy, applied = resolve([rule], TASKS["ops-report"])
        self.assertEqual(policy["tone"], "concise")
        self.assertEqual(applied, [])
        self.assertFalse(active(rule))

    def test_conflict_requires_explicit_replacement_and_history_survives(self):
        original = self.adopt()
        c = self.candidate("Use compact numbers in this project.")
        with self.assertRaises(Problem) as e:
            self.app.preview(self.owner, c["id"], {"mode": "offline"})
        self.assertEqual(e.exception.status, 409)
        self.adopt(c, replace_conflicts=True)
        policies = self.app.state(self.owner)["policies"]
        self.assertEqual(len(policies), 2)
        self.assertTrue(next(p for p in policies if p["id"] == original["id"])["retired_at"])

    def test_stale_preview_cannot_overwrite_new_policy(self):
        c1 = self.candidate()
        c1 = self.app.preview(self.owner, c1["id"], {"mode": "offline"})
        self.adopt(self.candidate("Use a friendly tone for this project."))
        with self.assertRaises(Problem) as e:
            self.app.adopt(self.owner, c1["id"], {"expected_version": 0})
        self.assertEqual(e.exception.status, 409)

    def test_unknown_owner_cannot_access_other_candidates(self):
        c = self.candidate()
        with self.assertRaises(Problem) as e:
            self.app.preview("owner-two", c["id"], {"mode": "offline"})
        self.assertEqual(e.exception.status, 404)

    def test_restart_keeps_history(self):
        self.adopt()
        self.app.run(self.owner, "ops-report", {"mode": "offline"})
        reopened = Rehearsal(Store(self.store.path))
        self.assertEqual(reopened.state(self.owner)["version"], 1)
        self.assertEqual(len(reopened.state(self.owner)["artifacts"]), 1)

    def test_retirement_reverts_effective_policy_without_losing_source(self):
        r = self.adopt()
        self.app.retire(self.owner, r["id"], {"expected_version": 1})
        report = self.app.run(self.owner, "ops-report", {"mode": "offline"})
        self.assertEqual(report["policy"]["number_format"], "compact")
        self.assertEqual(self.app.state(self.owner)["policies"][0]["source"], "sample:user-feedback")

    def test_live_failure_never_substitutes_offline_output(self):
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "", "NEBIUS_MODEL": ""}):
            app = Rehearsal(self.store, Nebius())
            with self.assertRaises(Problem) as e:
                app.run(self.owner, "ops-report", {"mode": "live"})
            self.assertEqual(e.exception.status, 503)
            self.assertEqual(app.state(self.owner)["artifacts"], [])

    def test_wrong_vendor_model_is_not_nebius_ready(self):
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "not-a-real-key", "NEBIUS_MODEL": "another/model"}):
            self.assertFalse(Nebius().ready)

    def test_local_model_is_explicit_and_distinct_from_nebius(self):
        class LocalStub:
            def generate(self, system, data):
                return {"title": "Synthetic mock", "body": "12.7k transactions, $9.6k, 3.17%. Source: sample:aster-october-v1"}, {
                    "mode": "local", "provider": "local mock for routing test", "actual_ai_call": False, "live_provider_call": False}
        app = Rehearsal(self.store, local_provider=LocalStub())
        result = app.run(self.owner, "ops-report", {"mode": "local"})
        self.assertEqual(result["provenance"]["mode"], "local")
        self.assertFalse(result["provenance"]["live_provider_call"])

    def test_unsupported_model_rule_is_rejected_with_provenance_and_no_adoption(self):
        class UnsupportedMock:
            def generate(self, system, data):
                return {"key": "number_format", "value": "invented-format", "scope": "project"}, {
                    "mode": "local", "actual_ai_call": False, "live_provider_call": False, "model": "mock-only"}
        app = Rehearsal(self.store, local_provider=UnsupportedMock())
        with self.assertRaises(Problem) as e:
            app.candidate(self.owner, {"text": "Do not round figures.", "project": "aster", "task": "ops-report",
                                       "source": "sample", "mode": "local"})
        self.assertEqual(e.exception.status, 422)
        self.assertEqual(e.exception.details["rejected_rule"]["value"], "invented-format")
        self.assertEqual(e.exception.details["extraction"]["model"], "mock-only")
        self.assertEqual(app.state(self.owner)["candidates"], [])
        self.assertEqual(app.state(self.owner)["policies"], [])

    def test_application_attaches_known_source_list_without_rewriting_model_numbers(self):
        raw = "Transactions: 12,743. Revenue: $9,584.62. Error rate: 3.17%."
        policy = {**DEFAULTS["aster"], "number_format": "exact"}
        rendered, assembly = assemble_artifact(TASKS["ops-report"], policy, raw, True)
        self.assertEqual(rendered, raw + "\n\nProvided source IDs: sample:aster-october-v1")
        self.assertTrue(assembly["source_footer_added"])
        self.assertFalse(assembly["numeric_tokens_rewritten"])
        self.assertFalse(assembly["model_source_id_present"])
        self.assertTrue(all(c["passed"] for c in artifact_checks(TASKS["ops-report"], policy, rendered)))
        bad_numbers = "Transactions: 12.7k. Revenue: $9.6k. Error rate: 3.17%."
        bad_rendered, _ = assemble_artifact(TASKS["ops-report"], policy, bad_numbers, True)
        self.assertTrue(bad_rendered.startswith(bad_numbers))
        self.assertFalse(artifact_checks(TASKS["ops-report"], policy, bad_rendered)[0]["passed"])

    def test_source_assembly_respects_no_sources_and_is_not_a_fake_model_call(self):
        policy = {**DEFAULTS["aster"], "include_sources": "no"}
        body, assembly = assemble_artifact(TASKS["ops-report"], policy, "A public sample.", False)
        self.assertEqual(body, "A public sample.")
        self.assertFalse(assembly["source_footer_added"])
        self.assertFalse(assembly["model_output_preserved"])
        self.assertEqual(assembly["provided_source_ids"], [])

    def test_evaluation_denominators_and_provenance_are_explicit(self):
        result = self.app.evaluate(self.owner, {"mode": "offline"})
        self.assertTrue(result["synthetic"])
        self.assertEqual([r["correct_routes"] for r in result["results"]], [1, 1, 2])
        self.assertEqual([r["fixture_output_passes"] for r in result["results"]], [1, 1, 2])
        self.assertTrue(all(r["total"] == 2 for r in result["results"]))
        self.assertTrue(all(not o["artifact"]["provenance"]["actual_ai_call"] for r in result["results"] for o in r["outputs"]))

    def test_reset_only_affects_current_workspace(self):
        self.adopt()
        self.app.candidate("owner-two", {"text": "Use exact numbers.", "project": "aster", "task": "ops-report", "source": "sample"})
        self.app.reset(self.owner)
        self.assertEqual(self.app.state(self.owner)["policies"], [])
        self.assertEqual(len(self.app.state("owner-two")["candidates"]), 1)

    def test_invalid_rule_and_timezone_are_rejected(self):
        c = self.candidate()
        for rule in (None, {**c["rule"], "value": "run shell"}, {**c["rule"], "expires_at": "2030-01-01T10:00:00"},
                     {**c["rule"], "project": "bloom"}):
            with self.subTest(rule=rule), self.assertRaises(Problem):
                self.app.preview(self.owner, c["id"], {"mode": "offline", "rule": rule})


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.app = Rehearsal(Store(Path(cls.temp.name) / "http.sqlite3"))
        cls.server = AppServer(("127.0.0.1", 0), cls.app)
        cls.port = cls.server.server_port
        cls.origin = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, method="GET", data=None, cookie=None, extra=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Origin": self.origin}
        if cookie:
            headers["Cookie"] = cookie
        if data is not None:
            headers["Content-Type"] = "application/json"
        headers.update(extra or {})
        body = json.dumps(data) if isinstance(data, (dict, list)) else data
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        raw, status, returned = response.read(), response.status, dict(response.getheaders())
        conn.close()
        result = json.loads(raw) if returned.get("Content-Type", "").startswith("application/json") else raw.decode()
        return status, result, returned

    def test_cookie_is_random_httponly_samesite_and_no_credentials_in_health(self):
        code, body, headers = self.request("/health")
        self.assertEqual(code, 200)
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Lax", headers["Set-Cookie"])
        self.assertIn("akashic_session=", headers["Set-Cookie"])
        self.assertNotIn("api_key", json.dumps(body).lower())

    def test_browser_workspaces_are_isolated(self):
        cookie1 = self.request("/api/state")[2]["Set-Cookie"].split(";", 1)[0]
        cookie2 = self.request("/api/state")[2]["Set-Cookie"].split(";", 1)[0]
        data = {"text": "Use exact numbers.", "project": "aster", "task": "ops-report", "source": "sample"}
        self.assertEqual(self.request("/api/candidates", "POST", data, cookie1)[0], 201)
        self.assertEqual(len(self.request("/api/state", cookie=cookie1)[1]["candidates"]), 1)
        self.assertEqual(self.request("/api/state", cookie=cookie2)[1]["candidates"], [])

    def test_missing_or_foreign_origin_is_rejected(self):
        for origin in ("", "https://attacker.example"):
            with self.subTest(origin=origin):
                self.assertEqual(self.request("/api/evaluate", "POST", {"mode": "offline"}, extra={"Origin": origin})[0], 403)

    def test_non_json_mutation_and_array_are_rejected(self):
        self.assertEqual(self.request("/api/reset", "POST", "x", extra={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("/api/reset", "POST", [1])[0], 400)

    def test_host_validation_and_path_traversal(self):
        self.assertEqual(self.request("/health", extra={"Host": "evil.example"})[0], 421)
        self.assertEqual(self.request("/../core.py")[0], 404)
        self.assertEqual(self.request("/.env")[0], 404)

    def test_prefix_and_static_relative_assets(self):
        code, html, headers = self.request("/akashic/")
        self.assertEqual(code, 200)
        self.assertIn('src="app.js"', html)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(self.request("/akashic/api/state")[0], 200)

    def test_full_api_rehearse_adopt_run(self):
        cookie = self.request("/api/state")[2]["Set-Cookie"].split(";", 1)[0]
        data = {"text": "Use exact numbers.", "project": "aster", "task": "ops-report", "source": "sample"}
        c = self.request("/api/candidates", "POST", data, cookie)[1]
        p = self.request(f'/api/candidates/{c["id"]}/preview', "POST", {"mode": "offline"}, cookie)[1]
        self.assertTrue(p["preview"]["other_project"]["policy_unchanged"])
        self.assertEqual(self.request(f'/api/candidates/{c["id"]}/adopt', "POST", {"expected_version": 0}, cookie)[0], 200)
        code, artifact, _ = self.request("/api/tasks/ops-report/run", "POST", {"mode": "offline"}, cookie)
        self.assertEqual(code, 200)
        self.assertIn("12,743 transactions", artifact["body"])
        self.assertFalse(artifact["provenance"]["actual_ai_call"])

    def test_reset_requires_explicit_confirmation(self):
        self.assertEqual(self.request("/api/reset", "POST", {})[0], 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
