"""Reject broken smoke payloads before any device mutation can begin."""
import argparse
from contextlib import redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation import smoke


class PayloadValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'x64').mkdir()
        (self.root / 'x64/probe.exe').write_bytes(b'probe-fixture')
        self.manifest = {'suiteVersion': 'fixture', 'files': {
            'x64/probe.exe': hashlib.sha256(b'probe-fixture').hexdigest()}}
        self.write_manifest()
        (self.root / 'suites.json').write_text(json.dumps({'suiteVersion': 'fixture'}))
        self.args = argparse.Namespace(payload=str(self.root))

    def write_manifest(self):
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest))

    def rejected(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            smoke.ensure_payload(self.args)

    def test_valid_payload_and_legacy_windows_separators(self):
        self.assertEqual(smoke.ensure_payload(self.args), self.root)
        digest = self.manifest['files'].pop('x64/probe.exe')
        self.manifest['files']['x64' + chr(92) + 'probe.exe'] = digest
        self.write_manifest()
        self.assertEqual(smoke.ensure_payload(self.args), self.root)

    def test_literal_newline_escape_is_not_json_whitespace(self):
        with (self.root / 'suites.json').open('a') as stream:
            stream.write(chr(92) + 'n')
        self.rejected()

    def test_mismatched_versions(self):
        self.manifest['suiteVersion'] = 'different'
        self.write_manifest()
        self.rejected()

    def test_modified_or_missing_executable(self):
        (self.root / 'x64/probe.exe').write_bytes(b'changed')
        self.rejected()
        (self.root / 'x64/probe.exe').unlink()
        self.rejected()

    def test_paths_cannot_escape_payload(self):
        for name in ('../probe.exe', '/probe.exe', 'C:/probe.exe', '..' + chr(92) + 'probe.exe'):
            self.manifest['files'] = {name: '0' * 64}
            self.write_manifest()
            self.rejected()

    def test_d3d9_profile_is_a_distinct_supported_contract(self):
        smoke.reject_bad_backend('d3d9 fixture', {'d3d': 'dxvk_legacy_d3d9'})
        suite = smoke.load_suites(smoke.load_cases())['dxvk-d3d9']
        self.assertTrue(suite['tests'])
        for entry in suite['tests']:
            self.assertEqual(entry.to_suite_json()['d3dBackend'], 'dxvk_legacy_d3d9')
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            smoke.reject_bad_backend('ambiguous fixture', {'d3d': 'dxvk'})


if __name__ == '__main__':
    unittest.main()
