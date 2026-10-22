"""Create a source archive without local environments or repository metadata."""

import argparse
import os
from pathlib import Path
import zipfile


EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
    ".mypy_cache", "dist", "node_modules",
}


def build_archive(output: Path, force: bool = False) -> int:
    root = Path(__file__).resolve().parent.parent
    output = output.resolve()
    if output.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing archive: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = root.name
    count = 0

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for current, directories, filenames in os.walk(root, followlinks=False):
            current_path = Path(current)
            directories[:] = sorted(
                name for name in directories
                if name not in EXCLUDED_DIRS
                and not (current_path / name).is_symlink()
            )
            for filename in sorted(filenames):
                source = current_path / filename
                if source.suffix.lower() in (".pyc", ".pyo") or source.is_symlink():
                    continue
                if source.name == ".env" or source.name.startswith(".env."):
                    continue
                if source.resolve() == output:
                    continue
                archive.write(source, Path(prefix) / source.relative_to(root))
                count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Archive path (defaults to dist/MIDNIGHTSIGNAL-source.zip).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing archive at the selected output path.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = args.output or root / "dist" / "MIDNIGHTSIGNAL-source.zip"
    count = build_archive(output, force=args.force)
    print(f"Created {output.resolve()} with {count} source files.")


if __name__ == "__main__":
    main()
