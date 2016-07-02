"""Contains base class for completers

Attributes:
    log (logging.Logger): logger for this module

"""
import re
import subprocess
import platform
import logging

from .. import error_vis
from .. import tools

log = logging.getLogger(__name__)


class BaseCompleter:

    """A base class for clang based completions

    Attributes:
        async_completions_ready (bool): is true after async completions ready
        completions (list): current list of completions
        error_vis (plugin.CompileErrors): object of compile errors class
        valid (bool): is completer valid
        version_str (str): version string of format "3.4" for clang v. 3.4
    """
    version_str = None
    error_vis = None

    flags_file = None

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
        check_version_cmd = clang_binary + " --version"
        log.info(" Getting version from command: `%s`", check_version_cmd)
        output = subprocess.check_output(check_version_cmd, shell=True)
        output_text = ''.join(map(chr, output))

        # now we have the output, and can extract version from it
        version_regex = re.compile("\d.\d")
        found = version_regex.search(output_text)
        self.version_str = found.group()
        if self.version_str > "3.8" and platform.system() == "Darwin":
            # info from this table: https://gist.github.com/yamaya/2924292
            osx_version = self.version_str
            self.version_str = tools.OSX_CLANG_VERSION_DICT[osx_version]
            info = {"platform": platform.system()}
            log.warning(
                " OSX version %s reported. Reducing it to %s. Info: %s",
                osx_version, self.version_str, info)
        log.info(" Found clang version: %s", self.version_str)
        # initialize error visuzlization
        self.error_vis = error_vis.CompileErrors()

    def needs_init(self, view):
        """ Check if the completer needs init.

        Args:
            view (sublime.View): current view

        Returns:
            bool: True if init needed, False if not
        """
        # TODO: test this approach. Call it in main file
        if not self.flags_file:
            log.debug(" .clang_complete file handler not initialized.")
            return True
        if self.flags_file.was_modified():
            log.debug(" .clang_complete file was modified. Need to reinit.")
            return True
        if self.exists_for_view(view.buffer_id()):
            log.debug(" view %s, already has a completer", view.buffer_id())
            return False
        log.debug(" need to init view '%s'", view.buffer_id())
        return True

    def remove(self, view_id):
        """called when completion for this view is not needed anymore.
        For actual implementation see children of this class.

        Args:
            view_id (sublime.View): current view

        Raises:
            NotImplementedError: Guarantees we do not call this abstract method
        """
        raise NotImplementedError("calling abstract method")

    def exists_for_view(self, view_id):
        """check if completer for this view is initialized and is ready to
        autocomplete. For real implementation see children.

        Args:
            view_id (int): view id

        Raises:
            NotImplementedError: Guarantees we do not call this abstract method
        """
        raise NotImplementedError("calling abstract method")

    def init(self, view, settings):
        """Initialize the completer for this view. For real implementation see
        children.

        Args:
            view (sublime.View): current view
            settings (Settings): plugin settings

        Raises:
            NotImplementedError: Guarantees we do not call this abstract method
        """
        raise NotImplementedError("calling abstract method")

    def complete(self, view, cursor_pos, show_errors):
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

    @staticmethod
    def run_command(command):
        """ Run a generic command in a subprocess

        Args:
            command (str): command to run

        Returns:
            str: raw command output
        """
        try:
            output = subprocess.check_output(command,
                                             stderr=subprocess.STDOUT,
                                             shell=True)
            output_text = ''.join(map(chr, output))
        except subprocess.CalledProcessError as e:
            output_text = e.output.decode("utf-8")
            log.info(" clang process finished with code: \n%s", e.returncode)
            log.info(" clang process output: \n%s", output_text)
        return output_text
