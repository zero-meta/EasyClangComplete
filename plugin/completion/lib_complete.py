"""This module contains class for libclang based completions

Attributes:
    cindex_dict (dict): dict of cindex entries for each version of clang
    log (logging.Logger): logger for this module
"""
import importlib
import sublime
import time
import logging

from os import path

from .. import error_vis
from .. import tools
from .base_complete import BaseCompleter
from .flags_file import FlagsFile


log = logging.getLogger(__name__)
log.debug(" reloading module")

Tools = tools.Tools

cindex_dict = {
    '3.2': tools.PKG_NAME + ".clang.cindex32",
    '3.3': tools.PKG_NAME + ".clang.cindex33",
    '3.4': tools.PKG_NAME + ".clang.cindex34",
    '3.5': tools.PKG_NAME + ".clang.cindex35",
    '3.6': tools.PKG_NAME + ".clang.cindex36",
    '3.7': tools.PKG_NAME + ".clang.cindex37",
    '3.8': tools.PKG_NAME + ".clang.cindex38",
}

clang_utils_module_name = tools.PKG_NAME + ".clang.utils"


class Completer(BaseCompleter):

    """Encapsulates completions based on libclang

    Attributes:
        tu_module (cindex.TranslationUnit): module for proper cindex
        translation_units (dict): dictionary of tu's for each view id
    """

    tu_module = None

    translation_units = {}

    def __init__(self, clang_binary):
        """Initialize the Completer from clang binary, reading its version.
        Picks an according cindex for the found version.

        Args:
            clang_binary (str): string for clang binary e.g. 'clang-3.6++'

        """
        super(Completer, self).__init__(clang_binary)

        # initialize cindex
        if self.version_str in cindex_dict:
            # import cindex bundled with this plugin. We cannot use the default
            # one because sublime uses python 3, but there are no python
            # bindings for python 3
            log.debug(
                " using bundled cindex: %s", cindex_dict[self.version_str])
            cindex = importlib.import_module(cindex_dict[self.version_str])
            # load clang helper class
            clang_utils = importlib.import_module(clang_utils_module_name)
            ClangUtils = clang_utils.ClangUtils
            # If we haven't already initialized the clang Python bindings, try
            # to figure out the path libclang.
            if not cindex.Config.loaded:
                # This will return something like /.../lib/clang/3.x.0
                libclang_dir = ClangUtils.find_libclang_dir(clang_binary)
                if libclang_dir:
                    cindex.Config.set_library_path(libclang_dir)

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

    def init(self, view, settings):
        """Initialize the completer. Builds the view.

        Args:
            view (sublime.View): current view
            settings (Settings): plugin settings

        """

        # Return early if this is an invalid view.
        if not Tools.is_valid_view(view):
            return

        file_name = view.file_name()
        file_body = view.substr(sublime.Region(0, view.size()))
        file_folder = path.dirname(file_name)

        # initialize unsaved files
        files = [(file_name, file_body)]

        # init needed variables from settings
        clang_flags = []

        # if we use project-specific settings we ignore everything else
        if settings.project_specific_settings:
            log.info(" overriding all flags by project ones")
            project_flags = settings.get_project_clang_flags()
            if project_flags:
                clang_flags.append(settings.std_flag)
                clang_flags += project_flags
            else:
                log.error(" there are no project-specific settings.")
                log.info(" falling back to using plugin settings.")
        if len(clang_flags) < 2:
            # add std flag to all flags
            clang_flags.append(settings.std_flag)
            # this means that project specific settings are either not used or
            # invalid, so we still need to initialize from settings

            # init includes to start with from settings
            includes = settings.populate_include_dirs(view)

            for include in includes:
                clang_flags.append('-I' + include)
            # support .clang_complete file with -I<indlude> entries
            if settings.search_clang_complete:
                if not self.flags_file:
                    self.flags_file = FlagsFile(
                        from_folder=file_folder,
                        to_folder=settings.project_base_folder)
                # add custom flags to general ones
                clang_flags += self.flags_file.get_flags(
                                separate_includes=False)
        # now we have the flags and can continue initializing the TU
        if Tools.get_view_syntax(view) != "C":
            # treat this as c++ even if it is a header
            log.debug(" This is a C++ file. Adding `-x c++` to flags")
            clang_flags = ['-x'] + ['c++'] + clang_flags
        log.debug(" clang flags are: %s", clang_flags)
        try:
            TU = Completer.tu_module
            start = time.time()
            log.debug(" compilation started for view id: %s", view.buffer_id())
            self.translation_units[view.buffer_id()] = TU.from_source(
                filename=file_name,
                args=clang_flags,
                unsaved_files=files,
                options=TU.PARSE_PRECOMPILED_PREAMBLE |
                TU.PARSE_CACHE_COMPLETION_RESULTS)
            end = time.time()
            log.debug(" compilation done in %s seconds", end - start)
        except Exception as e:
            log.error(" error while compiling: %s", e)
        if settings.errors_on_save:
            self.error_vis.generate(
                view, self.translation_units[view.buffer_id()].diagnostics,
                error_vis.FORMAT_LIBCLANG)
            self.error_vis.show_regions(view)

    def complete(self, view, cursor_pos, show_errors):
        """This function is called asynchronously to create a list of
        autocompletions. Using the current translation unit it queries libclang
        for the possible completions. It also shows compile errors if needed.

        Args:
            view (sublime.View): current view
            cursor_pos (int): sublime provided poistion of the cursor
            show_errors (bool): controls if we need to show errors

        """
        file_body = view.substr(sublime.Region(0, view.size()))
        (row, col) = view.rowcol(cursor_pos)
        row += 1
        col += 1

        # unsaved files
        files = [(view.file_name(), file_body)]

        # do nothing if there in no translation_unit present
        if not view.buffer_id() in self.translation_units:
            log.error(" cannot complete. No translation unit for view %s",
                      view.buffer_id())
            return None
        # execute clang code completion
        start = time.time()
        log.debug(" started code complete for view %s", view.buffer_id())
        complete_obj = self.translation_units[view.buffer_id()].codeComplete(
            view.file_name(),
            row, col,
            unsaved_files=files)
        end = time.time()
        if complete_obj is None or len(complete_obj.results) == 0:
            log.debug(" no completions")
            return None
        log.debug(" code complete done in %s seconds", end - start)

        self.completions = Completer._parse_completions(complete_obj)
        log.debug(self.completions)
        self.async_completions_ready = True
        Completer._reload_completions(view)
        if show_errors:
            self.error_vis.generate(
                view, self.translation_units[view.buffer_id()].diagnostics,
                error_vis.FORMAT_LIBCLANG)
            self.error_vis.show_regions(view)

    def update(self, view, show_errors):
        """Reparse the translation unit. This speeds up completions
        significantly, so we perform this upon file save.

        Args:
            view (sublime.View): current view
            show_errors (bool): if true - highlight compile errors

        Returns:
            bool: reparsed successfully

        """
        log.debug(" view is %s", view.buffer_id())
        if view.buffer_id() in self.translation_units:
            log.debug(
                " reparsing translation_unit for view %s", view.buffer_id())
            start = time.time()
            self.translation_units[view.buffer_id()].reparse()
            log.debug(" reparsed translation unit in %s seconds",
                      time.time() - start)
            if show_errors:
                self.error_vis.generate(
                    view, self.translation_units[view.buffer_id()].diagnostics,
                    error_vis.FORMAT_LIBCLANG)
                self.error_vis.show_regions(view)
            return True
        log.error(" no translation unit for view id %s", view.buffer_id())
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
                if not chunk:
                    continue
                if not chunk.spelling:
                    continue
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
