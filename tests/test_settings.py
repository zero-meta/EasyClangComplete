import sublime
import sys
from os import path
from unittest import TestCase
import logging

sys.path.append(path.dirname(path.dirname(__file__)))
from plugin.plugin_settings import Settings

class test_settings(TestCase):

    def test_init(self):
        settings = Settings()
        self.assertIsNotNone(settings.subl_settings)

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
        settings = Settings()
        self.assertTrue(settings.is_valid())

    def test_populate_includes(self):
        settings = Settings()
        self.assertTrue(settings.is_valid())
        settings.include_file_folder = True
        settings.include_parent_folder = True
        project_name = "PROJECT"

        settings.include_dirs = [
            path.realpath("$project_name/src"),
            path.realpath("/test/test")
        ]
        initial_dirs = list(settings.include_dirs)
        dirs = settings.populate_include_dirs(project_name, "", 
                                       path.realpath(__file__), 
                                       path.abspath(path.curdir))
        self.assertLess(len(initial_dirs), len(dirs))
        self.assertEqual(dirs[0], path.abspath(project_name+"/src"))
        self.assertEqual(dirs[1], initial_dirs[1])
        self.assertEqual(dirs[2], path.realpath(__file__))
        self.assertEqual(dirs[3], path.abspath(path.dirname(path.curdir)))



