import re

class CompileErrors:
    """docstring for CompileErrors"""

    pos_regex = re.compile("'(?P<file>.+)'.*"  # file
                               + "line\s(?P<row>\d+), "  # row
                                 + "column\s(?P<col>\d+)")  # col
    msg_regex = re.compile("b\"(?P<error>.+)\"")

    _TAG = "easy_clang_complete_errors"

    err_regions = {}

    def generate(self, view, tu_diagnostics):
        """Generate a dictionary that stores all errors along with their
        positions and descriptions. Needed to show these errors on the screen.

        Args:
            view (sublime.View): current view
        """
        # first clear old regions
        if view.id() in self.err_regions:
            del self.err_regions[view.id()]
        # create an empty region dict for view id
        self.err_regions[view.id()] = {}

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
            if error_dict['file'] == view.file_name():
                row = int(error_dict['row'])
                col = int(error_dict['col'])
                point = view.text_point(row - 1, col - 1)
                error_dict['region'] = view.word(point)
                if (row in self.err_regions[view.id()]):
                    self.err_regions[view.id()][row] += [error_dict]
                else:
                    self.err_regions[view.id()][row] = [error_dict]

    def show_regions(self, view):
        """Show current error regions

        Args:
            view (sublime.View): Current view
            current_error_dict (dict): error dict for current view
        """
        if view.id() not in self.err_regions:
          # view has no errors for it
          return
        current_error_dict = self.err_regions[view.id()]
        regions = CompileErrors._as_region_list(current_error_dict)
        view.add_regions(CompileErrors._TAG, regions, "string")

    def erase_regions(self, view):
        if view.id() not in self.err_regions:
          # view has no errors for it
          return
        view.erase_regions(CompileErrors._TAG)

    def show_popup_if_needed(self, view, row):
      if view.id() not in self.err_regions:
            return
      current_err_region_dict = self.err_regions[view.id()]
      if (row in current_err_region_dict):
          errors_dict = current_err_region_dict[row]
          errors_html = CompileErrors._as_html(errors_dict)
          view.show_popup(errors_html)
      else:
          print("key: {} not in error regions".format(row))

    def clear(self, view):
        if view.id() not in self.err_regions:
            # no errors for this view
            return
        view.hide_popup()
        self.erase_regions(view)
        self.err_regions[view.id()].clear()

    def remove_region(self, view_id, row):
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

