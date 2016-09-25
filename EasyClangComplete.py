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
import imp
import logging

from threading import Thread

from .plugin import tools
from .plugin import error_vis
from .plugin import plugin_settings
from .plugin.completion import lib_complete
from .plugin.completion import bin_complete
from .plugin.completion import flags_manager

# reload the modules
imp.reload(tools)
imp.reload(flags_manager)
imp.reload(plugin_settings)
imp.reload(error_vis)
imp.reload(lib_complete)
imp.reload(bin_complete)

# some useful aliases
SublBridge = tools.SublBridge
Tools = tools.Tools
PosStatus = tools.PosStatus

# unfortunately because of how sublime text initializes the plugins I cannot
# move these inside of some class.
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
    # As the plugin have just loaded, we might have missed an activation event
    # for the active view so completion will not work for it until re-activated.
    # Force active view initialization in that case.
    EasyClangComplete.on_activated_async(sublime.active_window().active_view())


class EasyClangComplete(sublime_plugin.EventListener):

    """Base class for this plugin. Most of the functionality is delegated

    """
    @staticmethod
    def on_activated_async(view):
        """Called upon activating a view. Execution in a worker thread.

        Args:
            view (sublime.View): current view

        """
        log.debug(" on_activated_async view id %s", view.buffer_id())
        if Tools.is_valid_view(view):
            if not completer:
                return
            if not completer.needs_init(view):
                return
            log.debug("init completer for view id: %s", view.buffer_id())
            completer.init(view, settings)

    @staticmethod
    def on_selection_modified(view):
        """Called when selection is modified. Executed in gui thread.

        Args:
            view (sublime.View): current view
        """
        if Tools.is_valid_view(view):
            (row, _) = SublBridge.cursor_pos(view)
            if not completer:
                return
            completer.error_vis.show_popup_if_needed(view, row)

    @staticmethod
    def on_modified_async(view):
        """Called in a worker thread when view is modified

        Args:
            view (sublime.View): current view
        """
        if Tools.is_valid_view(view):
            log.debug(" on_modified_async view id %s", view.buffer_id())
            if not completer:
                return
            completer.error_vis.clear(view)

    @staticmethod
    def on_post_save_async(view):
        """On save. Executed in a worker thread.

        Args:
            view (sublime.View): current view

        """
        if Tools.is_valid_view(view):
            log.debug(" saving view: %s", view.buffer_id())
            if not completer:
                return
            completer.error_vis.erase_regions(view)
            completer.update(view, settings.errors_on_save)

    @staticmethod
    def on_close(view):
        """Called on closing the view.

        Args:
            view (sublime.View): current view

        """
        if Tools.is_valid_view(view):
            log.debug(" closing view %s", view.buffer_id())
            if not completer:
                return
            completer.remove(view.buffer_id())

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
        log.debug(" on_query_completions view id %s", view.buffer_id())
        log.debug(" prefix: %s, locations: %s" % (prefix, locations))

        if not Tools.is_valid_view(view):
            log.debug(" not a valid view")
            return Tools.SHOW_DEFAULT_COMPLETIONS

        if not completer:
            log.debug(" no completer")
            return Tools.SHOW_DEFAULT_COMPLETIONS

        if completer.async_completions_ready:
            completer.async_completions_ready = False
            log.debug(" returning existing completions")
            return completer.get_completions(settings.hide_default_completions)

        # Verify that character under the cursor is one allowed trigger
        pos_status = Tools.get_position_status(locations[0], view, settings)
        if pos_status == PosStatus.WRONG_TRIGGER:
            # we are at a wrong trigger, remove all completions from the list
            log.debug(" wrong trigger")
            log.debug(" hiding default completions")
            return Tools.HIDE_DEFAULT_COMPLETIONS
        if pos_status == PosStatus.COMPLETION_NOT_NEEDED:
            log.debug(" completion not needed")
            # show default completions for now if allowed
            if settings.hide_default_completions:
                log.debug(" hiding default completions")
                return Tools.HIDE_DEFAULT_COMPLETIONS
            log.debug(" showing default completions")
            return Tools.SHOW_DEFAULT_COMPLETIONS

        # create a daemon thread to update the completions
        log.debug(" starting async auto_complete at pos: %s", locations[0])
        completion_thread = Thread(
            target=completer.complete,
            args=[view, locations[0], settings.errors_on_save])
        completion_thread.deamon = True
        completion_thread.start()

        # show default completions for now if allowed
        if settings.hide_default_completions:
            log.debug(" hiding default completions")
            return Tools.HIDE_DEFAULT_COMPLETIONS
        log.debug(" showing default completions")
        return Tools.SHOW_DEFAULT_COMPLETIONS
