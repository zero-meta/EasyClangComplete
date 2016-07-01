"""Tests for autocompletion
"""
import sublime
import sys
import time
import platform
from os import path
from unittest import TestCase

sys.path.append(path.dirname(path.dirname(__file__)))
from plugin.plugin_settings import Settings
from plugin.completion.bin_complete import Completer as CompleterBin
from plugin.completion.lib_complete import Completer as CompleterLib
from plugin.tools import PKG_NAME

def has_libclang():
    """
    Ensure libclang tests will run only on platforms that support this.

    Returns:
        str: row contents
    """
    if platform.system() == "Darwin":
        return True
    if platform.system() == "Linux":
        return True
    return False

class base_test_complete(object):
    """
    Base class for all tests that are independent of the Completer implementation.

    Attributes:
        view (sublime.View): view
        Completer (type): Completer class to use
    """
    def setUp(self):
        """ Setup method run before every test. """

        # Ensure we have a window to work with.
        s = sublime.load_settings("Preferences.sublime-settings")
        s.set("close_windows_when_empty", False)
        s = sublime.load_settings(PKG_NAME + ".sublime-settings")
        s.set("verbose", True)

        self.view = None

    def tearDown(self):
        """ Cleanup method run after every test. """

        # If we have a view, close it.
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")
            self.view = None

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

    def setUpCompleter(self):
        """
        Utility method to set up a completer for the current view.

        Returns:
            BaseCompleter: completer for the current view.
        """

        settings = Settings()

        clang_binary = settings.clang_binary
        completer = self.Completer(clang_binary)
        completer.init(
            view=self.view,
            settings=settings)

        return completer

    def getRow(self, row):
        """
        Get text of a particular row

        Args:
            row (int): number of row

        Returns:
            str: row contents
        """
        return self.view.substr(self.view.line(self.view.text_point(row, 0)))

    def test_setup_view(self):
        """ Test that setup view correctly sets up the view. """
        self.setUpView('test.cpp')

        file_name = path.join(path.dirname(__file__), 'test.cpp')
        self.assertEqual(self.view.file_name(), file_name)
        file = open(file_name, 'r')
        row = 0
        line = file.readline()
        while line:
            self.assertEqual(line[:-1], self.getRow(row))
            row += 1
            line = file.readline()
        file.close()

    def test_init(self):
        """ Test that the completer is properly initialized. """
        self.setUpView('test.cpp')
        completer = self.setUpCompleter()

        self.assertTrue(completer.exists_for_view(self.view.buffer_id()))
        self.assertIsNotNone(completer.version_str)

    def test_complete(self):
        """ Test autocompletion for user type. """
        self.setUpView('test.cpp')

        completer = self.setUpCompleter()
        self.assertTrue(completer.exists_for_view(self.view.buffer_id()))

        # Check the current cursor position is completable.
        self.assertEqual(self.getRow(5), "  a.")
        pos = self.view.text_point(5, 4)
        current_word = self.view.substr(self.view.word(pos))
        self.assertEqual(current_word, ".\n")

        # Load the completions.
        settings = Settings()
        completer.complete(self.view, pos, settings.errors_on_save)

        # Wait 2 seconds for them to load.
        counter = 0
        while not completer.async_completions_ready:
            time.sleep(0.1)
            counter += 1
            if counter > 20:
                self.fail("Async completions not ready after %d tries" % counter)

        # Verify that we got the expected completions back.
        self.assertIsNotNone(completer.completions)
        expected = ['a\tint a', 'a']
        self.assertIn(expected, completer.completions)

    def test_complete_vector(self):
        """ Test that we can complete vector members. """
        self.setUpView('test_vector.cpp')

        completer = self.setUpCompleter()
        self.assertTrue(completer.exists_for_view(self.view.buffer_id()))

        # Check the current cursor position is completable.
        self.assertEqual(self.getRow(3), "  vec.")
        pos = self.view.text_point(3, 6)
        current_word = self.view.substr(self.view.word(pos))
        self.assertEqual(current_word, ".\n")

        # Load the completions.
        settings = Settings()
        completer.complete(self.view, pos, settings.errors_on_save)

        # Wait 2 seconds for them to load.
        counter = 0
        while not completer.async_completions_ready:
            time.sleep(0.1)
            counter += 1
            if counter > 20:
                self.fail("Async completions not ready after %d tries" % counter)

        # Verify that we got the expected completions back.
        self.assertIsNotNone(completer.completions)
        expected = ['begin\titerator begin()', 'begin()']
        self.assertIn(expected, completer.completions)

    def test_unsaved_views(self):
        """ Test that we gracefully handle unsaved views. """
        # Construct an unsaved scratch view.
        self.view = sublime.active_window().new_file()
        self.view.set_scratch(True)

        # Manually set up a completer.
        settings = Settings()
        clang_binary = settings.clang_binary
        completer = self.Completer(clang_binary)
        completer.init(
            view=self.view,
            settings=settings)

        # Verify that the completer ignores the scratch view.
        self.assertFalse(completer.exists_for_view(self.view.buffer_id()))

# Define the actual test class implementations.
class test_bin_complete(base_test_complete, TestCase):
    """ Test class for the binary based completer. """
    Completer = CompleterBin

if has_libclang():
    class test_lib_complete(base_test_complete, TestCase):
        """ Test class for the library based completer. """
        Completer = CompleterLib
