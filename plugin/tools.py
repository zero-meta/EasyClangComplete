"""This module contains various tools

Attributes:
    log (logging): logger for this module
    OSX_CLANG_VERSION_DICT (dict): mapping from version number of OSX clang
        to the one of llvm clang.
        Taken from here: https://gist.github.com/yamaya/2924292
    PKG_NAME (str): this package name
"""
from os import path
from os import makedirs
from os import listdir

import sublime
import logging
import tempfile

import re

PKG_NAME = path.basename(path.dirname(path.dirname(__file__)))

OSX_CLANG_VERSION_DICT = {
    '4.2': '3.2',
    '5.0': '3.3',
    '5.1': '3.4',
    '6.0': '3.5',
    '6.1': '3.6',
    '7.0': '3.7',
    '7.3': '3.8',
    '8.0': '3.8'
}

log = logging.getLogger(__name__)


class SublBridge:

    """A small help class that bridges with sublime (maybe will grow)

    Attributes:
        NO_DEFAULT_COMPLETIONS (TYPE): Description
    """

    NO_DEFAULT_COMPLETIONS = sublime.INHIBIT_WORD_COMPLETIONS \
        | sublime.INHIBIT_EXPLICIT_COMPLETIONS

    @staticmethod
    def active_view_id():
        """ Get the id of the active view

        Returns:
            int: buffer id of the active view
        """
        return sublime.active_window().active_view().buffer_id()

    @staticmethod
    def cursor_pos(view, pos=None):
        """Get current cursor position. Returns position of the first cursor if
        multiple are present

        Args:
            view (sublime.View): current view
            pos (int, optional): given position. First selection by default

        Returns:
            (row, col): tuple of row and col for cursor position
        """
        if not pos:
            pos = view.sel()
            if len(pos) < 1:
                # something is wrong
                return None
            # we care about the first position
            pos = pos[0].a
        (row, col) = view.rowcol(pos)
        row += 1
        col += 1
        return (row, col)

    @staticmethod
    def next_line(view):
        """Get next line as text

        Args:
            view (sublime.View): current view

        Returns:
            str: text that the next line contains
        """
        (row, _) = SublBridge.cursor_pos(view)
        point_on_next_line = view.text_point(row, 0)
        line = view.line(point_on_next_line)
        return view.substr(line)


class PosStatus:

    """Enum class for position status

    Attributes:
        COMPLETION_NEEDED (int): completion needed
        COMPLETION_NOT_NEEDED (int): completion not needed
        WRONG_TRIGGER (int): trigger is wrong
    """
    COMPLETION_NEEDED = 0
    COMPLETION_NOT_NEEDED = 1
    WRONG_TRIGGER = 2


class File:
    """Class that handles a path to the file
    """
    __full_path = None
    __last_seen_modification = 0

    def __init__(self, file_path=None):
        """Initialize a new file and create if needed

        Args:
            file_path (str, optional): generate file object from this path
        """
        if not file_path or not path:
            # leave the object unitialized
            return
        self.__full_path = path.abspath(file_path)
        # initialize the file
        open(self.__full_path, 'a+').close()

    def full_path(self):
        """Get full path to file.

        Returns:
            str: full path
        """
        return self.__full_path

    def folder(self):
        """Get parent folder to the file.

        Returns:
            str: parent folder of a file
        """
        return path.dirname(self.__full_path)

    def loaded(self):
        """Is the file loaded?
        """
        if self.__full_path:
            return True
        return False

    def was_modified(self):
        """Was the file modified since the last access?

        Returns:
            bool: True if modified, False if not. Creation is modification.
        """
        if not self.loaded():
            return False
        actual_modification_time = path.getmtime(self.__full_path)
        log.debug(" last mod: %s, actual mod: %s",
                  self.__last_seen_modification, actual_modification_time)
        if actual_modification_time > self.__last_seen_modification:
            self.__last_seen_modification = actual_modification_time
            return True
        return False

    @staticmethod
    def search(file_name, from_folder, to_folder, search_content=None):
        """search for a file up the tree

        Args:
            file_name (TYPE): Description
            from_folder (str): path to folder where we start the search
            to_folder (str): path to folder we should not go beyond
            search_content (None, optional): Description

        Returns:
            File: found file
        """
        log.debug(" searching '%s' from '%s' to '%s'",
                  file_name, from_folder, to_folder)
        current_folder = from_folder
        one_past_stop_folder = path.dirname(to_folder)
        while current_folder != one_past_stop_folder:
            for file in listdir(current_folder):
                if file == file_name:
                    found_file = File(path.join(current_folder, file))
                    log.debug(" found '%s' file: %s",
                              file_name, found_file.full_path())
                    if search_content:
                        if File.contains(found_file.full_path(),
                                         search_content):
                            return found_file
                        else:
                            log.debug(" skipping file '%s'. ", found_file)
                            log.debug(" no line starts with: '%s'",
                                      search_content)
                            continue
                    # this is reached only if we don't search any content
                    return found_file
            if current_folder == path.dirname(current_folder):
                break
            current_folder = path.dirname(current_folder)
        return File()

    @staticmethod
    def contains(file_path, query):
        """Contains line

        Args:
            file_path (str): path to file
            query (str): string to search

        Returns:
            bool: True if contains str, False if not
        """
        with open(file_path) as f:
            for line in f:
                if line.lower().startswith(query):
                    log.debug(" found needed line: '%s'", line)
                    return True
        return False


class Tools:

    """just a bunch of helpful tools to unclutter main file

    Attributes:
        HIDE_DEFAULT_COMPLETIONS: a value to return from `on_query_completions`
            Ensures nothing will be shown apart from the output of this plugin
        SHOW_DEFAULT_COMPLETIONS: `None` to return from `on_query_completions`.
            This guarantees that sublime text will show default completions.
        syntax_regex (regex): regex to parse syntax setting
        valid_extensions (list): list of valid extensions for auto-completion
        valid_syntax (list): list of valid syntaxes for this plugin

    """

    syntax_regex = re.compile("\/([^\/]+)\.(?:tmLanguage|sublime-syntax)")

    valid_extensions = [".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx"]
    valid_syntax = ["C", "C++", "C Improved", "C++11"]

    SHOW_DEFAULT_COMPLETIONS = None
    HIDE_DEFAULT_COMPLETIONS = ([], sublime.INHIBIT_WORD_COMPLETIONS |
                                sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @staticmethod
    def get_temp_dir():
        """ Create a temporary folder if needed and return it """
        tempdir = path.join(tempfile.gettempdir(), PKG_NAME)
        if not path.exists(tempdir):
            makedirs(tempdir)
        return tempdir

    @staticmethod
    def get_view_syntax(view):
        """Get syntax from view description

        Args:
            view (sublime.View): Current view

        Returns:
            str: syntax, e.g. "C", "C++"
        """
        syntax = re.findall(Tools.syntax_regex,
                            view.settings().get('syntax'))
        if len(syntax) > 0:
            return syntax[0]
        return None

    @staticmethod
    def has_valid_syntax(view):
        """Check if syntax is valid for this plugin

        Args:
            view (sublime.View): current view

        Returns:
            bool: True if valid, False otherwise
        """
        syntax = Tools.get_view_syntax(view)
        if syntax in Tools.valid_syntax:
            log.debug(" file has valid syntax: `%s`", syntax)
            return True
        log.debug(" file has unsupported syntax: `%s`", syntax)
        return False

    @staticmethod
    def is_valid_view(view):
        """
        Check whether the given view is one we can and want to handle.

        Args:
            view (sublime.View): view to check

        Returns:
            bool: True if we want to handle this view, False otherwise
        """
        if not view:
            return False
        if not view.file_name():
            return False
        if not Tools.has_valid_syntax(view):
            return False
        if view.is_scratch():
            return False
        return True

    @staticmethod
    def has_valid_extension(view):
        """Test if the current file has a valid extension

        Args:
            view (sublime.View): current view

        Returns:
            bool: extension is valid
        """
        if not view or not view.file_name():
            return False
        (_, ext) = path.splitext(view.file_name())
        if ext in Tools.valid_extensions:
            return True
        return False

    @staticmethod
    def seconds_from_string(time_str):
        """ Get int seconds from string

        Args:
            time_str (str): string in format 'HH:MM:SS'

        Returns:
            int: seconds
        """
        h, m, s = time_str.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)

    @staticmethod
    def get_position_status(point, view, settings):
        """Check if the cursor focuses a valid trigger

        Args:
            point (int): position of the cursor in the file as defined by subl
            view (sublime.View): current view
            settings (TYPE): Description

        Returns:
            PosStatus: statuf for this position
        """
        trigger_length = 1

        word_on_the_left = view.substr(view.word(point - trigger_length))
        if word_on_the_left.isdigit():
            # don't autocomplete digits
            log.debug(" trying to autocomplete digit, are we? Not allowed.")
            return PosStatus.WRONG_TRIGGER

        # slightly counterintuitive `view.substr` returns ONE character
        # to the right of given point.
        curr_char = view.substr(point - trigger_length)
        wrong_trigger_found = False
        for trigger in settings.triggers:
            # compare to the last char of a trigger
            if curr_char == trigger[-1]:
                trigger_length = len(trigger)
                prev_char = view.substr(point - trigger_length)
                if prev_char == trigger[0]:
                    log.debug(" matched trigger '%s'.", trigger)
                    return PosStatus.COMPLETION_NEEDED
                else:
                    log.debug(" wrong trigger '%s%s'.", prev_char, curr_char)
                    wrong_trigger_found = True
        if wrong_trigger_found:
            # no correct trigger found, but a wrong one fired instead
            log.debug(" wrong trigger fired")
            return PosStatus.WRONG_TRIGGER

        if settings.autocomplete_all:
            return PosStatus.COMPLETION_NEEDED

        # if nothing fired we don't need to do anything
        log.debug(" no completions needed")
        return PosStatus.COMPLETION_NOT_NEEDED
