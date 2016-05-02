"""Summary

Attributes:
    log (logging.Logger): logger
"""
import sublime
import logging
import re

import os.path as path

from .tools import PKG_NAME

log = logging.getLogger(__name__)

class Settings:

    """class that encapsulates sublime settings
    
    Attributes:
        clang_binary (string): name of clang binary to be used
        complete_all (bool): flag to trigger autocompletion on every keystroke
        errors_on_save (bool): if true, show errors on save
        include_dirs (string[]): array of directories with headers
        include_file_folder (bool): if true, current location -> 'include_dirs'
        include_parent_folder (bool): if true, parent is added to 'include_dirs'
        search_clang_complete (bool): if true will search for '.clang_complete' 
                                                                file up the tree
        std_flag (string): flag of the c++ std library, e.g. -std=c++11
        subl_settings (sublime.settings): link to sublime text settings dict
        triggers (string[]): triggers that trigger autocompletion
        verbose (bool): verbose flag
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
            log.critical(" Could not load settings!")
            log.critical(" NO AUTOCOMPLETE WILL BE AVAILABLE")
            return
        if self.verbose:
            log.setLevel(logging.DEBUG)
            log.info(" settings successfully loaded")
        else:
            log.setLevel(logging.INFO)

    def on_settings_changed(self):
        """When user changes settings, trigger this.
        """
        self.load_settings()
        log.info(" settings changed and reloaded")

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

        if self.std_flag is None:
            self.std_flag = "-std=c++11"
            log.debug(" set std_flag to default: %s", self.std_flag)

    def is_valid(self):
        """Check settings validity. If any of the settings is None the settings
        are not valid.
        
        Returns:
            bool: validity of settings
        """
        if self.subl_settings is None:
            log.critical(" no subl_settings found")
            return False
        if self.verbose is None:
            log.critical(" no verbose flag found")
            return False
        if self.include_parent_folder is None:
            log.critical(" no include_parent_folder flag found")
            return False
        if self.include_file_folder is None:
            log.critical(" no include_file_folder flag found")
            return False
        if self.complete_all is None:
            log.critical(" no autocomplete_all flag found")
            return False
        if self.triggers is None:
            log.critical(" no triggers found")
            return False
        if self.include_dirs is None:
            log.critical(" no include_dirs setting found")
            return False
        if self.clang_binary is None:
            log.critical(" no clang_binary setting found")
            return False
        if self.std_flag is None:
            log.critical(" no std_flag setting found")
            return False
        if self.search_clang_complete is None:
            log.critical(" no search_clang_complete setting found")
            return False
        if self.errors_on_save is None:
            log.critical(" no errors_on_save setting found")
            return False
        return True

    def populate_include_dirs(self, project_name, project_base_folder, 
                              file_current_folder, file_parent_folder):
        """populate the include dirs based on the project
        
        
        Args:
            project_name (str): project name
            project_base_folder (str): project folder
            file_current_folder (str): current file folder
            file_parent_folder (str): file parent folder
        
        Returns:
            str[]: directories where clang searches for header files
        """
        # initialize new include_dirs
        include_dirs = list(self.include_dirs)
        log.debug(" populating include dirs with current variables:")
        log.debug(" project_base_name = %s", project_name)
        log.debug(" project_base_folder = %s", project_base_folder)
        log.debug(" file_parent_folder = %s", file_parent_folder)

        # replace project related variables to real ones
        for i, include_dir in enumerate(include_dirs):
            include_dir = re.sub(
                "(\$project_base_path)", project_base_folder, include_dir)
            include_dir = re.sub("(\$project_name)", project_name, include_dir)
            include_dir = path.abspath(include_dir)
            include_dirs[i] = include_dir

        if self.include_file_folder:
            include_dirs.append(file_current_folder)
        if self.include_parent_folder:
            include_dirs.append(file_parent_folder)

        # print resulting include dirs
        log.debug(" include_dirs = %s", include_dirs)
        return include_dirs
