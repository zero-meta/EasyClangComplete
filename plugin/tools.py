import os.path as path

PKG_NAME = path.basename(path.dirname(path.dirname(__file__)))


class SublBridge:
    """docstring for SublimeBridge"""

    @staticmethod
    def cursor_pos(view):
        """Get current cursor position. Returns position of the first cursor if
        multiple are present

        Args:
            view (sublime.View): current view

        Returns:
            (row, col): tuple of row and col for cursor position
        """
        pos = view.sel()
        if len(pos) < 1:
            # something is wrong
            return None
        (row, col) = view.rowcol(pos[0].a)
        row += 1
        col += 1
        return (row, col)

    @staticmethod
    def next_line(view):
        (row, _) = SublBridge.cursor_pos(view)
        point_on_next_line = view.text_point(row, 0)
        line = view.line(point_on_next_line)
        return view.substr(line)
