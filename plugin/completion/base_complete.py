"""Contains base class for completers

Attributes:
    log (logging.Logger): logger for this module

"""
import re
import logging

from os import path

from .. import error_vis
from .. import tools

from .flags_manager import FlagsManager
from .flags_manager import SearchScope

log = logging.getLogger(__name__)

Tools = tools.Tools


class BaseCompleter:

    """A base class for clang based completions

    Attributes:
        async_completions_ready (bool): is true after async completions ready
        completions (list): current list of completions
        error_vis (plugin.CompileErrors): object of compile errors class
        compiler_variant (CompilerVariant): compiler specific options
        flags_manager (FlagsManager): An object that manages all the flags and
            how to load them from disk to memory.
        valid (bool): is completer valid
        version_str (str): version string of format "3.4" for clang v. 3.4
    """
    version_str = None
    error_vis = None
    compiler_variant = None

    flags_manager = None

    completions = []

    async_completions_ready = False
    valid = False

    def __init__(self, clang_binary):
        """Initialize the BaseCompleter

        Args:
            clang_binary (str): string for clang binary e.g. 'clang-3.6++'

        Raises:
            RuntimeError: if clang not defined we throw an error

        """
        # check if clang binary is defined
        if not clang_binary:
            raise RuntimeError("clang binary not defined")

        # run the cmd to get the proper version of the installed clang
        self.version_str = Tools.get_clang_version_str(clang_binary)
        # initialize error visualization
        self.error_vis = error_vis.CompileErrors()

    def needs_init(self, view):
        """ Check if the completer needs init.

        Args:
            view (sublime.View): current view

        Returns:
            bool: True if init needed, False if not
        """
        # TODO: test this approach. Call it in main file
        if not self.flags_manager:
            log.debug(" flags handler not initialized. Do it.")
            return True
        if self.flags_manager.any_file_modified():
            log.debug(" .clang_complete or CMakeLists.txt were modified. "
                      "Need to reinit.")
            return True
        if self.exists_for_view(view.buffer_id()):
            log.debug(" view %s, already has a completer", view.buffer_id())
            return False
        log.debug(" need to init view '%s'", view.buffer_id())
        return True

    def remove(self, view_id):
        """
        Called when completion for this view is not needed anymore. For actual
        implementation see children of this class.

        Args:
            view_id (sublime.View): current view

        Raises:
            NotImplementedError: Guarantees we do not call this abstract method
        """
        raise NotImplementedError("calling abstract method")

    def exists_for_view(self, view_id):
        """
        Check if completer for this view is initialized and is ready to
        autocomplete. For real implementation see children.

        Args:
            view_id (int): view id

        Raises:
            NotImplementedError: Guarantees we do not call this abstract method
        """
        raise NotImplementedError("calling abstract method")

    def init(self, view, settings):
        """
        Initialize the completer for this view. For real implementation see
        children.

        Args:
            view (sublime.View): current view
            settings (Settings): plugin settings

        """
        if not view:
            return
        current_dir = path.dirname(view.file_name())
        search_scope = SearchScope(
            from_folder=current_dir,
            to_folder=settings.project_base_folder)
        self.flags_manager = FlagsManager(
            use_cmake=settings.generate_flags_with_cmake,
            flags_update_strategy=settings.cmake_flags_priority,
            cmake_prefix_paths=settings.cmake_prefix_paths,
            search_scope=search_scope)

    def complete(self, view, cursor_pos, current_job_id):
        """Function to generate completions. See children for implementation.

        Args:
            view (sublime.View): current view
            cursor_pos (int): sublime provided poistion of the cursor
            show_errors (bool): true if we want to visualize errors

        Raises:
            NotImplementedError: Guarantees we do not call this abstract method
        """
        raise NotImplementedError("calling abstract method")

    def update(self, view, show_errors):
        """Update the completer for this view. This can increase consequent
        completion speeds or is needed to just show errors.

        Args:
            view (sublime.View): this view
            show_errors (bool): controls if we show errors

        Raises:
            NotImplementedError: Guarantees we do not call this abstract method
        """
        raise NotImplementedError("calling abstract method")

    def show_errors(self, view, output):
        """ Show current complie errors

        Args:
            view (sublime.View): Current view
            output (object): opaque output to be parsed by compiler variant
        """
        errors = self.compiler_variant.errors_from_output(output)
        self.error_vis.generate(view, errors)
        self.error_vis.show_regions(view)

    def get_completions(self, hide_default_completions):
        """ Get completions. Manage hiding default ones.

        Args:
            hide_default_completions (bool): True if we hide default ones

        Returns:
            tupple: (completions, flags)
        """
        if hide_default_completions:
            log.debug(" hiding default completions")
            return (self.completions, tools.SublBridge.NO_DEFAULT_COMPLETIONS)
        else:
            log.debug(" adding clang completions to default ones")
            return self.completions

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
