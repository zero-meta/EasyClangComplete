Sublime Text 3 plugin that offers clang-based auto-completion for C++

# Let't get started! #
Follow the following steps to make sure everything runs smoothly!

## Install clang ##
- **Ubuntu**: `sudo apt-get install clang`
- **Other Linux**: use your package manager or install from `clang`
  [website](http://llvm.org/releases/download.html)
- **Windows**: install the latest release from `clang`
  [website](http://llvm.org/releases/download.html)
- **OSX**: ships `clang` by default. You are all set!

## Configure your includes ##
`Clang` will automatically search for headers in the folder that contains the
file you are working on and its parent. If you have a more sophisticated
project you will need to help `clang` just a little bit. There are three ways
to do it. Pick any of the following:

- Set `include_dirs` setting in `User Settings`:
  + see default [settings](EasyClangComplete.sublime-settings) to get started.
    These includes will be included in every project you run.
- Add `.clang_complete` file to the root of your project folder.
  + this file should contain all includes and macroses you want to use.
  + Example:
  ```
  -I/usr/include
  -I/opt/ros/indigo/include
  ```
- Add all the flags to pass to clang to `*.sublime-project` file.
  + add all settings as a string list under `settings` -> `clang_flags`.
  + Example:
  ```
  "settings":
  {
    "clang_flags": ["-std=c++11", "-I/usr/include"]
  }
  ```

## Check sublime completion settings ##
Add this to your `User Settings`:
```
"auto_complete_triggers":
[
    {
        "characters": ".:>",
        "selector": "source.c++ - string - comment - constant.numeric"
    }
],
```
It will ensure that Sublime Text will try to autocomplete your code when you
type `.`, `:` or `>`. The plugin will then ensure that completions are
triggered only when `.`, `::` or `->` are typed.
## You're good to go! ##

## More info here ##
Get more info in a readme:
https://github.com/niosus/EasyClangComplete/blob/master/README.md

You can find all the relevant settings you can set here:
https://github.com/niosus/EasyClangComplete/blob/master/README.md#settings-highlights
