# EasyClangComplete #

Sublime Text 3 plugin that offers clang-based auto-completion for C++

![Example](../pics/autocomplete_show_off.gif)

# Simple setup! #
Follow the following 3 steps to ensure the plugin works as expected!

## Install this plugin ##
- Best is to use [Package Control](https://packagecontrol.io/installation)
  + <kbd>CTRL</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> and install
    `EasyClangComplete`

## Install clang ##
- **Ubuntu**: `sudo apt-get install clang`
- **Windows**: install the latest release from `clang`
  [website](http://llvm.org/releases/download.html) (v >= 3.9)
- **OSX**: ships `clang` by default. You are all set!
- on other systems refer to their package managers or install from `clang`
  [website](http://llvm.org/releases/download.html)

## Configure your includes ##

### Using CMake? ###
Plugin automatically finds `CMakeLists.txt` and generates `.clang_complete`
from it for building our code.

### Not using CMake? ###
You will need a little bit of manual setup for now. Please see the following
[instructions][no_cmake].

## That's it! You're ready to use the plugin! ##
For more information please refer to the [GitHub][github_page] page.

[no_cmake]: https://github.com/niosus/EasyClangComplete#not-using-cmake
[github_page]: https://github.com/niosus/EasyClangComplete
