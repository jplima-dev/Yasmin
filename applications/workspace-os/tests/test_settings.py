from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace_os.settings import SettingsStore, effective_module_urls


class SettingsStoreTests(unittest.TestCase):
    def test_defaults_are_returned_without_creating_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary))
            settings = store.load()
            self.assertEqual(settings["theme"], "light")
            self.assertEqual(settings["accent"], "#ff5b3d")
            self.assertEqual(settings["font_size"], "comfortable")
            self.assertEqual(settings["language"], "pt-BR")
            self.assertFalse(settings["reduce_motion"])
            self.assertFalse(settings["sidebar_collapsed"])
            self.assertTrue(settings["dashboard_show_stats"])
            self.assertTrue(settings["dashboard_show_health"])
            self.assertEqual(settings["dashboard_card_size"], "comfortable")
            self.assertEqual(settings["auto_start_modules"], ["organizer", "bridge", "drive2"])
            self.assertTrue(settings["module_configs"]["drive2"]["run_local"])
            self.assertEqual(settings["favorite_modules"], ["organizer", "bridge", "photos"])
            self.assertFalse(store.path.exists())

    def test_update_is_persisted_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary))
            updated = store.update({"theme": "dark", "module_urls": {"drive2": "http://100.64.0.2:8000"}})
            self.assertEqual(updated["theme"], "dark")
            self.assertEqual(store.load()["module_urls"]["drive2"], "http://100.64.0.2:8000")
            payload = json.loads(store.path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 2)
            self.assertEqual(payload["revision"], 1)

    def test_invalid_external_url_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary))
            with self.assertRaises(ValueError):
                store.update({"module_urls": {"drive2": "file:///C:/segredo"}})
            with self.assertRaises(ValueError):
                store.update({"module_urls": {"drive2": "http://127.0.0.1:99999"}})

    def test_invalid_persisted_field_is_recovered_without_discarding_valid_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            path.write_text(json.dumps({
                "schema_version": 2,
                "theme": "dark",
                "density": "gigante",
                "unknown_future_setting": True,
            }), encoding="utf-8")
            store = SettingsStore(Path(temporary))
            settings = store.load()
            self.assertEqual(settings["theme"], "dark")
            self.assertEqual(settings["density"], "comfortable")
            status = store.load_status()
            self.assertTrue(status["recovered"])
            self.assertGreaterEqual(len(status["issues"]), 2)

    def test_corrupt_settings_are_backed_up_before_a_recovered_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            path.write_text('{"theme":', encoding="utf-8")
            store = SettingsStore(Path(temporary))
            self.assertEqual(store.load()["theme"], "light")
            store.update({"theme": "dark"})
            self.assertEqual(store.load()["theme"], "dark")
            self.assertEqual(store.recovery_path.read_text(encoding="utf-8"), '{"theme":')

    def test_unknown_setting_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary))
            with self.assertRaises(ValueError):
                store.update({"run_any_command": True})

    def test_visual_accessibility_settings_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary))
            updated = store.update({"font_size": "large", "reduce_motion": True, "sidebar_collapsed": True})
            self.assertEqual(updated["font_size"], "large")
            self.assertTrue(updated["reduce_motion"])
            self.assertTrue(updated["sidebar_collapsed"])
            with self.assertRaises(ValueError):
                store.update({"font_size": "gigante"})
            with self.assertRaises(ValueError):
                store.update({"reduce_motion": "sim"})

    def test_dashboard_preferences_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary))
            updated = store.update({
                "dashboard_show_stats": False,
                "dashboard_show_health": False,
                "dashboard_card_size": "wide",
            })
            self.assertFalse(updated["dashboard_show_stats"])
            self.assertFalse(updated["dashboard_show_health"])
            self.assertEqual(updated["dashboard_card_size"], "wide")
            with self.assertRaises(ValueError):
                store.update({"dashboard_card_size": "gigante"})

    def test_module_platform_preferences_are_namespaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary))
            updated = store.update({
                "disabled_modules": ["photos", "photos"],
                "file_associations": {"png": "photos", "csv": "sheets"},
                "keyboard_shortcuts": {"terminal": "Ctrl+Alt+T"},
            })
            self.assertEqual(updated["disabled_modules"], ["photos"])
            self.assertEqual(updated["file_associations"]["csv"], "sheets")
            self.assertEqual(updated["keyboard_shortcuts"]["terminal"], "Ctrl+Alt+T")

    def test_language_is_global_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary))
            self.assertEqual(store.update({"language": "en"})["language"], "en")
            self.assertEqual(store.load()["language"], "en")
            with self.assertRaises(ValueError):
                store.update({"language": "fr"})

    def test_legacy_color_name_is_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            path.write_text(json.dumps({"schema_version": 1, "accent": "purple"}), encoding="utf-8")
            settings = SettingsStore(Path(temporary)).load()
            self.assertEqual(settings["schema_version"], 2)
            self.assertEqual(settings["accent"], "#6750a4")

    def test_existing_installation_enables_local_driver_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            path.write_text(json.dumps({
                "schema_version": 2,
                "auto_start_modules": ["organizer", "bridge"],
                "module_configs": {"drive2": {"port": 8123}},
            }), encoding="utf-8")
            settings = SettingsStore(Path(temporary)).load()
            self.assertTrue(settings["module_configs"]["drive2"]["run_local"])
            self.assertIn("drive2", settings["auto_start_modules"])

            store = SettingsStore(Path(temporary))
            store.update({
                "auto_start_modules": ["organizer", "bridge"],
                "module_configs": {"drive2": {"run_local": True, "port": 8123}},
            })
            self.assertNotIn("drive2", store.load()["auto_start_modules"])

    def test_accent_requires_full_hex_color(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary))
            self.assertEqual(store.update({"accent": "#AABBCC"})["accent"], "#aabbcc")
            with self.assertRaises(ValueError):
                store.update({"accent": "blue"})

    def test_favorite_modules_are_unique_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary))
            updated = store.update({"favorite_modules": ["qrcode", "qrcode", "json"]})
            self.assertEqual(updated["favorite_modules"], ["qrcode", "json"])
            with self.assertRaises(ValueError):
                store.update({"favorite_modules": "qrcode"})

    def test_bridge_and_driver_profiles_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary))
            updated = store.update({
                "module_configs": {
                    "bridge": {"host": "0.0.0.0", "port": 9900, "max_chunk_mb": 8},
                    "drive2": {"port": 8123, "auth_enabled": True, "tailscale_only": True},
                }
            })
            self.assertEqual(updated["module_configs"]["bridge"]["port"], 9900)
            self.assertEqual(updated["module_configs"]["drive2"]["port"], 8123)
            self.assertTrue(updated["module_configs"]["drive2"]["auth_enabled"])
            with self.assertRaises(ValueError):
                store.update({"module_configs": {"bridge": {"port": 70000}}})

    def test_local_driver_url_overrides_remote_without_deleting_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SettingsStore(Path(temporary))
            settings = store.update({
                "module_urls": {"drive2": "http://100.64.0.2:8000"},
                "module_configs": {"drive2": {"run_local": True, "port": 8123}},
            })
            self.assertEqual(effective_module_urls(settings)["drive2"], "http://127.0.0.1:8123")
            remote = store.update({"module_configs": {"drive2": {"run_local": False, "port": 8123}}})
            self.assertEqual(effective_module_urls(remote)["drive2"], "http://100.64.0.2:8000")


if __name__ == "__main__":
    unittest.main()
