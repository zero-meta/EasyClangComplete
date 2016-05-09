# EasyClangComplete #

Sublime Text 3 plugin that offers auto-completion for C++

![Example](autocomplete_show_off.gif)

[![Build Status](https://goo.gl/3KUIVo)](https://goo.gl/nJ2NOU)
[![Build status](https://goo.gl/FqsNzm)](https://goo.gl/4N6nxe)
[![Codacy Badge](https://goo.gl/PDVYTj)](https://goo.gl/h52rHl)
[![MIT licensed](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Sublime Text 3](https://img.shields.io/badge/Sublime%20Text-3-green.svg)](https://www.sublimetext.com/3)

This plugin aims to provide easy-to-use, minimal-setup autocompletions for C++ for Sublime Text 3. It is built to function in an asynchronous way, so that you will not have to wait even when completions take slightly longer to load.

The plugin uses `libclang` with its python bindings to provide clang-based autocompletions. In case `libclang` cannot be initialized or found it will use completions based on the output of `clang -code-completion-at` run from the command line. If you want this as default behavior, set the setting `use_libclang` to `false`.

This plugin is intended to be easy to use. It should autocomplete STL out of the box and you should just add the folders your project uses to `include_dirs` list in the settings to make it autocomplete code all your project. If you experience problems - create an issue. I will try to respond as soon as possible.

## How to install ##
Use `Package Control` for Sublime Text. Install `EasyClangComplete` plugin from there. Then follow the OS-specific setup below.

If you cannot find it there or have other reasons not to use package control, clone this repository into the folder where the packages of your Sublime Text 3 live. Then follow the OS-specific setup below.

##### Linux #####
I have tested it on Ubuntu 14.04 and here the setup should be as simple as:
```bash
sudo apt-get install clang
```
You can also install any specific version of clang, e.g. `clang-3.6`. In this case don't forget to set the correct binary name in the settings, e.g.:
```
"clang_binary" : "clang++-3.6"
```
Ubuntu uses full featured `libclang` support which provides the full experience with blazingly fast autocompletion even for large code bases thanks to `reparse` python bindings function.

##### Windows #####
Just download the latest clang from the [clang website](http://llvm.org/releases/download.html). This should be enough to trigger simple completions. Additional steps may be needed if you want to use STL or third party libraries.

- `Microsoft visual C++` - works out of the box for visual studio 2015. Should also work for older version, but I haven't tested it. Please report back if it works for you on an older version out of the box.
- `MinGW` - setup should be similar to linux setup and provided all paths are configured correcty should work out of the box. `

*Help needed:* Currently this plugin works for Windows only in a binary mode by running a command in the cmd and parsing the output with regex. It works and should be fine for general user, but it would be cool to make it work with libclang as it is faster and should be more robust. I don't know much about Windows and I don't work in it, so if you are an expect in Windows - educate me! Fire up the issue with your suggestions! Let's make it work.

##### Mac  #####
Mac comes with `clang`. The only catch is that its versioning is different from `llvm` one. This makes it hard to match `libclang` to it. However, the autocompletions should be working out of the box.

*Help needed:* Unfortunately I do not own a mac. The unit tests for completion using `clang` binary pass on an `OSX` instance both for completing user-defined structures and for STL auto-completion. But there is a hack. I set the version of python bindings to `3.7` by hand. There is not simple way of knowing which version the internal `OSX` `clang` corresponds to in `LLVM` versioning scheme. But do correct me if I am wrong. Help me to make `libclang` work on a Mac!

## Settings highlights ##
I will only cover most important settings here.

##### Sublime Settings  #####
Make sure that sublime will actually autocomplete your code on specific characters like `>`, `.` or `:`.
 To have this behavior you can either modify your syntax-specific settings or add to your user preferences the following lines:
```
    "auto_complete_triggers":
    [
        {
            "characters": ".:>",
            "selector": "source.c++ - string - comment - constant.numeric"
        }
    ],
```

##### EasyClangComplete Settings  #####
**PLEASE RESTART SUBLIME TEXT AFTER EACH SETTINGS CHANGE**
- `include_dirs`:
    + stores the locations where `clang` should be looking for external headers, e.g. `Boost`, `Ros`, `Eigen`, `OpenCV`, etc.
    + you can use placeholders like `$project_base_name` or `$project_base_path` to make includes more convenient.
    + it is absolutely ok to include a folder that does not exist. `clang` knows how to deal with it and it will neither break anything nor make things slower.
    + See [my own settings](https://github.com/niosus/config-sublime/blob/master/Packages%2FUser%2FEasyClangComplete.sublime-settings#L4) as an example if you wish.
- `std_flag`:
    + sets the standard flag that will be used for compilation. Defaults to `std=c++11`
- `use_libclang`:
    + if `true` use libclang as backend. It is buggy on Windows and until there are good solutions to issue #4 there is a fallback option:
    + if `false` or if first option failed, use output from `clang -cc1 -completion-at` command and parse it with regular expressions.
- `search_clang_complete_file`:
    + seach for `.clang_complete` file up the tree. Project folder is the last one to search for the file.
    + If the file is found, its contents of style `-I<some_local_path>` are appended to include flags.
- `errors_on_save`:
    + if `use_libclang` is `true` the plugin can highlight errors on save. A tooltip with an error message will be shown if the caret goes over a highlighted line.
- `triggers`:
    + defaults are `".", "::", "->"`. The autocompletion does not trigger on `>` or `:`. It also ignores float numbers like `3.14`.

Please see the default settings file in the repo for more settings descriptions. Every setting in [settings file](EasyClangComplete.sublime-settings) should have an understandable comment. Should they not be clear - create an issue.


## Credits ##
The whole work seen here was originally a fork of another repository: https://github.com/pl-ca/ClangAutoComplete

However, with time this plugin has grown quite different from its origin and this is why you see it as a separate package now. Anyway, I encourage you to check out what @pl-ca has to offer and come back if you still like this plugin more.

The trick with multiple `clang.cindex` files is inspired by this repo: https://github.com/griebd/clangHelper Thanks for inspiration!

If you are an experienced python developer and find that something in my code sucks completely - **DO** tell me. Python is not my main language and I am always willing to learn.

## Tests ##
I have tried to cover most crucial functionality with unit tests using [UnitTesting](https://github.com/randy3k/UnitTesting) Sublime Text plugin. To check out the current status click on relevant badge on top of the page.
