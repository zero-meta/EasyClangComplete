import sublime
import sys
from os import path
from unittest import TestCase

easy_clang_complete = sys.modules["EasyClangComplete"]

SublBridge = easy_clang_complete.plugin.tools.SublBridge

class test_tools(TestCase):

    def test_pkg_name(self):
        self.assertEqual(easy_clang_complete.plugin.tools.PKG_NAME, 
                         "EasyClangComplete")

