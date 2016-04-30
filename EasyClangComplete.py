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
import imp
import importlib
import sys
import os.path as path

from threading import Thread

from .plugin import settings
from .plugin import complete
from .plugin import tools
from .plugin import error_vis
from .plugin.tools import PKG_NAME


imp.reload(tools)
imp.reload(complete)
imp.reload(settings)
imp.reload(error_vis)


def plugin_loaded():
    sublime_plugin.reload_plugin("EasyClangComplete")


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
    completion_helper = None
    compile_errors = None

    # TODO: this should be probably in settings
    valid_extensions = [".c", ".cpp", ".cxx", ".h", ".hpp", ".hxx"]

    def __init__(self):
        """Initialize the settings in the class
        """
        EasyClangComplete.settings = settings.Settings()
        EasyClangComplete.completion_helper = complete.CompleteHelper(
            self.settings.clang_binary,
            self.settings.verbose)
        EasyClangComplete.compile_errors = error_vis.CompileErrors()

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
        settings = EasyClangComplete.settings

        if settings.complete_all:
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

        for trigger in settings.triggers:
            if current_char in trigger:
                return True
        return False

    def on_activated_async(self, view):
        """When view becomes active, create a translation unit for it if it 
        doesn't already have one

        Args:
            view (sublime.View): current view

        """
        settings = EasyClangComplete.settings
        complete_helper = EasyClangComplete.completion_helper
        if self.has_valid_extension(view):
            if view.id() in complete_helper.translation_units:
                if settings.verbose:
                    print(PKG_NAME + ": view already has a completer")
                return
            if settings.verbose:
                print(PKG_NAME + ": view has no completer")
            project_base_folder = ""
            body = view.substr(sublime.Region(0, view.size()))
            variables = sublime.active_window().extract_variables()
            if ('folder' in variables):
                project_base_folder = variables['folder']
            complete_helper.init_completer(view_id=view.id(),
                                           initial_includes=settings.include_dirs,
                                           search_include_file=settings.search_clang_complete,
                                           std_flag=settings.std_flag,
                                           file_name=view.file_name(),
                                           file_body=body,
                                           project_base_folder=project_base_folder,
                                           verbose=settings.verbose)

    

    def on_selection_modified(self, view):
        """Called when selection is modified

        Args:
            view (sublime.View): current view
        """
        (row, col) = tools.SublBridge.cursor_pos(view)
        compile_errors = EasyClangComplete.compile_errors
        compile_errors.show_popup_if_needed(view, row)

    def on_modified_async(self, view):
        """called in a worker thread when view is modified

        Args:
            view (sublime.View): current view
        """
        view.hide_popup()
        compile_errors = EasyClangComplete.compile_errors
        (row, col) = tools.SublBridge.cursor_pos(view)
        compile_errors.remove_region(view.id(), row)
        compile_errors.show_regions(view)

    def on_post_save_async(self, view):
        """On save we want to reparse the translation unit

        Args:
            view (sublime.View): current view

        """
        complete_helper = EasyClangComplete.completion_helper
        compile_errors = EasyClangComplete.compile_errors
        if self.has_valid_extension(view):
            compile_errors.erase_regions(view)
            complete_helper.reparse(view.id(), self.settings.verbose)
            if self.settings.errors_on_save:
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
        EasyClangComplete.completion_helper.remove_tu(view.id())

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

        complete_helper = EasyClangComplete.completion_helper

        if complete_helper.async_completions_ready:
            complete_helper.async_completions_ready = False
            return (complete_helper.completions, sublime.INHIBIT_WORD_COMPLETIONS)

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
            target=complete_helper.complete, args=[view, locations[0]])
        completion_thread.deamon = True
        completion_thread.start()

        # remove all completions for now
        completions = []
        return (completions, sublime.INHIBIT_WORD_COMPLETIONS)
