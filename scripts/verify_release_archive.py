#!/usr/bin/env python3
"""Check pinned archive bytes and, optionally, a cached extracted source tree."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath
import tarfile

LOCK = Path(__file__).resolve().parents[1] / 'docs/migration/gnutls-archives.lock.json'

def verify(archive, source=None):
    archive = Path(archive)
    record = json.loads(LOCK.read_text())['archives'][archive.name]
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != record['sha256']:
        raise ValueError('Release archive checksum mismatch: ' + archive.name)
    if source is not None:
        source = Path(source)
        expected = set()
        with tarfile.open(archive) as bundle:
            for member in bundle:
                parts = PurePosixPath(member.name).parts
                if not parts or parts[0] in ('/', '..') or '..' in parts:
                    raise ValueError('Unsafe archive path: ' + member.name)
                if len(parts) == 1:
                    continue
                relative = Path(*parts[1:])
                path = source / relative
                if not path.parent.resolve().is_relative_to(source.resolve()):
                    raise ValueError("Cached source path escapes root: " + str(relative))
                if member.isdir():
                    continue
                expected.add(relative.as_posix())
                if member.issym():
                    if not path.is_symlink() or str(path.readlink()) != member.linkname:
                        raise ValueError('Cached source symlink differs: ' + str(relative))
                elif member.isfile():
                    if path.is_symlink() or not path.is_file():
                        raise ValueError('Cached source file missing: ' + str(relative))
                    if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(bundle.extractfile(member).read()).digest():
                        raise ValueError('Cached source content differs: ' + str(relative))
                else:
                    raise ValueError('Unsupported archive member: ' + member.name)
        actual_files = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file() or p.is_symlink()}
        if actual_files != expected:
            raise ValueError('Unexpected cached source files: ' + str(sorted(actual_files - expected)[:10]))
    print('PASS release archive identity: ' + archive.name + ' ' + actual)

def prepare_build_source(archive, source, destination):
    """Keep the verified release cache immutable across upstream generators."""
    source, destination = Path(source), Path(destination)
    if (destination.resolve().is_relative_to(source.resolve()) or
            source.resolve().is_relative_to(destination.resolve())):
        raise ValueError('Build source and release cache must be separate trees')
    verify(archive, source)
    # Refuse a reused destination instead of mixing old/generated source files.
    shutil.copytree(source, destination, symlinks=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--source-dir', type=Path)
    parser.add_argument('--build-copy', type=Path, help='Copy verified sources to a new writable build tree')
    args = parser.parse_args()
    if args.build_copy is not None:
        if args.source_dir is None:
            parser.error('--build-copy requires --source-dir')
        prepare_build_source(args.archive, args.source_dir, args.build_copy)
    else:
        verify(args.archive, args.source_dir)
