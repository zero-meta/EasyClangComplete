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

from plugin.error_vis import CompileErrors
from plugin.error_vis import FORMAT_BINARY
from plugin.tools import PKG_NAME
from plugin.completion.base_complete import Completer

log = logging.getLogger(__name__)


class ClangBinCompleter(Completer):

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

    init_flags = ["-cc1", "-fsyntax-only", "-x c++"]
    flags_dict = {}
    std_flag = None

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
        # init common completer interface
        Completer.__init__(self, clang_binary)

    def remove(self, view_id):
        if view_id in self.flags_dict:
            self.flags_dict[view_id] = []

    def exists_for_view(self, view_id):
        if view_id not in self.flags_dict:
            log.debug(" no build flags for view: %s", view_id)
            return False
        if len(self.flags_dict[view_id]) > 0:
            return True
        return False

    def init(self, view, includes, settings, project_folder):
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
        file_name = view.file_name()
        file_body = view.substr(sublime.Region(0, view.size()))
        file_folder = path.dirname(file_name)

        # initialize unsaved files
        files = [(file_name, file_body)]

        # set std_flag
        self.std_flag = std_flag

        # init needed variables from settings
        self.flags_dict[view.id()] = []
        for include in includes:
            self.flags_dict[view.id()].append('-I' + include)

        # support .clang_complete file with -I<indlude> entries
        if search_include_file:
            log.debug(" searching for .clang_complete in %s up to %s",
                      file_folder, project_folder)
            clang_complete_file = Completer._search_clang_complete_file(
                file_folder, project_folder)
            if clang_complete_file:
                log.debug(" found .clang_complete: %s", clang_complete_file)
                flags = Completer._parse_clang_complete_file(
                    clang_complete_file)
                self.flags_dict[view.id()] += flags

        log.debug(" clang flags are: %s", self.flags)

    def complete(self, view, cursor_pos):
        """This function is called asynchronously to create a list of
        autocompletions. Using the current translation unit it queries libclang
        for the possible completions.

        Args:
            view (sublime.View): current view
            cursor_pos (int): sublime provided poistion of the cursor

        """
        if not view.id() in self.flags_dict:
            log.error(" cannot complete view: %s", view.id())
            return None

        file_body = view.substr(sublime.Region(0, view.size()))
        (row, col) = view.rowcol(cursor_pos)
        row += 1
        col += 1

        tempdir = tempfile.gettempdir()
        temp_file_name = path.join(tempdir, path.basename(view.file_name()))
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
            includes=" ".join(self.flags_dict[view.id()]))
        log.debug(" clang command: \n%s", complete_cmd)
        # execute clang code completion
        start = time.time()
        log.debug(" started code complete for view %s", view.id())

        try:
            output = subprocess.check_output(complete_cmd, 
                                             stderr=subprocess.STDOUT, 
                                             shell=True)
            output_text = ''.join(map(chr, output))
        except subprocess.CalledProcessError as e:
            output_text = e.output.decode("utf-8")
            log.error(" clang process finished with code: \n%s", e.returncode)
            log.error(" clang process output: \n%s", output_text)
            self.error_vis.generate(view, output_text.splitlines(), FORMAT_BINARY)
            self.error_vis.show_regions(view)
            # we could stop here, but we continue as sometimes there are still
            # valid completions even though there were errors encountered

        # Process clang output, find COMPLETION lines and return them with a
        # little formating
        raw_complete = output_text.splitlines()
        end = time.time()
        log.debug(" code complete done in %s seconds", end - start)

        self.completions = ClangBinCompleter._parse_completions(raw_complete)
        self.async_completions_ready = True
        Completer._reload_completions(view)

    def update(self, view):
        file_body = view.substr(sublime.Region(0, view.size()))

        tempdir = tempfile.gettempdir()
        temp_file_name = path.join(tempdir, path.basename(view.file_name()))
        with open(temp_file_name, "w", encoding='utf-8') as tmp_file:
            tmp_file.write(file_body)

        complete_cmd = "{binary} {init} {std} {file} {includes}".format(
            binary=Completer.clang_binary,
            init=" ".join(Completer.init_flags),
            std=self.std_flag,
            file=temp_file_name,
            includes=" ".join(self.flags))
        log.debug(" clang command: \n%s", complete_cmd)
        # execute clang code completion
        start = time.time()
        log.debug(" started rebuilding view %s", view.id())

        try:
            output = subprocess.check_output(complete_cmd, 
                                             stderr=subprocess.STDOUT, 
                                             shell=True)
            output_text = ''.join(map(chr, output))
        except subprocess.CalledProcessError as e:
            output_text = e.output.decode("utf-8")
            log.error(" clang process finished with code: \n%s", e.returncode)
            log.error(" clang process output: \n%s", output_text)
            self.error_vis.generate(view, output_text.splitlines(), FORMAT_BINARY)
            self.error_vis.show_regions(view)
            return False

        end = time.time()
        log.debug(" rebuilding done in %s seconds", end - start)
        return True

    @staticmethod
    def _parse_completions(complete_results):
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
