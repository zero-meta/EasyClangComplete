"""EasyClangComplete plugin for Sublime Text 3.

Provides completion suggestions for C/C++ languages based on clang output

Attributes:
    cindex_dict (dict): names for cindex files with keys being clang versions
    PKG_NAME (string): Name of the package
"""

import sublime
import sublime_plugin
import os
import ntpath
import subprocess
import codecs
import re
import tempfile
import time
import importlib
import sys
import os.path as path

from threading import Thread

PKG_NAME = path.splitext(path.basename(__file__))[0]

cindex_dict = {
    '3.2': PKG_NAME + ".clang.cindex32",
    '3.3': PKG_NAME + ".clang.cindex33",
    '3.4': PKG_NAME + ".clang.cindex34",
    '3.5': PKG_NAME + ".clang.cindex35",
    '3.6': PKG_NAME + ".clang.cindex36",
    '3.7': PKG_NAME + ".clang.cindex37",
    '3.8': PKG_NAME + ".clang.cindex38",
}


class Settings:

    """class that encapsulates sublime settings

    Attributes:
        clang_binary (string): name of clang binary to be used
        complete_all (bool): flag to trigger autocompletion on every keystroke
        default_encoding (string): default encoding if view has none defined
        include_dirs (string[]): array of directories with headers
        include_parent_folder (bool): if true, parent will be added to 'include_dirs'
        std_flag (string): flag of the c++ std library, e.g. -std=c++11
        subl_settings (sublime.settings): link to sublime text settings dict
        tmp_file_path (string): name of a temp file
        translation_unit_module (cindex.translation_unit): translation unit that 
                                                          handles autocompletion
        triggers (string[]): triggers that trigger autocompletion
        verbose (bool): verbose flag
    """

    subl_settings = None

    verbose = None
    include_parent_folder = None
    complete_all = None
    default_encoding = None
    triggers = None
    include_dirs = None
    clang_binary = None
    std_flag = None
    translation_unit_module = None

    def __init__(self):
        """Initialize the class.
        """
        self.load_settings()
        if (not self.translation_unit_module):
            print(PKG_NAME + ": Error encountered while loading settings.")
            print(PKG_NAME + ": NO AUTOCOMPLETION WILL BE AVAILABLE.")
            return
        if (self.verbose):
            print(PKG_NAME + ": settings successfully loaded")

    def load_correct_clang_version(self, clang_binary):
        """Summary

        Args:
            clang_binary (str): name of the clang binary to use

        """
        if not clang_binary:
            if (self.verbose):
                print(PKG_NAME + ": clang binary not defined")
            return
        check_version_cmd = clang_binary + " --version"
        try:
            output = subprocess.check_output(check_version_cmd, shell=True)
            output_text = ''.join(map(chr, output))
        except subprocess.CalledProcessError as e:
            print(PKG_NAME + ": {}".format(e))
            self.clang_binary = None
            print(PKG_NAME + ": ERROR: make sure '{}' is in PATH."
                  .format(clang_binary))
            return

        version_regex = re.compile("\d.\d")
        found = version_regex.search(output_text)
        version_str = found.group()

        if (self.verbose):
            print(PKG_NAME + ": found a cindex for clang v: " + version_str)
        if (version_str in cindex_dict):
            cindex = importlib.import_module(cindex_dict[version_str])
            self.translation_unit_module = cindex.TranslationUnit

    def on_settings_changed(self):
        """When user changes settings, trigger this.
        """
        self.load_settings()
        if (self.verbose):
            print(PKG_NAME + ": settings changed and reloaded")

    def load_settings(self):
        """Load settings from sublime dictionary to internal variables
        """
        self.translation_unit_module = None
        self.subl_settings = sublime.load_settings(
            PKG_NAME + ".sublime-settings")
        self.verbose = self.subl_settings.get("verbose")
        self.complete_all = self.subl_settings.get("autocomplete_all")
        self.include_parent_folder = self.subl_settings.get(
            "include_parent_folder")
        self.tmp_file_path = self.subl_settings.get("tmp_file_path")
        self.default_encoding = self.subl_settings.get("default_encoding")
        self.triggers = self.subl_settings.get("triggers")
        self.include_dirs = self.subl_settings.get("include_dirs")
        self.clang_binary = self.subl_settings.get("clang_binary")
        self.std_flag = self.subl_settings.get("std_flag")

        self.subl_settings.clear_on_change(PKG_NAME)
        self.subl_settings.add_on_change(PKG_NAME, self.on_settings_changed)

        self.load_correct_clang_version(self.clang_binary)

        if self.tmp_file_path is None:
            self.tmp_file_path = path.join(
                tempfile.gettempdir(), "auto_complete_tmp")

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
        if self.translation_unit_module is None:
            return False
        if self.subl_settings is None:
            return False
        if self.verbose is None:
            return False
        if self.include_parent_folder is None:
            return False
        if self.complete_all is None:
            return False
        if self.default_encoding is None:
            return False
        if self.triggers is None:
            return False
        if self.include_dirs is None:
            return False
        if self.clang_binary is None:
            return False
        if std_flag is None:
            return False
        return True


class EasyClangComplete(sublime_plugin.EventListener):

    """Class that handles clang based auto completion

    Attributes:
        async_completions_ready (bool): flag that shows if there are 
            completions available from an autocomplete async call
        completions (list): list of completions
        settings (Settings): Custom handler for settings
        syntax_regex (regex): Regex to detect syntax
        translation_units (dict): dict of translation_units
        valid_extensions (list): list of valid extentions for autocompletion
    """
    settings = None
    translation_units = {}
    # TODO: this should be probably in settings
    valid_extensions = [".c", ".cpp", ".cxx", ".h", ".hpp", ".hxx"]

    async_completions_ready = False
    completions = []

    def __init__(self):
        """Initialize the settings in the class
        """
        self.settings = Settings()

    def populate_include_dirs(self):
        """populate the include dirs based on the project

        Returns:
            str[]: directories where clang searches for header files
        """
        # initialize these to nothing in case they are not present in the
        # variables
        project_path = ""
        project_name = ""
        file_parent_folder = ""
        file_current_folder = ""

        # initialize new include_dirs
        clang_include_dirs = self.settings.include_dirs

        # these variables should be populated by sublime text
        variables = sublime.active_window().extract_variables()
        if ('folder' in variables):
            project_path = variables['folder']
        if ('project_base_name' in variables):
            project_name = variables['project_base_name']
        if ('file' in variables):
            file_current_folder = path.dirname(variables['file'])
            file_parent_folder = path.join(
                path.dirname(variables['file']), "..")

        if (self.settings.verbose):
            print(PKG_NAME + ": project_base_name = {}".format(project_name))
            print(PKG_NAME + ": folder = {}".format(project_path))
            print(PKG_NAME + ": file_parent_folder = {}".format(
                file_parent_folder))
            print(PKG_NAME + ": std_flag = {}".format(self.settings.std_flag))

        # replace project related variables to real ones
        for i, include_dir in enumerate(clang_include_dirs):
            include_dir = re.sub(
                "(\$project_base_path)", project_path, include_dir)
            include_dir = re.sub("(\$project_name)", project_name, include_dir)
            include_dir = os.path.abspath(include_dir)
            clang_include_dirs[i] = include_dir

        clang_include_dirs.append(file_current_folder)
        if (self.settings.include_parent_folder):
            clang_include_dirs.append(file_parent_folder)

        return clang_include_dirs

    def has_valid_extension(self, view):
        """Test if the current file has a valid extension

        Args:
            view (sublime.View): current view

        Returns:
            bool: extension is valid
        """
        if (not view or not view.file_name()):
            return False
        (filname, ext) = os.path.splitext(view.file_name())
        if (ext in self.valid_extensions):
            if (self.settings.verbose):
                print(PKG_NAME + ": extension ", ext, "is valid.")
            return True
        if (self.settings.verbose):
            print(PKG_NAME + ": extension ", ext, "is not valid.")
        return False

    def needs_autocompletion(self, point, view):
        """Check if the cursor focuses a valid trigger

        Args:
            point (int): position of the cursor in the file as defined by subl
            view (sublime.View): current view

        Returns:
            bool: trigger is valid
        """
        if self.settings.complete_all:
            return True

        trigger_length = 1

        current_char = view.substr(point - trigger_length)

        if (current_char == '>'):
            trigger_length = 2
            if (view.substr(point - trigger_length) != '-'):
                return False
        if (current_char == ':'):
            trigger_length = 2
            if (view.substr(point - trigger_length) != ':'):
                return False

        word_on_the_left = view.substr(view.word(point - trigger_length))
        if (word_on_the_left.isdigit()):
            # don't autocomplete digits
            return False

        for trigger in self.settings.triggers:
            if current_char in trigger:
                return True
        return False

    def init_completer(self, view):
        """Initialize the completer

        Args:
            view (TYPE): Description

        Returns:
            TYPE: Description
        """
        # init settings if they were not initialized still
        if (self.settings is None) or (self.settings.is_valid() is False):
            self.settings = Settings()

        if (self.settings.verbose):
            print(PKG_NAME + ": loading file name: ", view.file_name())

        body = view.substr(sublime.Region(0, view.size()))
        files = [(view.file_name(), body)]

        # init needed variables from settings
        clang_include_dirs = self.populate_include_dirs()
        clang_includes = []
        for include in clang_include_dirs:
            clang_includes.append("-I" + include)

        try:
            tu = self.settings.translation_unit_module
            self.translation_units[view.id()] = tu.from_source(
                view.file_name(),
                [self.settings.std_flag] + clang_includes,
                unsaved_files=files,
                options=tu.PARSE_PRECOMPILED_PREAMBLE |
                tu.PARSE_CACHE_COMPLETION_RESULTS)
        except Exception as e:
            print(PKG_NAME+":", e)
        if (self.settings.verbose):
            print(PKG_NAME + ": compilation done.")

    def on_activated_async(self, view):
        """When view becomes active, create a translation unit for it if it 
        doesn't already have one

        Args:
            view (sublime.View): current view

        """
        if self.has_valid_extension(view):
            if view.id() in self.translation_units:
                if self.settings.verbose:
                    print(PKG_NAME + ": view already has a completer")
                return
            self.init_completer(view)

    def on_post_save_async(self, view):
        """On save we want to reparse the tu

        Args:
            view (sublime.View): current view

        """
        if self.has_valid_extension(view):
            if view.id() in self.translation_units:
                self.translation_units[view.id()].reparse()
                if self.settings.verbose:
                    print(PKG_NAME + ": reparsed translation unit")
                return
            # if there is none - generate a new one
            self.init_completer(view)

        # # at some point we will show errors reported by clang
        # if view.id() in self.translation_units:
        #     tu = self.translation_units[view.id()]
        #     print(len(tu.diagnostics))
        #     for diag in tu.diagnostics:
        #         print(diag.severity)
        #         print(diag.location)
        #         print(diag.spelling)
        #         print(diag.option)

    def on_close(self, view):
        """Remove the translation unit when view is closed

        Args:
            view (sublime.View): current view

        """
        if view.id() in self.translation_units:
            if self.settings.verbose:
                print("{}: removing translation unit for view: {}".format(
                      PKG_NAME, view.id()))
            del self.translation_units[view.id()]

    def process_completions(self, complete_results):
        """Create snippet-like structures from a list of completions

        Args:
            complete_results (list): raw completions list

        Returns:
            list: updated completions
        """
        completions = []
        for c in complete_results.results:
            hint = ''
            contents = ''
            place_holders = 1
            for chunk in c.string:
                hint += chunk.spelling
                if chunk.isKindTypedText():
                    trigger = chunk.spelling
                if chunk.isKindResultType():
                    hint += ' '
                    continue
                if chunk.isKindOptional():
                    continue
                if chunk.isKindInformative():
                    continue
                if chunk.isKindPlaceHolder():
                    contents += ('${' + str(place_holders) + ':' +
                                 chunk.spelling + '}')
                    place_holders += 1
                else:
                    contents += chunk.spelling
            completions.append([trigger + "\t" + hint, contents])
        return completions

    def reload_completions(self, view):
        """Ask sublime to reload the completions. Needed to update the active 
        completion list when async autocompletion task has finished.

        Args:
            view (sublime.View): current_view

        """
        view.run_command('hide_auto_complete')
        view.run_command('auto_complete', {
            'disable_auto_insert': True,
            'api_completions_only': True,
            'next_competion_if_showing': True, })

    def complete(self, view, cursor_pos):
        """This function is called asynchronously to create a list of
        autocompletions. Using the current translation unit it queries libclang
        about the possible completions.

        Args:
            view (sublime.View): current view
            cursor_pos (int): sublime provided poistion of the cursor

        """
        # init settings if they were not initialized yet
        if (self.settings is None) or (self.settings.is_valid() is False):
            self.settings = Settings()

        # init needed variables from settings
        clang_include_dirs = self.populate_include_dirs()

        (row, col) = view.rowcol(cursor_pos)
        row += 1
        col += 1

        current_file_name = view.file_name()
        file_contents = view.substr(sublime.Region(0, view.size()))
        files = [(current_file_name, file_contents)]

        # compile if there is not tranlation unit for this view yet
        if not view.id() in self.translation_units:
            return None
        # execute clang code completion
        complete_results = self.translation_units[view.id()].codeComplete(
            current_file_name,
            row, col,
            unsaved_files=files)
        if complete_results is None or len(complete_results.results) == 0:
            print("no completions")
            return None

        self.completions = self.process_completions(complete_results)
        self.async_completions_ready = True
        self.reload_completions(view)

    def on_query_completions(self, view, prefix, locations):
        """Function that is called when user queries completions in the code

        Args:
            view (sublime.View): current view
            prefix (TYPE): Description
            locations (list[int]): positions of the cursor. 
                                   Only locations[0] is considered here.

        Returns:
            sublime.Completions: completions with a flag
        """
        if view.is_scratch():
            return None

        if not self.has_valid_extension(view):
            return None

        if self.async_completions_ready:
            self.async_completions_ready = False
            return (self.completions, sublime.INHIBIT_WORD_COMPLETIONS)

        # Verify that character under the cursor is one allowed trigger
        if (not self.needs_autocompletion(locations[0], view)):
            # send empty completion and forbid to show other things
            completions = []
            return (completions, sublime.INHIBIT_WORD_COMPLETIONS)

        if self.settings.verbose:
            print("{}: starting async auto_complete at pos: {}".format(
                PKG_NAME, locations[0]))
        # create a daemon thread to update the completions
        completion_thread = Thread(
            target=self.complete, args=[view, locations[0]])
        completion_thread.deamon = True
        completion_thread.start()

        # remove all completions for now
        completions = []
        return (completions, sublime.INHIBIT_WORD_COMPLETIONS)
