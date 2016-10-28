"""This module encapsulates communication with sublime settings

Attributes:
    log (logging.Logger): logger
"""
import sublime
import logging
import re

import os.path as path

from .tools import PKG_NAME
from .tools import Tools

log = logging.getLogger(__name__)
log.debug(" reloading module")


class SettingsEnum:
    include_dirs = None
    std_flag_c = None
    std_flag_cpp = None
    search_clang_complete_file = None
    generate_flags_with_cmake = None
    cmake_flags_priority = None
    cmake_prefix_paths = None
    errors_on_save = None
    triggers = None
    use_libclang = None
    verbose = None
    include_file_folder = None
    include_file_parent_folder = None
    clang_binary = None
    autocomplete_all = None
    hide_default_completions = None
    max_tu_age = None


class Settings:

    """class that encapsulates sublime settings

    Attributes:
        clang_binary (string): name of clang binary to be used
        autocomplete_all (bool): flag to trigger completion on every keystroke
        errors_on_save (bool): if true, show errors on save
        include_dirs (string[]): array of directories with headers
        include_file_folder (bool): if true, current location -> 'include_dirs'
        include_file_parent_folder (bool): if true, parent -> 'include_dirs'
        project_base_folder (str): root folder of current project
        project_base_name (str): name of the current project
        project_specific_settings (TYPE): use project-specific settings
        search_clang_complete_file (bool): if true search for '.clang_complete'
            file up the tree
        std_flag_c (string): flag of the c std library, e.g. -std=c11
        std_flag_cpp (string): flag of the c++ std library, e.g. -std=c++11
        subl_settings (sublime.settings): link to sublime text settings dict
        triggers (string[]): triggers that trigger autocompletion
        use_libclang (bool): use libclang instead of parsing binary output
        verbose (bool): verbose flag
        cmake_flags_priority(str): priority of cmake flags. They can override
            user settings, do nothing, or ask user what to do.
        generate_flags_with_cmake(bool): generate .clang_complete file from
            CMake generated compilation database
        cmake_prefix_paths(list): some build systems need specific folders
            to be part of CMAKE_PREFIX_PATH. This sets just that.
        hide_default_completions(bool): do we hide default completions?
        max_tu_age(int): lifetime of translation units in seconds
    """
    subl_settings = None

    CMAKE_PRIORITIES = ["ask", "merge", "overwrite", "keep_old"]

    __change_listeners = []

    def __init__(self):
        """Initialize the class.
        """
        self.load_settings()
        if not self.is_valid():
            log.critical(" Could not load settings!")
            log.critical(" NO AUTOCOMPLETE WILL BE AVAILABLE")
            return

    def add_change_listener(self, listener):
        """Registers given listener to be notified whenever settings change.

        Args:
            listener (function): function to call on settings change
        """
        if listener in self.__change_listeners:
            log.error(' this settings listener was already added before')
        self.__change_listeners.append(listener)

    def on_settings_changed(self):
        """When user changes settings, trigger this.
        """
        self.load_settings()
        for listener in self.__change_listeners:
            listener()
        log.info(" settings changed and reloaded")

    def load_settings(self):
        """Load settings from sublime dictionary to internal variables
        """
        self.subl_settings = sublime.load_settings(
            PKG_NAME + ".sublime-settings")
        self.__load_vars_from_settings(self.subl_settings)

        self.subl_settings.clear_on_change(PKG_NAME)
        self.subl_settings.add_on_change(PKG_NAME, self.on_settings_changed)

        self.project_base_name = ""
        self.project_base_folder = ""
        variables = sublime.active_window().extract_variables()
        if 'folder' in variables:
            self.project_base_folder = variables['folder']
        if 'project_base_name' in variables:
            self.project_base_name = variables['project_base_name']

        # override nessesary settings from projects
        self.__update_settings_from_project_if_needed()

    def __update_settings_from_project_if_needed(self):
        """Get clang flags for the current project

        Returns:
            list(str): flags for clang, None if no project found
        """
        log.debug(" overriding settings by project ones if needed:")
        settings_handle = sublime.active_window().active_view().settings()
        self.__load_vars_from_settings(settings_handle)
        log.debug(" done.")

    def __load_vars_from_settings(self, settings_handle):
        for key, value in SettingsEnum.__dict__.items():
            if key.startswith('__') or callable(key):
                continue
            val = settings_handle.get(key)
            if val is not None:
                value = val
                # set this value to this object too
                setattr(self, key, val)
                # tell the user what we have done
                log.debug(" setting %s -> '%s'", key, val)

        # process some special settings
        if isinstance(self.max_tu_age, str):
            self.max_tu_age = Tools.seconds_from_string(self.max_tu_age)

    def __expand_include(self, include):
        """Expand include. Make sure path is ok given a specific os and add
        current project path if the include path is relative.

        Args:
            include (str): include in form -I<include>

        Returns:
            str: expanded include in form '-I "<include>"'
        """
        flag = None
        path_to_add = include[2:].rstrip()
        if path.isabs(path_to_add):
            flag = '-I "{}"'.format(path.normpath(path_to_add))
        else:
            flag = '-I "{}"'.format(
                path.join(self.project_base_folder, path_to_add))
        return flag

    def is_valid(self):
        """Check settings validity. If any of the settings is None the settings
        are not valid.

        Returns:
            bool: validity of settings
        """
        for key, value in self.__dict__.items():
            if key.startswith('__') or callable(key):
                continue
            if value is None:
                log.critical(" no setting '%s' found!", key)
                return False
        if self.cmake_flags_priority not in Settings.CMAKE_PRIORITIES:
            log.critical(" priority: '%s' is not one of allowed ones!",
                         self.cmake_flags_priority)
            return False
        return True

    def populate_include_dirs(self, view):
        """populate the include dirs based on the project

        Args:
            view (sublime.View): current view

        Returns:
            str[]: directories where clang searches for header files

        """
        # init folders needed:
        file_current_folder = path.dirname(view.file_name())
        file_parent_folder = path.dirname(file_current_folder)

        # initialize new include_dirs
        include_dirs = list(self.include_dirs)
        log.debug(" populating include dirs with current variables:")
        log.debug(" project_base_name = %s", self.project_base_name)
        log.debug(" project_base_folder = %s", self.project_base_folder)
        log.debug(" file_parent_folder = %s", file_parent_folder)

        # replace project related variables to real ones
        for i, include_dir in enumerate(include_dirs):
            include_dir = re.sub(
                r"\$project_base_path", re.escape(self.project_base_folder), include_dir)
            include_dir = re.sub(r"\$project_name",
                                 re.escape(self.project_base_name), include_dir)
            include_dir = path.abspath(include_dir)
            include_dirs[i] = include_dir

        if self.include_file_folder:
            include_dirs.append(file_current_folder)
        if self.include_file_parent_folder:
            include_dirs.append(file_parent_folder)

        # print resulting include dirs
        log.debug(" include_dirs = %s", include_dirs)
        return include_dirs
