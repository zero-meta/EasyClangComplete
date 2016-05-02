"""Summary

Attributes:
    cindex_dict (dict): dict of cindex entries for each version of clang
    log (logging.Logger): logger for this module
"""
import re
import subprocess
import importlib
import sublime
import time
import platform
import logging

from os import path
from os import listdir

from .tools import PKG_NAME

log = logging.getLogger(__name__)

cindex_dict = {
    '3.2': PKG_NAME + ".clang.cindex32",
    '3.3': PKG_NAME + ".clang.cindex33",
    '3.4': PKG_NAME + ".clang.cindex34",
    '3.5': PKG_NAME + ".clang.cindex35",
    '3.6': PKG_NAME + ".clang.cindex36",
    '3.7': PKG_NAME + ".clang.cindex37",
    '3.8': PKG_NAME + ".clang.cindex38",
}


class LibClangCompleter:

    """Encapsulates completions based on libclang

    Attributes:
        async_completions_ready (bool): turns true if there are completions
                                    that have become ready from an async call
        completions (list): current completions
        translation_units (dict): Dictionary of translation units for view ids
        tu_module (cindex.TranslationUnit): module for proper cindex
        version_str (str): clang version string
    """

    tu_module = None
    version_str = None

    completions = []
    translation_units = {}
    async_completions_ready = False

    def __init__(self, clang_binary, verbose):
        """Initialize the LibClangCompleter

        Args:
            clang_binary (str): string for clang binary e.g. 'clang-3.6++'
            verbose (bool): shows if we should show debug info

        """
        if verbose:
            log.setLevel(logging.DEBUG)
        else:
            log.setLevel(logging.INFO)

        # check if clang binary is defined
        if not clang_binary:
            log.critical(" clang binary not defined!")
            return

        # run the cmd to get the proper version of the installed clang
        check_version_cmd = clang_binary + " --version"
        try:
            log.info(" Getting version from command: `%s`", check_version_cmd)
            output = subprocess.check_output(check_version_cmd, shell=True)
            output_text = ''.join(map(chr, output))
        except subprocess.CalledProcessError as e:
            error_dict = {"clang_binary": clang_binary,
                          "error": e,
                          "advice": "make sure `clang_binary` is in PATH"}
            log.error(" Calling clang binary failed.", error_dict)
            return

        # now we have the output, and can extract version from it
        version_regex = re.compile("\d.\d")
        found = version_regex.search(output_text)
        LibClangCompleter.version_str = found.group()
        if LibClangCompleter.version_str > "3.8"
                and platform.system() == "Darwin":
            # to the best of my knowledge this is the last one available on macs
            # but it is a hack, yes
            LibClangCompleter.version_str = "3.7"
            info = {"platform": platform.system()}
            log.warning(" Wrong version reported. Reducing it to %s",
                        LibClangCompleter.version_str, info)
        log.info(" Found clang version: %s",
                 LibClangCompleter.version_str)
        if LibClangCompleter.version_str in cindex_dict:
            try:
                # should work if python bindings are installed
                cindex = importlib.import_module("clang.cindex")
            except Exception as e:
                # should work for other cases
                log.warning(" cannot get default cindex with error: %s", e)
                log.warning(" using bundled one: %s",
                            cindex_dict[LibClangCompleter.version_str])
                cindex = importlib.import_module(
                    cindex_dict[LibClangCompleter.version_str])
            LibClangCompleter.tu_module = cindex.TranslationUnit

    def get_diagnostics(self, view_id):
        """Every TU has diagnostics. And we can get errors from them. This
        functions returns current diagnostics for tu for view id.

        Args:
            view_id (int): view id

        Returns:
            tu.diagnostics: relevant diagnostics
        """
        if view_id not in self.translation_units:
            log.debug(" no diagnostics for view id: %s", view_id)
            return None
        return self.translation_units[view_id].diagnostics

    def remove_tu(self, view_id):
        """Remove tu for this view. Happens when we don't need it anymore.

        Args:
            view_id (int): view id

        """
        if view_id not in self.translation_units:
            log.error(" no tu for view id: %s, so not removing", view_id)
            return
        log.debug(" removing translation unit for view id: %s", view_id)
        del self.translation_units[view_id]

    def init_completer(self, view_id, initial_includes, search_include_file, 
                       std_flag, file_name, file_body, project_base_folder):
        """Initialize the completer

        Args:
            view_id (int): view id
            initial_includes (str[]): includes from settings
            search_include_file (bool): should we search for .clang_complete?
            std_flag (str): std flag, e.g. std=c++11
            file_name (str): file full path
            file_body (str): content of the file
            project_base_folder (str): project folder

        """
        file_current_folder = path.dirname(file_name)

        # initialize unsaved files
        files = [(file_name, file_body)]

        # init needed variables from settings
        clang_flags = [std_flag]
        for include in initial_includes:
            clang_flags.append('-I' + include)

        # support .clang_complete file with -I<indlude> entries
        if search_include_file:
            log.debug(" searching for .clang_complete in %s up to %s",
                      file_current_folder, project_base_folder)
            clang_complete_file = LibClangCompleter._search_clang_complete_file(
                file_current_folder, project_base_folder)
            if clang_complete_file:
                log.debug(" found .clang_complete: %s", clang_complete_file)
                flags = LibClangCompleter._parse_clang_complete_file(
                    clang_complete_file)
                clang_flags += flags

        log.debug(" clang flags are: %s", clang_flags)
        try:
            TU = LibClangCompleter.tu_module
            start = time.time()
            log.debug(" compilation started for view id: %s", view_id)
            self.translation_units[view_id] = TU.from_source(
                filename=file_name,
                args=clang_flags,
                unsaved_files=files,
                options=TU.PARSE_PRECOMPILED_PREAMBLE |
                TU.PARSE_CACHE_COMPLETION_RESULTS)
            end = time.time()
            log.debug(" compilation done in %s seconds", end - start)
        except Exception as e:
            log.error(" error while compiling: %s", e)

    def complete(self, view, cursor_pos):
        """This function is called asynchronously to create a list of
        autocompletions. Using the current translation unit it queries libclang
        for the possible completions.

        Args:
            view (sublime.View): current view
            cursor_pos (int): sublime provided poistion of the cursor

        """
        file_body = view.substr(sublime.Region(0, view.size()))
        (row, col) = view.rowcol(cursor_pos)
        row += 1
        col += 1

        # unsaved files
        files = [(view.file_name(), file_body)]

        # do nothing if there in no translation_unit present
        if not view.id() in self.translation_units:
            log.debug(" cannot complete. No translation unit for view %s",
                      view.id())
            return None
        # execute clang code completion
        start = time.time()
        log.debug(" started code complete for view %s", view.id())
        complete_results = self.translation_units[view.id()].codeComplete(
            view.file_name(),
            row, col,
            unsaved_files=files)
        end = time.time()
        if complete_results is None or len(complete_results.results) == 0:
            log.debug(" no completions")
            return None
        log.debug(" code complete done in %s seconds", end - start)

        self.completions = LibClangCompleter._process_completions(
            complete_results)
        self.async_completions_ready = True
        LibClangCompleter._reload_completions(view)

    def reparse(self, view_id):
        """Reparse the translation unit. This speeds up completions
        significantly, so we perform this upon file save.

        Args:
            view_id (int): view id

        Returns:
            bool: reparsed successfully
        """
        if view_id in self.translation_units:
            log.debug(" reparsing translation_unit for view %s", view_id)
            start = time.time()
            self.translation_units[view_id].reparse()
            log.debug(" reparsed translation unit in %s seconds",
                      time.time() - start)
            return True
        log.error(" no translation unit for view id %s")
        return False

    @staticmethod
    def _reload_completions(view):
        """Ask sublime to reload the completions. Needed to update the active 
        completion list when async autocompletion task has finished.

        Args:
            view (sublime.View): current_view

        """
        log.debug(" reload completion tooltip")
        view.run_command('hide_auto_complete')
        view.run_command('auto_complete', {
            'disable_auto_insert': True,
            'api_completions_only': True,
            'next_competion_if_showing': True, })

    @staticmethod
    def _process_completions(complete_results):
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

    @staticmethod
    def _search_clang_complete_file(start_folder, stop_folder):
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
            for file in listdir(current_folder):
                if file == ".clang_complete":
                    return path.join(current_folder, file)
            if current_folder == path.dirname(current_folder):
                break
            current_folder = path.dirname(current_folder)
        return None

    @staticmethod
    def _parse_clang_complete_file(file):
        """parse .clang_complete file

        Args:
            file (str): path to a file

        Returns:
            list(str): parsed list of includes from the file
        """
        flags = []
        folder = path.dirname(file)
        with open(file) as f:
            content = f.readlines()
            for line in content:
                if line.startswith('-D'):
                    flags.append(line)
                elif line.startswith('-I'):
                    path_to_add = line[2:].rstrip()
                    if path.isabs(path_to_add):
                        flags.append('-I' + path.normpath(path_to_add))
                    else:
                        flags.append('-I' + path.join(folder, path_to_add))
        log.debug(" .clang_complete contains flags: %s", flags)
        return flags
