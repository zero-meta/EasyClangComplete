"""Tests for settings
"""
import sublime
import sys
import time
from os import path
from unittest import TestCase
sys.path.append(path.dirname(path.dirname(__file__)))

from plugin.plugin_settings import Settings


class test_settings(TestCase):
    """Tests for settings
    """
    def setUp(self):
        """Set up testing environment
        """
        self.view = None
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

    def test_init(self):
        """Test that settings are correctly initialized

        """
        settings = Settings()
        self.assertIsNotNone(settings.subl_settings)
        # test other settings
        self.assertIsNotNone(settings.verbose)
        self.assertIsNotNone(settings.include_file_folder)
        self.assertIsNotNone(settings.include_parent_folder)
        self.assertIsNotNone(settings.triggers)
        self.assertIsNotNone(settings.include_dirs)
        self.assertIsNotNone(settings.clang_binary)
        self.assertIsNotNone(settings.std_flag)
        self.assertIsNotNone(settings.search_clang_complete)
        self.assertIsNotNone(settings.errors_on_save)

    def test_valid(self):
        """Test validity

        """
        settings = Settings()
        self.assertTrue(settings.is_valid())

    def test_populate_includes(self):
        """Testing include population
        """
        # open any existing file
        self.tearDown()
        self.setUpView('test_wrong_triggers.cpp')
        # now test the things
        settings = Settings()
        self.assertTrue(settings.is_valid())
        settings.include_file_folder = True
        settings.include_parent_folder = True
        settings.include_dirs = [
            path.realpath("/$project_name/src"),
            path.realpath("/test/test")
        ]
        initial_dirs = list(settings.include_dirs)
        dirs = settings.populate_include_dirs(self.view)

        current_folder = path.dirname(self.view.file_name())
        parent_folder = path.dirname(current_folder)
        self.assertLess(len(initial_dirs), len(dirs))
        self.assertNotEqual(dirs[0], initial_dirs[0])
        self.assertEqual(dirs[1], initial_dirs[1])
        self.assertEqual(dirs[2], current_folder)
        self.assertEqual(dirs[3], parent_folder)
