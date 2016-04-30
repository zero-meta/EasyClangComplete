import sublime
import sys
from os import path
from unittest import TestCase

easy_clang_complete = sys.modules["EasyClangComplete"]

SublBridge = easy_clang_complete.plugin.tools.SublBridge

# for testing sublime command
class test_tools_command(TestCase):

    def setUp(self):
        self.view = sublime.active_window().new_file()
        # make sure we have a window to work with
        s = sublime.load_settings("Preferences.sublime-settings")
        s.set("close_windows_when_empty", False)

    def tearDown(self):
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")

    def setText(self, string):
        self.view.run_command("insert", {"characters": string})

    def appendText(self, string, scroll_to_end = True):
        self.view.run_command("append", {"characters": string, 
                              "scroll_to_end": scroll_to_end})

    def move(self, dist, forward = True):
        for i in range(dist):
          self.view.run_command("move", {"by": "characters", "forward": forward})

    def getRow(self, row):
        return self.view.substr(self.view.line(self.view.text_point(row, 0)))

    def test_cursor_pos(self):
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
        self.setText("hello\nworld!")
        self.move(10, forward=False)
        next_line = SublBridge.next_line(self.view)
        self.assertEqual(next_line, "world!")


class test_tools(TestCase):

    def test_pkg_name(self):
        self.assertEqual(easy_clang_complete.plugin.tools.PKG_NAME, 
                         "EasyClangComplete")

