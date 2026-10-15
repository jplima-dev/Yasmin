from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.run_bridge import discover_lan_address


class BridgeAdapterTests(unittest.TestCase):
    def test_discovery_returns_address_or_none(self) -> None:
        address = discover_lan_address()
        self.assertTrue(address is None or isinstance(address, str))

    @patch("scripts.run_bridge.socket.socket")
    def test_discovery_closes_probe_on_failure(self, socket_factory) -> None:
        probe = socket_factory.return_value
        probe.connect.side_effect = OSError("sem rota")
        with patch("scripts.run_bridge.socket.gethostbyname", return_value="127.0.0.1"):
            self.assertIsNone(discover_lan_address())
        probe.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

