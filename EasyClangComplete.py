"""EasyClangComplete plugin for Sublime Text 3.

Provides completion suggestions for C/C++ languages based on clang output

Attributes:
    cindex_dict (dict): names for cindex files with keys being clang versions
    PKG_NAME (string): Name of the package
"""

import sublime
import sublime_plugin
import os
import imp
import time
import importlib
import sys
import logging
import os.path as path

from threading import Thread

from .plugin import settings
from .plugin import complete
from .plugin import tools
from .plugin import error_vis
from .plugin.tools import PKG_NAME

# reload the modules
imp.reload(tools)
imp.reload(complete)
imp.reload(settings)
imp.reload(error_vis)

from .plugin.tools import SublBridge

# unfortunately because of how subl initializes the plugins I cannot move these
# inside of some class.
plugin_settings = None
complete_helper = None
compile_errors = None

log = logging.getLogger(__name__)


def plugin_loaded():
    global plugin_settings
    global complete_helper
    global compile_errors
    plugin_settings = settings.Settings()
    complete_helper = complete.CompleteHelper(plugin_settings.clang_binary,
                                              plugin_settings.verbose)
    compile_errors = error_vis.CompileErrors(plugin_settings.verbose)

    if plugin_settings.verbose:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)


class EasyClangComplete(sublime_plugin.EventListener):

    """Class that handles clang based auto completion

    Attributes:
        async_completions_ready (bool): flag that shows if there are 
            completions available from an autocomplete async call
        completions (list): list of completions
        err_msg_regex (TYPE): Description
        err_pos_regex (TYPE): Description
        err_regions (dict): Description
        plugin_settings (Settings): Custom handler for plugin_settings
        translation_units (dict): dict of translation_units
        valid_extensions (list): list of valid extentions for autocompletion

    Deleted Attributes:
        syntax_regex (regex): Regex to detect syntax
    """
    # TODO: this should be probably in plugin_settings
    valid_extensions = [".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx"]

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
        if ext in EasyClangComplete.valid_extensions:
            return True
        return False

    def needs_autocompletion(self, point, view):
        """Check if the cursor focuses a valid trigger

        Args:
            point (int): position of the cursor in the file as defined by subl
            view (sublime.View): current view

        Returns:
            bool: trigger is valid
        """
        if plugin_settings.complete_all:
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
        if word_on_the_left.isdigit():
            # don't autocomplete digits
            return False

        for trigger in plugin_settings.triggers:
            if current_char in trigger:
                return True
        return False

    def on_activated_async(self, view):
        """When view becomes active, create a translation unit for it if it 
        doesn't already have one

        Args:
            view (sublime.View): current view

        """
        log.debug(" on_activated_async view id %s", view.id())
        if self.has_valid_extension(view):
            if view.id() in complete_helper.translation_units:
                log.debug(" view %s, already has a completer", view.id())
                return
            log.debug("init completer for view id: %s", view.id())
            project_base_name = ""
            project_base_folder = ""
            body = view.substr(sublime.Region(0, view.size()))
            variables = sublime.active_window().extract_variables()
            if 'folder' in variables:
                project_base_folder = variables['folder']
            if 'project_base_name' in variables:
                project_base_name = variables['project_base_name']
            current_folder = path.dirname(view.file_name())
            parent_folder = path.dirname(current_folder)
            include_dirs = plugin_settings.populate_include_dirs(
                    project_name=project_base_name,
                    project_base_folder=project_base_folder,
                    file_current_folder=current_folder,
                    file_parent_folder=parent_folder)
            complete_helper.init_completer(
                view_id=view.id(),
                initial_includes=include_dirs,
                search_include_file=plugin_settings.search_clang_complete,
                std_flag=plugin_settings.std_flag,
                file_name=view.file_name(),
                file_body=body,
                project_base_folder=project_base_folder)

    def on_selection_modified(self, view):
        """Called when selection is modified

        Args:
            view (sublime.View): current view
        """
        (row, col) = SublBridge.cursor_pos(view)
        compile_errors.show_popup_if_needed(view, row)

    def on_modified_async(self, view):
        """called in a worker thread when view is modified

        Args:
            view (sublime.View): current view
        """
        log.debug(" on_modified_async view id %s", view.id())
        compile_errors.clear(view)

    def on_post_save_async(self, view):
        """On save we want to reparse the translation unit

        Args:
            view (sublime.View): current view

        """
        log.debug(" on_post_save_async")
        if self.has_valid_extension(view):
            compile_errors.erase_regions(view)
            complete_helper.reparse(view.id())
            if plugin_settings.errors_on_save:
                diagnostics = complete_helper.get_diagnostics(view.id())
                if not diagnostics:
                    # no diagnostics
                    return
                compile_errors.generate(view, diagnostics)
                compile_errors.show_regions(view)

    def on_close(self, view):
        """Remove the translation unit when view is closed

        Args:
            view (sublime.View): current view

        """
        log.debug(" closing view %s", view.id())
        complete_helper.remove_tu(view.id())

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
        log.debug(" on_query_completions view id %s", view.id())
        if view.is_scratch():
            return None

        if not self.has_valid_extension(view):
            return None

        if complete_helper.async_completions_ready:
            complete_helper.async_completions_ready = False
            return (complete_helper.completions, sublime.INHIBIT_WORD_COMPLETIONS)

        # Verify that character under the cursor is one allowed trigger
        if (not self.needs_autocompletion(locations[0], view)):
            # send empty completion and forbid to show other things
            completions = []
            return (completions, sublime.INHIBIT_WORD_COMPLETIONS)

        log.debug(" starting async auto_complete at pos: %s", locations[0])

        # create a daemon thread to update the completions
        completion_thread = Thread(
            target=complete_helper.complete, args=[view, locations[0]])
        completion_thread.deamon = True
        completion_thread.start()

        # remove all completions for now
        completions = []
        return (completions, sublime.INHIBIT_WORD_COMPLETIONS)
