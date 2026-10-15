from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.security import ActionGate, DeviceIdentity


class SecurityTests(unittest.TestCase):
    def test_identity_is_persistent_and_signature_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "identity.pem"
            first = DeviceIdentity.load_or_create(path)
            second = DeviceIdentity.load_or_create(path)
            self.assertEqual(first.public_key, second.public_key)
            payload = {"action": "ring", "target": "phone"}
            signature = base64.urlsafe_b64decode(first.sign(payload))
            public = Ed25519PublicKey.from_public_bytes(base64.urlsafe_b64decode(first.public_key))
            public.verify(signature, json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())

    def test_confirmation_is_bound_and_single_use(self) -> None:
        gate = ActionGate()
        confirmation = gate.request("owner", "lock", "phone")
        self.assertFalse(gate.consume(confirmation.token, "attacker", "lock", "phone"))
        confirmation = gate.request("owner", "lock", "phone")
        self.assertTrue(gate.consume(confirmation.token, "owner", "lock", "phone"))
        self.assertFalse(gate.consume(confirmation.token, "owner", "lock", "phone"))


if __name__ == "__main__":
    unittest.main()

