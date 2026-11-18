import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from organizer import apply_moves, plan_moves


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
            "photo.JPG": "Pictures/photo.JPG",
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
            apply_moves([(source, destination)])
        self.assertEqual(source.read_text(), self.samples[source.name])
        self.assertEqual(destination.read_text(), "arrived after preview")

    def test_apply_rejects_changed_destination_symlink(self):
        moves = plan_moves(self.folder, self.home)
        (self.home / "Documents/jobs").symlink_to(self.folder)
        with self.assertRaisesRegex(ValueError, "Unsafe destination"):
            apply_moves(moves)
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
            "ordinary_photo.png": "Pictures",
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
                          self.home / "Pictures/Screenshots/photo.JPG")])
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


if __name__ == "__main__":
    unittest.main()
