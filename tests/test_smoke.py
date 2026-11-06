"""Offline CLI smoke tests. Never call live provider endpoints."""

import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / 'provider_monitor.py'


class CLISmokeTests(unittest.TestCase):
    def test_help(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), '--help'],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--llm-all-providers', result.stdout)
        self.assertIn('--aws-region', result.stdout)
        self.assertIn('--ssh-host', result.stdout)

    def test_demo_creates_html_and_csv_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'offline-demo.html'
            result = subprocess.run(
                [sys.executable, str(SCRIPT), '--all-tests',
                 '--llm-all-providers', '--demo', '--output', str(output)],
                capture_output=True, text=True, timeout=40, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.exists())
            html = output.read_text(encoding='utf-8')
            for expected in ('DEMONSTRATION DATA', 'Amazon Web Services',
                             'LLM API providers', 'Anthropic', 'Kimi', 'Mistral'):
                self.assertIn(expected, html)
            csv_file = output.with_suffix('.csv')
            self.assertTrue(csv_file.exists())
            with csv_file.open(newline='', encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            self.assertGreater(len(rows), 10)

    def test_cloud_region_help_command(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), '--list-cloud-regions'],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('eu-central-1', result.stdout)
        self.assertIn('westeurope', result.stdout)


if __name__ == '__main__':
    unittest.main()
