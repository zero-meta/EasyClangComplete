A plugin for easy to use clang-based completions::

    ╔═╗┌─┐┌─┐┬ ┬  ╔═╗┬  ┌─┐┌┐┌┌─┐  ╔═╗┌─┐┌┬┐┌─┐┬  ┌─┐┌┬┐┌─┐
    ║╣ ├─┤└─┐└┬┘  ║  │  ├─┤││││ ┬  ║  │ ││││├─┘│  ├┤  │ ├┤
    ╚═╝┴ ┴└─┘ ┴   ╚═╝┴─┘┴ ┴┘└┘└─┘  ╚═╝└─┘┴ ┴┴  ┴─┘└─┘ ┴ └─┘

Let't get started!
==================

You're just two simple steps away!

1. Install clang
----------------

- **Ubuntu**        : ``sudo apt-get install clang``
- **OSX**           : ships `clang` by default. You are all set!
- **Windows**       : install the latest release from clang website.
- **Other Systems** : use your package manager or install from clang website.
- clang website: http://llvm.org/releases/download.html

2. Configure your includes
--------------------------

Using CMake?
~~~~~~~~~~~~

Plugin will run cmake on a proper ``CMakeLists.txt`` in your project folder and
will use information from it to complete your code out of the box.

Have a compilation database?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Plugin will search for a compilation database ``compile_commands.json`` in the
project folder and will load it to complete your code. If you want to specify a
custom path to a comilation database you can do it in settings::

    "flags_sources": [
        {"file": "compile_commands.json", "search_in": "<YOUR_PATH>"},
    ]

None of the above?
~~~~~~~~~~~~~~~~~~

You will need a little bit of manual setup for now. Clang will automatically
search for headers in the folder that contains the file you are working on and
its parent. If you have a more sophisticated project you will need to help clang
just a little bit. There are three ways to do it.

Pick **ANY** of the following:

- Set include dirs in ``"common_flags"`` setting in ``User Settings``.
- Override ``"common_flags"`` setting in your project file, i.e. one that has
  extension: ``*.sublime-project``. Just define the same setting in project
  specific settings with either one of two prefixes: ``"ecc_"`` or
  ``"easy_clang_complete_"`` to override a corresponding setting in your user
  settings. See the project file in this repo for a working example. Minimal
  example for clarity::

    {
      "settings":
      {
        "ecc_common_flags": ["-Isrc", "-I/usr/include"],
        "easy_clang_complete_verbose": true
      }
    }

- It is recommended to use one of the above, but if you already have a file with
  flags, you can add ``.clang_complete`` file to the root of your project
  folder. This file adds additional flags to the ones defined with in
  ``"common_flags"``. Example::

    -Isrc
    -I/usr/include

That's it! You're ready to use the plugin!
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

More info here
~~~~~~~~~~~~~~

Get more info in a readme:
https://github.com/niosus/EasyClangComplete/blob/master/README.md

Please see the default settings ``EasyClangComplete.sublime-settings``
shipped with the plugin for explanations and sane default values.

Thanks!
=======

💜 this plugin? Consider buying me a 🍵
https://github.com/niosus/EasyClangComplete#support-it
