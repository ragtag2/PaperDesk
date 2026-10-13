"""Offline checks at the fixture loader and manual seeder boundaries."""

from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

from experiments import seed
from experiments.seed import load_fixture


class MemoryCollection:
    """MongoDB boundary double for the seeder's fixed-ID replacement writes."""

    def __init__(self, documents=()):
        self.documents = {document["_id"]: deepcopy(document) for document in documents}

    def find_one(self, query, _projection=None):
        identity = query["_id"]
        if isinstance(identity, dict):
            return next((deepcopy(document) for key, document in self.documents.items()
                         if key not in identity["$nin"]), None)
        return deepcopy(self.documents.get(identity))

    def create_index(self, *_args, **_kwargs):
        pass

    def find(self, _query, fields):
        return [{key: deepcopy(document[key]) for key in fields if key in document}
                for document in self.documents.values()]

    def bulk_write(self, operations, **_kwargs):
        # Interpret the driver's write objects only inside the database double.
        for operation in operations:
            self.documents[operation._filter["_id"]] = deepcopy(operation._doc)


class MemoryDatabase(dict):
    @property
    def users(self):
        return self["users"]


@contextmanager
def changed_fixture(filename, row_index, field, value):
    """Corrupt a disposable CSV copy, never the checked-in fixture."""
    with TemporaryDirectory() as directory:
        destination = Path(directory)
        for name in ("teams.csv", "users.csv", "tickets.csv"):
            (destination / name).write_bytes((seed.FIXTURE_DIR / name).read_bytes())
        with (destination / filename).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns, rows = reader.fieldnames, list(reader)
        rows[row_index][field] = value
        with (destination / filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        with patch("experiments.seed.FIXTURE_DIR", destination):
            yield


class FixtureTests(unittest.TestCase):
    def test_expanded_suite_loads_thirty_cases_and_twelve_teams(self):
        fixture = load_fixture()
        self.assertEqual(len(fixture["tickets"]), 30)
        self.assertEqual(len(fixture["teams"]), 12)
        self.assertEqual(len(fixture["users"]), 32)

    def test_existing_runner_loads_both_case_groups(self):
        from collections import Counter
        from experiments.run import load_cases

        _fixture, cases, _digest = load_cases()
        self.assertEqual(len(cases), 30)
        self.assertEqual(Counter(case["group"] for case in cases.values()),
                         {"regression": 10, "held_out": 20})

    def test_local_validation_exports_only_additions_without_credentials_or_database(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "new-cases.csv"
            output = StringIO()
            with patch("sys.argv", ["seed", "--validate-only", "--export-new-cases", str(destination)]), \
                    patch("experiments.seed.load_dotenv", side_effect=AssertionError("Env file read")), \
                    patch("experiments.seed.MongoClient", side_effect=AssertionError("Database connection")), \
                    redirect_stdout(output):
                seed.main()
            summary = json.loads(output.getvalue())
            self.assertEqual(summary["groups"], {"regression": 10, "held_out": 20})
            self.assertEqual(summary["cases"], 30)
            self.assertEqual(summary["teams"], 12)
            self.assertEqual(summary["users"], 32)
            with destination.open(encoding="utf-8", newline="") as handle:
                exported = list(csv.DictReader(handle))
            with (seed.FIXTURE_DIR / "tickets.csv").open(encoding="utf-8-sig", newline="") as handle:
                additions = list(csv.DictReader(handle))[10:]
            self.assertEqual(exported, additions)

    def test_original_fixture_records_are_unchanged(self):
        originals = (
            ("teams.csv", 6, "9fa00b684cffd64722cfa7c6f4aaa256d587bb7f798106cc08dc5ae076a51fe0"),
            ("users.csv", 15, "c8c85b8864ada5551814753ba69e6b926e02762aa4e2b9d5273857c42847410a"),
            ("tickets.csv", 10, "26101a76f75034297a89112d252dd7f78456c63fb271890c31199f86fdbee153"),
        )
        # Fingerprints captured from the original records before appending anything.
        for filename, count, expected in originals:
            with self.subTest(file=filename):
                with (seed.FIXTURE_DIR / filename).open(encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))[:count]
                actual = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
                self.assertEqual(actual, expected)

    def test_invalid_additions_are_rejected_by_the_loader(self):
        invalid = (
            ("tickets.csv", 10, "case_id", "E01"),
            ("tickets.csv", 10, "expected_answer_json", "{invalid"),
            ("tickets.csv", 10, "required_summary_facts_json", "[]"),
            ("tickets.csv", 10, "required_reason_facts_json", "{}"),
            ("tickets.csv", 10, "creatorId", "200000000000000000000025"),
            ("tickets.csv", 10, "title", "x" * 121),
            ("teams.csv", 6, "responsibilities", "x" * 5001),
            ("users.csv", 15, "_id", "200000000000000000000001"),
            ("users.csv", 15, "isActive", "yes"),
            ("users.csv", 15, "teamId", "100000000000000000000099"),
            ("users.csv", 24, "isActive", "true"),
        )
        for filename, index, field, value in invalid:
            with self.subTest(file=filename, field=field), changed_fixture(filename, index, field, value):
                with self.assertRaises(ValueError):
                    load_fixture()

    def test_zero_active_team_and_current_references_remain_distinct_from_prior_coordination(self):
        from experiments.run import load_cases

        _fixture, cases, _digest = load_cases()
        by_case = {case["case_id"]: case for case in cases.values()}
        legal = by_case["E14"]["expected_answer"]
        self.assertEqual([team["teamId"] for team in legal["relevantTeams"]], ["100000000000000000000010"])
        self.assertEqual(legal["stakeholderUserIds"], [])
        self.assertEqual(by_case["E20"]["expected_answer"]["stakeholderUserIds"],
                         ["200000000000000000000007", "200000000000000000000008"])
        self.assertEqual(by_case["E29"]["expected_answer"]["relevantTeams"], [])
        for case_id, current_team in (("E27", "100000000000000000000012"), ("E28", "100000000000000000000005")):
            case = by_case[case_id]
            self.assertEqual([team["teamId"] for team in case["expected_answer"]["relevantTeams"]], [current_team])
            self.assertNotIn(current_team, {team["teamId"] for team in case["ticket"]["coordination"]["relevantTeams"]})

    def test_export_does_not_overwrite_an_existing_file(self):
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "existing.csv"
            destination.write_text("preserve this file", encoding="utf-8")
            with patch("sys.argv", ["seed", "--validate-only", "--export-new-cases", str(destination)]):
                with self.assertRaises(FileExistsError):
                    seed.main()
            self.assertEqual(destination.read_text(encoding="utf-8"), "preserve this file")

    def run_seed(self, database):
        mongo = MagicMock()
        mongo.__getitem__.side_effect = lambda name: database if name == "paperdesk_eval" else self.fail(name)
        with patch("sys.argv", ["seed"]), \
                patch.dict("os.environ", {"MONGODB_URI": "mongodb://unused.invalid", "MONGODB_DB_NAME": "paperdesk"}, clear=True), \
                patch("experiments.seed.load_dotenv"), \
                patch("experiments.seed.MongoClient") as constructor, \
                patch("experiments.seed.bcrypt.hashpw", side_effect=lambda *_args: secrets.token_hex(16).encode()), \
                patch("experiments.seed.bcrypt.gensalt"), redirect_stdout(StringIO()):
            constructor.return_value.__enter__.return_value = mongo
            seed.main()

    def test_repeated_seed_preserves_existing_users_and_restores_only_application_records(self):
        fixture = load_fixture()
        original_users = deepcopy(fixture["users"][:15])
        for user in original_users:
            user.update(passwordHash="existing-discarded-password-hash", sessionVersion=3)
        database = MemoryDatabase({
            "teams": MemoryCollection(fixture["teams"][:6]),
            "users": MemoryCollection(original_users),
            "tickets": MemoryCollection(fixture["tickets"][:10]),
        })
        self.run_seed(database)
        for user in original_users:
            self.assertEqual(database.users.find_one({"_id": user["_id"]}), user)
        first_seed = {name: deepcopy(collection.documents) for name, collection in database.items()}
        self.run_seed(database)
        self.assertEqual({name: collection.documents for name, collection in database.items()}, first_seed)
        self.assertEqual(len(database["teams"].documents), 12)
        self.assertEqual(len(database["users"].documents), 32)
        self.assertEqual(len(database["tickets"].documents), 30)
        allowed = {"_id", "title", "description", "category", "priority", "status", "creatorId",
                   "assigneeId", "coordination", "createdAt", "updatedAt"}
        self.assertTrue(all(set(ticket) == allowed for ticket in database["tickets"].documents.values()))

    def test_seed_rejects_unexpected_existing_records_before_writes(self):
        database = MemoryDatabase({name: MemoryCollection() for name in ("teams", "users", "tickets")})
        from bson import ObjectId

        unexpected = {"_id": ObjectId("100000000000000000000099"), "name": "Not a fixture team"}
        database["teams"].documents[unexpected["_id"]] = unexpected
        before = {name: deepcopy(collection.documents) for name, collection in database.items()}
        with self.assertRaisesRegex(ValueError, "records outside this fixture"):
            self.run_seed(database)
        self.assertEqual({name: collection.documents for name, collection in database.items()}, before)

    def test_preserved_login_state_does_not_change_frozen_agent_facts(self):
        from experiments.run import check_database, FixtureMismatchError

        fixture = load_fixture()
        database = MemoryDatabase({name: MemoryCollection(documents) for name, documents in fixture.items()})
        user_id = fixture["users"][0]["_id"]
        database.users.documents[user_id].update(passwordHash="existing-discarded-password-hash", sessionVersion=3)
        self.run_seed(database)
        check_database(database, fixture)
        database.users.documents[user_id]["isActive"] = False
        with self.assertRaises(FixtureMismatchError):
            check_database(database, fixture)


if __name__ == "__main__":
    unittest.main()
