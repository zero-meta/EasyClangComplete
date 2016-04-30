import sublime
import re

import os.path as path

from .tools import PKG_NAME

class Settings:

    """class that encapsulates sublime settings

    Attributes:
        clang_binary (string): name of clang binary to be used
        complete_all (bool): flag to trigger autocompletion on every keystroke
        errors_on_save (TYPE): Description
        include_dirs (string[]): array of directories with headers
        include_parent_folder (bool): if true, parent is added to 'include_dirs'
        search_clang_complete (TYPE): Description
        std_flag (string): flag of the c++ std library, e.g. -std=c++11
        subl_settings (sublime.settings): link to sublime text settings dict
        translation_unit_module (cindex.translation_unit): translation unit that 
                                                          handles autocompletion
        triggers (string[]): triggers that trigger autocompletion
        verbose (bool): verbose flag

    Deleted Attributes:
        tmp_file_path (string): name of a temp file
    """

    subl_settings = None

    verbose = None
    include_file_folder = None
    include_parent_folder = None
    complete_all = None
    triggers = None
    include_dirs = None
    clang_binary = None
    std_flag = None
    search_clang_complete = None
    errors_on_save = None

    def __init__(self):
        """Initialize the class.
        """
        self.load_settings()
        if not self.is_valid():
            print(PKG_NAME + ": Error encountered while loading settings.")
            print(PKG_NAME + ": NO AUTOCOMPLETION WILL BE AVAILABLE.")
            return
        if self.verbose:
            print(PKG_NAME + ": settings successfully loaded")

    def on_settings_changed(self):
        """When user changes settings, trigger this.
        """
        self.load_settings()
        if (self.verbose):
            print(PKG_NAME + ": settings changed and reloaded")

    def load_settings(self):
        """Load settings from sublime dictionary to internal variables
        """
        self.subl_settings = sublime.load_settings(
            PKG_NAME + ".sublime-settings")
        self.verbose = self.subl_settings.get("verbose")
        self.complete_all = self.subl_settings.get("autocomplete_all")
        self.include_parent_folder = self.subl_settings.get(
            "include_file_parent_folder")
        self.include_file_folder = self.subl_settings.get("include_file_folder")
        self.triggers = self.subl_settings.get("triggers")
        self.include_dirs = self.subl_settings.get("include_dirs")
        self.clang_binary = self.subl_settings.get("clang_binary")
        self.errors_on_save = self.subl_settings.get("errors_on_save")
        self.std_flag = self.subl_settings.get("std_flag")
        self.search_clang_complete = self.subl_settings.get(
            "search_clang_complete_file")

        self.subl_settings.clear_on_change(PKG_NAME)
        self.subl_settings.add_on_change(PKG_NAME, self.on_settings_changed)

        if (self.std_flag is None):
            self.std_flag = "-std=c++11"
            if (self.verbose):
                print(PKG_NAME + ": set std_flag to default: '{}'".format(
                    self.std_flag))

    def is_valid(self):
        """Check settings validity. If any of the settings is None the settings
        are not valid.

        Returns:
            bool: validity of settings
        """
        if self.subl_settings is None:
            print(PKG_NAME + ":ERROR: no sublime settings found")
            return False
        if self.verbose is None:
            print(PKG_NAME + ":ERROR: no verbose flag found")
            return False
        if self.include_parent_folder is None:
            print(PKG_NAME + ":ERROR: no include_parent_folder flag found")
            return False
        if self.include_file_folder is None:
            print(PKG_NAME + ":ERROR: no include_file_folder flag found")
            return False
        if self.complete_all is None:
            print(PKG_NAME + ":ERROR: no autocomplete_all flag found")
            return False
        if self.triggers is None:
            print(PKG_NAME + ":ERROR: no triggers setting found")
            return False
        if self.include_dirs is None:
            print(PKG_NAME + ":ERROR: no include_dirs found")
            return False
        if self.clang_binary is None:
            print(PKG_NAME + ":ERROR: no clang_binary setting found")
            return False
        if self.std_flag is None:
            print(PKG_NAME + ":ERROR: no std_flag setting found")
            return False
        if self.search_clang_complete is None:
            print(PKG_NAME + ":ERROR: no search_clang_complete setting found")
            return False
        if self.errors_on_save is None:
            print(PKG_NAME + ":ERROR: no errors_on_save setting found")
            return False
        return True

    def populate_include_dirs(self, project_name, project_base_folder, 
                              file_current_folder, file_parent_folder):
        """populate the include dirs based on the project

        Returns:
            str[]: directories where clang searches for header files
        """

        # initialize new include_dirs
        include_dirs = self.include_dirs

        if self.verbose:
            print(PKG_NAME + ": project_base_name = {}".format(project_name))
            print(PKG_NAME + ": project_base_folder = {}".format(
                project_base_folder))
            print(PKG_NAME + ": file_parent_folder = {}".format(
                file_parent_folder))

        # replace project related variables to real ones
        for i, include_dir in enumerate(include_dirs):
            include_dir = re.sub(
                "(\$project_base_path)", project_base_folder, include_dir)
            include_dir = re.sub("(\$project_name)", project_name, include_dir)
            include_dir = os.path.abspath(include_dir)
            include_dirs[i] = include_dir

        if self.include_file_folder:
            include_dirs.append(file_current_folder)
        if self.include_parent_folder:
            include_dirs.append(file_parent_folder)

        # print resulting include dirs
        if self.verbose:
            print("{}: include_dirs from settings: {}".format(
                PKG_NAME, include_dirs))
        return include_dirs
