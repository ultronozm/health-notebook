#!/usr/bin/env python3
"""Create a separate notebook; refuse existing paths and paths inside the kit."""
import argparse
from pathlib import Path
import shutil
import subprocess


def initialize(destination):
    kit = Path(__file__).resolve().parent.parent
    target = Path(destination).expanduser().absolute()
    resolved = target.resolve()
    if resolved == kit or kit in resolved.parents:
        raise ValueError("Choose a private directory outside the public setup kit")
    if target.exists() or target.is_symlink():
        raise ValueError("Destination already exists; no files were changed")
    if not shutil.which("git"):
        raise ValueError("Install git first")
    # copytree refuses collisions; never merge into an existing notebook.
    shutil.copytree(kit / "notebook-template", target)
    target.chmod(0o700)
    subprocess.run(["git", "init", "--initial-branch=main", str(target)], check=True)
    print(f"Created {target}. No remote or commit was added. Fill in PROFILE.md.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", nargs="?", default="~/health-notebook")
    args = parser.parse_args()
    try:
        initialize(args.destination)
    except ValueError as error:
        parser.error(str(error))
