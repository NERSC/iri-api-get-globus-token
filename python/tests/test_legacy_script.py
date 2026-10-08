"""The legacy entry point must also work as a single downloaded file."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class LegacyScriptTests(unittest.TestCase):
    def test_downloaded_script_help_without_package(self):
        source = Path(__file__).resolve().parents[2] / "get_globus_token.py"
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / source.name
            shutil.copyfile(source, script)
            # The test environment has nersc-tokens installed. Block its imports
            # to reproduce a legacy user with only globus-sdk available.
            bootstrap = """
import importlib.abc
import runpy
import sys

class BlockPackage(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'nersc_tokens', 'filelock'}:
            raise ModuleNotFoundError(fullname)

sys.meta_path.insert(0, BlockPackage())
sys.argv = [sys.argv[1], '--help']
runpy.run_path(sys.argv[0], run_name='__main__')
"""
            result = subprocess.run(
                [sys.executable, "-I", "-c", bootstrap, str(script)],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        for option in ("--facilities", "--print-token", "--refresh-only",
                       "--force-login", "--no-prompt-login", "--validate-iri"):
            self.assertIn(option, result.stdout)
        self.assertIn("auth_tokens.json", result.stdout)


if __name__ == "__main__":
    unittest.main()
