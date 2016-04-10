"""ClangAutoComplete plugin for Sublime Text 3.

Provides completion suggestions for C/C++ languages based on clang output

Attributes:
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
import os.path as path

PKG_NAME = "ClangAutoComplete"

# try system clang python bindings
try:
    from clang.cindex import TranslationUnit
# use customized clang python bindings
except:
    from clangHelper.tools.libclang_version import get_libclang_version
    if get_libclang_version() == '32':
        from clangHelper.clang.cindex32 import TranslationUnit
    if get_libclang_version() == '33':
        from clangHelper.clang.cindex33 import TranslationUnit
    if get_libclang_version() == '34':
        from clangHelper.clang.cindex34 import TranslationUnit
    if get_libclang_version() == '35':
        from clangHelper.clang.cindex35 import TranslationUnit
    if get_libclang_version() == '36':
        from clangHelper.clang.cindex36 import TranslationUnit
    elif get_libclang_version() == '37':
        from clangHelper.clang.cindex37 import TranslationUnit
    if get_libclang_version() == '38':
        from clangHelper.clang.cindex38 import TranslationUnit
    # else:
    #     raise 'couldn\'t load any clang python bindings, plugin is disabled!'

print("loaded clang version: ", get_libclang_version())


class Settings:

    """class that encapsulates sublime settings

    Attributes:
        clang_binary (string): name of clang binary to be used
        complete_all (bool): flag to trigger autocompletion on every keystroke
        default_encoding (string): default encoding if view has none defined
        include_dirs (string[]): array of directories with headers
        include_parent_folder (bool): if true, parent will be added to 'include_dirs'
        selectors (string[]): selectors that trigger autocompletion
        std_flag (string): flag of the c++ std library, e.g. -std=c++11
        subl_settings (sublime.settings): link to sublime text settings dict
        tmp_file_path (string): name of a temp file
        verbose (bool): verbose flag
    """

    subl_settings = None

    verbose = None
    include_parent_folder = None
    complete_all = None
    default_encoding = None
    selectors = None
    include_dirs = None
    clang_binary = None
    std_flag = None

    def __init__(self):
        """Initialize the class.
        """
        self.load_settings()
        if (self.verbose):
            print(PKG_NAME + ": settings loaded")

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
            "include_parent_folder")
        self.tmp_file_path = self.subl_settings.get("tmp_file_path")
        self.default_encoding = self.subl_settings.get("default_encoding")
        self.selectors = self.subl_settings.get("selectors")
        self.include_dirs = self.subl_settings.get("include_dirs")
        self.clang_binary = self.subl_settings.get("clang_binary")
        self.std_flag = self.subl_settings.get("std_flag")

        self.subl_settings.clear_on_change(PKG_NAME)
        self.subl_settings.add_on_change(PKG_NAME, self.on_settings_changed)

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
        if self.selectors is None:
            return False
        if self.include_dirs is None:
            return False
        if self.clang_binary is None:
            return False
        if std_flag is None:
            return False
        return True


class ClangAutoComplete(sublime_plugin.EventListener):

    """Class that handles clang based auto completion

    Attributes:
        completion_regex (regex): regex to search for completions
        file_ext (regex): regex to find file extension
        settings (Settings): Custom handler for settings
        syntax_regex (regex): Regex to detect syntax
    """
    settings = None
    completers = {}

    completion_regex = re.compile("COMPLETION: ([^ ]+) : ([^\\n]+)")
    file_ext = re.compile("[^\.]+\.([^\\n]+)")
    syntax_regex = re.compile("\/([^\/]+)\.(?:tmLanguage|sublime-syntax)")

    def __init__(self):
        """Initialize the settings in the class
        """
        self.settings = Settings()

    def populate_include_dirs(self):
        """populate the include dirs based on the project

        Returns:
            string[]: directories where clang searches for header files
        """
        # initialize these to nothing in case they are not present in the
        # variables
        project_path = ""
        project_name = ""
        file_parent_folder = ""

        # initialize new include_dirs
        clang_include_dirs = self.settings.include_dirs

        # these variables should be populated by sublime text
        variables = sublime.active_window().extract_variables()
        if ('folder' in variables):
            project_path = variables['folder']
        if ('project_base_name' in variables):
            project_name = variables['project_base_name']
        if ('file' in variables):
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

        if (self.settings.include_parent_folder):
            clang_include_dirs.append(file_parent_folder)

        return clang_include_dirs

    def guess_syntax_flags(self, view):
        """Guess the syntax (C or C++) and return flags. The code tries to guess
        by the syntax variable from sublime. If this fails it tries to guess by
        extension of an active file.

        Args:
            view (sublime.View): current view

        Returns:
            string: flags for current language
        """
        syntax_flags = None
        c_flags = ""
        cpp_flags = self.settings.std_flag + " -x c++"
        if view.settings().get('syntax') is not None:
            syntax = re.findall(
                self.syntax_regex, view.settings().get('syntax'))
            if len(syntax) > 0:
                if syntax[0] == "C++":
                    syntax_flags = cpp_flags
                elif syntax[0] == "C":
                    syntax_flags = c_flags
        if syntax_flags is None and \
                view.file_name() is not None:
            file_ext = re.findall(self.file_ext, view.file_name())
            if len(file_ext) > 0 and file_ext[0] == "cpp":
                syntax_flags = cpp_flags
        if syntax_flags is None:
            syntax_flags = c_flags
        return syntax_flags

    def write_body_to_temp_file(self, body, enc):
        """We use a temp file to store the file that will be used with clang.
        This function creates this file.

        Args:
            body (string): text from current view to provide context to clang
            enc (string): encoding
        """
        if enc == "Undefined":
            enc = self.settings.default_encoding
        with open(self.settings.tmp_file_path, "w", encoding=enc) as tmp_file:
            tmp_file.write(body)

    def construct_clang_command(
            self, row, col, syntax_flags, include_dirs):
        """Construct the clang command

        Args:
            row (int): cursor line position
            col (int): cursor char position in line
            syntax_flags (string): current syntax flags
            include_dirs (string[]): a list of include directories

        Returns:
            string: clang command
        """
        # Build clang command
        clang_bin = self.settings.clang_binary
        clang_flags = "-cc1 " + syntax_flags + " -fsyntax-only"
        clang_target = "-code-completion-at " + self.settings.tmp_file_path + \
            ":"+str(row)+":"+str(col) + \
            " "+self.settings.tmp_file_path
        clang_includes = " -I ."
        for dir in self.settings.include_dirs:
            clang_includes += " -I " + dir

        # Execute clang command, exit 0 to suppress error from
        # check_output()
        clang_cmd = clang_bin + " " + clang_flags + \
            " " + clang_target + clang_includes
        if (self.settings.verbose):
            print(PKG_NAME + ": clang command: \n\t{}".format(clang_cmd))
        return clang_cmd

    def run_clang_subprocess(self, clang_cmd):
        """Run a subprocess for generating clang completions

        Args:
            clang_cmd (string): clang command

        Returns:
            string: Raw command output
        """
        try:
            output = subprocess.check_output(clang_cmd, shell=True)
            print(output)
            output_text = ''.join(map(chr, output))
        except subprocess.CalledProcessError as e:
            output_text = e.output.decode("utf-8")
        return output_text

    def parse_clang_output(self, raw_clang_output):
        """Parse clang command output

        Args:
            raw_clang_output (string): output of the clang command

        Returns:
            string[]: completions
        """
        output_lines = raw_clang_output.splitlines()
        completions = []
        longest_len = 0
        for line in output_lines:
            tmp_res = re.findall(self.completion_regex, line)
            if len(tmp_res) <= 0:
                continue
            if len(tmp_res[0][0]) > longest_len:
                longest_len = len(tmp_res[0][0])
            completions.append([tmp_res[0][1], tmp_res[0][0]])

        for tuple in completions:
            tuple[0] = tuple[1].ljust(longest_len) + " - " + tuple[0]
        return completions

    def valid_selector_in_focus(self, body, pos):
        """Check if the cursor focuses valid selector

        Args:
            body (string): body in focus
            pos (int): position of the cursor

        Returns:
            bool: selector is valid
        """
        if self.settings.complete_all:
            return True

        selector_is_valid = False
        for selector in self.settings.selectors:
            if selector in body[pos-len(selector):pos]:
                selector_is_valid = True
        return selector_is_valid

    def init_completer(self, view):
        # init settings if they were not initialized still
        if (self.settings is None) or (self.settings.is_valid() is False):
            self.settings = Settings()

        if (self.settings.verbose):
            print(PKG_NAME, ": loading file name: ", view.file_name())

        body = view.substr(sublime.Region(0, view.size()))
        files = [(view.file_name(), body)]

        # init needed variables from settings
        clang_include_dirs = self.populate_include_dirs()
        clang_includes = []
        for include in clang_include_dirs:
            clang_includes.append("-I" + include)

        self.completers[view.id()] = TranslationUnit.from_source(
            view.file_name(),
            [self.settings.std_flag] + clang_includes,
            unsaved_files=files,
            options=TranslationUnit.PARSE_PRECOMPILED_PREAMBLE |
            TranslationUnit.PARSE_CACHE_COMPLETION_RESULTS)

    def on_post_save_async(self, view):
        print("saved id: ", view.id())
        self.init_completer(view)

    def on_load_async(self, view):
        print("loaded id: ", view.id())
        self.init_completer(view)

    def on_query_completions(self, view, prefix, locations):
        """Function that is called when user queries completions in the code

        Args:
            view (sublime.View): current view
            prefix (TYPE): Description
            locations (TYPE): Description

        Returns:
            sublime.Completions: completions with a flag
        """

        # init settings if they were not initialized still
        if (self.settings is None) or (self.settings.is_valid() is False):
            self.settings = Settings()

        # init needed variables from settings
        clang_include_dirs = self.populate_include_dirs()

        # Find exact Line:Column position of cursor for clang
        pos = view.sel()[0].begin()
        body = view.substr(sublime.Region(0, view.size()))

        # Verify that character under the cursor is one allowed selector
        if (not self.valid_selector_in_focus(body, pos)):
            return None

        row = body[:pos].count('\n') + 1
        col = pos-body.rfind("\n", 0, len(body[:pos]))

        # Create temporary file name that reflects what user is currently
        # typing
        # self.write_body_to_temp_file(body, view.encoding())

        # Find language used (C vs C++) based first on
        # sublime's syntax settings (supporting "C" and "C++").
        # If we do not recognize the current settings, try to
        # decide based on file extension.
        # syntax_flags = self.guess_syntax_flags(view)

        # # Build clang command
        # clang_cmd = self.construct_clang_command(
        #     row, col, syntax_flags, clang_include_dirs)

        current_file_name = view.file_name()
        files = [(current_file_name, body)]

        # execute clang code completion
        start = time.time()
        cr = self.completers[view.id()].codeComplete(
            current_file_name,
            row, col,
            unsaved_files=files)
        if cr is None or len(cr.results) == 0:
            print("no completions")
            return None
        end = time.time()
        print("time to call clang: ", end - start)

        start = time.time()
        # build code completions
        completions = []
        for c in cr.results:
            hint = ''
            contents = ''
            place_holders = 1
            for chunk in c.string:
                if chunk.isKindTypedText():
                    trigger = chunk.spelling
                hint += chunk.spelling
                if chunk.isKindResultType():
                    hint += ' '
                    continue
                if chunk.isKindPlaceHolder():
                    contents += ('${' + str(place_holders) + ':' +
                                 chunk.spelling + '}')
                    place_holders += 1
                else:
                    contents += chunk.spelling
            completions.append([trigger + "\t" + hint, contents])

        # # Execute clang command, exit 0 to suppress error from check_output()
        # raw_clang_output = self.run_clang_subprocess(clang_cmd)

        end = time.time()
        print("time to show: ", end - start)

        # Process clang output, find COMPLETION lines and return them with a
        # little formating
        # completions = self.parse_clang_output(raw_clang_output)
        return (completions, sublime.INHIBIT_WORD_COMPLETIONS)
