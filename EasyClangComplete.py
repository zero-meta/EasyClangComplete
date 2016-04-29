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
    translation_unit_module = None

    subl_settings = None

    verbose = None
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
        if not self.translation_unit_module:
            print(PKG_NAME + ": Error encountered while loading settings.")
            print(PKG_NAME + ": NO AUTOCOMPLETION WILL BE AVAILABLE.")
            return
        if self.verbose:
            print(PKG_NAME + ": settings successfully loaded")

    def load_correct_clang_version(self, clang_binary):
        """Load correct libclang version guessed from clang binary name
        
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
            print(PKG_NAME + ":ERROR: make sure '{}' is in PATH."
                  .format(clang_binary))
            return

        version_regex = re.compile("\d.\d")
        found = version_regex.search(output_text)
        version_str = found.group()

        if (self.verbose):
            print(PKG_NAME + ": found a cindex for clang v: " + version_str)
        if (version_str in cindex_dict):
            try:
                # should work if python bindings are installed
                cindex = importlib.import_module("clang.cindex")
            except Exception as e:
                # should work for other cases
                print("cannot get default clang with error:", e)
                print("getting bundled one")
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
            "include_file_parent_folder")
        self.triggers = self.subl_settings.get("triggers")
        self.include_dirs = self.subl_settings.get("include_dirs")
        self.clang_binary = self.subl_settings.get("clang_binary")
        self.errors_on_save = self.subl_settings.get("errors_on_save")
        self.std_flag = self.subl_settings.get("std_flag")
        self.search_clang_complete = self.subl_settings.get(
            "search_clang_complete_file")

        self.subl_settings.clear_on_change(PKG_NAME)
        self.subl_settings.add_on_change(PKG_NAME, self.on_settings_changed)

        self.load_correct_clang_version(self.clang_binary)

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
            print(PKG_NAME + ":ERROR: no translation unit module")
            return False
        if self.subl_settings is None:
            print(PKG_NAME + ":ERROR: no sublime settings found")
            return False
        if self.verbose is None:
            print(PKG_NAME + ":ERROR: no verbose flag found")
            return False
        if self.include_parent_folder is None:
            print(PKG_NAME + ":ERROR: no parent folder include flag found")
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


class EasyClangComplete(sublime_plugin.EventListener):

    """Class that handles clang based auto completion
    
    Attributes:
        async_completions_ready (bool): flag that shows if there are 
            completions available from an autocomplete async call
        completions (list): list of completions
        err_msg_regex (TYPE): Description
        err_pos_regex (TYPE): Description
        err_regions (dict): Description
        settings (Settings): Custom handler for settings
        translation_units (dict): dict of translation_units
        valid_extensions (list): list of valid extentions for autocompletion
    
    Deleted Attributes:
        syntax_regex (regex): Regex to detect syntax
    """
    settings = None
    translation_units = {}
    # TODO: this should be probably in settings
    valid_extensions = [".c", ".cpp", ".cxx", ".h", ".hpp", ".hxx"]

    async_completions_ready = False
    completions = []

    err_pos_regex = re.compile("'(?P<file>.+)'.*"  # file
                               + "line\s(?P<row>\d+), "  # row
                               + "column\s(?P<col>\d+)")  # col
    err_msg_regex = re.compile("b\"(?P<error>.+)\"")
    err_regions = {}

    def __init__(self):
        """Initialize the settings in the class
        """
        self.settings = Settings()

    def populate_include_dirs(self):
        """populate the include dirs based on the project
        
        Returns:
            str[]: directories where clang searches for header files
        """

        def search_clang_complete_file(start_folder, stop_folder):
            """search for .clang_complete file up the tree
            
            Args:
                start_folder (str): path to folder where we start the search
                stop_folder (str): path to folder we should not go beyond
            
            Returns:
                str: path to .clang_complete file or None if not found
            """
            current_folder = start_folder
            one_past_stop_folder = path.dirname(stop_folder)
            while current_folder != one_past_stop_folder:
                for file in os.listdir(current_folder):
                    if file == ".clang_complete":
                        return path.join(current_folder, file)
                if (current_folder == path.dirname(current_folder)):
                    break
                current_folder = path.dirname(current_folder)
            return None

        def parse_clang_complete_file(file):
            """parse .clang_complete file
            
            Args:
                file (str): path to a file
            
            Returns:
                list(str): parsed list of includes from the file
            """
            includes = []
            folder = path.dirname(file)
            with open(file) as f:
                content = f.readlines()
                for line in content:
                    if line.startswith("-I"):
                        path_to_add = line[2:].rstrip()
                        if path.isabs(path_to_add):
                            includes.append(path.normpath(path_to_add))
                        else:
                            includes.append(path.join(folder, path_to_add))
            return includes

        # initialize these to nothing in case they are not present in the
        # variables
        project_base_folder = ""
        project_name = ""
        file_parent_folder = ""
        file_current_folder = ""

        # initialize new include_dirs
        clang_include_dirs = self.settings.include_dirs

        # these variables should be populated by sublime text
        variables = sublime.active_window().extract_variables()
        if ('folder' in variables):
            project_base_folder = variables['folder']
        if ('project_base_name' in variables):
            project_name = variables['project_base_name']
        if ('file' in variables):
            file_current_folder = path.dirname(variables['file'])
            file_parent_folder = path.dirname(file_current_folder)

        if self.settings.verbose:
            print(PKG_NAME + ": project_base_name = {}".format(project_name))
            print(PKG_NAME + ": project_base_folder = {}".format(
                project_base_folder))
            print(PKG_NAME + ": file_parent_folder = {}".format(
                file_parent_folder))
            print(PKG_NAME + ": std_flag = {}".format(self.settings.std_flag))

        # replace project related variables to real ones
        for i, include_dir in enumerate(clang_include_dirs):
            include_dir = re.sub(
                "(\$project_base_path)", project_base_folder, include_dir)
            include_dir = re.sub("(\$project_name)", project_name, include_dir)
            include_dir = os.path.abspath(include_dir)
            clang_include_dirs[i] = include_dir

        clang_include_dirs.append(file_current_folder)
        if (self.settings.include_parent_folder):
            clang_include_dirs.append(file_parent_folder)

        # support .clang_complete file with -I<indlude> entries
        if self.settings.search_clang_complete:
            clang_complete_file = search_clang_complete_file(
                file_current_folder, project_base_folder)
            if clang_complete_file:
                if self.settings.verbose:
                    print("{}: found {}".format(PKG_NAME, clang_complete_file))
                parsed_includes = parse_clang_complete_file(
                    clang_complete_file)
                if self.settings.verbose:
                    print("{}: .clang_complete contains includes: {}".format(
                        PKG_NAME, parsed_includes))
                clang_include_dirs += parsed_includes

        # print resulting include dirs
        if self.settings.verbose:
            print("{}: clang_include_dirs: {}".format(
                PKG_NAME, clang_include_dirs))
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
            view (sublime.View): Description
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
            if (self.settings.verbose):
                print(PKG_NAME + ": compilation started.")
            tu = self.settings.translation_unit_module
            self.translation_units[view.id()] = tu.from_source(
                view.file_name(),
                [self.settings.std_flag] + clang_includes,
                unsaved_files=files,
                options=tu.PARSE_PRECOMPILED_PREAMBLE |
                tu.PARSE_CACHE_COMPLETION_RESULTS)
        except Exception as e:
            print(PKG_NAME + ":", e)
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
            if self.settings.verbose:
                print(PKG_NAME + ": view has no completer")
            self.init_completer(view)

    def err_regions_list(self, err_regions_dict):
        """Make a list from error region dict
        
        Args:
            err_regions_dict (dict): dict of error regions for current view
        
        Returns:
            list(Region): list of regions to show on sublime view 
        """
        region_list = []
        for errors_list in err_regions_dict.values():
            for error in errors_list:
                region_list.append(error['region'])
        print(region_list)
        return region_list

    def show_errors(self, view, current_error_dict):
        """Show current error regions
        
        Args:
            view (sublime.View): Current view
            current_error_dict (dict): error dict for current view
        """
        regions = self.err_regions_list(current_error_dict)
        view.add_regions("clang_errors", regions, "string")

    def generate_errors_dict(self, view):
        """Generate a dictionary that stores all errors along with their
        positions and descriptions. Needed to show these errors on the screen.
        
        Args:
            view (sublime.View): current view
        """
        # first clear old regions
        if view.id() in self.err_regions:
            del self.err_regions[view.id()]
        # create an empty region dict for view id
        self.err_regions[view.id()] = {}

        # create new ones
        if view.id() in self.translation_units:
            tu = self.translation_units[view.id()]
            for diag in tu.diagnostics:
                location_search = self.err_pos_regex.search(str(diag.location))
                if not location_search:
                    continue
                error_dict = location_search.groupdict()
                msg_search = self.err_msg_regex.search(str(diag.spelling))
                if not msg_search:
                    continue
                error_dict.update(msg_search.groupdict())
                if (error_dict['file'] == view.file_name()):
                    row = int(error_dict['row'])
                    col = int(error_dict['col'])
                    point = view.text_point(row - 1, col - 1)
                    error_dict['region'] = view.word(point)
                    if (row in self.err_regions[view.id()]):
                        self.err_regions[view.id()][row] += [error_dict]
                    else:
                        self.err_regions[view.id()][row] = [error_dict]

    def get_correct_cursor_pos(self, view):
        """Get current cursor position. Returns position of the first cursor if
        multiple are present
        
        Args:
            view (sublime.View): current view
        
        Returns:
            (row, col): tuple of row and col for cursor position
        """
        pos = view.sel()
        if (len(pos) < 1):
            # something is wrong
            return None
        (row, col) = view.rowcol(pos[0].a)
        row += 1
        col += 1
        return (row, col)

    def on_selection_modified(self, view):
        """Called when selection is modified
        
        Args:
            view (sublime.View): current view
        """
        if view.id() not in self.err_regions:
            return
        (row, col) = self.get_correct_cursor_pos(view)
        current_err_region_dict = self.err_regions[view.id()]
        if (row in current_err_region_dict):
            errors_dict = current_err_region_dict[row]
            errors_html = ""
            for entry in errors_dict:
                errors_html += "<p><tt>" + entry['error'] + "</tt></p>"
            view.show_popup(errors_html)
        else:
            print("key: {} not in error regions".format(row))

    def on_modified_async(self, view):
        """called in a worker thread when view is modified
        
        Args:
            view (sublime.View): current view
        """
        if view.id() not in self.err_regions:
            print("view id: {} has no error regions".format(view.id()))
            return
        (row, col) = self.get_correct_cursor_pos(view)
        view.hide_popup()
        if row in self.err_regions[view.id()]:
            print("removing row", row)
            del self.err_regions[view.id()][row]
        if self.err_regions[view.id()]:
            self.show_errors(view, self.err_regions[view.id()])

    def on_post_save_async(self, view):
        """On save we want to reparse the translation unit
        
        Args:
            view (sublime.View): current view
        
        """
        if self.has_valid_extension(view):
            if view.id() in self.translation_units:
                if self.settings.verbose:
                    start = time.time()
                    print(PKG_NAME + ": reparsing translation unit")
                self.translation_units[view.id()].reparse()
                if self.settings.verbose:
                    print("{}: reparsed translation unit in {} sec".format(
                        PKG_NAME, time.time() - start))
                if self.settings.errors_on_save:
                    self.generate_errors_dict(view)
                    self.show_errors(view, self.err_regions[view.id()])
                return
            # if there is none - generate a new one
            self.init_completer(view)

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
