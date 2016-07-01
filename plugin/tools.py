"""This module contains various tools

Attributes:
    log (logging): logger for this module
    OSX_CLANG_VERSION_DICT (dict): mapping from version number of OSX clang
        to the one of llvm clang.
        Taken from here: https://gist.github.com/yamaya/2924292
    PKG_NAME (str): this package name
"""
import os.path as path
import sublime
import logging
import re

PKG_NAME = path.basename(path.dirname(path.dirname(__file__)))

OSX_CLANG_VERSION_DICT = {
    '4.2': '3.2',
    '5.0': '3.3',
    '5.1': '3.4',
    '6.0': '3.5',
    '6.1': '3.6',
    '7.0': '3.7',
    '7.3': '3.7'
}

log = logging.getLogger(__name__)


class SublBridge:

    """ A small help class that bridges with sublime (maybe will grow)
    """

    @staticmethod
    def cursor_pos(view):
        """Get current cursor position. Returns position of the first cursor if
        multiple are present

        Args:
            view (sublime.View): current view

        Returns:
            (row, col): tuple of row and col for cursor position
        """
        pos = view.sel()
        if len(pos) < 1:
            # something is wrong
            return None
        (row, col) = view.rowcol(pos[0].a)
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

    """ Enum class for position status

    Attributes:
        COMPLETION_NEEDED (int): completion needed
        COMPLETION_NOT_NEEDED (int): completion not needed
        WRONG_TRIGGER (int): trigger is wrong
    """
    COMPLETION_NEEDED = 0
    COMPLETION_NOT_NEEDED = 1
    WRONG_TRIGGER = 2


class Tools:

    """ just a bunch of helpful tools to unclutter main file

    Attributes:
        syntax_regex (regex): regex to parse syntax setting
        valid_extensions (list): list of valid extentions for autocompletion
        valid_synax (list): list of valid syntaxes for this plugin
        SHOW_DEFAULT_COMPLETIONS: `None` to return from `on_query_completions`.
            This guarantees that sublime text will show default completions.
        HIDE_DEFAULT_COMPLETIONS: a valud to return from `on_query_completions`.
            Ensures nothing will be shown apart from the output of this plugin

    """

    syntax_regex = re.compile("\/([^\/]+)\.(?:tmLanguage|sublime-syntax)")

    valid_extensions = [".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx"]
    valid_syntax = ["C", "C++", "C Improved", "C++11"]

    SHOW_DEFAULT_COMPLETIONS = None
    HIDE_DEFAULT_COMPLETIONS = ([], sublime.INHIBIT_WORD_COMPLETIONS |
                                sublime.INHIBIT_EXPLICIT_COMPLETIONS)

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
        log.debug(" file has unsopported syntax: `%s`", syntax)
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
            # no correct trigger found, vut a wrong one fired instead
            log.debug(" wrong trigger fired")
            return PosStatus.WRONG_TRIGGER

        if settings.complete_all:
            return PosStatus.COMPLETION_NEEDED

        # if nothing fired we don't need to do anything
        log.debug(" no completions needed")
        return PosStatus.COMPLETION_NOT_NEEDED
