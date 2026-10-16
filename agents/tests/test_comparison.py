"""Offline comparison behavior through saved runs, exports, and report artifacts."""

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from experiments.compare import generate_report


def save_study(directory):
    directory.mkdir(parents=True, exist_ok=True)
    cases = [{"case_id": f"E{i:02}", "dataset_item_id": f"item-{i}",
              "ticket_id": f"{i:024}", "group": "regression" if i <= 10 else "held_out"}
             for i in range(1, 31)]
    manifest = {"study_id": "offline", "dataset_id": "dataset", "dataset_sha256": "dataset-hash",
                "fixture_sha256": "fixture-hash", "source_sha256": "source-hash", "model": "offline",
                "base_prompt_sha256": "prompt-hash", "langfuse_base_url": "http://localhost:3001",
                "profiles": {v: {"profile_sha256": f"profile-{v}", "prompt_sha256": f"prompt-{v}"}
                             for v in "ABCDE"}, "cases": cases, "cases_per_variant": 30,
                "planned_variants": list("ABCDE")}
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    digest = sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    scores, observations = [], []
    for variant in "ABCDE":
        configuration = {k: manifest[k] for k in ("study_id", "dataset_id", "dataset_sha256",
                         "fixture_sha256", "source_sha256", "model", "base_prompt_sha256")}
        configuration.update(variant=variant, run_name=f"run-{variant}", manifest_sha256=digest,
                             **manifest["profiles"][variant])
        records = []
        for case in cases:
            key = f"{variant}-{case['case_id']}"
            output = {"ticketId": case["ticket_id"], "summary": "A supported summary.",
                      "relevantTeams": [{"teamId": "team", "reason": "Owns this issue."}],
                      "stakeholderUserIds": ["user"]}
            metadata = {"study_id": "offline", "variant": variant, "run_name": f"run-{variant}",
                        "case_id": case["case_id"], "dataset_id": "dataset", "group": case["group"],
                        "expected_answer": deepcopy(output), "analysis_seconds": 2,
                        "task_observation_id": f"task-{key}", "analysis_id": f"analysis-{key}",
                        "analysis_metrics": {"modelCalls": 1, "toolCalls": ["TeamAssessment"],
                                             "databaseToolCalls": ["get_ticket"]}}
            records.append({**case, "variant": variant, "input": {"ticketId": case["ticket_id"]},
                            "output": output, "execution_status": "passed", "metadata": metadata,
                            "trace_id": f"trace-{key}", "dataset_run_id": f"run-id-{variant}",
                            "scores": [{"name": n, "value": 1} for n in (
                                "execution_success", "team_exact_match", "stakeholder_expected_match",
                                "stakeholders_match_selected_teams", "application_valid")]})
            observations.extend([
                {"id": f"task-{key}", "traceId": f"trace-{key}", "name": "paperdesk-eval-case",
                 "type": "SPAN", "metadata": deepcopy(metadata)},
                {"id": f"agent-{key}", "traceId": f"trace-{key}", "name": "ticket-analysis",
                 "type": "AGENT", "parentObservationId": f"task-{key}",
                 "metadata": {"analysisId": f"analysis-{key}"}},
                {"id": f"generation-{key}", "traceId": f"trace-{key}", "name": "model",
                 "type": "GENERATION", "parentObservationId": f"agent-{key}", "totalCost": 0.01,
                 "costDetails": {"input": 0.008, "output": 0.002, "total": 0.01},
                 "usageDetails": {"input": 100, "output": 20, "input_cached_tokens": 0}},
            ])
            for name in ("summary_quality", "reason_quality"):
                scores.append({"id": f"{key}-{name}", "traceId": f"trace-{key}",
                               "observationId": f"task-{key}", "name": name, "value": 1,
                               "comment": "Supported by current facts."})
        (directory / f"{variant}-results.json").write_text(json.dumps({"run_name": f"run-{variant}",
            "configuration": configuration, "cases": records}), encoding="utf-8")
    return scores, observations


class ComparisonTests(unittest.TestCase):
    def test_saved_runs_produce_grouped_html_and_csv_with_langfuse_costs(self):
        with TemporaryDirectory() as folder:
            study, out = Path(folder) / "study", Path(folder) / "report"
            scores, observations = save_study(study)
            report = generate_report(study, scores, observations, out)
            baseline = report["summaries"]["all"]["A"]
            self.assertEqual(baseline["team_correct"], 30)
            self.assertEqual(baseline["summary_quality"]["mean"], 1)
            self.assertAlmostEqual(baseline["agent_cost"]["total"], 0.30)
            self.assertEqual(report["summaries"]["regression"]["A"]["planned"], 10)
            self.assertEqual(report["summaries"]["held_out"]["A"]["planned"], 20)
            self.assertTrue((out / "comparison.html").exists())
            with (out / "cases.csv").open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 150)

    def test_case_pairing_and_group_deltas_use_identities_and_equal_case_weights(self):
        with TemporaryDirectory() as folder:
            study = Path(folder) / "study"
            scores, observations = save_study(study)
            for score in scores:
                if score["name"] == "reason_quality" and score["traceId"] == "trace-B-E01":
                    score["value"] = 0.5
                if score["name"] == "summary_quality" and score["traceId"] == "trace-B-E11":
                    score["value"] = 0.5
            path = study / "B-results.json"
            run = json.loads(path.read_text())
            run["cases"][0]["scores"][1]["value"] = 0
            run["cases"][0]["output"]["relevantTeams"] *= 3
            run["cases"].reverse()
            path.write_text(json.dumps(run))
            report = generate_report(study, list(reversed(scores)), observations, Path(folder) / "out")
            self.assertAlmostEqual(report["summaries"]["all"]["B"]["reason_quality"]["mean"], 29.5 / 30)
            self.assertAlmostEqual(report["summaries"]["regression"]["B"]["reason_quality"]["mean"], 0.95)
            self.assertAlmostEqual(report["summaries"]["held_out"]["B"]["summary_quality"]["mean"], 0.975)
            self.assertEqual(len(report["comparisons"]["all"]), 8)
            changes = report["comparisons"]["all"]["A/B"]
            self.assertAlmostEqual(changes["metrics"]["team_rate"]["delta"], -1 / 30)
            self.assertEqual(changes["interpretation"], "trade-off or regression")
            self.assertEqual(changes["cases"][0]["case_id"], "E01")
            self.assertEqual(changes["cases"][0]["metrics"]["team_exact_match"]["delta"], -1)

    def test_missing_failed_pending_error_and_empty_selection_remain_distinct(self):
        with TemporaryDirectory() as folder:
            study = Path(folder) / "study"
            scores, observations = save_study(study)
            path = study / "A-results.json"
            run = json.loads(path.read_text())
            run["cases"][0]["output"]["relevantTeams"] = []
            run["cases"][0]["metadata"]["expected_answer"]["relevantTeams"] = []
            run["cases"][1]["output"]["relevantTeams"] = []
            run["cases"][2].update(execution_status="failed", output=None)
            run["cases"][2]["scores"] = [{"name": n, "value": 0} for n in (
                "execution_success", "team_exact_match", "stakeholder_expected_match",
                "stakeholders_match_selected_teams", "application_valid")]
            run["cases"] = [r for r in run["cases"] if r["case_id"] != "E04"]
            path.write_text(json.dumps(run))
            (study / "E-results.json").unlink()
            scores = [s for s in scores if not s["traceId"].startswith("trace-E-")
                      and s["traceId"] not in ("trace-A-E03", "trace-A-E04")
                      and not (s["name"] == "reason_quality" and s["traceId"] in ("trace-A-E01", "trace-A-E02"))
                      and not (s["name"] == "summary_quality" and s["traceId"] == "trace-A-E06")]
            observations = [o for o in observations if not o["traceId"].startswith("trace-E-") and o["traceId"] != "trace-A-E04"]
            for s in scores:
                if s["traceId"] == "trace-A-E05" and s["name"] == "summary_quality":
                    s.update(status="error", value=None, comment="Judge unavailable.")
            report = generate_report(study, scores, observations, Path(folder) / "out")
            rows = {r["case_id"]: r for r in report["cases"] if r["variant"] == "A"}
            self.assertEqual(rows["E01"]["summary_quality"]["value"], 1)
            self.assertEqual(rows["E01"]["reason_quality"]["status"], "not_applicable")
            self.assertEqual(rows["E02"]["reason_quality"]["value"], 0)
            self.assertEqual(rows["E03"]["summary_quality"]["status"], "ineligible")
            self.assertEqual(rows["E04"]["execution_status"], "missing")
            self.assertEqual(rows["E05"]["summary_quality"]["status"], "error")
            self.assertIsNone(rows["E05"]["summary_quality"]["value"])
            self.assertEqual(rows["E06"]["summary_quality"]["status"], "pending")
            self.assertEqual(report["summaries"]["all"]["E"]["execution"], {"not_started": 30})
            self.assertEqual(report["summaries"]["all"]["A"]["summary_quality"]["scored"], 26)
            self.assertIsNone(report["summaries"]["all"]["A"]["team_rate"])
            self.assertEqual(report["comparisons"]["all"]["A/B"]["interpretation"], "incomplete evidence")

    def test_costs_separate_evaluators_and_mark_an_incomplete_export_partial(self):
        with TemporaryDirectory() as folder:
            study = Path(folder) / "study"
            scores, observations = save_study(study)
            path = study / "A-results.json"
            run = json.loads(path.read_text())
            run["cases"][0]["metadata"]["analysis_metrics"]["modelCalls"] = 2
            path.write_text(json.dumps(run))
            observations += [
                {"id": "judge-root", "traceId": "trace-A-E01", "type": "EVALUATOR"},
                {"id": "judge-call", "traceId": "trace-A-E01", "type": "GENERATION",
                 "parentObservationId": "judge-root", "totalCost": 0.5},
            ]
            report = generate_report(study, scores, observations, Path(folder) / "out")
            row = report["cases"][0]
            self.assertEqual(row["resources"]["judge_cost"]["total"], 0.5)
            self.assertEqual(row["resources"]["agent_cost"]["status"], "partial")
            self.assertIsNone(row["resources"]["agent_cost"]["total"])
            self.assertEqual(row["resources"]["agent_cost"]["known_total"], 0.01)
            self.assertIsNone(report["comparisons"]["all"]["A/B"]["metrics"]["agent_cost"]["delta"])

    def test_duplicate_unmatched_mismatched_and_invalid_judge_scores_are_rejected(self):
        with TemporaryDirectory() as folder:
            study = Path(folder) / "study"
            scores, observations = save_study(study)
            for bad in (dict(scores[0]), {**scores[0], "observationId": "wrong-task"},
                        {**scores[0], "datasetRunId": "wrong-run"}, {**scores[0], "value": float("nan")},
                        {**scores[0], "value": 0.3}):
                with self.subTest(bad=bad):
                    selected = scores + [bad] if bad == scores[0] else [bad] + scores[1:]
                    with self.assertRaises(ValueError):
                        generate_report(study, selected, observations, Path(folder) / "out")

    def test_provenance_drift_duplicate_runs_and_item_mismatch_are_rejected(self):
        with TemporaryDirectory() as folder:
            study = Path(folder) / "study"
            scores, observations = save_study(study)
            path = study / "B-results.json"
            original = path.read_text()
            for field in ("source_sha256", "dataset_sha256", "profile_sha256", "manifest_sha256"):
                changed = json.loads(original)
                changed["configuration"][field] = "wrong"
                path.write_text(json.dumps(changed))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    generate_report(study, scores, observations, Path(folder) / "out")
            changed = json.loads(original)
            changed["cases"][0]["case_id"] = "E30"
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                generate_report(study, scores, observations, Path(folder) / "out")
            path.write_text(original)
            (study / "duplicate.json").write_text(original)
            with self.assertRaises(ValueError):
                generate_report(study, scores, observations, Path(folder) / "out")

    def test_offline_command_is_repeatable_preserves_sources_and_escapes_output(self):
        from experiments.compare import main
        with TemporaryDirectory() as folder:
            study, out = Path(folder) / "study", Path(folder) / "out"
            scores, observations = save_study(study)
            path = study / "A-results.json"
            saved = json.loads(path.read_text())
            saved["cases"][0]["output"]["summary"] = '</script><img src=x onerror="alert(1)">'
            path.write_text(json.dumps(saved))
            export = Path(folder) / "export.json"
            export.write_text(json.dumps({"scores": scores, "observations": observations}))
            original = {f.name: f.read_bytes() for f in study.glob("*.json")}
            args = ["--study", str(study), "--export", str(export), "--out", str(out)]
            with patch("urllib.request.urlopen", side_effect=AssertionError("Offline command cannot access the network")):
                self.assertEqual(main(args), 0)
                first = (out / "comparison.html").read_bytes()
                self.assertEqual(main(args), 0)
                self.assertEqual(first, (out / "comparison.html").read_bytes())
            self.assertNotIn('</script><img src=x', first.decode())
            self.assertEqual(original, {f.name: f.read_bytes() for f in study.glob("*.json")})

    def test_explicit_fetch_reads_paginated_observations_and_scores_without_hosted_writes(self):
        from experiments.compare import main
        with TemporaryDirectory() as folder:
            study, out = Path(folder) / "study", Path(folder) / "out"
            scores, observations = save_study(study)
            requests = []

            def respond(request, timeout):
                self.assertEqual(request.get_method(), "GET")
                parsed = urlsplit(request.full_url)
                params = parse_qs(parsed.query)
                requests.append((parsed.path, params))
                if parsed.path == "/api/public/v3/scores":
                    self.assertLessEqual(int(params["limit"][0]), 100)
                    selected = params["traceId"][0].split(",")
                    rows = [{**s, "subject": {"kind": "observation", "id": s["observationId"], "traceId": s["traceId"]}}
                            for s in scores if s["traceId"] in selected]
                elif parsed.path == "/api/public/v2/observations":
                    selected = json.loads(params["filter"][0])[0]["value"]
                    rows = [o for o in observations if o["traceId"] in selected]
                else:
                    self.fail("Unexpected network operation")
                start = int(params.get("cursor", ["0"])[0])
                cursor = str(start + 15) if start + 15 < len(rows) else None
                return BytesIO(json.dumps({"data": rows[start:start + 15], "meta": {"cursor": cursor}}).encode())

            with patch.dict("os.environ", {"LANGFUSE_BASE_URL": "http://localhost:3001", "LANGFUSE_PUBLIC_KEY": "test", "LANGFUSE_SECRET_KEY": "test"}), \
                    patch("urllib.request.urlopen", side_effect=respond):
                self.assertEqual(main(["--study", str(study), "--fetch-langfuse", "--out", str(out)]), 0)
            snapshots = list(out.glob("langfuse-export-*.json"))
            self.assertEqual(len(snapshots), 1)
            snapshot = json.loads(snapshots[0].read_text())
            self.assertEqual(len(snapshot["scores"]), 300)
            self.assertEqual(len(snapshot["observations"]), 450)
            self.assertTrue(any("cursor" in params for _, params in requests))

    def test_zero_baselines_have_absolute_changes_and_unavailable_percentages(self):
        with TemporaryDirectory() as folder:
            study = Path(folder) / "study"
            scores, observations = save_study(study)
            path = study / "A-results.json"
            run = json.loads(path.read_text())
            for row in run["cases"]:
                row["scores"][1]["value"] = 0
            path.write_text(json.dumps(run))
            report = generate_report(study, scores, observations, Path(folder) / "out")
            comparison = report["comparisons"]["all"]["A/B"]
            self.assertEqual(comparison["metrics"]["team_rate"]["delta"], 1)
            self.assertIsNone(comparison["metrics"]["team_rate"]["percent"])
            self.assertEqual(comparison["interpretation"], "improved on this cohort")

    def test_mixed_judge_versions_are_rejected_and_known_versions_are_retained(self):
        with TemporaryDirectory() as folder:
            study = Path(folder) / "study"
            scores, observations = save_study(study)
            for score in scores:
                score["metadata"] = {"evaluator_id": score["name"], "evaluator_version_id": "v1",
                                     "job_configuration_id": "frozen-job"}
            scores[0]["metadata"]["evaluator_version_id"] = "v2"
            with self.assertRaises(ValueError):
                generate_report(study, scores, observations, Path(folder) / "out")
            scores[0]["metadata"]["evaluator_version_id"] = "v1"
            report = generate_report(study, scores, observations, Path(folder) / "out")
            self.assertEqual(report["judge_provenance"]["summary_quality"]["status"], "available")
            self.assertEqual(report["judge_provenance"]["summary_quality"]["identity"]["evaluator_version_id"], "v1")

    def test_rubric_zero_keeps_imported_explanation_and_cost_limitations_are_explicit(self):
        with TemporaryDirectory() as folder:
            study = Path(folder) / "study"
            scores, observations = save_study(study)
            path = study / "A-results.json"
            run = json.loads(path.read_text())
            run["cases"][0]["output"]["relevantTeams"] = []
            path.write_text(json.dumps(run))
            scores[1].update(value=0, comment="The agent omitted the required IT Support team.")
            report = generate_report(study, scores, observations, Path(folder) / "out")
            self.assertEqual(report["cases"][0]["reason_quality"]["comment"], scores[1]["comment"])
            self.assertEqual(report["judge_provenance"]["summary_quality"]["status"], "unavailable")
            self.assertIsNone(report["cost_accounting"]["effective_pricing_date"])
            self.assertIn("unavailable", report["cost_accounting"]["cached_input_treatment"])


if __name__ == "__main__":
    unittest.main()
