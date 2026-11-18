# ame-organizer

![imgalt](https://github.com/zelda19/ame-organizer/blob/main/assets/ame-organizer.png)
**Your Downloads folder isn’t a filing system.**
Preview the cleanup. Keep both copies. Move files only when you say so.

A small Python command-line tool that routes downloads into your home folders using file extensions and a few filename rules. No dependencies, background service, or AI guessing what your files contain.

## See it before you move it

```text
resume.pdf -> /home/you/Documents/jobs/resume.pdf
Screenshot_2026.png -> /home/you/Pictures/Screenshots/Screenshot_2026.png
photo.jpg -> /home/you/Pictures/photo.jpg
report.pdf -> /home/you/Documents/report (1).pdf
Preview: 4 file(s). Nothing changed.
```

Illustrative output: `report (1).pdf` means `report.pdf` already exists at the destination. Neither copy is overwritten.

## Try it

Requires Python 3 and a filesystem that supports hard links. Tested on Linux with Python 3.14.

1. Get the code:
   ```bash
   git clone https://github.com/zelda19/ame-organizer.git
   cd ame-organizer
   ```
2. Preview your Downloads folder:
   ```bash
   python3 organizer.py ~/Downloads
   ```
3. Choose which files to move with a `y/n` question for each file:
   ```bash
   python3 organizer.py ~/Downloads --select
   ```

The folder argument is the **source**. Destinations are always under your home directory—not inside the source folder. Preview does not create directories or move files.

## Select files with y/n

```bash
python3 organizer.py ~/Downloads --select
```

No numbered choices: review each destination and answer `y` or `n`.

```text
resume.pdf -> /home/you/Documents/jobs/resume.pdf
Move this file? [y/N]: y
photo.jpg -> /home/you/Pictures/photo.jpg
Move this file? [y/N]: n
```

| Answer | Result |
|---|---|
| `y` or `yes` | Approve this file |
| `n`, `no`, or Enter | Skip this file |
| Ctrl+C before moves begin | Cancel the entire selection |

Answers are case-insensitive. **Approved files move only after you finish answering every question.** End-of-input or an invalid answer also cancels without moving anything.

`--select` cannot be combined with `--apply`. Without either option, the command still only previews; `--apply` still moves every matched file.

## Move all matched files

If you want to move everything in the preview without individual questions:

```bash
python3 organizer.py ~/Downloads --apply
```

## Undo the last cleanup

```bash
python3 organizer.py --undo
```

If you already have the local `ame-organizer` command installed, use `ame-organizer --undo`.

Undo works from any current directory. You can also keep a folder argument:

```bash
python3 organizer.py ~/Downloads --undo
```

Both forms undo the **last recorded cleanup**, not a cleanup filtered by folder. Any folder argument is ignored, even if that folder no longer exists. The restore preview shows exactly which original paths will be used.

```text
Restore: /home/you/Documents/jobs/resume.pdf -> /home/you/Downloads/resume.pdf
Undo this cleanup? [y/N]: y
Restored: /home/you/Downloads/resume.pdf
Undone: 1 file(s).
```

Type `y` or `yes` to restore the latest cleanup that has not been undone. Any other answer, Enter, Ctrl+C at the prompt, or end-of-input cancels. Do not combine `--undo` with `--apply` or `--select`.

- **Future cleanups only.** Moves made before this feature was installed have no history and cannot be undone.
- **No overwrites.** Undo checks every recorded file before starting. It refuses occupied original paths and moved files that are missing, changed, replaced, or symbolic links. Clear the conflict yourself, then retry.
- **Partial cleanups are recorded.** If a move or undo stops midway, completed steps stay completed. Run `--undo` again to recover the latest remaining recorded steps. Empty cleanups, cancelled selections, and previews do not replace previous history.
- **Local history, not a backup.** Paths, file identity, modification time, size, and a SHA-256 fingerprint are stored in `~/.local/state/ame-organizer/history.sqlite3`. File contents are not stored or uploaded. Removing the history loses undo; it cannot recover deleted file contents.
- **Files are checked, not guessed.** Hashing reads each moved file, which adds work for large files. Empty destination folders remain after undo.

## Where files go

Filename matching is case-insensitive. Special rules apply only within their matching file type.

| File | Destination |
|---|---|
| Documents containing `resume` or standalone `cv` in the filename | `~/Documents/jobs/` |
| Pictures whose filename contains `screenshot` anywhere (case-insensitive) | `~/Pictures/Screenshots/` |
| Other documents / pictures | `~/Documents/` / `~/Pictures/` |
| Audio / videos | `~/Music/` / `~/Videos/` |
| Archives, apps, and unrecognized file types | Stay where they are |

Supported extensions:

- **Documents:** `.pdf`, `.txt`, `.doc`, `.docx`, `.csv`, `.xlsx`
- **Pictures:** `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`
- **Audio:** `.mp3`, `.wav`, `.flac`
- **Videos:** `.mp4`, `.mkv`, `.mov`

For example, `my_cv.pdf` matches the jobs rule; `activity.pdf` does not. A resume called `document123.pdf` goes to ordinary Documents: routing uses names, not contents. File contents are read only to fingerprint moves for safe undo.

## Safety and limits

- **Preview is the default.** `--apply` moves all matched files; `--select` moves only the files you approve with `y` or `yes`.
- **Duplicates get numbered.** Existing and already-planned filenames are reserved. A collision appearing during apply stops the operation instead of overwriting.
- **No recursive cleanup.** Subfolders, hidden files, and symbolic links are skipped. Destination directories and their ancestors must not be symbolic links.
- **Same filesystem only.** Moves use a hard link followed by removing the source name. Cross-filesystem moves and filesystems without hard links are unsupported.
- **No automatic rollback or background monitoring.** If apply fails, earlier moves stay completed; use `--undo` to recover recorded moves. An interruption between linking and unlinking may leave both names; undo recognizes that state. Do not run cleanups or undo concurrently, or edit the same files while they run. Real power-loss recovery is not verified.

Each run builds a fresh plan; a later apply can differ from an earlier preview if files have changed.

## Test it

```bash
python3 -m unittest -v
```

Tests use temporary home and Downloads folders, not your real files. They cover routing, duplicate reservations, preview, apply, selection, cancellation, invalid input, undo, partial cleanups, simulated interruptions, changed or missing files, unsafe history, symlinks, and skipped files.

## Small on purpose

`organizer.py` contains the routing, preview, apply, SQLite move history, and undo logic. `test_organizer.py` checks those behaviors using Python’s standard library.

Routing rules live in the script. No configuration framework, content scanning, or mascot required.
