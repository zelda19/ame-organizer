"""Organize files by type: preview by default, move only with --apply."""

import argparse
import os
import re
from pathlib import Path


CATEGORIES = {
    "Documents": {".pdf", ".txt", ".doc", ".docx", ".csv", ".xlsx"},
    "Pictures": {".jpg", ".jpeg", ".png", ".gif", ".webp"},
    "Music": {".mp3", ".wav", ".flac"},
    "Videos": {".mp4", ".mkv", ".mov"},
}


def check_directory(directory):
    for path in (directory, *directory.parents):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError(f"Unsafe destination directory: {path}")


def plan_moves(folder, home=None):
    """Reserve unique destinations against both existing and planned files."""
    if not folder.is_dir():
        raise ValueError(f"Not a directory: {folder}")
    home = Path.home() if home is None else home
    moves = []
    reserved = set()
    for source in sorted(folder.iterdir()):
        if source.name.startswith(".") or source.is_symlink() or not source.is_file():
            continue
        category = next(
            (name for name, extensions in CATEGORIES.items()
             if source.suffix.lower() in extensions),
            None,
        )
        if category is None:
            continue
        target_dir = home / category
        name = source.stem.lower()
        if category == "Documents" and (
            "resume" in name or re.search(r"(?<![a-z0-9])cv(?![a-z0-9])", name)
        ):
            target_dir /= "jobs"
        elif category == "Pictures" and name.startswith("screenshot"):
            target_dir /= "Screenshots"
        check_directory(target_dir)
        if source.parent == target_dir:
            continue
        destination = target_dir / source.name
        number = 1
        while destination.exists() or destination.is_symlink() or destination in reserved:
            destination = target_dir / f"{source.stem} ({number}){source.suffix}"
            number += 1
        reserved.add(destination)
        moves.append((source, destination))
    return moves


def apply_moves(moves):
    for source, destination in moves:
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Source is no longer a regular file: {source}")
        check_directory(destination.parent)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.link(source, destination, follow_symlinks=False)
        source.unlink()
        print(f"Moved: {source.name} -> {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Source folder; sort into home folders (not recursive)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Move all matched files")
    mode.add_argument("--select", action="store_true", help="Approve each file with y/n before moving")
    args = parser.parse_args()
    try:
        moves = plan_moves(args.folder.expanduser().resolve())
        if args.select:
            if not moves:
                print("No files to organize.")
                return
            selected = []
            print("Answer for each file; approved files move after all questions.")
            try:
                for source, destination in moves:
                    print(f"{source.name} -> {destination}")
                    answer = input("Move this file? [y/N]: ").strip().lower()
                    if answer in ("y", "yes"):
                        selected.append((source, destination))
                    elif answer not in ("", "n", "no"):
                        raise ValueError("Invalid answer. Use y or n. Nothing changed.")
            except (EOFError, KeyboardInterrupt):
                print("\nCancelled. Nothing changed.")
                return
            moves = selected
        if args.apply or args.select:
            apply_moves(moves)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Error: {error}\nStopped; earlier moves, if any, are kept.\n")
    if args.apply or args.select:
        print(f"Applied: {len(moves)} file(s).")
        return
    for source, destination in moves:
        print(f"{source.name} -> {destination}")
    print(f"Preview: {len(moves)} file(s). Nothing changed.")


if __name__ == "__main__":
    main()
