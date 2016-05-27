"""EasyClangComplete plugin for Sublime Text 3.

Provides completion suggestions for C/C++ languages based on clang

Attributes:
    completer (plugin.completion.base_completion.BaseCompleter):
        This object handles auto completion. It can be one of the following:
        - bin_complete.Completer
        - lib_complete.Completer

    log (logging.Logger): logger for this module
    settings (plugin_settings.Settings): class that encapsulates settings
"""

import sublime
import sublime_plugin
import os
import imp
import logging
import os.path as path

from threading import Thread

from .plugin import tools
from .plugin import error_vis
from .plugin import plugin_settings
from .plugin.completion import lib_complete
from .plugin.completion import bin_complete

# reload the modules
imp.reload(tools)
imp.reload(plugin_settings)
imp.reload(error_vis)
imp.reload(lib_complete)
imp.reload(bin_complete)

from .plugin.tools import SublBridge

# unfortunately because of how subl initializes the plugins I cannot move these
# inside of some class.
settings = None
completer = None

log = logging.getLogger(__name__)


def plugin_loaded():
    """called right after sublime api is ready to use. We need it to initialize
    all the different classes that encapsulate functionality. We can only
    properly init them after sublime api is available."""
    global settings
    global completer
    settings = plugin_settings.Settings()
    # init the loggers
    if settings.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # init everythin else
    if settings.use_libclang:
        log.info(" init completer based on libclang")
        completer = lib_complete.Completer(settings.clang_binary)
        if not completer.valid:
            log.error(" cannot initialize completer with libclang.")
            log.info(" falling back to using clang in a subprocess.")
            completer = None
    if not completer:
        log.info(" init completer based on clang from cmd")
        completer = bin_complete.Completer(settings.clang_binary)


class EasyClangComplete(sublime_plugin.EventListener):

    """Base class for this plugin. Most of the functionality is delegated

    Attributes:
        valid_extensions (list): list of valid extentions for autocompletion

    """
    # TODO: this should be probably in settings
    valid_extensions = [".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx"]

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
        (_, ext) = os.path.splitext(view.file_name())
        if ext in EasyClangComplete.valid_extensions:
            return True
        return False

    @staticmethod
    def needs_autocompletion(point, view):
        """Check if the cursor focuses a valid trigger

        Args:
            point (int): position of the cursor in the file as defined by subl
            view (sublime.View): current view

        Returns:
            bool: trigger is valid
        """
        if settings.complete_all:
            return True

        trigger_length = 1

        current_char = view.substr(point - trigger_length)

        if current_char == '>':
            trigger_length = 2
            if view.substr(point - trigger_length) != '-':
                return False
        if current_char == ':':
            trigger_length = 2
            if view.substr(point - trigger_length) != ':':
                return False

        word_on_the_left = view.substr(view.word(point - trigger_length))
        if word_on_the_left.isdigit():
            # don't autocomplete digits
            return False

        for trigger in settings.triggers:
            if current_char in trigger:
                return True
        return False

    @staticmethod
    def on_activated_async(view):
        """Called upon activating a view. Execution in a worker thread.

        Args:
            view (sublime.View): current view

        """
        log.debug(" on_activated_async view id %s", view.id())
        if EasyClangComplete.has_valid_extension(view):
            if completer.exists_for_view(view.id()):
                log.debug(" view %s, already has a completer", view.id())
                return
            log.debug("init completer for view id: %s", view.id())
            current_folder = path.dirname(view.file_name())
            parent_folder = path.dirname(current_folder)
            include_dirs = settings.populate_include_dirs(
                file_current_folder=current_folder,
                file_parent_folder=parent_folder)
            completer.init(
                view=view,
                includes=include_dirs,
                settings=settings)

    @staticmethod
    def on_selection_modified(view):
        """Called when selection is modified. Executed in gui thread.

        Args:
            view (sublime.View): current view
        """
        if EasyClangComplete.has_valid_extension(view):
            (row, _) = SublBridge.cursor_pos(view)
            completer.error_vis.show_popup_if_needed(view, row)

    @staticmethod
    def on_modified_async(view):
        """Called in a worker thread when view is modified

        Args:
            view (sublime.View): current view
        """
        log.debug(" on_modified_async view id %s", view.id())
        if EasyClangComplete.has_valid_extension(view):
            completer.error_vis.clear(view)

    @staticmethod
    def on_post_save_async(view):
        """On save. Executed in a worker thread.

        Args:
            view (sublime.View): current view

        """
        log.debug(" saving view: %s", view.id())
        if EasyClangComplete.has_valid_extension(view):
            completer.error_vis.erase_regions(view)
            completer.update(view, settings.errors_on_save)

    @staticmethod
    def on_close(view):
        """Called on closing the view.

        Args:
            view (sublime.View): current view

        """
        log.debug(" closing view %s", view.id())
        if EasyClangComplete.has_valid_extension(view):
            completer.remove(view.id())

    @staticmethod
    def on_query_completions(view, prefix, locations):
        """Function that is called when user queries completions in the code

        Args:
            view (sublime.View): current view
            prefix (TYPE): Description
            locations (list[int]): positions of the cursor (first if many).

        Returns:
            sublime.Completions: completions with a flag
        """
        log.debug(" on_query_completions view id %s", view.id())
        if view.is_scratch():
            return None

        if not EasyClangComplete.has_valid_extension(view):
            return None

        if completer.async_completions_ready:
            completer.async_completions_ready = False
            return (completer.completions, sublime.INHIBIT_WORD_COMPLETIONS)

        # Verify that character under the cursor is one allowed trigger
        if not EasyClangComplete.needs_autocompletion(locations[0], view):
            # send None and show completions from other plugins if available
            return None

        log.debug(" starting async auto_complete at pos: %s", locations[0])

        # create a daemon thread to update the completions
        completion_thread = Thread(
            target=completer.complete,
            args=[view, locations[0], settings.errors_on_save])
        completion_thread.deamon = True
        completion_thread.start()

        # show default completions for now
        return None
