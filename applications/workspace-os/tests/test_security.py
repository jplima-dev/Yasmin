from __future__ import annotations

import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from workspace_os.migrations import ModuleMigrationRunner
from workspace_os.observability import StructuredModuleLogs
from workspace_os.operations import OperationGate
from workspace_os.platform import ModuleDataStore
from workspace_os.registry import ModuleRegistry
from workspace_os.security import SessionAuth, TerminalPolicy
from workspace_os.terminal import _command_for_audit


class SessionAndTerminalPolicyTests(unittest.TestCase):
    def test_session_token_is_ephemeral_and_verified_safely(self) -> None:
        auth = SessionAuth(ttl_seconds=60)
        self.assertTrue(auth.verify(auth.token))
        self.assertFalse(auth.verify("token-incorreto"))
        self.assertGreater(auth.expires_at, int(time.time()))

    def test_dangerous_and_write_commands_require_one_use_confirmation(self) -> None:
        policy = TerminalPolicy(restricted=True)
        dangerous = policy.classify("Remove-Item C:\\dados -Recurse -Force")
        simple_delete = policy.classify("Remove-Item C:\\dados\\arquivo.txt")
        git_discard = policy.classify("git restore arquivo.txt")
        write = policy.classify("git commit -am teste")
        read = policy.classify("git status --short")
        self.assertEqual(dangerous.risk, "dangerous")
        self.assertEqual(simple_delete.risk, "dangerous")
        self.assertEqual(git_discard.risk, "dangerous")
        self.assertTrue(write.requires_confirmation)
        self.assertFalse(read.requires_confirmation)
        nonce, _ = policy.issue_confirmation("git commit -am teste", "C:\\repo")
        self.assertTrue(policy.consume_confirmation(nonce, "git commit -am teste", "C:\\repo"))
        self.assertFalse(policy.consume_confirmation(nonce, "git commit -am teste", "C:\\repo"))

    def test_terminal_is_unrestricted_by_default(self) -> None:
        policy = TerminalPolicy()
        decision = policy.classify("Remove-Item C:\\dados -Recurse -Force")
        self.assertEqual(decision.permission, "terminal:unrestricted")
        self.assertEqual(decision.risk, "unrestricted")
        self.assertFalse(decision.requires_confirmation)

    def test_terminal_audit_redacts_possible_credentials(self) -> None:
        redacted, digest = _command_for_audit("tool --token segredo-super-secreto")
        self.assertNotIn("segredo-super-secreto", redacted)
        self.assertTrue(redacted.startswith("[redigido"))
        self.assertEqual(len(digest), 20)


class OperationGateTests(unittest.TestCase):
    def test_concurrent_and_replayed_operations_are_rejected(self) -> None:
        gate = OperationGate(replay_ttl=60)
        self.assertTrue(gate.acquire("POST /api/modules/a/start", "same")[0])
        self.assertFalse(gate.acquire("POST /api/modules/a/start", "other")[0])
        gate.release("POST /api/modules/a/start")
        self.assertFalse(gate.acquire("POST /api/modules/a/start", "same")[0])
        self.assertTrue(gate.acquire("POST /api/modules/a/start", "fresh")[0])


class MigrationAndLogsTests(unittest.TestCase):
    def test_declarative_migration_is_atomic_and_backed_up(self) -> None:
        workspace = Path(__file__).resolve().parents[1]
        registry = ModuleRegistry(workspace / "config/modules.json", workspace.parent)
        module = replace(registry.get("writer"), data_schema_version=2, migrations=({
            "from": 1, "to": 2,
            "operations": [
                {"op": "rename", "from": "profile.name", "to": "profile.displayName"},
                {"op": "default", "path": "profile.active", "value": True},
            ],
        },))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ModuleDataStore(root)
            store.save("writer", {"schemaVersion": 1, "data": {"profile": {"name": "Ink"}}})
            result = ModuleMigrationRunner(store, root).migrate(module)
            snapshot = store.get("writer")
            self.assertTrue(result["changed"])
            self.assertEqual(snapshot["schemaVersion"], 2)
            self.assertEqual(snapshot["data"]["profile"], {"displayName": "Ink", "active": True})
            self.assertTrue(list((root / "migration-backups" / "writer").glob("*.json")))

    def test_structured_logs_rotate_and_remain_queryable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            logs = StructuredModuleLogs(Path(temporary), max_bytes=160, backups=2)
            for index in range(12):
                logs.write("writer", "test.event", sequence=index, detail="x" * 40)
            self.assertTrue(logs.tail("writer"))
            self.assertTrue((Path(temporary) / "logs" / "modules" / "writer.jsonl.1").is_file())


if __name__ == "__main__":
    unittest.main()
