"""Summary
"""
import sublime
import sys
import time
import platform
from os import path
from unittest import TestCase

sys.path.append(path.dirname(path.dirname(__file__)))
from plugin.plugin_settings import Settings
from plugin.completion.bin_complete import Completer
from plugin.completion.lib_complete import Completer as CompleterLib

def has_libclang():
        if platform.system() == "Darwin":
            return True
        if platform.system() == "Linux":
            # FIXME: disable linux libclang for now
            return False
        return False

class test_complete_command(TestCase):
    """Test complete commands

    Attributes:
        view (sublime.View): view
    """
    def setUp(self):
        """Set up the file to autocomplete

        """
        file_name = path.join(path.dirname(__file__), 'test.cpp')
        self.view = sublime.active_window().open_file(file_name)
        while self.view.is_loading():
            time.sleep(0.1)
        # make sure we have a window to work with
        s = sublime.load_settings("Preferences.sublime-settings")
        s.set("close_windows_when_empty", False)

    def tearDown(self):
        """close the file. Finish test.

        """
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")

    def getRow(self, row):
        """Get text of a particular row

        Args:
            row (int): number of row

        Returns:
            str: row contents
        """
        return self.view.substr(self.view.line(self.view.text_point(row, 0)))

    def test_setup(self):
        """Test that the initial setup is valid

        """
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
        """Test that completer version is properly initialized

        """
        completer = Completer("clang++")
        self.assertIsNotNone(completer.version_str)
        print("version is: {}".format(completer.version_str))

    def test_init_lib(self):
        """Test that completer version is properly initialized

        """
        if not has_libclang():
            # we don't check libclang on platforms that lack its support
            return
        completer = CompleterLib("clang++")
        self.assertIsNotNone(completer.version_str)
        print("version is: {}".format(completer.version_str))

    def test_init_completer(self):
        """Test that completer is properly initialized

        """
        settings = Settings()
        current_folder = path.dirname(self.view.file_name())
        parent_folder = path.dirname(current_folder)
        include_dirs = settings.populate_include_dirs(
            file_current_folder=current_folder,
            file_parent_folder=parent_folder)
        completer = Completer("clang++")
        completer.init(view=self.view,
                       includes=include_dirs,
                       settings=settings)
        self.assertTrue(completer.exists_for_view(self.view.id()))

    def test_init_completer_lib(self):
        """Test that completer is properly initialized

        """
        if not has_libclang():
            return
        settings = Settings()
        current_folder = path.dirname(self.view.file_name())
        parent_folder = path.dirname(current_folder)
        include_dirs = settings.populate_include_dirs(
            file_current_folder=current_folder,
            file_parent_folder=parent_folder)
        completer = Completer("clang++")
        completer.init(view=self.view,
                       includes=include_dirs,
                       settings=settings)
        self.assertTrue(completer.exists_for_view(self.view.id()))

    def test_complete(self):
        """Test autocompletion for user type

        """
        file_name = path.join(path.dirname(__file__), 'test.cpp')
        self.view = sublime.active_window().open_file(file_name)
        while self.view.is_loading():
            time.sleep(0.1)
        # now the file should be ready
        settings = Settings()
        current_folder = path.dirname(self.view.file_name())
        parent_folder = path.dirname(current_folder)
        include_dirs = settings.populate_include_dirs(
            file_current_folder=current_folder,
            file_parent_folder=parent_folder)
        completer = Completer("clang++")
        completer.init(view=self.view,
                       includes=include_dirs,
                       settings=settings)
        self.assertTrue(completer.exists_for_view(self.view.id()))
        self.assertEqual(self.getRow(5), "  a.")
        pos = self.view.text_point(5, 4)
        current_word = self.view.substr(self.view.word(pos))
        self.assertEqual(current_word, ".\n")
        completer.complete(self.view, pos, settings.errors_on_save)
        counter = 0
        while not completer.async_completions_ready:
            time.sleep(0.1)
            counter += 1
            if counter > 20:
                break
        self.assertIsNotNone(completer.completions)
        expected = ['a\tint a', 'a']
        self.assertTrue(expected in completer.completions)

    def test_complete_lib(self):
        """Test autocompletion for user type

        """
        if not has_libclang():
            return
        file_name = path.join(path.dirname(__file__), 'test.cpp')
        self.view = sublime.active_window().open_file(file_name)
        while self.view.is_loading():
            time.sleep(0.1)
        # now the file should be ready
        settings = Settings()
        current_folder = path.dirname(self.view.file_name())
        parent_folder = path.dirname(current_folder)
        include_dirs = settings.populate_include_dirs(
            file_current_folder=current_folder,
            file_parent_folder=parent_folder)
        completer = Completer("clang++")
        completer.init(view=self.view,
                       includes=include_dirs,
                       settings=settings)
        self.assertTrue(completer.exists_for_view(self.view.id()))
        self.assertEqual(self.getRow(5), "  a.")
        pos = self.view.text_point(5, 4)
        current_word = self.view.substr(self.view.word(pos))
        self.assertEqual(current_word, ".\n")
        completer.complete(self.view, pos, settings.errors_on_save)
        counter = 0
        while not completer.async_completions_ready:
            time.sleep(0.1)
            counter += 1
            if counter > 20:
                break
        self.assertIsNotNone(completer.completions)
        expected = ['a\tint a', 'a']
        self.assertTrue(expected in completer.completions)

    def test_complete_vector(self):
        """Test completion for std::vector

        """
        file_name = path.join(path.dirname(__file__), 'test_vector.cpp')
        self.view = sublime.active_window().open_file(file_name)
        while self.view.is_loading():
            time.sleep(0.1)
        # now the file should be ready
        settings = Settings()
        current_folder = path.dirname(self.view.file_name())
        parent_folder = path.dirname(current_folder)
        include_dirs = settings.populate_include_dirs(
            file_current_folder=current_folder,
            file_parent_folder=parent_folder)
        completer = Completer("clang++")
        completer.init(view=self.view,
                       includes=include_dirs,
                       settings=settings)
        self.assertTrue(completer.exists_for_view(self.view.id()))
        self.assertEqual(self.getRow(3), "  vec.")
        pos = self.view.text_point(3, 6)
        current_word = self.view.substr(self.view.word(pos))
        self.assertEqual(current_word, ".\n")
        completer.complete(self.view, pos, settings.errors_on_save)
        counter = 0
        while not completer.async_completions_ready:
            time.sleep(0.1)
            counter += 1
            if counter > 20:
                break
        print(completer.completions[:10])
        self.assertIsNotNone(completer.completions)
        expected = ['begin\titerator begin()', 'begin()']
        self.assertTrue(expected in completer.completions)
