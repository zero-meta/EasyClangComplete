"""module for compile error visualization

Attributes:
    FORMAT_BINARY (str): constant for picking binary parsing strategy
    FORMAT_LIBCLANG (str): constant for picking library parsing strategy
    log (logging): this module logger
"""
import re
import logging
from os import path

log = logging.getLogger(__name__)

FORMAT_LIBCLANG = "libclang"
FORMAT_BINARY = "binary"

class CompileErrors:
    """Comple errors is a class that encapsulates compile error visualization

    Attributes:
        err_regions (dict): dictionary of error regions for view ids
        error_regex (re): regex to find contents of an error
        msg_regex (re): regex to find error message
        pos_regex (re): regex to find position of an error
    """

    pos_regex = re.compile("'(?P<file>.+)'.*"  # file
                           + "line\s(?P<row>\d+), "  # row
                           + "column\s(?P<col>\d+)")  # col
    msg_regex = re.compile("b\"(?P<error>.+)\"")
    error_regex = re.compile("(?P<file>.*):" +
                             "(?P<row>\d+):(?P<col>\d+): " +
                             ".*error: (?P<error>.*)")


    _TAG = "easy_clang_complete_errors"

    err_regions = {}

    def generate(self, view, errors, error_format):
        """Generate a dictionary that stores all errors along with their
        positions and descriptions. Needed to show these errors on the screen.

        Args:
            view (sublime.View): current view
            errors (list): list of unparsed errors in format @error_format
            error_format (str): either FORMAT_LIBCLANG or FORMAT_BINARY
        """
        log.debug(" generating error regions for view %s", view.buffer_id())
        # first clear old regions
        if view.buffer_id() in self.err_regions:
            log.debug(" removing old error regions")
            del self.err_regions[view.buffer_id()]
        # create an empty region dict for view id
        self.err_regions[view.buffer_id()] = {}

        if error_format == FORMAT_LIBCLANG:
            # expect a tu_diagnostics instance
            self.errors_from_tu_diag(view, errors)
        elif error_format == FORMAT_BINARY:
            # expect a list of strings for each line of cmd output
            self.errors_from_clang_output(view, errors)
        else:
            logging.critical(
                " error_format:'%s' should match '%s' or '%s'",
                error_format, FORMAT_LIBCLANG, FORMAT_BINARY)
        log.debug(" %s error regions ready", len(self.err_regions))


    def errors_from_clang_output(self, view, clang_output):
        """Parse errors received from clang binary output

        Args:
            view (sublime.View): current view
            clang_output (list): list of unparsed errors
        """
        for line in clang_output:
            error_search = CompileErrors.error_regex.search(line)
            if not error_search:
                continue
            error_dict = error_search.groupdict()
            self.add_error(view, error_dict)

    def errors_from_tu_diag(self, view, tu_diagnostics):
        """Parse errors received from diagnostics of a translation unit (used
        with libclang)

        Args:
            view (sublime.View): current view
            tu_diagnostics (diagnostics): diagnostics from a translation unit
        """
        # create new ones
        for diag in tu_diagnostics:
            location = str(diag.location)
            spelling = str(diag.spelling)
            pos_search = CompileErrors.pos_regex.search(location)
            msg_search = CompileErrors.msg_regex.search(spelling)
            if not pos_search or not msg_search:
                # not valid, continue
                continue
            error_dict = pos_search.groupdict()
            error_dict.update(msg_search.groupdict())
            self.add_error(view, error_dict)

    def add_error(self, view, error_dict):
        """Put new compile error in the dictionary of errors

        Args:
            view (sublime.View): current view
            error_dict (dict): current error dict {row, col, file, region}
        """
        logging.debug(" adding error %s", error_dict)
        if path.basename(error_dict['file']) == path.basename(view.file_name()):
            row = int(error_dict['row'])
            col = int(error_dict['col'])
            point = view.text_point(row - 1, col - 1)
            error_dict['region'] = view.word(point)
            if row in self.err_regions[view.buffer_id()]:
                self.err_regions[view.buffer_id()][row] += [error_dict]
            else:
                self.err_regions[view.buffer_id()][row] = [error_dict]

    def show_regions(self, view):
        """Show current error regions

        Args:
            view (sublime.View): Current view
        """
        if view.buffer_id() not in self.err_regions:
            # view has no errors for it
            return
        current_error_dict = self.err_regions[view.buffer_id()]
        regions = CompileErrors._as_region_list(current_error_dict)
        log.debug(" showing error regions: %s", regions)
        view.add_regions(CompileErrors._TAG, regions, "string")

    def erase_regions(self, view):
        """erase error regions for view

        Args:
            view (sublime.View): erase regions for view
        """
        if view.buffer_id() not in self.err_regions:
            # view has no errors for it
            return
        log.debug(" erasing error regions for view %s", view.buffer_id())
        view.erase_regions(CompileErrors._TAG)

    def show_popup_if_needed(self, view, row):
        """Show a popup if it is needed in this row

        Args:
            view (sublime.View): current view
            row (int): number of row
        """
        if view.buffer_id() not in self.err_regions:
            return
        current_err_region_dict = self.err_regions[view.buffer_id()]
        if row in current_err_region_dict:
            errors_dict = current_err_region_dict[row]
            errors_html = CompileErrors._as_html(errors_dict)
            view.show_popup(errors_html)
        else:
            log.debug(" no error regions for row: %s", row)

    def clear(self, view):
        """Clear errors from dict for view

        Args:
            view (sublime.View): current view
        """
        if view.buffer_id() not in self.err_regions:
            # no errors for this view
            return
        view.hide_popup()
        self.erase_regions(view)
        self.err_regions[view.buffer_id()].clear()

    def remove_region(self, view_id, row):
        """remove a region for view_id in row

        Args:
            view_id (int): view id
            row (int): row number
        """
        if view_id not in self.err_regions:
            # no errors for this view
            return
        current_error_dict = self.err_regions[view_id]
        if row not in current_error_dict:
            # no errors for this row
            return
        del current_error_dict[row]

    @staticmethod
    def _as_html(errors_dict):
        """Show error as html

        Args:
            errors_dict (dict): Current error
        """
        errors_html = ""
        for entry in errors_dict:
            errors_html += "<p><tt>" + entry['error'] + "</tt></p>"
        return errors_html

    @staticmethod
    def _as_region_list(err_regions_dict):
        """Make a list from error region dict

        Args:
            err_regions_dict (dict): dict of error regions for current view

        Returns:
            list(Region): list of regions to show on sublime view
        """
        region_list = []
        for errors_list in err_regions_dict.values():
            for error in errors_list:
                region_list.append(error['region'])
        return region_list
