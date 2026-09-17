"""Unit tests for tools/pipeline.py commands."""

from __future__ import annotations

import argparse
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.pipeline import cmd_status

ROOT = Path(__file__).resolve().parent.parent


class TestPipelineCommands(unittest.TestCase):
    def test_cmd_status_outputs_dashboard(self):
        args = argparse.Namespace(json=False)
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            code = cmd_status(args)
        self.assertEqual(code, 0)
        out = captured.getvalue()
        self.assertIn("AI JOB SEARCH PIPELINE DASHBOARD", out)
        self.assertIn("Application Funnel:", out)
        self.assertIn("Tailored Assets:", out)

    def test_cmd_status_outputs_json(self):
        args = argparse.Namespace(json=True)
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            code = cmd_status(args)
        self.assertEqual(code, 0)
        data = json.loads(captured.getvalue())
        self.assertIn("funnel", data)
        self.assertIn("assets", data)
        self.assertIn("scraped_total", data["funnel"])
        self.assertIn("tracked_total", data["funnel"])
        self.assertIsInstance(data["funnel"]["tracked_total"], int)


if __name__ == "__main__":
    unittest.main()
