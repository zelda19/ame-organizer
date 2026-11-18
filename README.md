# ame-organizer

**Your Downloads folder isn’t a filing system.**
![imgalt](https://github.com/zelda19/ame-organizer/blob/main/assets/ame-organizer.png)

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
3. Review the paths. To actually move the files:
   ```bash
   python3 organizer.py ~/Downloads --apply
   ```

The folder argument is the **source**. Destinations are always under your home directory—not inside the source folder. Preview does not create directories or move files.

## Where files go

Filename matching is case-insensitive. Special rules apply only within their matching file type.

| File | Destination |
|---|---|
| Documents containing `resume` or standalone `cv` in the filename | `~/Documents/jobs/` |
| Pictures whose filename starts with `screenshot` | `~/Pictures/Screenshots/` |
| Other documents / pictures | `~/Documents/` / `~/Pictures/` |
| Audio / videos | `~/Music/` / `~/Videos/` |
| Archives, apps, and unrecognized file types | Stay where they are |

Supported extensions:

- **Documents:** `.pdf`, `.txt`, `.doc`, `.docx`, `.csv`, `.xlsx`
- **Pictures:** `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`
- **Audio:** `.mp3`, `.wav`, `.flac`
- **Videos:** `.mp4`, `.mkv`, `.mov`

For example, `my_cv.pdf` matches the jobs rule; `activity.pdf` does not. A resume called `document123.pdf` goes to ordinary Documents: the tool reads names, not contents.

## Safety and limits

- **Preview is the default.** Only `--apply` moves files.
- **Duplicates get numbered.** Existing and already-planned filenames are reserved. A collision appearing during apply stops the operation instead of overwriting.
- **No recursive cleanup.** Subfolders, hidden files, and symbolic links are skipped. Destination directories and their ancestors must not be symbolic links.
- **Same filesystem only.** Moves use a hard link followed by removing the source name. Cross-filesystem moves and filesystems without hard links are unsupported.
- **No rollback or background monitoring.** If apply fails, earlier moves stay completed. An interruption between linking and unlinking may leave both names. Do not reorganize the same files concurrently.

Each run builds a fresh plan; a later apply can differ from an earlier preview if files have changed.

## Test it

```bash
python3 -m unittest -v
```

Tests use temporary home and Downloads folders, not your real files. They cover routing, duplicate reservations, preview, apply, changed destinations, symlinks, and skipped files.

## Small on purpose

`organizer.py` contains the routing, preview, and apply logic. `test_organizer.py` checks those behaviors using Python’s standard library.

Routing rules live in the script. No configuration framework, content scanning, or mascot required.
