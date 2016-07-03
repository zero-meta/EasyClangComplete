""" Module with a class for .clang_complete file

Attributes:
    log (logging.log): logger for this module
"""
import logging
import subprocess

from os import path
from os import listdir

log = logging.getLogger(__name__)


class FlagsFile:

    """
    A class that incapsulates operations with .clang_complete file
    """

    _clang_complete_file = None
    _last_modification_time = 0

    def __init__(self, from_folder, to_folder):
        """search for .clang_complete file up the tree

        Args:
            from_folder (str): path to folder where we start the search
            to_folder (str): path to folder we should not go beyond

        Returns:
            str: path to .clang_complete file or None if not found
        """
        current_folder = from_folder
        one_past_stop_folder = path.dirname(to_folder)
        while current_folder != one_past_stop_folder:
            for file in listdir(current_folder):
                if file == ".clang_complete":
                    self._clang_complete_file = path.join(current_folder, file)
                    self._last_modification_time = path.getmtime(
                        self._clang_complete_file)
                    log.debug(" found .clang_complete file: %s",
                              self._clang_complete_file)
                    return
            if current_folder == path.dirname(current_folder):
                break
            current_folder = path.dirname(current_folder)

    def found(self):
        if not self._clang_complete_file:
            return False
        return True

    @staticmethod
    def find_cmake_file(project_path):
        for file in listdir(project_path):
            if file == "CMakeLists.txt":
                cmake_lists_file = path.join(project_path, file)
                log.debug(" found: %s", cmake_lists_file)
                return cmake_lists_file
        # no CMakeLists.txt found
        return None

    @staticmethod
    def generate_from_cmake(project_path):
        import os
        cmake_file = FlagsFile.find_cmake_file(project_path)
        if not cmake_file:
            log.debug(" no CMakeLists.txt found in %s.", project_path)
            log.debug(" skip .clang_complete file generation.")
            return False
        cmake_dir = path.abspath(path.dirname(cmake_file))
        cmake_cmd = "cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON " + cmake_dir
        tempdir = "/tmp/build"
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

        database = path.join(tempdir, "compile_commands.json")
        if not path.exists(database):
            log.error(" cmake has finished, but no compilation database.")
            return False

        includes = FlagsFile.includes_from_compile_database(database)
        include_file = path.join(project_path, '.clang_complete')
        log.debug(" clang complete file: %s", include_file)
        FlagsFile.write_includes_to_file(includes, include_file)
        return True

    @staticmethod
    def write_includes_to_file(includes, file):
        f = open(file, 'w')
        # overwrite file
        f.seek(0)
        f.write('\n'.join(includes) + '\n')
        f.close()

    @staticmethod
    def includes_from_compile_database(database_file):
        import json
        data = None
        with open(database_file) as data_file:
            data = json.load(data_file)
        if not data:
            return None
        include_set = set()
        for entry in data:
            command = entry['command']
            all_command_parts = command.split()
            for (i, part) in enumerate(all_command_parts):
                if part.startswith('-I'):
                    include_set.add(part)
                if part.startswith('-isystem'):
                    include_set.add(all_command_parts[i] +
                                    ' ' + all_command_parts[i + 1])
        log.debug(" include set: %s", include_set)
        return include_set

    def was_modified(self):
        """ checks if .clang_complete file has been modified since it was
        last seen by the plugin

        Returns:
            bool: True if modified, False if not
        """
        if not self._clang_complete_file:
            # it was not even found yet
            return False
        actual_modification_time = path.getmtime(self._clang_complete_file)
        if actual_modification_time > self._last_modification_time:
            log.info(" .clang_complete was modified.")
            self._last_modification_time = actual_modification_time
            return True
        return False

    def get_flags(self, separate_includes):
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
        file = self._clang_complete_file
        if not file:
            log.error(" cannot get flags from clang_complete_file. No file.")
            return []

        flags = []
        folder = path.dirname(file)
        mask = '{}{}'
        if separate_includes:
            mask = '{} "{}"'
        with open(file) as f:
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
                    log.debug(" line: %s", line)
                    path_to_add = line[8:].rstrip().strip()
                    if path.isabs(path_to_add):
                        flags.append(mask.format(
                            '-isystem', path.normpath(path_to_add)))
                    else:
                        flags.append(mask.format(
                            '-isystem', path.join(folder, path_to_add)))
        log.debug(" .clang_complete contains flags: %s", flags)
        return flags
