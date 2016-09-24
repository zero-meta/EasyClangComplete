""" Class to have a timestamped translation unit
"""
from time import time


class StampedTu:
    """ class for time stamped translation unit
    """

    __translation_unit = None
    __time = None

    def __init__(self, translation_unit):
        """ Initialize the object. Take current time as initialization.

        Args:
            translation_unit (cindex.TranslationUnit): translation unit
        """
        self.__translation_unit = translation_unit
        self.__time = time()

    def is_older_than(self, age_in_seconds):
        """ check if this translation unit is older than some time in secs

        Args:
            age_in_seconds (float): time in seconds

        Returns:
            bool: True if older, False otherwise
        """
        if time() - self.__time > age_in_seconds:
            return True
        return False

    def touch(self):
        """ update time of object """
        self.__time = time()

    def tu(self):
        """ Get translation unit and update time because we used it """
        self.__time = time()
        return self.__translation_unit

    def creation_time(self):
        """ Get creation time """
        return self.__time
