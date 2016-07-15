""" Module with a class for .clang_complete file

Attributes:
    log (logging.log): logger for this module
"""
import logging
import sublime
import subprocess

from os import path

from ..tools import Tools
from ..tools import File

log = logging.getLogger(__name__)


class SearchScope:
    """docstring for SearchScope"""
    from_folder = None
    to_folder = None

    def __init__(self, from_folder=None, to_folder=None):
        self.from_folder = from_folder
        self.to_folder = to_folder

    def valid(self):
        if self.from_folder and self.to_folder:
            return True
        return False


class FlagsManager:

    _cmake_file = File()
    _clang_complete_file = File()
    _flags = []
    _search_scope = SearchScope()
    _use_cmake = False
    _flags_update_strategy = "ask"
    _cmake_prefix_paths = []

    _possible_prefixes = ['std', 'isystem', 'D', 'I']
    _include_prefixes = ['isystem', 'I']

    cmake_mask = 'cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON {path}'

    CMAKE_FILE_NAME = "CMakeLists.txt"
    CMAKE_DB_FILE_NAME = "compile_commands.json"
    CLANG_COMPLETE_FILE_NAME = ".clang_complete"

    def __init__(self,
                 use_cmake,
                 flags_update_strategy,
                 cmake_prefix_paths=[],
                 search_scope=SearchScope()):
        if not search_scope.valid():
            log.error(" search scope is wrong.", search_scope)
        self._search_scope = search_scope
        self._use_cmake = use_cmake
        self._flags_update_strategy = flags_update_strategy
        self._cmake_prefix_paths = cmake_prefix_paths
        # expand all entries containing "~"
        self._cmake_prefix_paths \
            = [path.expanduser(x) for x in self._cmake_prefix_paths]
        log.debug(" expanded CMAKE_PREFIX_PATHs: %s", self._cmake_prefix_paths)

    def any_file_modified(self):
        if self._cmake_file.was_modified():
            return True
        if self._clang_complete_file.was_modified():
            return True
        return False

    def get_flags(self, separate_includes):
        if self._use_cmake and not self._cmake_file.loaded():
            # CMakeLists.txt was not loaded yet, so search for it
            log.debug(" cmake file not loaded yet. Searching for one...")
            self._cmake_file = File.search(
                file_name=FlagsManager.CMAKE_FILE_NAME,
                from_folder=self._search_scope.from_folder,
                to_folder=self._search_scope.to_folder,
                search_content="project")

        if self._use_cmake and self._cmake_file.was_modified():
            # generate a .clang_complete file from cmake file if cmake file
            # exists and was modified
            log.debug(" CMakeLists.txt was modified."
                      " Generate new .clang_complete")
            compilation_db = FlagsManager.compile_cmake(
                cmake_file=self._cmake_file,
                prefix_paths=self._cmake_prefix_paths)
            if compilation_db:
                new_flags = FlagsManager.flags_from_database(
                    database_file=compilation_db,
                    separate_includes=separate_includes)
                new_clang_file_path = path.join(
                    self._cmake_file.folder(),
                    FlagsManager.CLANG_COMPLETE_FILE_NAME)
                # there is no need to modify anything if the flags have not
                # changed since we have last read them
                curr_flags = FlagsManager.flags_from_clang_file(
                                file=File(new_clang_file_path),
                                separate_includes=separate_includes)
                if len(new_flags.symmetric_difference(curr_flags)) > 0:
                    log.debug("'%s' is not equal to '%s' by %s so update",
                              new_flags, curr_flags,
                              new_flags.symmetric_difference(curr_flags))
                    FlagsManager.write_flags_to_file(
                        new_flags, new_clang_file_path,
                        self._flags_update_strategy)
                else:
                    log.debug(" the flags have not changed so we don't "
                              "modify the .clang_complete file")
            else:
                log.warning(" could not get compilation database from cmake")

        if not self._clang_complete_file.loaded():
            log.debug(" .clang_complete not loaded. Searching for one...")
            self._clang_complete_file = File.search(
                file_name=FlagsManager.CLANG_COMPLETE_FILE_NAME,
                from_folder=self._search_scope.from_folder,
                to_folder=self._search_scope.to_folder)

        if self._clang_complete_file.was_modified():
            log.debug(" .clang_complete modified. Load new flags.")
            self._flags = FlagsManager.flags_from_clang_file(
                self._clang_complete_file, separate_includes)

        # the flags are now in final state, we can return them
        return self._flags

    @staticmethod
    def compile_cmake(cmake_file, prefix_paths):
        import os
        import hashlib
        cmake_cmd = FlagsManager.cmake_mask.format(path=cmake_file.folder())
        unique_proj_str = hashlib.md5(
            cmake_file.full_path().encode('utf-8')).hexdigest()
        tempdir = path.join(
            Tools.get_temp_dir(), 'cmake_builds', unique_proj_str)
        if not path.exists(tempdir):
            os.makedirs(tempdir)
        try:
            my_env = os.environ.copy()
            # TODO: add variables that are otherwise missing
            my_env['CMAKE_PREFIX_PATH'] = ":".join(prefix_paths)
            output = subprocess.check_output(cmake_cmd,
                                             stderr=subprocess.STDOUT,
                                             shell=True,
                                             cwd=tempdir,
                                             env=my_env)
            output_text = ''.join(map(chr, output))
        except subprocess.CalledProcessError as e:
            output_text = e.output.decode("utf-8")
            log.info(" clang process finished with code: \n%s", e.returncode)
            log.info(" clang process output: \n%s", output_text)
        log.debug(" cmake produced output: \n%s", output_text)

        database_path = path.join(tempdir, FlagsManager.CMAKE_DB_FILE_NAME)
        if not path.exists(database_path):
            log.error(" cmake has finished, but no compilation database.")
            return None
        return File(database_path)

    @staticmethod
    def write_flags_to_file(new_flags, file_path, strategy):
        if path.exists(file_path):
            log.debug(" path already exists")
            flag_strategy = FlagsManager.get_flags_strategy(strategy)
            log.debug(" picked '%s' strategy.", flag_strategy)
            if flag_strategy == "keep_old":
                return
            if flag_strategy == "merge":
                # union of two flags sets
                curr_flags = set(FlagsManager.flags_from_clang_file(
                    File(file_path), separate_includes=False))
                new_flags = new_flags.union(curr_flags)
            # unhandled is only "overwrite". "ask" is not possible here.
        f = open(file_path, 'w')
        # write file
        f.seek(0)
        f.write('\n'.join(new_flags) + '\n')
        f.close()

    @staticmethod
    def get_flags_strategy(strategy):
        if strategy == "ask":
            user_pick = sublime.yes_no_cancel_dialog(
                ".clang_complete file exists. What do you want to do?",
                "Merge!", "Overwrite!")
            if user_pick == sublime.DIALOG_YES:
                return "merge"
            if user_pick == sublime.DIALOG_NO:
                return "overwrite"
            if user_pick == sublime.DIALOG_CANCEL:
                return "keep_old"
        else:
            return strategy

    @staticmethod
    def flags_from_database(database_file, separate_includes):
        import json
        data = None
        with open(database_file.full_path()) as data_file:
            data = json.load(data_file)
        if not data:
            return None
        flags_set = set()
        for entry in data:
            command = entry['command']
            all_command_parts = command.split(' -')
            current_flags = FlagsManager.parse_flags(
                database_file, all_command_parts, separate_includes)
            flags_set = flags_set.union(current_flags)
        log.debug(" flags set: %s", flags_set)
        return flags_set

    @staticmethod
    def flags_from_clang_file(file, separate_includes):
        """parse .clang_complete file

        Args:
            separate_includes (bool):  Separation is needed for binary complete
                if True: -I<include> turns to '-I "<include>"'.
                if False: stays -I<include>

        Returns:
            list(str): parsed list of includes from the file

        Deleted Parameters:
            file (str): path to a file
        """
        if not file.loaded():
            log.error(" cannot get flags from clang_complete_file. No file.")
            return []

        flags = set()
        with open(file.full_path()) as f:
            content = f.readlines()
            flags = FlagsManager.parse_flags(file, content, separate_includes)
        log.debug(" .clang_complete contains flags: %s", flags)
        return flags

    @staticmethod
    def parse_flags(file, lines, separate_includes):
        mask = '{}{}'
        if separate_includes:
            mask = '{} "{}"'
        folder = file.folder()
        flags = set()
        log.debug(" all lines: %s", lines)
        for line in lines:
            for prefix in FlagsManager._possible_prefixes:
                full_prefix = '-' + prefix
                if not line.startswith('-'):
                    line = '-' + line
                if line.startswith(full_prefix):
                    flag_content = line[len(full_prefix):].strip()
                    flag_content = flag_content.strip('"')
                    if prefix in FlagsManager._include_prefixes:
                        if not path.isabs(flag_content):
                            flag_content = path.join(folder, flag_content)
                    flags.add(mask.format(full_prefix, flag_content))
        return flags
