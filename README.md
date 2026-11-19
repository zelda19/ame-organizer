# ame-organizer

<p align="center">
  <img src="assets/ame%20profile.jpg" alt="ame-organizer mascot" width="200">
</p>

<p align="center"><b>Your Downloads folder isn't a filing system.</b></p>

Sort your downloads into the right home folders. Preview first, choose with `y/n`, and undo a cleanup if needed.

## Get started

Requires Python 3 (tested on Linux with Python 3.14). No extra packages.

```bash
git clone https://github.com/zelda19/ame-organizer.git
cd ame-organizer
```

## Use it

Run these from the project folder:

```bash
python3 organizer.py ~/Downloads           # Preview only (nothing is moved)
python3 organizer.py ~/Downloads --select  # Choose files with y/n
python3 organizer.py ~/Downloads --apply   # Move all matched files
python3 organizer.py --undo                # Undo the last recorded cleanup
```

![Preview output of ame-organizer](assets/ame-organizer.png)

With `--select`, answer **`y` to approve** or **`n` / Enter to skip** each file. Files move only after all questions are answered. Ctrl+C before then cancels the selection.

`--undo` shows what it will restore and asks for `y/n` confirmation. You can also run `python3 organizer.py ~/Downloads --undo`; the folder is ignored and the last recorded cleanup is used.

If you have the `ame-organizer` launcher installed, use it in place of `python3 organizer.py` to run from any folder.

## Where files go

Destinations are under your home folder, **not inside Downloads**.

| File | Destination |
|---|---|
| Documents with `resume` or standalone `cv` in the name | `~/Documents/jobs/` |
| Pictures with `screenshot` anywhere in the name | `~/Pictures/Screenshots/` |
| Pictures with `wallpaper` anywhere in the name | `~/Pictures/Wallpapers/` |
| Other supported pictures, even with random names | `~/Pictures/Photos/` |
| Other supported documents | `~/Documents/` |
| Supported audio / videos | `~/Music/` / `~/Videos/` |
| Archives, apps, and unknown file types | Left alone |

Names are matched without regard to capitalization. Routing uses filenames and extensions, not what a file contains. If a picture name contains both `screenshot` and `wallpaper`, Screenshots wins. Missing destination folders are created only when files are moved.

## Safety notes

- **No overwrites:** duplicates become names like `resume (1).pdf`.
- **No digging into folders:** subfolders, hidden files, and symbolic links are skipped.
- **Undo needs history:** only recorded moves can be restored. Undo stops if files changed, went missing, were replaced, or their original paths are occupied. History is stored locally at `~/.local/state/ame-organizer/history.sqlite3`. It is not a file backup.
- **Same drive only:** Downloads and the destination folders must be on the same filesystem (hard-link support is required). Destination folders cannot be symbolic links.
- **One run at a time:** don't edit the files while a cleanup or undo is running.
- **If interrupted:** completed moves stay completed, and `--undo` can recover recorded ones. Real power-loss recovery has not been verified.

## Run the tests

```bash
python3 -m unittest -v
```

Tests use temporary folders, not your personal files.