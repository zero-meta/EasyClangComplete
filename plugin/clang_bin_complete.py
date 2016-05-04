"""Summary

Attributes:
    cindex_dict (dict): dict of cindex entries for each version of clang
    log (logging.Logger): logger for this module
"""
import re
import subprocess
import sublime
import time
import platform
import logging
import tempfile

from os import path
from os import listdir

from .tools import PKG_NAME

log = logging.getLogger(__name__)


class Completer:

    """Encapsulates completions based on the output from clang_binary

    Attributes:
        async_completions_ready (bool): turns true if there are completions
                                    that have become ready from an async call
        completions (list): current completions
        translation_units (dict): Dictionary of translation units for view ids
        tu_module (cindex.TranslationUnit): module for proper cindex
        version_str (str): clang version string
    """

    clang_binary = None
    version_str = None
    init_flags = ["-cc1", "-fsyntax-only", "-x c++"]
    flags = []
    std_flag = None

    completions = []
    async_completions_ready = False

    compl_regex = re.compile("COMPLETION:\s(?P<name>.*)\s:\s(?P<content>.*)")

    PARAM_TAG = "param"
    TYPE_TAG = "type"
    OPTS_TAG = "opts"
    PARAM_CHARS = "\w\s\*\&\<\>:,\(\)\$\{\}"
    group_params = "(?P<{param_tag}>[{param_chars}]+)".format(
        param_chars=PARAM_CHARS,
        param_tag=PARAM_TAG)
    group_types = "(?P<{type_tag}>[{type_chars}]+)".format(
        type_tag=TYPE_TAG,
        type_chars=PARAM_CHARS)
    group_opts = "(?P<{opts_tag}>[{type_chars}]+)".format(
        opts_tag=OPTS_TAG,
        type_chars=PARAM_CHARS)

    compl_content_regex = re.compile(
        "\<#{group_params}#\>|\[#{group_types}#\]".format(
            group_params=group_params, group_types=group_types))

    opts_regex = re.compile("{{#{}#}}".format(group_opts))

    def __init__(self, clang_binary):
        """Initialize the Completer

        Args:
            clang_binary (str): string for clang binary e.g. 'clang-3.6++'
            verbose (bool): shows if we should show debug info

        """
        # check if clang binary is defined
        if not clang_binary:
            log.critical(" clang binary not defined!")
            return

        Completer.clang_binary = clang_binary
        # run the cmd to get the proper version of the installed clang
        check_version_cmd = clang_binary + " --version"
        try:
            log.info(" Getting version from command: `%s`", check_version_cmd)
            output = subprocess.check_output(check_version_cmd, shell=True)
            output_text = ''.join(map(chr, output))
        except subprocess.CalledProcessError as e:
            error_dict = {"clang_binary": clang_binary,
                          "error": e,
                          "advice": "make sure `clang_binary` is in PATH"}
            log.error(" Calling clang binary failed.", error_dict)
            return

        # now we have the output, and can extract version from it
        version_regex = re.compile("\d.\d")
        found = version_regex.search(output_text)
        Completer.version_str = found.group()
        log.info(" Found clang version: %s",
                 Completer.version_str)

    def get_diagnostics(self, view_id):
        log.debug(" not implemented")
        return None

    def remove_tu(self, view_id):
        self.flags = []

    def has_completer(self, view_id):
        if len(self.flags) > 0:
            return True
        return False

    def init_completer(self, view_id, initial_includes, search_include_file,
                       std_flag, file_name, file_body, project_base_folder):
        """Initialize the completer

        Args:
            view_id (int): view id
            initial_includes (str[]): includes from settings
            search_include_file (bool): should we search for .clang_complete?
            std_flag (str): std flag, e.g. std=c++11
            file_name (str): file full path
            file_body (str): content of the file
            project_base_folder (str): project folder

        """
        file_current_folder = path.dirname(file_name)

        # initialize unsaved files
        files = [(file_name, file_body)]

        # set std_flag
        self.std_flag = std_flag

        # init needed variables from settings
        self.flags = []
        for include in initial_includes:
            self.flags.append('-I' + include)

        # support .clang_complete file with -I<indlude> entries
        if search_include_file:
            log.debug(" searching for .clang_complete in %s up to %s",
                      file_current_folder, project_base_folder)
            clang_complete_file = Completer._search_clang_complete_file(
                file_current_folder, project_base_folder)
            if clang_complete_file:
                log.debug(" found .clang_complete: %s", clang_complete_file)
                flags = Completer._parse_clang_complete_file(
                    clang_complete_file)
                self.flags += flags

        log.debug(" clang flags are: %s", self.flags)

    def complete(self, view, cursor_pos):
        """This function is called asynchronously to create a list of
        autocompletions. Using the current translation unit it queries libclang
        for the possible completions.

        Args:
            view (sublime.View): current view
            cursor_pos (int): sublime provided poistion of the cursor

        """

        file_body = view.substr(sublime.Region(0, view.size()))
        (row, col) = view.rowcol(cursor_pos)
        row += 1
        col += 1

        tempdir = tempfile.gettempdir()
        temp_file_name = path.join(tempdir, 'test.cpp')
        with open(temp_file_name, "w", encoding='utf-8') as tmp_file:
            tmp_file.write(file_body)

        complete_at_str = "{complete_flag} {file}:{row}:{col} {file}".format(
            complete_flag="-code-completion-at",
            file=temp_file_name, row=row, col=col)

        complete_cmd = "{binary} {init} {std} {complete_at} {includes}".format(
            binary=Completer.clang_binary,
            init=" ".join(Completer.init_flags),
            std=self.std_flag,
            complete_at=complete_at_str,
            includes=" ".join(self.flags))
        log.debug(" clang command: \n%s", complete_cmd)
        # execute clang code completion
        start = time.time()
        log.debug(" started code complete for view %s", view.id())

        try:
            output = subprocess.check_output(complete_cmd, shell=True)
            output_text = ''.join(map(chr, output))
        except subprocess.CalledProcessError as e:
            output_text = e.output.decode("utf-8")
            log.critical(" %s", output_text)
        # Process clang output, find COMPLETION lines and return them with a
        # little formating
        complete_results = output_text.splitlines()
        end = time.time()
        log.debug(" code complete done in %s seconds", end - start)
        log.debug(" completions: %s", complete_results)

        self.completions = Completer._process_completions(
            complete_results)
        self.async_completions_ready = True
        Completer._reload_completions(view)

    def reparse(self, view_id):
        """Reparse the translation unit. This speeds up completions
        significantly, so we perform this upon file save.

        Args:
            view_id (int): view id

        Returns:
            bool: reparsed successfully
        """
        return True

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
    def _process_completions(complete_results):
        """Create snippet-like structures from a list of completions

        Args:
            complete_results (list): raw completions list

        Returns:
            list: updated completions
        """
        class Parser:
            place_holders = 0

            def tokenize_params(match):
                Parser.place_holders += 1
                dict_match = match.groupdict()
                if dict_match[Completer.PARAM_TAG]:
                    return "${{{count}:{text}}}".format(
                        count=Parser.place_holders,
                        text=dict_match[Completer.PARAM_TAG])
                return ''

            def make_pretty(match):
                dict_match = match.groupdict()
                if dict_match[Completer.PARAM_TAG]:
                    return dict_match[Completer.PARAM_TAG]
                if dict_match[Completer.TYPE_TAG]:
                    return dict_match[Completer.TYPE_TAG] + ' '
                return ''

        completions = []
        for completion in complete_results:
            pos_search = Completer.compl_regex.search(completion)
            if not pos_search:
                log.warning(" completion %s did not match pattern %s",
                            completion, Completer.compl_regex)
                continue
            comp_dict = pos_search.groupdict()
            log.debug("completions parsed: %s", comp_dict)
            trigger = comp_dict['name']
            contents = re.sub(Completer.compl_content_regex,
                              Parser.tokenize_params,
                              comp_dict['content'])
            contents = re.sub(Completer.opts_regex, '', contents)
            hint = re.sub(Completer.compl_content_regex,
                          Parser.make_pretty,
                          comp_dict['content'])
            hint = re.sub(Completer.opts_regex, '', hint)
            completions.append([trigger + "\t" + hint, contents])
        return completions

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
