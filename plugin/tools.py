import os.path as path

PKG_NAME = path.basename(path.dirname(path.dirname(__file__)))

class SublimeBridge(object):
  """docstring for SublimeBridge"""
  def __init__(self, arg):
    super(SublimeBridge, self).__init__()
    self.arg = arg
