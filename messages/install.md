Sublime Text 3 plugin that offers clang-based auto-completion for C++

# Let't get started! #
Follow the following steps to make sure everything runs smoothly!

## Install clang ##
- **Ubuntu**: `sudo apt-get install clang`
- **Windows**: install the latest release from `clang`
  [website](http://llvm.org/releases/download.html) (v >= 3.9)
- **OSX**: ships `clang` by default. You are all set!
- **Other Systems**: use your bundled package manager or install from `clang`
  [website](http://llvm.org/releases/download.html)

## Configure your includes ##

### Are you using CMake? ###
Plugin automatically generates `.clang_complete` and uses it for building our
code.

### Not using CMake? ###
You will need a little bit of manual setup for now. `Clang` will automatically
search for headers in the folder that contains the file you are working on and
its parent. If you have a more sophisticated project you will need to help
`clang` just a little bit. There are three ways to do it. Pick any of the
following:

- Set `include_dirs` setting in `User Settings`:
  + see default [settings](EasyClangComplete.sublime-settings) to get started.
    These includes will be included in every project you run.
- Add `.clang_complete` file to the root of your project folder.
  + this file should contain all includes and macroses you want to use.
  + Example:
  ```
  -Isrc
  -I/usr/include
  -I/opt/ros/indigo/include
  ```
- Override flags setting in your project file! Just define the same setting in
  project specific settings with either one of two prefixes: `"ecc_"` or
  `"easy_clang_complete"`. See the project file in this repo for a working
  example. Minimal example for clarity:
  ```json
      {
        "settings":
        {
          "ecc_include_dirs":
          ["-Isrc", "-I/usr/include"],
          "easy_clang_complete_verbose": true
        }
      }
  ```

## That's it! You're ready to use the plugin! ##

## More info here ##
Get more info in a readme:
https://github.com/niosus/EasyClangComplete/blob/master/README.md

Please see the default settings [file](EasyClangComplete.sublime-settings)
shipped with the plugin for explanations and sane default values.

## Thanks ##
It is really important for me that you are using the plugin. If you have
problems - submit issues and we will eventually solve them together.

If you like the plugin, consider supporting the development! It takes me quite
some time to implement everything as good as I can. Find ways to support the
plugin here: https://github.com/niosus/EasyClangComplete#support-it
