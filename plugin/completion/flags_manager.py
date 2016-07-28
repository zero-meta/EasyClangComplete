""" Module with a class for managing flags from different sources

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
    """
    Encapsulation of a search scope for code cleanness.
    """
    from_folder = None
    to_folder = None

    def __init__(self, from_folder=None, to_folder=None):
        """
        Initialize the search scope. If eny of the folders in None,
        set it to root

        Args:
            from_folder (str, optional): search from this folder
            to_folder (str, optional): search up to this folder
        """
        self.from_folder = from_folder
        self.to_folder = to_folder
        if not self.to_folder:
            self.to_folder = path.abspath('/')
        if not self.from_folder:
            self.from_folder = path.abspath('/')

    def valid(self):
        """ Is the search scope valid?

        Returns:
            bool: True if valid, False otherwise
        """
        if self.from_folder and self.to_folder:
            return True
        return False


class FlagsManager:
    """
    A class that manages all the work with flags generation and update.

    Attributes:
        CLANG_COMPLETE_FILE_NAME (str): constant name of file to store flags
        CMAKE_DB_FILE_NAME (str): constant name of cmake database file
        CMAKE_FILE_NAME (str): constant name of CMakeLists.txt file
        cmake_mask (str format): mask for cmake command with path to fill
    """
    _cmake_file = File()
    _clang_complete_file = File()
    _flags = []
    _search_scope = SearchScope()
    _use_cmake = False
    _flags_update_strategy = "ask"
    _cmake_prefix_paths = []

    _possible_prefixes = ['std', 'isystem', 'D', 'I']
    _include_prefixes = ['isystem', 'I']

    cmake_mask = 'cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON "{path}" -G Ninja'

    CMAKE_FILE_NAME = "CMakeLists.txt"
    CMAKE_DB_FILE_NAME = "compile_commands.json"
    CLANG_COMPLETE_FILE_NAME = ".clang_complete"

    def __init__(self,
                 use_cmake,
                 flags_update_strategy,
                 cmake_prefix_paths=None,
                 search_scope=SearchScope()):
        """
        Initialize the flags manager

        Args:
            use_cmake (bool): should we search for CMakeLists.txt?
            flags_update_strategy (str): how to deal with flags conflicts?
            cmake_prefix_paths (str[], optional): should we add any file paths
                to the CMAKE_PREFIX_PATH before building a cmake project?
            search_scope (tools.SearchScope, optional): search scope where to
                search for CMakeLists.txt file and .clang_complete file.
        """
        if not search_scope.valid():
            log.error(" search scope is wrong.")
            return
        if not cmake_prefix_paths:
            cmake_prefix_paths = []
        self._search_scope = search_scope
        self._use_cmake = use_cmake
        self._flags_update_strategy = flags_update_strategy
        self._cmake_prefix_paths = cmake_prefix_paths
        # expand all entries containing "~"
        self._cmake_prefix_paths \
            = [path.expanduser(x) for x in self._cmake_prefix_paths]
        log.debug(" expanded CMAKE_PREFIX_PATHs: %s", self._cmake_prefix_paths)

    def any_file_modified(self):
        """
        Any of the checked files was modified since last use.

        Returns:
            bool: True if modified, False otherwise
        """
        if self._cmake_file.was_modified():
            return True
        if self._clang_complete_file.was_modified():
            return True
        return False

    def get_flags(self, separate_includes):
        """
        A function that handles getting all the flags. It will generate new
        flags in a lazy fashion. When any changes are detected and will update
        the needed files and flags generated from them. In case no changes have
        been made to .clang_complete file or to CMakeLists.txt file it will
        just return already existing flags.

        Args: separate_includes (bool): should we separate include path from
            their identifier?

        Returns:
            str[]: flags
        """
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
                    if len(curr_flags) > 0:
                        strategy = self._flags_update_strategy
                    else:
                        # there are no current flags, so no need to ask user
                        # what to do, just write the new file content
                        strategy = "overwrite"
                    FlagsManager.write_flags_to_file(
                        new_flags, new_clang_file_path, strategy)
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
        """
        Compiles cmake given a CMakeLists.txt file and get a new compilation
        database path to further parse the generated flags. The build is
        performed in a temporary folder with a unique folder name for the
        project being built - a hex number generated from the pull path to
        current CMakeListst.txt file.

        Args:
            cmake_file (tools.file): file object for CMakeLists.txt file
            prefix_paths (str[]): paths to add to CMAKE_PREFIX_PATH before
            running `cmake`
        """
        import os
        import shutil
        import hashlib
        cmake_cmd = FlagsManager.cmake_mask.format(path=cmake_file.folder())
        unique_proj_str = hashlib.md5(
            cmake_file.full_path().encode('utf-8')).hexdigest()
        tempdir = path.join(
            Tools.get_temp_dir(), 'cmake_builds', unique_proj_str)
        # ensure a clean build
        shutil.rmtree(tempdir, ignore_errors=True)
        os.makedirs(tempdir)
        try:
            # sometimes there are variables missing to carry out the build. We
            # can set them here from the settings.
            my_env = os.environ.copy()
            my_env['CMAKE_PREFIX_PATH'] = ":".join(prefix_paths)
            log.info(' runnign command: %s', cmake_cmd)
            output = subprocess.check_output(cmake_cmd,
                                             stderr=subprocess.STDOUT,
                                             shell=True,
                                             cwd=tempdir,
                                             env=my_env)
            output_text = ''.join(map(chr, output))
        except subprocess.CalledProcessError as e:
            output_text = e.output.decode("utf-8")
            log.info(" clang process finished with code: \n%s", e.returncode)
        log.info(" cmake produced output: \n%s", output_text)

        database_path = path.join(tempdir, FlagsManager.CMAKE_DB_FILE_NAME)
        if not path.exists(database_path):
            log.error(" cmake has finished, but no compilation database.")
            return None
        return File(database_path)

    @staticmethod
    def write_flags_to_file(new_flags, file_path, strategy):
        """
        Given new set of flags, check if we need to overwrite flags and then if
        needed write these flags to the `.clang_complete` file.

        Args:
            new_flags (set(str)): new flags
            file_path (str): path to .clang_complete file
            strategy (str): strategy to deal with conflicts in flags

        """
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
        """
        Get a str representing strategy used when dealing with new flags. Does
        not change the default strategy unless "ask" starategy is default. Then
        the strategy will be picked by asking the user.

        Args:
            strategy (str): default strategy

        Returns:
            str: picked strategy
        """
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
        """Get flags from cmake compilation database
        Args: database_file (tools.File): compilation database file
            separate_includes (bool): separate include specifier from the path
            by a space
        Returns:
            set(str): flags
        """
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
        """
        Parse .clang_complete file

        Args:
            separate_includes (bool):  Separation is needed for binary complete
                if True: -I<include> turns to '-I "<include>"'.
                if False: stays -I<include>

        Returns:
            se(tstr): parsed list of includes from the file
        """
        if not path.exists(file.full_path()):
            log.debug(" .clang_complete does not exist yet. No flags present.")
            return []
        if not file.loaded():
            log.error(" cannot get flags from clang_complete_file. No file.")
            return []

        flags = set()
        with open(file.full_path()) as f:
            content = f.readlines()
            flags = FlagsManager.parse_flags(file.full_path(),
                                             content,
                                             separate_includes)
        log.debug(" .clang_complete contains flags: %s", flags)
        return flags

    @staticmethod
    def parse_flags(folder, lines, separate_includes):
        """
        Parse the flags in a given file

        Args:
            folder (str): current folder
            lines (str[]): lines to parse
            separate_includes (bool): if True "-I/blah" turns to "-I '/blah'"

        Returns:
            str[]: flags
        """
        mask = '{}{}'
        if separate_includes:
            mask = '{} "{}"'
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
