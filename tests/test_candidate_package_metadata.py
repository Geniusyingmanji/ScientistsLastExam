"""Candidate pins refer to mounted installations, separately from trusted metadata."""
from __future__ import annotations

import importlib.metadata
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from sle.runtime_identity import current_runtime_descriptor
from sle.secure_eval import (
    _candidate_package_mounts,
    _mounted_candidate_distribution_version,
    read_candidate_packages,
)


def _install(root, version, *, metadata=True, name='packaging', imports=('packaging',)):
    root.mkdir(parents=True, exist_ok=True)
    files = []
    for module in imports:
        package = root / module
        package.mkdir(exist_ok=True)
        (package / '__init__.py').write_text('__version__ = %r\n' % version)
        files.append(module + '/__init__.py,,')
    if metadata:
        info = root / (name.replace('-', '_') + '-' + version + '.dist-info')
        info.mkdir(exist_ok=True)
        (info / 'METADATA').write_text('Metadata-Version: 2.1\nName: %s\nVersion: %s\n' % (name, version))
        (info / 'RECORD').write_text('\n'.join(files) + '\n')


@contextmanager
def _paths(overlay, sites):
    import sys
    with patch.object(sys, 'path', [str(overlay), *map(str, sites), *sys.path]), patch(
        'sle.secure_eval._site_package_roots', return_value=sites
    ), patch('sle.secure_eval.candidate_distribution_pins', return_value={'packaging': '26.2'}):
        yield


class CandidatePackageMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.overlay = self.root / 'pytest-target'
        self.site = self.root / 'site-packages'
        self.later = self.root / 'dist-packages'
        self.task = self.root / 'task'
        (self.task / 'frontier_eval').mkdir(parents=True)
        (self.task / 'frontier_eval/candidate_packages.txt').write_text('qutip\n')

    def test_trusted_overlay_cannot_certify_a_different_mounted_version(self):
        _install(self.overlay, '26.2')
        _install(self.site, '24.2')
        with _paths(self.overlay, [self.site]):
            self.assertEqual(importlib.metadata.version('packaging'), '26.2')
            descriptor = current_runtime_descriptor(('packaging',))
            self.assertEqual(descriptor['distributions']['packaging'], '26.2')
            mounts = _candidate_package_mounts(('qutip', 'packaging'))
            self.assertEqual(mounts, [(self.site / 'packaging', '/packages/packaging')])
            self.assertEqual(_mounted_candidate_distribution_version('packaging', mounts), '24.2')
            with self.assertRaisesRegex(RuntimeError, "candidate-mounted package 'packaging' has version 24.2, expected 26.2"):
                read_candidate_packages(self.task)

    def test_overlay_only_metadata_cannot_describe_an_unrecorded_site_package(self):
        _install(self.overlay, '26.2')
        _install(self.site, '24.2', metadata=False)
        with _paths(self.overlay, [self.site]):
            self.assertEqual(importlib.metadata.version('packaging'), '26.2')
            with self.assertRaisesRegex(RuntimeError, 'missing, ambiguous or mismatched file metadata'):
                read_candidate_packages(self.task)

    def test_earlier_shadow_package_cannot_borrow_later_site_metadata(self):
        _install(self.site, '24.2', metadata=False)
        _install(self.later, '26.2')
        with _paths(self.overlay, [self.site, self.later]):
            self.assertEqual(importlib.metadata.version('packaging'), '26.2')
            with self.assertRaisesRegex(RuntimeError, 'missing, ambiguous or mismatched file metadata'):
                read_candidate_packages(self.task)

    def test_matching_versions_pass_without_mounting_the_trusted_overlay(self):
        _install(self.overlay, '26.2')
        _install(self.site, '26.2')
        with _paths(self.overlay, [self.site]):
            self.assertEqual(read_candidate_packages(self.task), ('qutip', 'packaging'))
            self.assertEqual(_candidate_package_mounts(('qutip', 'packaging')),
                             [(self.site / 'packaging', '/packages/packaging')])

    def test_duplicate_site_paths_do_not_duplicate_one_distribution(self):
        _install(self.site, '26.2')
        with _paths(self.overlay, [self.site, self.site]):
            self.assertEqual(read_candidate_packages(self.task), ('qutip', 'packaging'))

    def test_ambiguous_metadata_at_the_mounted_site_is_rejected(self):
        _install(self.site, '26.2')
        _install(self.site, '24.2')
        with _paths(self.overlay, [self.site]):
            mounts = _candidate_package_mounts(('packaging',))
            with self.assertRaisesRegex(RuntimeError, 'missing, ambiguous or mismatched file metadata'):
                _mounted_candidate_distribution_version('packaging', mounts)

    def test_distribution_import_aliases_use_file_ownership(self):
        _install(self.site, '10.4.0', name='Pillow', imports=('PIL', 'pillow.libs'))
        with _paths(self.overlay, [self.site]):
            mounts = _candidate_package_mounts(('PIL', 'pillow.libs'))
            self.assertEqual(_mounted_candidate_distribution_version('pillow', mounts), '10.4.0')

    def test_mount_order_and_first_site_precedence_are_preserved(self):
        _install(self.site, 'fixture', imports=('numpy', 'scipy', 'packaging'))
        _install(self.later, 'fixture', imports=('numpy', 'numpy.libs', 'packaging', 'not_requested'))
        with _paths(self.overlay, [self.site, self.later]):
            self.assertEqual(_candidate_package_mounts(('packaging',)), [
                (self.site / 'numpy', '/packages/numpy'),
                (self.site / 'scipy', '/packages/scipy'),
                (self.site / 'packaging', '/packages/packaging'),
                (self.later / 'numpy.libs', '/packages/numpy.libs'),
            ])


if __name__ == '__main__':
    unittest.main()
