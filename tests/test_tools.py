"""Test tools

Attributes:
    easy_clang_complete (module): this plugin module
    SublBridge (SublBridge): class for subl bridge
"""
import sublime
import sys
import time
from os import path
from unittest import TestCase

easy_clang_complete = sys.modules["EasyClangComplete"]

sys.path.append(path.dirname(path.dirname(__file__)))
Settings = easy_clang_complete.plugin.plugin_settings.Settings
SublBridge = easy_clang_complete.plugin.tools.SublBridge
Tools = easy_clang_complete.plugin.tools.Tools
PosStatus = easy_clang_complete.plugin.tools.PosStatus
# for testing sublime command

class test_tools_command(TestCase):
    """Test commands
    """
    def setUp(self):
        """Set up testing environment
        """
        self.view = sublime.active_window().new_file()
        # make sure we have a window to work with
        s = sublime.load_settings("Preferences.sublime-settings")
        s.set("close_windows_when_empty", False)

    def setUpView(self, filename):
        """
        Utility method to set up a view for a given file.

        Args:
            filename (str): The filename to open in a new view.
        """
        # Open the view.
        file_path = path.join(path.dirname(__file__), filename)
        self.view = sublime.active_window().open_file(file_path)

        # Ensure it's loaded.
        while self.view.is_loading():
            time.sleep(0.1)

    def tearDown(self):
        """ Cleanup method run after every test. """

        # If we have a view, close it.
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")
            self.view = None

    def setText(self, string):
        """Set text to a view

        Args:
            string (str): some string to set
        """
        self.view.run_command("insert", {"characters": string})

    def appendText(self, string, scroll_to_end=True):
        """Append text to view. Moves the cursor too.

        Args:
            string (str): text to append
            scroll_to_end (bool, optional): should we scroll to the end?
        """
        self.view.run_command("append", {"characters": string,
                                         "scroll_to_end": scroll_to_end})

    def move(self, dist, forward=True):
        """Move the cursor by distance

        Args:
            dist (int): pixels to move
            forward (bool, optional): forward or backward in the file

        """
        for _ in range(dist):
            self.view.run_command("move",
                                  {"by": "characters", "forward": forward})

    def getRow(self, row):
        """Get row text

        Args:
            row (int): number of row

        Returns:
            str: text of this row
        """
        return self.view.substr(self.view.line(self.view.text_point(row, 0)))

    def test_cursor_pos(self):
        """Test cursor position
        """
        self.setText("hello")
        (row, col) = SublBridge.cursor_pos(self.view)
        self.assertEqual(row, 1)
        self.assertEqual(col, 6)
        self.setText("\nworld!")
        (row, col) = SublBridge.cursor_pos(self.view)
        self.assertEqual(row, 2)
        self.assertEqual(col, 7)
        self.move(10, forward=False)
        (row, col) = SublBridge.cursor_pos(self.view)
        self.assertEqual(row, 1)
        self.assertEqual(col, 3)

    def test_next_line(self):
        """Test returning next line
        """
        self.setText("hello\nworld!")
        self.move(10, forward=False)
        next_line = SublBridge.next_line(self.view)
        self.assertEqual(next_line, "world!")

    def test_wrong_triggers(self):
        """ Test that we don't complete on numbers and wrong triggers. """
        self.tearDown()
        self.setUpView('test_wrong_triggers.cpp')
        # Load the completions.
        settings = Settings()

        # Check the current cursor position is completable.
        self.assertEqual(self.getRow(2), "  a > 2.")

        # check that '>' does not trigger completions
        pos = self.view.text_point(2, 5)
        current_word = self.view.substr(self.view.word(pos))
        self.assertEqual(current_word, "> ")

        status = Tools.get_position_status(pos, self.view, settings)

        # Verify that we got the expected completions back.
        self.assertEqual(status, PosStatus.WRONG_TRIGGER)

        # check that ' >' does not trigger completions
        pos = self.view.text_point(2, 4)
        current_word = self.view.substr(self.view.word(pos))
        self.assertEqual(current_word, " >")

        status = Tools.get_position_status(pos, self.view, settings)

        # Verify that we got the expected completions back.
        self.assertEqual(status, PosStatus.COMPLETION_NOT_NEEDED)

        # check that '2.' does not trigger completions
        pos = self.view.text_point(2, 8)
        current_word = self.view.substr(self.view.word(pos))
        self.assertEqual(current_word, ".\n")

        status = Tools.get_position_status(pos, self.view, settings)

        # Verify that we got the expected completions back.
        self.assertEqual(status, PosStatus.WRONG_TRIGGER)


class test_tools(TestCase):
    """Test other things
    """
    def test_pkg_name(self):
        """Test if the package name is correct
        """
        self.assertEqual(easy_clang_complete.plugin.tools.PKG_NAME,
                         "EasyClangComplete")
