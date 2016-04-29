import sublime
import sys
from unittest import TestCase

easy_clang_complete = sys.modules["EasyClangComplete.EasyClangComplete"]

class test_settings(TestCase):

    def test_init(self):
        settings = easy_clang_complete.Settings()
        self.assertIsNotNone(settings.subl_settings)
        self.assertIsNotNone(settings.translation_unit_module)

        self.assertIsNotNone(settings.verbose)
        self.assertIsNotNone(settings.include_parent_folder)
        self.assertIsNotNone(settings.triggers)
        self.assertIsNotNone(settings.include_dirs)
        self.assertIsNotNone(settings.clang_binary)
        self.assertIsNotNone(settings.std_flag)
        self.assertIsNotNone(settings.search_clang_complete)
        self.assertIsNotNone(settings.errors_on_save)

    def test_valid(self):
        settings = easy_clang_complete.Settings()
        self.assertTrue(settings.is_valid())
