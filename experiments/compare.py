"""Import saved evaluation evidence and generate a standalone HTML/CSV comparison.

Offline by default. --fetch-langfuse performs only bounded, read-only API requests.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import mean


VARIANTS = "ABCDE"
JUDGES = ("summary_quality", "reason_quality")
CHECKS = ("execution_success", "team_exact_match", "stakeholder_expected_match",
          "stakeholders_match_selected_teams", "application_valid")
PAIRS = (("A", "B"), ("A", "C"), ("A", "D"), ("A", "E"),
         ("B", "C"), ("B", "D"), ("C", "E"), ("D", "E"))
COMMON_FIELDS = ("study_id", "database", "fixture_sha256", "source_sha256", "packages",
                 "model", "temperature", "model_base_url", "model_timeout_seconds",
                 "model_max_tokens", "model_max_retries", "dataset_id", "dataset_name",
                 "dataset_version", "dataset_sha256", "base_prompt_sha256", "interval_seconds")


def number(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("A numeric value cannot be a boolean.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Numeric values must be finite.")
    return result


def normalize(row):
    """Accept Langfuse's camelCase API and snake_case CSV headers."""
    names = ("id", "name", "value", "comment", "status", "error", "traceId", "observationId",
             "parentObservationId", "type", "metadata", "totalCost", "costDetails", "usageDetails",
             "subject", "datasetRunId", "datasetItemId", "caseId", "studyId", "model", "projectId")
    aliases = {name.replace("_", "").lower(): name for name in names}
    result = {aliases.get(key.replace("_", "").lower(), key): value for key, value in row.items()}
    for key in ("metadata", "costDetails", "usageDetails", "subject"):
        if isinstance(result.get(key), str):
            result[key] = json.loads(result[key]) if result[key] else {}
    subject = result.get("subject") or {}
    if subject:
        if subject.get("kind") != "observation":
            if result.get("name") in JUDGES:
                raise ValueError("Judge scores must identify their task observation.")
        else:
            result.update(traceId=subject.get("traceId"), observationId=subject.get("id"))
    return result


def read_export(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        if Path(path).suffix.lower() == ".csv":
            rows = list(csv.DictReader(handle))
        else:
            payload = json.load(handle)
            rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("An export must contain a list of records.")
    return [normalize(row) for row in rows]


def load_study(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    planned = manifest["cases"]
    if (len(planned) != 30 or {c["case_id"] for c in planned} != {f"E{i:02}" for i in range(1, 31)}
            or len({c["dataset_item_id"] for c in planned}) != 30
            or len({c["ticket_id"] for c in planned}) != 30
            or any(c["group"] != ("regression" if c["case_id"] <= "E10" else "held_out") for c in planned)):
        raise ValueError("The manifest must identify the 30 unique cases and their original 10/new 20 groups.")
    digest = sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    runs = {}
    sources = [{"file": "manifest.json", "sha256": sha256((directory / "manifest.json").read_bytes()).hexdigest()}]
    for path in sorted(directory.glob("*.json")):
        saved = json.loads(path.read_text(encoding="utf-8"))
        if "configuration" not in saved or "cases" not in saved:
            continue
        cfg = saved["configuration"]
        variant = cfg.get("variant")
        if variant not in list(VARIANTS) or variant in runs:
            raise ValueError(f"Unknown or duplicate variant report: {path.name}.")
        if cfg.get("manifest_sha256") != digest:
            raise ValueError(f"{variant}: report does not match the frozen manifest.")
        for key in COMMON_FIELDS:
            if key in manifest and cfg.get(key) != manifest[key]:
                raise ValueError(f"{variant}: incomparable {key}.")
        for key in ("profile_sha256", "prompt_sha256", "tools", "preload_ticket", "preload_directory", "name"):
            if key not in manifest["profiles"][variant]:
                continue
            if cfg.get(key) != manifest["profiles"][variant][key]:
                raise ValueError(f"{variant}: mismatched {key}.")
        if saved["run_name"] != cfg.get("run_name"):
            raise ValueError(f"{variant}: mismatched run name.")
        runs[variant] = saved
        sources.append({"file": path.name, "sha256": sha256(path.read_bytes()).hexdigest()})
    names = [run["run_name"] for run in runs.values()]
    if len(names) != len(set(names)):
        raise ValueError("Run names must be unique across variants.")
    return manifest, runs, sources


def planned_cases(manifest, runs):
    result, traces, run_ids = [], set(), set()
    for variant in VARIANTS:
        run = runs.get(variant)
        saved = {}
        for record in run["cases"] if run else []:
            item = record["dataset_item_id"]
            if item in saved:
                raise ValueError(f"{variant}: duplicate dataset item {item}.")
            saved[item] = record
        if set(saved) - {c["dataset_item_id"] for c in manifest["cases"]}:
            raise ValueError(f"{variant}: unknown dataset item.")
        variant_run_ids = {c.get("dataset_run_id") for c in saved.values()} - {None}
        if len(variant_run_ids) > 1 or variant_run_ids & run_ids:
            raise ValueError(f"{variant}: duplicate or inconsistent dataset run identity.")
        run_ids.update(variant_run_ids)
        for identity in sorted(manifest["cases"], key=lambda c: c["case_id"]):
            row = deepcopy(saved.get(identity["dataset_item_id"], {}))
            if row and (row["case_id"] != identity["case_id"] or row["group"] != identity["group"]
                        or row.get("variant") != variant
                        or row.get("input", {}).get("ticketId") != identity["ticket_id"]):
                raise ValueError(f"{variant}/{identity['case_id']}: mismatched case identity.")
            metadata = row.get("metadata") or {}
            for key, expected in {"study_id": manifest["study_id"], "variant": variant,
                                  "dataset_id": manifest["dataset_id"], "case_id": identity["case_id"],
                                  "run_name": run["run_name"] if run else None}.items():
                if key in metadata and metadata[key] != expected:
                    raise ValueError(f"{variant}/{identity['case_id']}: mismatched metadata {key}.")
            trace = row.get("trace_id")
            if trace and trace in traces:
                raise ValueError("Cases must have unique trace identities.")
            if trace:
                traces.add(trace)
            checks = {}
            for check in row.get("scores", []):
                if check["name"] not in CHECKS:
                    continue
                if check["name"] in checks or number(check["value"]) not in (0, 1):
                    raise ValueError("Duplicate or invalid deterministic score.")
                checks[check["name"]] = number(check["value"])
            row.update(identity, variant=variant, run_name=run["run_name"] if run else None,
                       execution_status=row.get("execution_status", "missing" if run else "not_started"),
                       metadata=metadata, checks=checks)
            result.append(row)
    return result


def judge_result(row, name):
    if row["execution_status"] != "passed" or row.get("output") is None:
        return {"status": "ineligible", "value": None, "comment": "Analysis did not complete."}
    expected = row["metadata"].get("expected_answer")
    if not isinstance(expected, dict) or "relevantTeams" not in expected:
        raise ValueError("Successful cases need their saved expected answer for judge eligibility.")
    if name == "reason_quality" and not row["output"]["relevantTeams"]:
        if not expected["relevantTeams"]:
            return {"status": "not_applicable", "value": None, "comment": "Expected and returned teams are empty."}
        return {"status": "scored", "value": 0, "comment": "Rubric: expected teams but none returned.",
                "source": "existing_rubric"}
    return {"status": "pending", "value": None, "comment": "No judge score in this export."}


def attach_judges(cases, scores, observations):
    tasks = {}
    for row in cases:
        for name in JUDGES:
            row[name] = judge_result(row, name)
        trace, metadata = row.get("trace_id"), row["metadata"]
        candidates = [o for o in observations.get(trace, []) if o.get("name") == "paperdesk-eval-case"]
        task_id = row.get("task_observation_id") or metadata.get("task_observation_id")
        if len(candidates) > 1:
            raise ValueError(f"{row['variant']}/{row['case_id']}: ambiguous task observations.")
        if candidates:
            task = candidates[0]
            if task_id and task_id != task["id"]:
                raise ValueError("Export task ID differs from the saved task ID.")
            task_meta = task.get("metadata") or {}
            for key, expected in (("case_id", row["case_id"]), ("variant", row["variant"]),
                                  ("study_id", metadata.get("study_id")), ("run_name", row["run_name"]),
                                  ("dataset_id", metadata.get("dataset_id"))):
                if task_meta.get(key) != expected:
                    raise ValueError(f"Export task metadata does not match {key}.")
            task_id = task["id"]
        row["task_observation_id"] = task_id
        if trace and task_id:
            tasks[(trace, task_id)] = row
    seen, ids = set(), set()
    for original in scores:
        score = normalize(original)
        name = score.get("name")
        if name not in JUDGES:
            continue
        key = (score.get("traceId"), score.get("observationId"))
        row = tasks.get(key)
        if row is None:
            raise ValueError("Judge score does not match a saved task observation.")
        unique = (*key, name)
        if unique in seen or (score.get("id") and score["id"] in ids):
            raise ValueError("Duplicate judge score; select one explicit evaluation result.")
        seen.add(unique)
        ids.add(score.get("id"))
        for key, expected in (("datasetRunId", row.get("dataset_run_id")),
                              ("datasetItemId", row["dataset_item_id"]), ("caseId", row["case_id"]),
                              ("studyId", row["metadata"].get("study_id"))):
            if score.get(key) and score[key] != expected:
                raise ValueError(f"Judge score has mismatched {key}.")
        existing = row[name]
        if existing["status"] in ("ineligible", "not_applicable"):
            raise ValueError("Judge score was exported for an ineligible case.")
        status = str(score.get("status") or "scored").lower()
        if status not in ("scored", "pending", "error"):
            raise ValueError("Judge status must be scored, pending, or error.")
        value = number(score.get("value"))
        if status == "scored" and (value is None or not 0 <= value <= 1
                                   or (name == "summary_quality" and value not in (0, 0.5, 1))):
            raise ValueError("Invalid judge score value.")
        if status != "scored" and value is not None:
            raise ValueError("Pending/error judge records cannot contain a numeric score.")
        if existing.get("source") == "existing_rubric":
            if status == "scored" and value != 0:
                raise ValueError("Reason score contradicts the existing empty-selection rubric.")
            # A deterministic rubric zero remains visible while retaining import evidence.
            existing["imported_score"] = score
            if status == "scored" and score.get("comment"):
                existing["rubric_comment"] = existing["comment"]
                existing["comment"] = score["comment"]
        else:
            row[name] = {"status": status, "value": value, "comment": score.get("comment") or score.get("error") or "",
                         "source": "langfuse", "score_id": score.get("id"), "metadata": score.get("metadata")}


def judge_provenance(scores):
    result = {}
    fields = ("evaluator_id", "evaluator_version_id", "job_configuration_id")
    for name in JUDGES:
        records = [normalize(s) for s in scores if s.get("name") == name]
        identity, complete = {}, 0
        for field in fields:
            values = {(s.get("metadata") or {}).get(field) for s in records} - {None, ""}
            if len(values) > 1:
                raise ValueError(f"{name}: incomparable judge {field} values.")
            identity[field] = next(iter(values)) if values else None
        complete = sum(all((s.get("metadata") or {}).get(f) for f in fields) for s in records)
        result[name] = {"identity": identity, "records": len(records), "identified": complete,
                        "status": "available" if records and complete == len(records)
                                  else "partial" if any(identity.values()) else "unavailable"}
    return result


def resource_totals(generations, key, expected_calls=None):
    values = []
    for generation in generations:
        if key == "cost":
            value = generation.get("totalCost")
            if value is None:
                value = (generation.get("costDetails") or {}).get("total")
        else:
            value = (generation.get("usageDetails") or {}).get(key)
        parsed = number(value)
        if parsed is not None and parsed < 0:
            raise ValueError("Resource usage and cost cannot be negative.")
        values.append(parsed)
    known = [v for v in values if v is not None]
    complete = bool(values) and len(known) == len(values) and expected_calls in (None, len(values))
    return {"total": sum(known) if complete else None, "known_total": sum(known) if known else None,
            "status": "available" if complete else "partial" if known else "unavailable",
            "recorded": len(known), "calls": len(values), "expected_calls": expected_calls}


def attach_resources(cases, observations):
    for row in cases:
        nodes = observations.get(row.get("trace_id"), [])
        by_id = {o["id"]: o for o in nodes}
        agents = [o for o in nodes if o.get("name") == "ticket-analysis"
                  and (o.get("metadata") or {}).get("analysisId") == row["metadata"].get("analysis_id")]
        if len(agents) > 1:
            raise ValueError("Ambiguous analysis cost scope.")
        agent_id = agents[0]["id"] if agents else None
        generations, judge_generations = [], []
        for node in nodes:
            if node.get("type") != "GENERATION":
                continue
            ancestors, parent, visited = [], node.get("parentObservationId"), {node["id"]}
            while parent in by_id:
                if parent in visited:
                    raise ValueError("Observation ancestry contains a cycle.")
                visited.add(parent)
                ancestors.append(parent)
                parent = by_id[parent].get("parentObservationId")
            if agent_id and agent_id in ancestors:
                generations.append(node)
            elif any(by_id[p].get("type") == "EVALUATOR" for p in ancestors):
                judge_generations.append(node)
        metrics = row["metadata"].get("analysis_metrics") or {}
        requested = metrics.get("toolCalls")
        expected_calls = metrics.get("modelCalls")
        row["resources"] = {
            "agent_cost": resource_totals(generations, "cost", expected_calls),
            "judge_cost": resource_totals(judge_generations, "cost"),
            "input_tokens": resource_totals(generations, "input", expected_calls),
            "output_tokens": resource_totals(generations, "output", expected_calls),
            "cached_input_tokens": resource_totals(generations, "input_cached_tokens", expected_calls),
            "latency_seconds": number(row["metadata"].get("analysis_seconds")),
            "model_calls": metrics.get("modelCalls"),
            "model_database_requests": sum(t in ("get_ticket", "list_teams", "get_team_members") for t in requested)
                                       if requested is not None else None,
            "structured_calls": requested.count("TeamAssessment") if requested is not None else None,
            "combined_database_reads": len(metrics["databaseToolCalls"]) if "databaseToolCalls" in metrics else None,
            "read_attribution": metrics.get("databaseReads"),
            "raw_metrics": metrics,
        }
        project = next((o.get("projectId") for o in nodes if o.get("projectId")), None)
        base = row["metadata"].get("langfuse_base_url")
        row["trace_url"] = None
        if project and row.get("trace_id") and base:
            row["trace_url"] = f"{base}/project/{project}/traces/{row['trace_id']}"


def summarize(cases):
    result = {}
    for group in ("all", "regression", "held_out"):
        result[group] = {}
        for variant in VARIANTS:
            cohort = [r for r in cases if r["variant"] == variant and (group == "all" or r["group"] == group)]
            stats = {"planned": len(cohort), "execution": dict(Counter(r["execution_status"] for r in cohort)),
                     "team_correct": sum(r["checks"].get("team_exact_match") == 1 for r in cohort),
                     "team_scored": sum("team_exact_match" in r["checks"] for r in cohort)}
            stats["team_rate"] = stats["team_correct"] / len(cohort) if stats["team_scored"] == len(cohort) else None
            for name in JUDGES:
                counts = Counter(r[name]["status"] for r in cohort)
                values = [r[name]["value"] for r in cohort if r[name]["status"] == "scored"]
                stats[name] = {"mean": mean(values) if values else None,
                               "eligible": sum(counts[s] for s in ("scored", "pending", "error")),
                               **{s: counts[s] for s in ("scored", "pending", "error", "not_applicable", "ineligible")}}
            for name in ("agent_cost", "judge_cost", "input_tokens", "output_tokens", "cached_input_tokens",
                         "latency_seconds", "model_calls", "model_database_requests", "structured_calls", "combined_database_reads"):
                raw = [r["resources"][name] for r in cohort]
                values = [v["total"] if isinstance(v, dict) else v for v in raw]
                known = [v for v in values if v is not None]
                stats[name] = {"total": sum(known) if known else None, "mean": mean(known) if known else None,
                               "available": len(known), "planned": len(cohort)}
            result[group][variant] = stats
    return result


def difference(before, after):
    return {"before": before, "after": after,
            "delta": after - before if before is not None and after is not None else None,
            "percent": 100 * (after - before) / before if before not in (None, 0) and after is not None else None}


def compare_cases(cases, summaries):
    comparisons = {}
    for group, grouped in summaries.items():
        comparisons[group] = {}
        index = {(r["variant"], r["case_id"]): r for r in cases if group == "all" or r["group"] == group}
        case_ids = sorted({identity[1] for identity in index})
        for before, after in PAIRS:
            a, b = grouped[before], grouped[after]
            deltas = {"team_rate": difference(a["team_rate"], b["team_rate"])}
            for metric in JUDGES:
                deltas[metric] = difference(a[metric]["mean"], b[metric]["mean"])
            for metric in ("agent_cost", "judge_cost", "input_tokens", "output_tokens", "cached_input_tokens",
                           "model_calls", "model_database_requests", "structured_calls", "combined_database_reads", "latency_seconds"):
                measure = "mean" if metric == "latency_seconds" else "total"
                deltas[metric] = difference(a[metric][measure] if a[metric]["available"] == a["planned"] else None,
                                            b[metric][measure] if b[metric]["available"] == b["planned"] else None)
            paired = []
            complete = True
            for case_id in case_ids:
                left, right = index[(before, case_id)], index[(after, case_id)]
                metrics = {"team_exact_match": difference(left["checks"].get("team_exact_match"), right["checks"].get("team_exact_match"))}
                for metric in JUDGES:
                    metrics[metric] = difference(left[metric]["value"], right[metric]["value"])
                for metric in ("agent_cost", "judge_cost", "input_tokens", "output_tokens", "cached_input_tokens",
                               "latency_seconds", "model_calls", "model_database_requests", "structured_calls", "combined_database_reads"):
                    lvalue, rvalue = left["resources"][metric], right["resources"][metric]
                    metrics[metric] = difference(lvalue["total"] if isinstance(lvalue, dict) else lvalue,
                                                 rvalue["total"] if isinstance(rvalue, dict) else rvalue)
                quality = [metrics[k]["delta"] for k in ("team_exact_match", *JUDGES)]
                paired.append({"case_id": case_id, "metrics": metrics,
                               "gain": any(v is not None and v > 0 for v in quality),
                               "loss": any(v is not None and v < 0 for v in quality),
                               "output_changed": left.get("output") != right.get("output")})
                for row in (left, right):
                    complete &= (row["execution_status"] in ("passed", "failed") and len(row["checks"]) == len(CHECKS)
                                 and all(row[k]["status"] not in ("pending", "error") for k in JUDGES))
            quality = [deltas[k]["delta"] for k in ("team_rate", *JUDGES)]
            if not complete or None in quality:
                interpretation = "incomplete evidence"
            elif any(v > 0 for v in quality) and all(v >= 0 for v in quality):
                interpretation = "improved on this cohort"
            elif all(v == 0 for v in quality):
                interpretation = "quality tied"
            else:
                interpretation = "trade-off or regression"
            comparisons[group][f"{before}/{after}"] = {"before": before, "after": after, "metrics": deltas,
                "cases": paired, "complete": complete, "interpretation": interpretation,
                "gains": sum(c["gain"] for c in paired), "losses": sum(c["loss"] for c in paired)}
    return comparisons


def generate_report(study, scores, observations, out, *, export_provenance=None):
    manifest, runs, sources = load_study(study)
    cases = planned_cases(manifest, runs)
    grouped, ids = {}, set()
    traces = {r.get("trace_id") for r in cases} - {None}
    for original in observations:
        observation = normalize(original)
        key = (observation.get("traceId"), observation.get("id"))
        if not all(key) or key in ids or key[0] not in traces:
            raise ValueError("Duplicate, incomplete, or unmatched observation identity.")
        ids.add(key)
        grouped.setdefault(key[0], []).append(observation)
    for row in cases:
        row["metadata"].setdefault("langfuse_base_url", manifest.get("langfuse_base_url"))
    attach_judges(cases, scores, grouped)
    attach_resources(cases, grouped)
    summaries = summarize(cases)
    report = {"study_id": manifest["study_id"], "cases": cases, "summaries": summaries,
              "comparisons": compare_cases(cases, summaries),
              "judge_provenance": judge_provenance(scores),
              "sources": sources, "export": export_provenance, "pairs": PAIRS,
              "cost_source": "Langfuse-reported USD; may be inferred from configured model prices.",
              "cost_accounting": {
                  "currency": "USD", "model": manifest.get("model"), "provider_endpoint": manifest.get("model_base_url"),
                  "rate_source": "Langfuse configured model prices or ingested costDetails; not distinguished by export.",
                  "effective_pricing_date": None,
                  "cached_input_treatment": "Use exported costDetails; historical cache pricing treatment is unavailable.",
                  "value_type": "Langfuse-reported; provider-reported versus inferred is unavailable in this export.",
              }}
    out = Path(out)
    if out.resolve() == Path(study).resolve():
        raise ValueError("Write reports to a separate output directory.")
    out.mkdir(parents=True, exist_ok=True)
    data = json.dumps(report, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    template = Path(__file__).with_name("comparison.html").read_text(encoding="utf-8")
    (out / "comparison.html").write_text(template.replace("__REPORT_DATA__", data), encoding="utf-8")
    columns = ("variant", "case_id", "group", "execution_status", "team_exact_match", "summary_quality",
               "summary_status", "summary_comment", "reason_quality", "reason_status", "reason_comment",
               "agent_cost_usd", "agent_cost_status", "judge_cost_usd", "latency_seconds", "input_tokens",
               "output_tokens", "model_calls", "trace_id", "task_observation_id", "dataset_item_id",
               "dataset_run_id", "trace_url", "team_delta_vs_A", "summary_delta_vs_A", "reason_delta_vs_A", "cost_delta_vs_A_usd",
               "output", "expected_answer", "summary_evidence", "reason_evidence", "deterministic_checks", "resource_evidence", "errors")
    with (out / "cases.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in cases:
            resource = row["resources"]
            flat = {key: row.get(key) for key in columns}
            flat.update(team_exact_match=row["checks"].get("team_exact_match"),
                        summary_quality=row["summary_quality"]["value"], summary_status=row["summary_quality"]["status"],
                        summary_comment=row["summary_quality"]["comment"], reason_quality=row["reason_quality"]["value"],
                        reason_status=row["reason_quality"]["status"], reason_comment=row["reason_quality"]["comment"],
                        agent_cost_usd=resource["agent_cost"]["total"], agent_cost_status=resource["agent_cost"]["status"],
                        judge_cost_usd=resource["judge_cost"]["total"], latency_seconds=resource["latency_seconds"],
                        input_tokens=resource["input_tokens"]["total"], output_tokens=resource["output_tokens"]["total"],
                        model_calls=resource["model_calls"], output=json.dumps(row.get("output"), ensure_ascii=False),
                        expected_answer=json.dumps(row["metadata"].get("expected_answer"), ensure_ascii=False),
                        summary_evidence=json.dumps(row["summary_quality"], ensure_ascii=False),
                        reason_evidence=json.dumps(row["reason_quality"], ensure_ascii=False),
                        deterministic_checks=json.dumps(row.get("scores", [])), resource_evidence=json.dumps(resource),
                        errors=json.dumps({k: v for k, v in row["metadata"].items() if "error" in k or k == "error_stage"}))
            if row["variant"] != "A":
                change = next(c for c in report["comparisons"]["all"][f"A/{row['variant']}"]["cases"] if c["case_id"] == row["case_id"])
                for column, metric in (("team_delta_vs_A", "team_exact_match"), ("summary_delta_vs_A", "summary_quality"),
                                       ("reason_delta_vs_A", "reason_quality"), ("cost_delta_vs_A_usd", "agent_cost")):
                    flat[column] = change["metrics"][metric]["delta"]
            writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v
                             for k, v in flat.items()})
    return report


def fetch_langfuse(manifest, runs):
    """One explicit snapshot of this study's traces; no SDK tracing or writes."""
    import base64
    import os
    import urllib.error
    import urllib.parse
    import urllib.request
    from dotenv import dotenv_values

    environment = dotenv_values(Path(__file__).resolve().parent.parent / "agents" / ".env")
    public = os.environ.get("LANGFUSE_PUBLIC_KEY") or environment.get("LANGFUSE_PUBLIC_KEY")
    secret = os.environ.get("LANGFUSE_SECRET_KEY") or environment.get("LANGFUSE_SECRET_KEY")
    base = (os.environ.get("LANGFUSE_BASE_URL") or environment.get("LANGFUSE_BASE_URL") or "").rstrip("/")
    if not public or not secret or base != manifest.get("langfuse_base_url", "").rstrip("/"):
        raise ValueError("Configure Langfuse keys and the study's exact LANGFUSE_BASE_URL in agents/.env.")
    authorization = "Basic " + base64.b64encode(f"{public}:{secret}".encode()).decode()

    def pages(endpoint, params):
        records, cursors = [], set()
        while True:
            request = urllib.request.Request(base + endpoint + "?" + urllib.parse.urlencode(params),
                                             headers={"Authorization": authorization})
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    payload = json.load(response)
            except urllib.error.HTTPError as error:
                raise ValueError(f"Langfuse export request failed with HTTP {error.code}.") from None
            except (urllib.error.URLError, TimeoutError):
                raise ValueError("Could not reach the configured Langfuse endpoint.") from None
            records.extend(payload["data"])
            cursor = (payload.get("meta") or {}).get("cursor")
            if not cursor:
                return records
            if cursor in cursors:
                raise ValueError("Langfuse returned a repeated pagination cursor.")
            cursors.add(cursor)
            params = {**params, "cursor": cursor}

    traces = sorted({row.get("trace_id") for run in runs.values() for row in run["cases"]} - {None})
    scores, observations = [], []
    for offset in range(0, len(traces), 20):
        batch = traces[offset:offset + 20]
        filters = json.dumps([{"type": "stringOptions", "column": "traceId", "operator": "any of", "value": batch}])
        observations.extend(pages("/api/public/v2/observations", {
            "filter": filters, "fields": "core,basic,metadata,usage,model", "limit": 1000}))
        scores.extend(row for row in pages("/api/public/v3/scores", {
            "traceId": ",".join(batch), "fields": "details,subject", "limit": 100}) if row.get("name") in JUDGES)
    return {"study_id": manifest["study_id"], "dataset_id": manifest["dataset_id"],
            "manifest_sha256": sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            "base_url": base, "fetched_at": datetime.now(timezone.utc).isoformat(),
            "scores": scores, "observations": observations}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True, help="Directory containing manifest.json and saved A-E reports")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--fetch-langfuse", action="store_true", help="Explicit read-only snapshot of this study's existing scores/costs")
    source.add_argument("--export", type=Path, help="Previously saved combined JSON snapshot")
    source.add_argument("--scores", type=Path, help="Langfuse score CSV/JSON export")
    parser.add_argument("--observations", type=Path, help="Langfuse observation CSV/JSON export, with metadata and costs")
    parser.add_argument("--out", type=Path, help="Output directory (default: <study>/comparison)")
    args = parser.parse_args(argv)
    if args.observations and (args.fetch_langfuse or args.export):
        parser.error("--observations accompanies --scores, not a combined snapshot.")
    out = args.out or args.study / "comparison"
    try:
        manifest, runs, _ = load_study(args.study)
        if out.resolve() == args.study.resolve():
            raise ValueError("Write reports to a separate output directory.")
        provenance = []
        if args.fetch_langfuse:
            snapshot = fetch_langfuse(manifest, runs)
            out.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            export_path = out / f"langfuse-export-{stamp}.json"
            export_path.write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            args.export = export_path
        if args.export:
            snapshot = json.loads(args.export.read_text(encoding="utf-8-sig"))
            for key, expected in (("study_id", manifest["study_id"]), ("dataset_id", manifest["dataset_id"]),
                                  ("manifest_sha256", sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()),
                                  ("base_url", manifest.get("langfuse_base_url"))):
                if key in snapshot and snapshot[key] != expected:
                    raise ValueError(f"Combined export has mismatched {key}.")
            scores, observations = snapshot["scores"], snapshot["observations"]
            provenance.append({"file": args.export.name, "sha256": sha256(args.export.read_bytes()).hexdigest(),
                               "fetched_at": snapshot.get("fetched_at"), "base_url": snapshot.get("base_url")})
        else:
            scores = read_export(args.scores) if args.scores else []
            observations = read_export(args.observations) if args.observations else []
            for path in (args.scores, args.observations):
                if path:
                    if path.resolve() in ((out / "cases.csv").resolve(), (out / "comparison.html").resolve()):
                        raise ValueError("An output file would overwrite an input export.")
                    provenance.append({"file": path.name, "sha256": sha256(path.read_bytes()).hexdigest()})
        generate_report(args.study, scores, observations, out, export_provenance=provenance)
        print(f"HTML report: {out / 'comparison.html'}\nCase data: {out / 'cases.csv'}")
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"Comparison failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
