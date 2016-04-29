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
from .plugin.tools import PKG_NAME


imp.reload(tools)
imp.reload(complete)
imp.reload(settings)


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
    # TODO: this should be probably in settings
    valid_extensions = [".c", ".cpp", ".cxx", ".h", ".hpp", ".hxx"]

    err_pos_regex = re.compile("'(?P<file>.+)'.*"  # file
                               + "line\s(?P<row>\d+), "  # row
                               + "column\s(?P<col>\d+)")  # col
    err_msg_regex = re.compile("b\"(?P<error>.+)\"")
    err_regions = {}

    def __init__(self):
        """Initialize the settings in the class
        """
        EasyClangComplete.settings = settings.Settings()
        EasyClangComplete.completion_helper = complete.CompleteHelper(
            self.settings.clang_binary,
            self.settings.verbose)

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

        complete_helper = EasyClangComplete.completion_helper

        # create new ones
        if view.id() in complete_helper.translation_units:
            tu = complete_helper.translation_units[view.id()]
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
            self.completion_helper.reparse(view.id(), self.settings.verbose)
            if self.settings.errors_on_save:
                self.generate_errors_dict(view)
                self.show_errors(view, self.err_regions[view.id()])

    def on_close(self, view):
        """Remove the translation unit when view is closed

        Args:
            view (sublime.View): current view

        """
        if view.id() in self.completion_helper.translation_units:
            if self.settings.verbose:
                print("{}: removing translation unit for view: {}".format(
                      PKG_NAME, view.id()))
            del self.translation_units[view.id()]

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
