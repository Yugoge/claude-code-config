"""Unit tests for scripts/aggregate-dev-report.py"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load module (filename has hyphens — cannot use normal import)
# ---------------------------------------------------------------------------

_SCRIPT = Path(__file__).parent.parent / "scripts" / "aggregate-dev-report.py"

_spec = importlib.util.spec_from_file_location("aggregate_dev_report", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

main = _mod.main
_is_worker_for_task = _mod._is_worker_for_task
_validate_shards = _mod._validate_shards

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

BARE_TID = "20260101-120000"
OTHER_TID = "20260202-090000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _good_shard(task_id: str = BARE_TID, sha: str = "abc123def456") -> dict:
    return {
        "task_id": task_id,
        "baseline_head_sha": sha,
        "baseline_dirty_snapshot": "",
        "dev": {
            "status": "completed",
            "tasks_completed": [],
            "scripts_created": [],
            "permissions_to_add": [],
            "files_modified": [f"src/{task_id}.py"],
            "files_created": [],
            "observed_preexisting": [],
        },
        "blocking_issues": [],
        "recommendations": [],
    }


def _write(dev_dir: Path, filename: str, data: dict) -> Path:
    p = dev_dir / filename
    p.write_text(json.dumps(data))
    return p


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "docs" / "dev").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# AC1: 0 shards → exit 0, action=skipped
# ---------------------------------------------------------------------------

class TestZeroShards:
    def test_no_shards_returns_skipped(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        rc = main(["--task-id", BARE_TID])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "ok"
        assert out["action"] == "skipped"

    def test_one_shard_also_skipped(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        _write(dev_dir, f"dev-report-A-{BARE_TID}.json", _good_shard())

        rc = main(["--task-id", BARE_TID])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["action"] == "skipped"


# ---------------------------------------------------------------------------
# AC2: 2 shards (role-first) → exit 0, action=aggregated, canonical written
# ---------------------------------------------------------------------------

class TestRoleFirstNaming:
    def test_two_role_first_shards_aggregated(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        _write(dev_dir, f"dev-report-A-{BARE_TID}.json", _good_shard())
        _write(dev_dir, f"dev-report-B-{BARE_TID}.json", _good_shard())

        rc = main(["--task-id", BARE_TID])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["action"] == "aggregated"

        canonical = dev_dir / f"dev-report-{BARE_TID}.json"
        assert canonical.exists()
        data = json.loads(canonical.read_text())
        assert sorted(data["parallel_workers"]) == ["A", "B"]
        assert data["dev"]["status"] == "completed"

    def test_files_modified_union_across_role_first_shards(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        shard_a = _good_shard()
        shard_a["dev"]["files_modified"] = ["alpha.py"]
        shard_b = _good_shard()
        shard_b["dev"]["files_modified"] = ["beta.py"]
        _write(dev_dir, f"dev-report-A-{BARE_TID}.json", shard_a)
        _write(dev_dir, f"dev-report-B-{BARE_TID}.json", shard_b)

        main(["--task-id", BARE_TID])
        capsys.readouterr()

        canonical = dev_dir / f"dev-report-{BARE_TID}.json"
        data = json.loads(canonical.read_text())
        assert "alpha.py" in data["dev"]["files_modified"]
        assert "beta.py" in data["dev"]["files_modified"]


# ---------------------------------------------------------------------------
# AC3: 2 shards (task-first) → exit 0, action=aggregated
# ---------------------------------------------------------------------------

class TestTaskFirstNaming:
    def test_two_task_first_shards_aggregated(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        _write(dev_dir, f"dev-report-{BARE_TID}-worker1.json", _good_shard())
        _write(dev_dir, f"dev-report-{BARE_TID}-worker2.json", _good_shard())

        rc = main(["--task-id", BARE_TID])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["action"] == "aggregated"

    def test_non_worker_label_draft_not_counted(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        _write(dev_dir, f"dev-report-A-{BARE_TID}.json", _good_shard())
        # "draft" is a NON_WORKER_LABEL — must not count as a second shard
        _write(dev_dir, f"dev-report-{BARE_TID}-draft.json", _good_shard())

        rc = main(["--task-id", BARE_TID])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["action"] == "skipped"


# ---------------------------------------------------------------------------
# AC4: canonical present + 2 matching shards → action=validated
# ---------------------------------------------------------------------------

class TestCanonicalPresent:
    def test_matching_canonical_returns_validated(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        _write(dev_dir, f"dev-report-A-{BARE_TID}.json", _good_shard())
        _write(dev_dir, f"dev-report-B-{BARE_TID}.json", _good_shard())
        canonical_data = {
            "task_id": BARE_TID,
            "parallel_workers": ["A", "B"],
            "baseline_head_sha": "abc123def456",
        }
        _write(dev_dir, f"dev-report-{BARE_TID}.json", canonical_data)

        rc = main(["--task-id", BARE_TID])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["action"] == "validated"


# ---------------------------------------------------------------------------
# AC5: malformed shard JSON → exit 1
# ---------------------------------------------------------------------------

class TestMalformedShard:
    def test_malformed_json_shard_exits_1(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        _write(dev_dir, f"dev-report-A-{BARE_TID}.json", _good_shard())
        (dev_dir / f"dev-report-B-{BARE_TID}.json").write_text("{broken: json")

        rc = main(["--task-id", BARE_TID])
        assert rc == 1


# ---------------------------------------------------------------------------
# AC6: task isolation — shards from OTHER_TID don't bleed into BARE_TID
# ---------------------------------------------------------------------------

class TestTaskIsolation:
    def test_shards_from_different_bare_tid_excluded(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        # Only one shard for BARE_TID
        _write(dev_dir, f"dev-report-A-{BARE_TID}.json", _good_shard())
        # Two shards for OTHER_TID — must not be picked up as shards for BARE_TID
        _write(dev_dir, f"dev-report-A-{OTHER_TID}.json", _good_shard(OTHER_TID))
        _write(dev_dir, f"dev-report-B-{OTHER_TID}.json", _good_shard(OTHER_TID))

        rc = main(["--task-id", BARE_TID])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["action"] == "skipped"

    def test_unit_is_worker_for_task_wrong_bare_tid(self):
        is_worker, _ = _is_worker_for_task(
            f"dev-report-A-{OTHER_TID}.json", BARE_TID, BARE_TID
        )
        assert not is_worker


# ---------------------------------------------------------------------------
# AC7: stale canonical (sha mismatch) → exit 1
# ---------------------------------------------------------------------------

class TestStaleCanonical:
    def test_stale_sha_in_canonical_exits_1(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        _write(dev_dir, f"dev-report-A-{BARE_TID}.json", _good_shard(sha="newsha"))
        _write(dev_dir, f"dev-report-B-{BARE_TID}.json", _good_shard(sha="newsha"))
        stale_canonical = {
            "task_id": BARE_TID,
            "parallel_workers": ["A", "B"],
            "baseline_head_sha": "oldsha",
        }
        _write(dev_dir, f"dev-report-{BARE_TID}.json", stale_canonical)

        rc = main(["--task-id", BARE_TID])
        assert rc == 1

    def test_stale_workers_list_in_canonical_exits_1(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        _write(dev_dir, f"dev-report-A-{BARE_TID}.json", _good_shard())
        _write(dev_dir, f"dev-report-B-{BARE_TID}.json", _good_shard())
        _write(dev_dir, f"dev-report-C-{BARE_TID}.json", _good_shard())
        stale_canonical = {
            "task_id": BARE_TID,
            "parallel_workers": ["A", "B"],  # missing C
            "baseline_head_sha": "abc123def456",
        }
        _write(dev_dir, f"dev-report-{BARE_TID}.json", stale_canonical)

        rc = main(["--task-id", BARE_TID])
        assert rc == 1


# ---------------------------------------------------------------------------
# AC8: shard with dev.status != "completed" → exit 1
# ---------------------------------------------------------------------------

class TestDevStatusNotCompleted:
    def test_failed_dev_status_exits_1(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        bad = _good_shard()
        bad["dev"]["status"] = "failed"
        _write(dev_dir, f"dev-report-A-{BARE_TID}.json", bad)
        _write(dev_dir, f"dev-report-B-{BARE_TID}.json", _good_shard())

        rc = main(["--task-id", BARE_TID])
        assert rc == 1

    def test_in_progress_dev_status_exits_1(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        bad = _good_shard()
        bad["dev"]["status"] = "in_progress"
        _write(dev_dir, f"dev-report-A-{BARE_TID}.json", bad)
        _write(dev_dir, f"dev-report-B-{BARE_TID}.json", _good_shard())

        rc = main(["--task-id", BARE_TID])
        assert rc == 1

    def test_unit_validate_shards_catches_non_completed(self):
        shards = [
            ("A", _good_shard()),
            ("B", {**_good_shard(), "dev": {"status": "failed"}}),
        ]
        errors = _validate_shards(shards, BARE_TID)
        assert any("status" in e for e in errors)


# ---------------------------------------------------------------------------
# Bonus: baseline_head_sha mismatch across shards → exit 1
# ---------------------------------------------------------------------------

class TestShardSHAMismatch:
    def test_mismatched_baseline_sha_across_shards_exits_1(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        _write(dev_dir, f"dev-report-A-{BARE_TID}.json", _good_shard(sha="sha1111"))
        _write(dev_dir, f"dev-report-B-{BARE_TID}.json", _good_shard(sha="sha9999"))

        rc = main(["--task-id", BARE_TID])
        assert rc == 1

    def test_unit_validate_shards_catches_sha_mismatch(self):
        shards = [
            ("A", _good_shard(sha="sha1111")),
            ("B", _good_shard(sha="sha9999")),
        ]
        errors = _validate_shards(shards, BARE_TID)
        assert any("baseline_head_sha" in e for e in errors)


# ---------------------------------------------------------------------------
# Bonus: dry-run skips write
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_does_not_write_canonical(
        self, project_dir: Path, capsys: pytest.CaptureFixture
    ):
        dev_dir = project_dir / "docs" / "dev"
        _write(dev_dir, f"dev-report-A-{BARE_TID}.json", _good_shard())
        _write(dev_dir, f"dev-report-B-{BARE_TID}.json", _good_shard())

        rc = main(["--task-id", BARE_TID, "--dry-run"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["action"] == "skipped"
        assert not (dev_dir / f"dev-report-{BARE_TID}.json").exists()
