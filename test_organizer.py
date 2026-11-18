import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from organizer import apply_moves, plan_moves, undo_cleanup


class OrganizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ame-organizer-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.folder = self.home / "Downloads"
        self.folder.mkdir()
        self.env = {**os.environ, "HOME": str(self.home)}
        self.samples = {
            "report.pdf": "new report",
            "report (1).pdf": "another report",
            "photo.JPG": "photo",
            "notes.txt": "notes",
            "ame_resume.pdf": "resume",
        }
        for name, content in self.samples.items():
            (self.folder / name).write_text(content)
        (self.home / "Documents").mkdir()
        (self.home / "Documents" / "report.pdf").write_text("original report")

    def test_five_files_and_duplicate_reservations(self):
        moves = plan_moves(self.folder, self.home)
        self.assertEqual(len(moves), 5)
        destinations = {source.name: target.relative_to(self.home).as_posix()
                        for source, target in moves}
        self.assertEqual(destinations, {
            "ame_resume.pdf": "Documents/jobs/ame_resume.pdf",
            "notes.txt": "Documents/notes.txt",
            "photo.JPG": "Pictures/Photos/photo.JPG",
            "report (1).pdf": "Documents/report (1).pdf",
            "report.pdf": "Documents/report (2).pdf",
        })
        for name, content in self.samples.items():
            self.assertEqual((self.folder / name).read_text(), content)
        self.assertFalse((self.home / "Pictures").exists())
        self.assertFalse((self.home / "Documents/jobs").exists())
        self.assertEqual(
            (self.home / "Documents/report.pdf").read_text(), "original report"
        )

    def test_preview_command(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("organizer.py")), str(self.folder)],
            capture_output=True, text=True, check=True, env=self.env,
        )
        self.assertIn("Preview: 5 file(s). Nothing changed.", result.stdout)
        print("\nFive-file preview:\n" + result.stdout, end="")

    def test_rejects_destination_symlink(self):
        (self.home / "Pictures").symlink_to(self.home / "Documents")
        with self.assertRaisesRegex(ValueError, "Unsafe destination"):
            plan_moves(self.folder, self.home)

    def test_skips_source_symlink(self):
        (self.folder / "linked.pdf").symlink_to(self.folder / "report.pdf")
        self.assertEqual(len(plan_moves(self.folder, self.home)), 5)

    def test_apply_command_preserves_contents_and_existing_file(self):
        moves = plan_moves(self.folder, self.home)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("organizer.py")),
             str(self.folder), "--apply"],
            capture_output=True, text=True, check=True, env=self.env,
        )
        for source, destination in moves:
            self.assertFalse(source.exists())
            self.assertEqual(destination.read_text(), self.samples[source.name])
        self.assertEqual(
            (self.home / "Documents/report.pdf").read_text(), "original report"
        )
        self.assertEqual(plan_moves(self.folder, self.home), [])
        self.assertIn("Applied: 5 file(s).", result.stdout)
        print("\nFive-file apply:\n" + result.stdout, end="")

    def test_apply_refuses_new_collision(self):
        source, destination = plan_moves(self.folder, self.home)[0]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("arrived after preview")
        with self.assertRaises(FileExistsError):
            apply_moves([(source, destination)], self.home)
        self.assertEqual(source.read_text(), self.samples[source.name])
        self.assertEqual(destination.read_text(), "arrived after preview")

    def test_apply_rejects_changed_destination_symlink(self):
        moves = plan_moves(self.folder, self.home)
        (self.home / "Documents/jobs").symlink_to(self.folder)
        with self.assertRaisesRegex(ValueError, "Unsafe destination"):
            apply_moves(moves, self.home)
        self.assertTrue((self.folder / "ame_resume.pdf").exists())

    def test_invalid_folder_command(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("organizer.py")),
             str(self.folder / "missing"), "--apply"],
            capture_output=True, text=True, env=self.env,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Not a directory", result.stderr)

    def test_remaining_rules_and_cv_word_boundaries(self):
        examples = {
            "Screenshot_2026.png": "Pictures/Screenshots",
            "2026_screenshot_edit.png": "Pictures/Screenshots",
            "2026_11_15_16_15_02_screenshot.png": "Pictures/Screenshots",
            "2026_SCREENSHOT.JPG": "Pictures/Screenshots",
            "nature_wallpaper.png": "Pictures/Wallpapers",
            "WALLPAPER_2026.JPG": "Pictures/Wallpapers",
            "wallpaper_screenshot.png": "Pictures/Screenshots",
            "ordinary_photo.png": "Pictures/Photos",
            "IMG_9382.jpg": "Pictures/Photos",
            "a8f29.png": "Pictures/Photos",
            "wallpaper.pdf": "Documents",
            "AME-CV.pdf": "Documents/jobs",
            "my_cv.pdf": "Documents/jobs",
            "activity.pdf": "Documents",
            "song.mp3": "Music",
            "clip.mp4": "Videos",
        }
        for name in examples:
            (self.folder / name).touch()
        destinations = {source.name: destination.parent.relative_to(self.home).as_posix()
                        for source, destination in plan_moves(self.folder, self.home)}
        for name, target in examples.items():
            self.assertEqual(destinations[name], target)

    def test_leaves_archives_unknown_hidden_and_subfolders_alone(self):
        for name in ("bundle.zip", "program.AppImage", "unknown.xyz", ".private.pdf"):
            (self.folder / name).touch()
        (self.folder / "Stash").mkdir()
        (self.folder / "Stash/nested.pdf").touch()
        self.assertEqual(len(plan_moves(self.folder, self.home)), 5)

    def test_rejects_symlinked_ancestor(self):
        (self.home / "Documents/jobs").mkdir()
        (self.home / "Documents/jobs/resume.pdf").touch()
        (self.home / "Pictures").symlink_to(self.home / "Documents")
        with self.assertRaisesRegex(ValueError, "Unsafe destination"):
            apply_moves([(self.folder / "photo.JPG",
                          self.home / "Pictures/Screenshots/photo.JPG")], self.home)
        self.assertTrue((self.folder / "photo.JPG").exists())

    def test_already_in_destination_stays_put(self):
        self.assertEqual(plan_moves(self.home / "Documents", self.home), [])

    def test_select_moves_only_yes_files(self):
        moves = plan_moves(self.folder, self.home)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("organizer.py")),
             str(self.folder), "--select"],
            input=" Y \nn\nyes\nNo\n\n", capture_output=True, text=True, env=self.env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ame_resume.pdf ->", result.stdout)
        self.assertEqual(result.stdout.count("Move this file? [y/N]:"), 5)
        self.assertIn("Applied: 2 file(s).", result.stdout)
        for index, (source, destination) in enumerate(moves, 1):
            if index in (1, 3):
                self.assertFalse(source.exists())
                self.assertEqual(destination.read_text(), self.samples[source.name])
            else:
                self.assertTrue(source.exists())
                self.assertFalse(destination.exists())

    def test_select_invalid_input_moves_nothing(self):
        for answer in ("1\n", "abc\n", "y\ninvalid\n"):
            with self.subTest(answer=answer):
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).with_name("organizer.py")),
                     str(self.folder), "--select"],
                    input=answer, capture_output=True, text=True, env=self.env,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("Invalid answer", result.stderr)
                for name, content in self.samples.items():
                    self.assertEqual((self.folder / name).read_text(), content)
                self.assertFalse((self.home / "Documents/jobs").exists())

    def test_select_cancel_or_end_of_input_moves_nothing(self):
        for answer in ("", "y\n"):
            with self.subTest(answer=answer):
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).with_name("organizer.py")),
                     str(self.folder), "--select"],
                    input=answer, capture_output=True, text=True, env=self.env,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Cancelled. Nothing changed.", result.stdout)
                self.assertEqual(len(plan_moves(self.folder, self.home)), 5)

    def test_select_no_or_enter_skips_every_file(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("organizer.py")),
             str(self.folder), "--select"],
            input="n\nno\n\nN\n\n", capture_output=True, text=True, env=self.env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Applied: 0 file(s).", result.stdout)
        for name, content in self.samples.items():
            self.assertEqual((self.folder / name).read_text(), content)
        self.assertFalse((self.home / "Documents/jobs").exists())

    def test_select_cannot_combine_with_apply(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("organizer.py")),
             str(self.folder), "--select", "--apply"],
            input="y\n", capture_output=True, text=True, env=self.env,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(plan_moves(self.folder, self.home)), 5)

    def test_select_empty_folder_does_not_prompt(self):
        empty = self.home / "empty"
        empty.mkdir()
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("organizer.py")),
             str(empty), "--select"],
            input="", capture_output=True, text=True, env=self.env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No files to organize.", result.stdout)
        self.assertNotIn("Move this file?", result.stdout)

    def run_command(self, *args, answer="", cwd=None):
        return subprocess.run(
            [sys.executable, str(Path(__file__).with_name("organizer.py")), *args],
            input=answer, capture_output=True, text=True, env=self.env, cwd=cwd,
        )

    def test_undo_restores_last_cleanup_without_touching_existing_files(self):
        applied = self.run_command(str(self.folder), "--apply")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        undone = self.run_command("--undo", answer="y\n")
        self.assertEqual(undone.returncode, 0, undone.stderr)
        self.assertIn("Undo this cleanup? [y/N]:", undone.stdout)
        self.assertIn("Undone: 5 file(s).", undone.stdout)
        for name, content in self.samples.items():
            self.assertEqual((self.folder / name).read_text(), content)
        self.assertEqual(
            (self.home / "Documents/report.pdf").read_text(), "original report"
        )
        self.assertEqual(len(plan_moves(self.folder, self.home)), 5)
        again = self.run_command("--undo", answer="y\n")
        self.assertIn("No cleanup to undo.", again.stdout)

    def test_undo_without_history_does_not_create_history(self):
        result = self.run_command("--undo")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No cleanup to undo.", result.stdout)
        self.assertFalse((self.home / ".local").exists())

    def test_undo_cancel_keeps_files_and_history_available(self):
        moves = plan_moves(self.folder, self.home)
        self.assertEqual(self.run_command(str(self.folder), "--apply").returncode, 0)
        for answer in ("n\n", "\n", "", "invalid\n"):
            result = self.run_command("--undo", answer=answer)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Cancelled. Nothing changed.", result.stdout)
            for source, destination in moves:
                self.assertFalse(source.exists())
                self.assertEqual(destination.read_text(), self.samples[source.name])
        self.assertEqual(self.run_command("--undo", answer="yes\n").returncode, 0)
        self.assertTrue((self.folder / "ame_resume.pdf").exists())

    def test_undo_refuses_existing_original_without_restoring_other_files(self):
        moves = plan_moves(self.folder, self.home)
        self.assertEqual(self.run_command(str(self.folder), "--apply").returncode, 0)
        source = self.folder / "ame_resume.pdf"
        source.write_text("new download")
        result = self.run_command("--undo", answer="y\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("original path is occupied", result.stderr)
        self.assertEqual(source.read_text(), "new download")
        for _, destination in moves:
            self.assertTrue(destination.exists())
        self.assertFalse((self.folder / "notes.txt").exists())

    def test_undo_refuses_changed_moved_file_before_restoring_anything(self):
        moves = plan_moves(self.folder, self.home)
        self.assertEqual(self.run_command(str(self.folder), "--apply").returncode, 0)
        destination = self.home / "Documents/jobs/ame_resume.pdf"
        destination.write_text("edited resume")
        result = self.run_command("--undo", answer="y\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("changed or was replaced", result.stderr)
        self.assertEqual(destination.read_text(), "edited resume")
        for source, target in moves:
            self.assertFalse(source.exists())
            self.assertTrue(target.exists())

    def test_undo_refuses_replacement_even_with_identical_contents(self):
        self.assertEqual(self.run_command(str(self.folder), "--apply").returncode, 0)
        destination = self.home / "Documents/jobs/ame_resume.pdf"
        destination.rename(self.home / "saved-resume.pdf")
        destination.write_text("resume")
        result = self.run_command("--undo", answer="y\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("changed or was replaced", result.stderr)
        self.assertTrue(destination.exists())
        self.assertFalse((self.folder / "ame_resume.pdf").exists())

    def test_undo_refuses_missing_moved_file(self):
        self.assertEqual(self.run_command(str(self.folder), "--apply").returncode, 0)
        (self.home / "Documents/jobs/ame_resume.pdf").rename(self.home / "saved-resume.pdf")
        result = self.run_command("--undo", answer="y\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("moved file is missing", result.stderr)
        self.assertFalse((self.folder / "notes.txt").exists())

    def test_undo_refuses_symlinked_original_directory(self):
        self.assertEqual(self.run_command(str(self.folder), "--apply").returncode, 0)
        self.folder.rename(self.home / "old-downloads")
        self.folder.symlink_to(self.home / "Documents")
        result = self.run_command("--undo", answer="y\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unsafe destination directory", result.stderr)
        self.assertTrue((self.home / "Documents/jobs/ame_resume.pdf").exists())

    def test_undo_recovers_successes_from_partial_cleanup(self):
        moves = plan_moves(self.folder, self.home)
        (self.home / "Documents/notes.txt").write_text("arrived after preview")
        with self.assertRaises(FileExistsError):
            apply_moves(moves, self.home)
        self.assertFalse((self.folder / "ame_resume.pdf").exists())
        result = self.run_command("--undo", answer="y\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Undone: 1 file(s).", result.stdout)
        self.assertEqual((self.folder / "ame_resume.pdf").read_text(), "resume")
        self.assertEqual(
            (self.home / "Documents/notes.txt").read_text(), "arrived after preview"
        )

    def test_undo_affects_only_latest_cleanup_and_noop_does_not_replace_it(self):
        first = self.run_command(str(self.folder), "--select", answer="y\nn\nn\nn\nn\n")
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_command(str(self.folder), "--select", answer="n\ny\nn\nn\n")
        self.assertEqual(second.returncode, 0, second.stderr)
        skipped = self.run_command(str(self.folder), "--select", answer="\n\n\n")
        self.assertEqual(skipped.returncode, 0, skipped.stderr)
        result = self.run_command("--undo", answer="y\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Undone: 1 file(s).", result.stdout)
        self.assertEqual((self.folder / "photo.JPG").read_text(), "photo")
        self.assertFalse((self.folder / "ame_resume.pdf").exists())
        self.assertTrue((self.home / "Documents/jobs/ame_resume.pdf").exists())

    def test_undo_rejects_other_modes(self):
        for args in (("--undo", "--apply"), ("--undo", "--select")):
            result = self.run_command(*args, answer="y\n")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(len(plan_moves(self.folder, self.home)), 5)

    def test_undo_accepts_optional_folder_from_any_working_directory(self):
        elsewhere = self.home / "elsewhere"
        elsewhere.mkdir()
        marker = elsewhere / "keep.txt"
        marker.write_text("untouched")
        for args in ((str(self.folder), "--undo"),
                     ("--undo", str(elsewhere)),
                     (str(self.home / "missing"), "--undo"),
                     ("--undo",)):
            with self.subTest(args=args):
                applied = self.run_command(str(self.folder), "--apply")
                self.assertEqual(applied.returncode, 0, applied.stderr)
                result = self.run_command(*args, answer="y\n", cwd=elsewhere)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Undone: 5 file(s).", result.stdout)
                if len(args) > 1:
                    self.assertIn("folder argument is ignored", result.stdout)
                for name, content in self.samples.items():
                    self.assertEqual((self.folder / name).read_text(), content)
                self.assertEqual(marker.read_text(), "untouched")

    def test_undo_recovers_move_interrupted_before_or_after_link(self):
        move = plan_moves(self.folder, self.home)[0]
        # Inject filesystem failures at the two boundaries around link/unlink.
        for boundary in ("organizer.os.link", "organizer.Path.unlink"):
            with self.subTest(boundary=boundary):
                with patch(boundary, side_effect=KeyboardInterrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        apply_moves([move], self.home)
                result = self.run_command("--undo", answer="y\n")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(move[0].read_text(), "resume")
                self.assertFalse(move[1].exists())

    def test_undo_can_resume_after_interruption_between_link_and_unlink(self):
        source, destination = plan_moves(self.folder, self.home)[0]
        apply_moves([(source, destination)], self.home)
        with patch("organizer.Path.home", return_value=self.home):
            with patch("builtins.input", return_value="y"):
                with patch("organizer.Path.unlink", side_effect=KeyboardInterrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        undo_cleanup()
        self.assertTrue(source.exists())
        self.assertTrue(destination.exists())
        result = self.run_command("--undo", answer="y\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(source.read_text(), "resume")
        self.assertFalse(destination.exists())

    def test_corrupt_history_stops_apply_without_moving_files(self):
        history = self.home / ".local/state/ame-organizer/history.sqlite3"
        history.parent.mkdir(parents=True)
        history.write_bytes(b"not a sqlite database")
        result = self.run_command(str(self.folder), "--apply")
        self.assertEqual(result.returncode, 1)
        self.assertIn("database", result.stderr)
        self.assertEqual(len(plan_moves(self.folder, self.home)), 5)

    def test_symlinked_history_is_rejected_without_changing_target(self):
        history = self.home / ".local/state/ame-organizer/history.sqlite3"
        history.parent.mkdir(parents=True)
        target = self.home / "unrelated.txt"
        target.write_text("keep me")
        history.symlink_to(target)
        result = self.run_command(str(self.folder), "--apply")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unsafe history file", result.stderr)
        self.assertEqual(target.read_text(), "keep me")
        self.assertEqual(len(plan_moves(self.folder, self.home)), 5)


if __name__ == "__main__":
    unittest.main()
