"""Summary

Attributes:
    log (logging.Logger): logger for this module

Deleted Attributes:
    cindex_dict (dict): dict of cindex entries for each version of clang
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
from plugin.completion.base_complete import BaseCompleter

log = logging.getLogger(__name__)


class Completer(BaseCompleter):

    """Encapsulates completions based on the output from clang_binary
    
    Attributes:
        
        clang_binary (str): e.g. "clang++" or "clang++-3.6"
        flags_dict (dict): compilation flags lists for each view
        init_flags (list): flags that every command needs
        std_flag (TYPE): std flag, e.g. "std=c++11"
        
        completions (list): current completions
        async_completions_ready (bool): turns true if there are completions
                                    that have become ready from an async call
    
        compl_regex (regex): regex to parse raw completion into name and content
        compl_content_regex (regex): regex to parse the content of the completion
        opts_regex (regex): regex to detect optional parameters
    
        group_params (str): string that describes a group to capture function parameters
        group_types (str): string that describes a group to capture type names
        group_opts (str): string that describes a group to capture optional parameters
        
        PARAM_CHARS (str): chars allowed to be part of function or type
        PARAM_TAG (str): function params tag for convenience
        TYPE_TAG (str): type name tag for convenience
        OPTS_TAG (str): optional params tag for convenience
    
    """
    clang_binary = None

    init_flags = ["-c", "-fsyntax-only", "-x c++"]
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
    group_opts = "(?P<{opts_tag}>[{opts_chars}]+)".format(
        opts_tag=OPTS_TAG,
        opts_chars=PARAM_CHARS)

    compl_content_regex = re.compile(
        "\<#{group_params}#\>|\[#{group_types}#\]".format(
            group_params=group_params, group_types=group_types))

    opts_regex = re.compile("{{#{}#}}".format(group_opts))

    def __init__(self, clang_binary):
        """Initialize the Completer
        
        Args:
            clang_binary (str): string for clang binary e.g. 'clang-3.6++'
        
        """
        # init common completer interface
        BaseCompleter.__init__(self, clang_binary)
        Completer.clang_binary = clang_binary

    def remove(self, view_id):
        """remove compile flags for view
        
        Args:
            view_id (int): current view id
        """
        if view_id in self.flags_dict:
            self.flags_dict[view_id] = []

    def exists_for_view(self, view_id):
        """check if compile flags exist for view id
        
        Args:
            view_id (int): current view id
        
        Returns:
            bool: compile flags exist for this view
        """
        if view_id not in self.flags_dict:
            log.debug(" no build flags for view: %s", view_id)
            return False
        if len(self.flags_dict[view_id]) > 0:
            return True
        return False

    def init(self, view, includes, settings, project_folder):
        """Initialize the completer
        
        Args:
            view (sublime.View): current view
            includes (list): includes from settings
            settings (Settings): plugin settings
            project_folder (str): current project folder
        
        """
        file_name = view.file_name()
        file_body = view.substr(sublime.Region(0, view.size()))
        file_folder = path.dirname(file_name)

        # initialize unsaved files
        files = [(file_name, file_body)]

        # set std_flag
        self.std_flag = settings.std_flag

        # init needed variables from settings
        self.flags_dict[view.id()] = []
        for include in includes:
            self.flags_dict[view.id()].append('-I "{}"'.format(include))

        # support .clang_complete file with -I "<indlude>" entries
        if settings.search_clang_complete:
            log.debug(" searching for .clang_complete in %s up to %s",
                      file_folder, project_folder)
            clang_complete_file = Completer._search_clang_complete_file(
                file_folder, project_folder)
            if clang_complete_file:
                log.debug(" found .clang_complete: %s", clang_complete_file)
                flags = Completer._parse_clang_complete_file(
                    clang_complete_file)
                self.flags_dict[view.id()] += flags

        log.debug(" clang flags are: %s", self.flags_dict[view.id()])

    def complete(self, view, cursor_pos, show_errors):
        """This function is called asynchronously to create a list of
        autocompletions. It builds up a clang command that is then executed
        as a subprocess. The output is parsed for completions and/or errors
        
        Args:
            view (sublime.View): current view
            cursor_pos (int): sublime provided poistion of the cursor
            show_errors (bool): true if we want to visualize errors
        
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

        complete_at_str = "{complete_flag}={file}:{row}:{col} {file}".format(
            complete_flag="-Xclang -code-completion-at",
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
            log.info(" clang process finished with code: \n%s", e.returncode)
            log.info(" clang process output: \n%s", output_text)
            if show_errors:
                self.error_vis.generate(view, output_text.splitlines(), 
                                        FORMAT_BINARY)
                self.error_vis.show_regions(view)
            # we could stop here, but we continue as sometimes there are still
            # valid completions even though there were errors encountered

        # Process clang output, find COMPLETION lines and return them with a
        # little formating
        raw_complete = output_text.splitlines()
        end = time.time()
        log.debug(" code complete done in %s seconds", end - start)

        self.completions = Completer._parse_completions(raw_complete)
        self.async_completions_ready = True
        Completer._reload_completions(view)

    def update(self, view, show_errors):
        """update build for current view
        
        Args:
            view (sublime.View): this view
            show_errors (TYPE): do we need to show errors? If not this is a 
                dummy function as we gain nothing from building it with binary.
        
        """
        if view.id() not in self.flags_dict:
            log.error(" Cannot update view %s. No build flags.", view.id())
            return False

        if not show_errors:
            # in this class there is no need to rebuild the file. It brings no
            # benefits. We only want to do it if we need to show errors.
            return False

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
            includes=" ".join(self.flags_dict[view.id()]))
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
            log.info(" clang process finished with code: \n%s", e.returncode)
            log.info(" clang process output: \n%s", output_text)
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
            """Help class to parse completions with regex
            
            Attributes:
                place_holders (int): number of place holders in use
            """
            def __init__(self):
                self.place_holders = 0

            def tokenize_params(self, match):
                """Create tockens from a match. Used as part or re.sub function
                
                Args:
                    match (re.match): current match
                
                Returns:
                    str: current match, wrapped in snippet
                """
                dict_match = match.groupdict()
                if dict_match[Completer.PARAM_TAG]:
                    self.place_holders += 1
                    return "${{{count}:{text}}}".format(
                        count=self.place_holders,
                        text=dict_match[Completer.PARAM_TAG])
                return ''

            def make_pretty(self, match):
                """Process raw match and remove ugly placeholders. Needed to
                have a human readable text for each completion.
                
                Args:
                    match (re.match): current completion
                
                Returns:
                    str: match stripped from unneeded placeholders
                """
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
            parser = Parser()
            contents = re.sub(Completer.compl_content_regex,
                              parser.tokenize_params,
                              comp_dict['content'])
            contents = re.sub(Completer.opts_regex, '', contents)
            hint = re.sub(Completer.compl_content_regex,
                          parser.make_pretty,
                          comp_dict['content'])
            hint = re.sub(Completer.opts_regex, '', hint)
            completions.append([trigger + "\t" + hint, contents])
        return completions
