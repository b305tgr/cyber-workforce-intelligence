from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


class PackageTests(unittest.TestCase):
    def test_source_archive_excludes_local_state_and_secrets(self):
        source_script = Path(__file__).resolve().parent.parent / "scripts" / "package.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "SampleProject"
            scripts = root / "scripts"
            scripts.mkdir(parents=True)
            shutil.copy2(source_script, scripts / "package.py")
            for relative in (
                "app.py", ".git/config", ".venv/pyvenv.cfg",
                "__pycache__/cached.pyc", ".env", ".env.local",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("test", encoding="utf-8")
            archive_path = Path(temporary) / "sample.zip"
            subprocess.run(
                [sys.executable, str(scripts / "package.py"), "--output", str(archive_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())
        self.assertIn("SampleProject/app.py", names)
        self.assertNotIn("SampleProject/.env", names)
        self.assertNotIn("SampleProject/.env.local", names)
        self.assertFalse(any("/.git/" in name for name in names))
        self.assertFalse(any("/.venv/" in name for name in names))
        self.assertFalse(any("__pycache__" in name for name in names))


if __name__ == "__main__":
    unittest.main()
