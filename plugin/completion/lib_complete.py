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
import sys

from os import path
from os import listdir

from plugin.error_vis import CompileErrors
from plugin.error_vis import FORMAT_LIBCLANG
from plugin.tools import PKG_NAME
from plugin.completion.base_complete import Completer

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


class LibClangCompleter(Completer):

    """Encapsulates completions based on libclang
    
    Attributes:
        async_completions_ready (bool): turns true if there are completions
                                    that have become ready from an async call
        completions (list): current completions
        translation_units (dict): Dictionary of translation units for view ids
        tu_module (cindex.TranslationUnit): module for proper cindex
        valid (bool): validity of this completer
        version_str (str): clang version string
    """

    tu_module = None
    version_str = None
    error_vis = None

    translation_units = {}

    def __init__(self, clang_binary):
        """Initialize the Completer
        
        Args:
            clang_binary (str): string for clang binary e.g. 'clang-3.6++'
        
        """
        Completer.__init__(self, clang_binary)

        # initialize cindex
        if Completer.version_str in cindex_dict:
            try:
                # should work if python bindings are installed
                cindex = importlib.import_module("clang.cindex")
            except Exception as e:
                # should work for other cases
                log.warning(" cannot get default cindex with error: %s", e)
                log.warning(" using bundled one: %s",
                            cindex_dict[Completer.version_str])
                cindex = importlib.import_module(
                    cindex_dict[Completer.version_str])
            Completer.tu_module = cindex.TranslationUnit
            # check if we can build an index. If not, set valid to false
            try:
                cindex.Index.create()
                self.valid = True
            except Exception as e:
                log.error(" error: %s", e)
                self.valid = False

    def remove(self, view_id):
        """Remove tu for this view. Happens when we don't need it anymore.
        
        Args:
            view_id (int): view id
        
        """
        if view_id not in self.translation_units:
            log.error(" no tu for view id: %s, so not removing", view_id)
            return
        log.debug(" removing translation unit for view id: %s", view_id)
        del self.translation_units[view_id]

    def exists_for_view(self, view_id):
        """find if there is a completer for the view
        
        Args:
            view_id (int): current view id
        
        Returns:
            bool: has completer
        """
        if view_id in self.translation_units:
            return True
        return False

    def init(self, view, includes, settings, project_folder):
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
        file_name = view.file_name()
        file_body = view.substr(sublime.Region(0, view.size()))
        file_folder = path.dirname(file_name)

        # initialize unsaved files
        files = [(file_name, file_body)]

        # init needed variables from settings
        clang_flags = [settings.std_flag]
        for include in includes:
            clang_flags.append('-I' + include)

        # support .clang_complete file with -I<indlude> entries
        if search_include_file:
            log.debug(" searching for .clang_complete in %s up to %s",
                      file_folder, project_folder)
            clang_complete_file = Completer._search_clang_complete_file(
                file_folder, project_folder)
            if clang_complete_file:
                log.debug(" found .clang_complete: %s", clang_complete_file)
                flags = Completer._parse_clang_complete_file(
                    clang_complete_file)
                clang_flags += flags

        log.debug(" clang flags are: %s", clang_flags)
        try:
            TU = Completer.tu_module
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
        complete_obj = self.translation_units[view.id()].codeComplete(
            view.file_name(),
            row, col,
            unsaved_files=files)
        end = time.time()
        if complete_obj is None or len(complete_obj.results) == 0:
            log.debug(" no completions")
            return None
        log.debug(" code complete done in %s seconds", end - start)

        self.completions = LibClangCompleter._parse_completions(complete_obj)
        self.async_completions_ready = True
        Completer._reload_completions(view)

    def update(self, view, show_errors):
        """Reparse the translation unit. This speeds up completions
        significantly, so we perform this upon file save.
        
        Args:
            view_id (int): view id
        
        Returns:
            bool: reparsed successfully
        """
        if view.id() in self.translation_units:
            log.debug(" reparsing translation_unit for view %s", view.id())
            start = time.time()
            self.translation_units[view.id()].reparse()
            log.debug(" reparsed translation unit in %s seconds",
                      time.time() - start)
            if show_errors:
                logging.debug(" visualizing errors")
                self.error_vis.generate(
                    view, self.translation_units[view.id()].diagnostics, 
                    error_vis.LIBCLANG)
                self.error_vis.show_regions()
            return True
        log.error(" no translation unit for view id %s")
        return False

    @staticmethod
    def _parse_completions(complete_results):
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
