"""Contains base class for completers

Attributes:
    log (logging.Logger): logger for this module

"""
import re
import subprocess
import platform
import logging

from os import path
from os import listdir

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

    def init(self, view, includes, settings):
        """Initialize the completer for this view. For real implementation see
        children.

        Args:
            view (sublime.View): current view
            includes (list): includes from settings
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
    def _search_clang_complete_file(start_folder, stop_folder):
        """search for .clang_complete file up the tree

        Args:
            start_folder (str): path to folder where we start the search
            stop_folder (str): path to folder we should not go beyond

        Returns:
            str: path to .clang_complete file or None if not found
        """
        current_folder = start_folder
        one_past_stop_folder = path.dirname(stop_folder)
        while current_folder != one_past_stop_folder:
            for file in listdir(current_folder):
                if file == ".clang_complete":
                    return path.join(current_folder, file)
            if current_folder == path.dirname(current_folder):
                break
            current_folder = path.dirname(current_folder)
        return None

    @staticmethod
    def _parse_clang_complete_file(file, separate_includes):
        """parse .clang_complete file

        Args:
            file (str): path to a file
            separate_includes (bool): if True: -I<include> turns to '-I "<include>"'.
                                      if False: stays -I<include>
                                      Separation is needed for binary completion

        Returns:
            list(str): parsed list of includes from the file
        """
        flags = []
        folder = path.dirname(file)
        mask = '-I{}'
        if separate_includes:
            mask = '-I "{}"'
        with open(file) as f:
            content = f.readlines()
            for line in content:
                if line.startswith('-D'):
                    flags.append(line)
                elif line.startswith('-I'):
                    path_to_add = line[2:].rstrip()
                    if path.isabs(path_to_add):
                        flags.append(mask.format(
                            path.normpath(path_to_add)))
                    else:
                        flags.append(mask.format(
                            path.join(folder, path_to_add)))
        log.debug(" .clang_complete contains flags: %s", flags)
        return flags
