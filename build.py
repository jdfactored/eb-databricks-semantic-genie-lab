# /// script
# requires-python = ">=3.13"
# dependencies = ["homework"]
# ///
import pathlib
import shutil

from homework import prepare


def main() -> None:
    source_dir = pathlib.Path.cwd()

    homework_dir = prepare.prepare(
        source_dir,
        extensions=None,
        copy_unaffected_files=True,
        ignore_patterns=[".git", "__pycache__", "*.pyc", ".vocareum/.infrastructure", ".examples"],
    )

    (homework_dir / "build.py").unlink()
    (homework_dir / ".github" / "workflows" / "publish-homework.yml").unlink()
    (homework_dir / ".github" / "workflows" / "propagate-template-updates.yml").unlink()
    (homework_dir / ".github" / "workflows" / "publish-to-vocareum.yml").unlink()
    (homework_dir / ".github" / "workflows" / "register-lab-in-content-registry.yml").unlink()    
    shutil.copytree(homework_dir, "dist")
    shutil.rmtree(homework_dir)

    print(f"Homework created from {source_dir} in ./dist/")


if __name__ == "__main__":
    main()
