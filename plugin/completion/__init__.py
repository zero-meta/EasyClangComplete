"""Completer part of the plugin
  base_completer: abstract class for completions

  bin_completer: sibling of `base_completer` that handles completions using
  clang binary.

  lib_completer: sibling of `base_completer` that handles completions using
  libclang and its python bindings
"""
__all__ = ["base_completer", "bin_completer", "lib_completer"]
