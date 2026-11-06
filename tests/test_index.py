"""No network traffic: verifies LLM provider and crawler indexes are in sync."""
import json
import importlib.util
import io
import os
from unittest.mock import patch
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from provider_monitor import LLM_PRESETS

class LLMIndexTests(unittest.TestCase):
    def test_cli_list_llms_offline(self):
        r = subprocess.run([sys.executable, str(ROOT / 'provider_monitor.py'), '--list-llm-providers'],
                           check=False, text=True, capture_output=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stderr)
        for provider in LLM_PRESETS:
            self.assertIn(provider, r.stdout)

    def test_public_json_matches_builtin_presets(self):
        data = json.loads((ROOT / 'llm_index.json').read_text(encoding='utf-8'))
        self.assertEqual({row['id'] for row in data['providers']}, set(LLM_PRESETS))
        self.assertGreaterEqual(len(data['ai_crawlers']), 6)
        for row in data['providers']:
            self.assertEqual(row['api_base_url'], LLM_PRESETS[row['id']][1])
            self.assertEqual(row['api_key_environment_variable'], LLM_PRESETS[row['id']][2])
            self.assertNotIn('api_key', row)
        self.assertEqual(len({b['agent'] for b in data['ai_crawlers']}), len(data['ai_crawlers']))

    def test_llms_txt_references_exist(self):
        for line in (ROOT / 'llms.txt').read_text(encoding='utf-8').splitlines():
            if '](' not in line:
                continue
            path = line.split('](', 1)[1].split(')', 1)[0]
            self.assertTrue((ROOT / path).is_file(), path)

    def test_model_indexer_is_key_safe_and_detects_pagination(self):
        spec = importlib.util.spec_from_file_location('model_indexer', ROOT / 'scripts/fetch_model_index.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        class FakeResponse(io.BytesIO):
            status = 200
        class FakeOpener:
            def open(self, request, timeout):
                self.headers = dict(request.header_items())
                self.url = request.full_url
                return FakeResponse(b'{"data":[{"id":"example-model","display_name":"Example"}],"has_more":true}')
        opener = FakeOpener()
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY':'test-secret-DO-NOT-COMMIT'}):
            with patch.object(module, 'LLM_HTTP_OPENER', opener):
                info = module.fetch_one('anthropic', 2)
        self.assertEqual(info['model_count'], 1)
        self.assertTrue(info['partial'])
        self.assertEqual(info['models'], [{'id': 'example-model', 'name': 'Example'}])
        self.assertEqual(opener.headers['X-api-key'], 'test-secret-DO-NOT-COMMIT')
        self.assertEqual(opener.url, 'https://api.anthropic.com/v1/models')
        self.assertNotIn('test-secret-DO-NOT-COMMIT', json.dumps(info))

    def test_model_indexer_help_offline(self):
        r = subprocess.run([sys.executable, str(ROOT / 'scripts/fetch_model_index.py'), '--help'],
                           check=False, text=True, capture_output=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('--all-providers', r.stdout)
        self.assertIn('--provider', r.stdout)

if __name__ == '__main__':
    unittest.main()
