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

    def test_generated_build_source_does_not_mutate_release_cache(self):
        build_source = self.root / 'build/source'
        gate.prepare_build_source(self.archive, self.source, build_source)
        (build_source / 'configure').write_text('build generator changed this file')
        (build_source / 'lib').mkdir()
        (build_source / 'lib/libunistring.sym-t1').write_text('generated symbols')
        gate.verify(self.archive, self.source)
        with self.assertRaises(ValueError):
            gate.verify(self.archive, build_source)

    def test_builder_configures_and_touches_only_mutable_copy(self):
        script = (ROOT / 'scripts/build_gnutls.sh').read_text()
        body = script.split('build_one() {', 1)[1].split('\n}', 1)[0]
        copy_at = body.index('--source-dir "$src" --build-copy "$build/source"')
        bind_at = body.index('src="$build/source"')
        configure_at = body.index('"$src/configure"')
        touch_at = body.index('find "$src"')
        self.assertLess(copy_at, bind_at)
        self.assertLess(bind_at, configure_at)
        self.assertLess(configure_at, touch_at)
        self.assertNotIn('TARBALL_DIR', body)

    def test_build_copy_rejects_tampered_source(self):
        (self.source / 'extra.h').write_text('unexpected')
        with self.assertRaisesRegex(ValueError, 'Unexpected cached'):
            gate.prepare_build_source(self.archive, self.source, self.root / 'build/source')
        self.assertFalse((self.root / 'build/source').exists())

    def test_build_copy_requires_separate_and_fresh_destination(self):
        for destination in (self.source, self.source / 'nested', self.root):
            with self.assertRaisesRegex(ValueError, 'separate trees'):
                gate.prepare_build_source(self.archive, self.source, destination)
        destination = self.root / 'existing'
        destination.mkdir()
        with self.assertRaises(FileExistsError):
            gate.prepare_build_source(self.archive, self.source, destination)

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
