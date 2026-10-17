#!/usr/bin/env python3
"""Synthetic regression checks; never download or execute release payloads."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('archive_gate', ROOT / 'scripts/verify_release_archive.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class ArchiveIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = self.root / 'sample-1.tar.gz'
        self.source = self.root / 'source'
        self.source.mkdir()
        with tarfile.open(self.archive, 'w:gz') as bundle:
            item = tarfile.TarInfo('sample-1/configure')
            data = b'#!/bin/sh\necho fixture\n'
            item.size = len(data)
            bundle.addfile(item, io.BytesIO(data))
        (self.source / 'configure').write_bytes(data)
        self.lock = self.root / 'lock.json'
        self.lock.write_text(json.dumps({'archives': {self.archive.name: {'sha256': hashlib.sha256(self.archive.read_bytes()).hexdigest()}}}))
        self.original_lock = gate.LOCK
        gate.LOCK = self.lock

    def tearDown(self):
        gate.LOCK = self.original_lock
        self.temp.cleanup()

    def test_valid_archive_and_cached_tree(self):
        gate.verify(self.archive, self.source)

    def test_archive_tamper_rejected(self):
        with self.archive.open('ab') as output:
            output.write(b'tampered')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            gate.verify(self.archive)

    def test_cached_source_tamper_rejected(self):
        (self.source / 'configure').write_text('wrong content')
        with self.assertRaisesRegex(ValueError, 'content differs'):
            gate.verify(self.archive, self.source)

    def test_cached_source_missing_rejected(self):
        (self.source / 'configure').unlink()
        with self.assertRaisesRegex(ValueError, 'file missing'):
            gate.verify(self.archive, self.source)

    def test_cached_source_extra_rejected(self):
        (self.source / 'extra.h').write_text('unexpected')
        with self.assertRaisesRegex(ValueError, 'Unexpected cached'):
            gate.verify(self.archive, self.source)

    def test_cached_regular_file_replaced_with_link_rejected(self):
        (self.source / 'configure').unlink()
        (self.source / 'configure').symlink_to(self.lock)
        with self.assertRaisesRegex(ValueError, 'file missing'):
            gate.verify(self.archive, self.source)

if __name__ == '__main__':
    unittest.main()
