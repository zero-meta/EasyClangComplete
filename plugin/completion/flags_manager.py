""" Module with a class for .clang_complete file

Attributes:
    log (logging.log): logger for this module
"""
import logging
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

    cmake_mask = "cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON {}"

    CMAKE_FILE_NAME = "CMakeLists.txt"
    CMAKE_DB_FILE_NAME = "compile_commands.json"
    CLANG_COMPLETE_FILE_NAME = ".clang_complete"

    def __init__(self, search_scope=SearchScope()):
        if not search_scope.valid():
            log.error(" search scope is wrong.", search_scope)
        self._search_scope = search_scope

    def any_file_modified(self):
        if self._cmake_file.was_modified():
            return True
        if self._clang_complete_file.was_modified():
            return True
        return False

    def get_flags(self, separate_includes):
        if not self._cmake_file.loaded():
            # CMakeLists.txt was not loaded yet, so search for it
            log.debug(" cmake file not loaded yet. Searching for one...")
            self._cmake_file = File.search(
                file_name=FlagsManager.CMAKE_FILE_NAME,
                from_folder=self._search_scope.from_folder,
                to_folder=self._search_scope.to_folder)

        if self._cmake_file.was_modified():
            # generate a .clang_complete file from cmake file if cmake file
            # exists and was modified
            log.debug(" CMakeLists.txt was modified."
                      " Generate new .clang_complete")
            compilation_db = FlagsManager.compile_cmake(
                self._cmake_file)
            if compilation_db:
                flags_set = FlagsManager.flags_from_database(compilation_db)
                new_clang_file_path = path.join(
                    self._cmake_file.folder(),
                    FlagsManager.CLANG_COMPLETE_FILE_NAME)
                FlagsManager.write_flags_to_file(
                    flags_set, new_clang_file_path)
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
    def compile_cmake(cmake_file):
        import os
        cmake_cmd = FlagsManager.cmake_mask.format(cmake_file.folder())
        tempdir = path.join(Tools.get_temp_dir(), 'build')
        if not path.exists(tempdir):
            os.makedirs(tempdir)
        try:
            output = subprocess.check_output(cmake_cmd,
                                             stderr=subprocess.STDOUT,
                                             shell=True,
                                             cwd=tempdir)
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
    def write_flags_to_file(flags, file_path):
        f = open(file_path, 'w')
        # overwrite file
        f.seek(0)
        f.write('\n'.join(flags) + '\n')
        f.close()

    @staticmethod
    def flags_from_database(database_file):
        import json
        data = None
        with open(database_file.full_path()) as data_file:
            data = json.load(data_file)
        if not data:
            return None
        flags_set = set()
        for entry in data:
            command = entry['command']
            all_command_parts = command.split()
            for (i, part) in enumerate(all_command_parts):
                if part.startswith('-I') or part.startswith('-D'):
                    flags_set.add(part)
                    continue
                if part.startswith('-isystem'):
                    flags_set.add(
                        all_command_parts[i] + ' ' + all_command_parts[i + 1])
                    continue
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

        flags = []
        folder = file.folder()
        mask = '{}{}'
        if separate_includes:
            mask = '{} "{}"'
        with open(file.full_path()) as f:
            content = f.readlines()
            for line in content:
                if line.startswith('-D'):
                    flags.append(line)
                elif line.startswith('-I'):
                    path_to_add = line[2:].rstrip()
                    if path.isabs(path_to_add):
                        flags.append(mask.format(
                            '-I', path.normpath(path_to_add)))
                    else:
                        flags.append(mask.format(
                            '-I', path.join(folder, path_to_add)))
                elif line.startswith('-isystem'):
                    path_to_add = line[8:].rstrip().strip()
                    if path.isabs(path_to_add):
                        flags.append(mask.format(
                            '-isystem', path.normpath(path_to_add)))
                    else:
                        flags.append(mask.format(
                            '-isystem', path.join(folder, path_to_add)))
        log.debug(" .clang_complete contains flags: %s", flags)
        return flags
