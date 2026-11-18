"""Organize files by type: preview, select, apply, or undo a recorded cleanup."""

import argparse
from contextlib import closing
import hashlib
import os
import re
import sqlite3
import uuid
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
        elif category == "Pictures" and "screenshot" in name:
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


def file_signature(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Missing or unsafe file: {path}")
    with path.open("rb") as file:
        info = os.fstat(file.fileno())
        digest = hashlib.sha256()
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, digest.hexdigest())


def history_path(home=None):
    home = Path.home() if home is None else home
    return home / ".local/state/ame-organizer/history.sqlite3"


def open_history(path):
    check_directory(path.parent)
    if path.is_symlink():
        raise ValueError(f"Unsafe history file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    history = sqlite3.connect(path)
    history.row_factory = sqlite3.Row
    history.execute("""
        CREATE TABLE IF NOT EXISTS moves (
            id INTEGER PRIMARY KEY,
            batch TEXT NOT NULL,
            source TEXT NOT NULL,
            destination TEXT NOT NULL,
            device INTEGER NOT NULL,
            inode INTEGER NOT NULL,
            size INTEGER NOT NULL,
            mtime INTEGER NOT NULL,
            digest TEXT NOT NULL,
            state TEXT NOT NULL
        )
    """)
    history.commit()
    return history


def apply_moves(moves, home=None):
    if not moves:
        return
    batch = uuid.uuid4().hex
    with closing(open_history(history_path(home))) as history:
        for source, destination in moves:
            source, destination = source.absolute(), destination.absolute()
            check_directory(source.parent)
            signature = file_signature(source)
            check_directory(destination.parent)
            destination.parent.mkdir(parents=True, exist_ok=True)
            entry = history.execute(
                """INSERT INTO moves
                   (batch, source, destination, device, inode, size, mtime, digest, state)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (batch, str(source), str(destination), *signature),
            ).lastrowid
            # Save intent before changing files, so interrupted moves are recoverable.
            history.commit()
            try:
                os.link(source, destination, follow_symlinks=False)
            except OSError:
                history.execute("UPDATE moves SET state = 'failed' WHERE id = ?", (entry,))
                history.commit()
                raise
            if file_signature(destination) != signature or file_signature(source) != signature:
                raise ValueError(f"File changed while moving; both names kept: {source}")
            source.unlink()
            history.execute("UPDATE moves SET state = 'moved' WHERE id = ?", (entry,))
            history.commit()
            print(f"Moved: {source.name} -> {destination}")


def undo_plan(entries):
    plan = []
    for entry in entries:
        source, destination = Path(entry["source"]), Path(entry["destination"])
        if not source.is_absolute() or not destination.is_absolute() or source == destination:
            raise ValueError("Invalid paths in cleanup history.")
        check_directory(source.parent)
        check_directory(destination.parent)
        expected = tuple(entry[key] for key in ("device", "inode", "size", "mtime", "digest"))
        if source.exists() or source.is_symlink():
            if file_signature(source) != expected:
                raise ValueError(f"Cannot undo: original path is occupied: {source}")
            action = "remove_extra_link"
        else:
            action = "restore"
        if destination.exists() or destination.is_symlink():
            if file_signature(destination) != expected:
                raise ValueError(f"Cannot undo: moved file changed or was replaced: {destination}")
        elif action == "remove_extra_link":
            action = "already_restored"
        else:
            raise ValueError(f"Cannot undo: moved file is missing: {destination}")
        plan.append((entry["id"], source, destination, action))
    return plan


def undo_cleanup():
    path = history_path()
    check_directory(path.parent)
    if not path.exists() and not path.is_symlink():
        print("No cleanup to undo.")
        return
    with closing(open_history(path)) as history:
        latest = history.execute(
            "SELECT batch FROM moves WHERE state IN ('pending', 'moved') ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest is None:
            print("No cleanup to undo.")
            return
        entries = history.execute(
            """SELECT * FROM moves WHERE batch = ? AND state IN ('pending', 'moved')
               ORDER BY id DESC""", (latest["batch"],)
        ).fetchall()
        plan = undo_plan(entries)
        for _, source, destination, _ in plan:
            print(f"Restore: {destination} -> {source}")
        try:
            answer = input("Undo this cleanup? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer not in ("y", "yes"):
            print("Cancelled. Nothing changed.")
            return
        # Recheck after confirmation; every entry must be safe before restoration starts.
        undo_plan(entries)
        for entry in entries:
            entry_id, source, destination, action = undo_plan([entry])[0]
            if action == "restore":
                source.parent.mkdir(parents=True, exist_ok=True)
                os.link(destination, source, follow_symlinks=False)
            if action != "already_restored":
                destination.unlink()
            history.execute("UPDATE moves SET state = 'undone' WHERE id = ?", (entry_id,))
            history.commit()
            print(f"Restored: {source}")
        print(f"Undone: {len(entries)} file(s).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path, help="Source folder (not recursive); optional and ignored with --undo")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Move all matched files")
    mode.add_argument("--select", action="store_true", help="Approve each file with y/n before moving")
    mode.add_argument("--undo", action="store_true", help="Confirm and undo the last recorded cleanup, regardless of folder")
    args = parser.parse_args()
    if not args.undo and args.folder is None:
        parser.error("a source folder is required unless using --undo")
    try:
        if args.undo:
            if args.folder is not None:
                print("Undo uses the last recorded cleanup; folder argument is ignored.")
            undo_cleanup()
            return
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
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"Error: {error}\nStopped; earlier moves, if any, are kept.\n")
    if args.apply or args.select:
        print(f"Applied: {len(moves)} file(s).")
        return
    for source, destination in moves:
        print(f"{source.name} -> {destination}")
    print(f"Preview: {len(moves)} file(s). Nothing changed.")


if __name__ == "__main__":
    main()
