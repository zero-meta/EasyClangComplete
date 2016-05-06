"""Summary

Attributes:
    cindex_dict (dict): dict of cindex entries for each version of clang
    log (logging.Logger): logger for this module
"""
import re
import subprocess
import importlib
import sublime
import time
import platform
import logging

from os import path
from os import listdir

from plugin.error_vis import CompileErrors
from plugin.tools import PKG_NAME

log = logging.getLogger(__name__)

class BaseCompleter:
    version_str = None
    error_vis = None

    completions = []

    async_completions_ready = False
    valid = False

    def __init__(self, clang_binary):
        """Initialize the BaseCompleter
        
        Args:
            clang_binary (str): string for clang binary e.g. 'clang-3.6++'
        
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
            # to the best of my knowledge this is the last one available on macs
            # but it is a hack, yes
            self.version_str = "3.7"
            info = {"platform": platform.system()}
            log.warning(" Wrong version reported. Reducing it to %s",
                        self.version_str, info)
        log.info(" Found clang version: %s", self.version_str)
        # initialize error visuzlization
        self.error_vis = CompileErrors()

    def remove(self, view_id):
        raise NotImplementedError("calling abstract method")

    def exists_for_view(self, view_id):
        raise NotImplementedError("calling abstract method")

    def init(self, view, includes, settings, project_folder, show_errors):
        raise NotImplementedError("calling abstract method")

    def complete(self, view, cursor_pos, show_errors):
        raise NotImplementedError("calling abstract method")

    def update(self, view, show_errors):
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
    def _parse_clang_complete_file(file):
        """parse .clang_complete file
        
        Args:
            file (str): path to a file
        
        Returns:
            list(str): parsed list of includes from the file
        """
        flags = []
        folder = path.dirname(file)
        with open(file) as f:
            content = f.readlines()
            for line in content:
                if line.startswith('-D'):
                    flags.append(line)
                elif line.startswith('-I'):
                    path_to_add = line[2:].rstrip()
                    if path.isabs(path_to_add):
                        flags.append('-I' + path.normpath(path_to_add))
                    else:
                        flags.append('-I' + path.join(folder, path_to_add))
        log.debug(" .clang_complete contains flags: %s", flags)
        return flags
