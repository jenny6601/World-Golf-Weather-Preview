import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("fetch_long_range", pathlib.Path("scripts/fetch_long_range.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.course = {
            "course_id": "test-course",
            "course_name": "Test Golf Course",
            "country_code": "JP",
            "latitude": 26.2,
            "longitude": 127.7,
            "timezone": "Asia/Tokyo"
        }

    def test_rejects_invalid_coordinates(self):
        course = dict(self.course, latitude=120)
        with self.assertRaises(ValueError):
            MODULE.validate_course(course)

    def test_rejects_missing_country_code(self):
        course = dict(self.course)
        del course["country_code"]
        with self.assertRaises(ValueError):
            MODULE.validate_course(course)

    @patch("urllib.request.urlopen")
    def test_preserves_raw_provider_payload_and_retrieval_time(self, mocked):
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({
                    "latitude": 26.2,
                    "longitude": 127.7,
                    "timezone": "UTC",
                    "generationtime_ms": 1.2,
                    "hourly": {"time": ["2026-11-21T00:00"], "precipitation": [0.0]}
                }).encode()
        mocked.return_value = Response()
        result = MODULE.fetch_model(self.course, "ecmwf_ec46")
        self.assertEqual(result["model"], "ecmwf_ec46")
        self.assertEqual(result["provider_payload"]["hourly"]["precipitation"], [0.0])
        self.assertIn("retrieved_at", result)
        self.assertNotIn("issued_at", result)

    def test_no_targets_creates_manifest_without_api_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = pathlib.Path(tmp) / "courses.json"
            output = pathlib.Path(tmp) / "out"
            config.write_text('{"courses": []}', encoding="utf-8")
            with patch("sys.argv", ["fetch_long_range.py", "--courses", str(config), "--output", str(output)]):
                with patch.object(MODULE, "fetch_model") as fetch:
                    self.assertEqual(MODULE.main(), 0)
                    fetch.assert_not_called()
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "no_targets_configured")


if __name__ == "__main__":
    unittest.main()
