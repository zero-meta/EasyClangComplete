import platform
import logging
import subprocess

from os import path

log = logging.getLogger(__name__)

class ClangUtils:
    """docstring for ClangUtils"""
    libclang_name = None

    linux_suffixes = ['.so', '.so.1']
    osx_suffixes = ['.dylib']
    windows_suffixes = ['.dll']

    @staticmethod
    def get_suffixes():
        if platform.system() == "Windows":
            return ClangUtils.windows_suffixes
        if platform.system() == "Linux":
            return ClangUtils.linux_suffixes
        if platform.system() == "Darwin":
            return ClangUtils.osx_suffixes
        return None

    @staticmethod
    def dir_from_output(output):
        if platform.system() == "Windows":
            return path.dirname(output)
        if platform.system() == "Linux":
            return path.dirname(output)
        if platform.system() == "Darwin":
            # [HACK] uh... I'm not sure why it happens like this...
            return path.join(path.dirname(output), '..', '..')
        return None

    @staticmethod
    def find_libclang_dir(clang_binary):
        for suffix in ClangUtils.get_suffixes():
            file = None
            # pick a name for a file
            log.debug(" we are on '%s'", platform.system())
            file = "libclang{}".format(suffix)
            log.debug(" searching for: '%s'", file)
            # let's find the library
            get_library_path_cmd = [clang_binary, "-print-file-name={}".format(file)]
            output = subprocess.check_output(
                get_library_path_cmd).decode('utf8').strip()
            log.debug(" libclang search output = '%s'", output)
            if output:
                libclang_dir = ClangUtils.dir_from_output(output)
                if path.isdir(libclang_dir):
                    log.info(" found libclang dir: '%s'", libclang_dir)
                    log.info(" found library file: '%s'", file)
                    ClangUtils.libclang_name = file
                    return libclang_dir
            log.warning(" clang could not find '%s'", file)
        # if we haven't found anything there is nothing to return
        log.error(" no libclang found at all")
        return None