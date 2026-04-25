"""tests/unit/hermes_skill/test_agent_comm.py"""

import json
import os

from agent_comm import (
    collect_responses,
    general_profile_dir,
    get_status,
    invoke_generals,
    send_to_inbox,
)


class TestGeneralProfileDir:
    def test_returns_hermes_profiles_path(self):
        path = general_profile_dir("caocao")
        assert path.endswith(".hermes/profiles/caocao")
        assert path.startswith(os.path.expanduser("~"))


class TestSendToInbox:
    def test_writes_context_to_inbox(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agent_comm.HERMES_ROOT", str(tmp_path / ".hermes"))
        send_to_inbox("caocao", json.dumps({"situation": "test"}, ensure_ascii=False))
        inbox = tmp_path / ".hermes" / "profiles" / "caocao" / "inbox.json"
        assert inbox.is_file()
        assert "test" in inbox.read_text(encoding="utf-8")

    def test_overwrites_existing_inbox(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agent_comm.HERMES_ROOT", str(tmp_path / ".hermes"))
        send_to_inbox("caocao", json.dumps({"v1": "old"}))
        send_to_inbox("caocao", json.dumps({"v2": "new"}))
        inbox = tmp_path / ".hermes" / "profiles" / "caocao" / "inbox.json"
        assert "new" in inbox.read_text()
        assert "old" not in inbox.read_text()


class TestInvokeGenerals:
    def test_returns_error_when_inbox_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agent_comm.HERMES_ROOT", str(tmp_path / ".hermes"))
        results = invoke_generals(["nonexistent"], timeout=10)
        assert results[0]["status"] == "error"
        assert "inbox" in results[0].get("error", "")

    def test_runs_subprocess_and_writes_outbox(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agent_comm.HERMES_ROOT", str(tmp_path / ".hermes"))
        prof_dir = tmp_path / ".hermes" / "profiles" / "caocao"
        prof_dir.mkdir(parents=True)
        (prof_dir / "inbox.json").write_text(json.dumps({"q": "test"}), encoding="utf-8")

        def fake_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = '{"action": "fight", "effort": 0.9}'
                stderr = ""

            return Result()

        monkeypatch.setattr("agent_comm.subprocess.run", fake_run)

        results = invoke_generals(["caocao"], timeout=10)
        assert results[0]["status"] == "ok"
        outbox = prof_dir / "outbox.json"
        assert outbox.is_file()
        assert "fight" in outbox.read_text()


class TestCollectResponses:
    def test_returns_pending_when_outbox_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agent_comm.HERMES_ROOT", str(tmp_path / ".hermes"))
        results = collect_responses(["caocao"])
        assert results[0]["status"] == "pending"

    def test_reads_existing_outbox(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agent_comm.HERMES_ROOT", str(tmp_path / ".hermes"))
        prof_dir = tmp_path / ".hermes" / "profiles" / "caocao"
        prof_dir.mkdir(parents=True)
        (prof_dir / "outbox.json").write_text('{"action": "retreat"}', encoding="utf-8")
        results = collect_responses(["caocao"])
        assert results[0]["status"] == "ready"
        assert "retreat" in results[0]["response"]


class TestGetStatus:
    def test_returns_all_profiles(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agent_comm.HERMES_ROOT", str(tmp_path / ".hermes"))
        for gid in ["caocao", "liubei"]:
            p = tmp_path / ".hermes" / "profiles" / gid
            p.mkdir(parents=True)
            (p / "SOUL.md").write_text("# Soul")
            (p / "inbox.json").write_text("{}")

        status_list = get_status()
        ids = [s["general_id"] for s in status_list]
        assert "caocao" in ids
        assert "liubei" in ids
        for s in status_list:
            if s["general_id"] == "caocao":
                assert s["has_soul"] is True
                assert s["has_inbox"] is True
                assert s["has_outbox"] is False
