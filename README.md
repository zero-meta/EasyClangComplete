# EasyClangComplete #

Sublime Text 3 plugin that offers auto-completion for C++

![Example](autocomplete_show_off.gif)

This plugin aims to provide easy-to-use, minimal-setup autocompletions for C++ for Sublime Text 3. It is built to function in an asynchronous way, so that you will not have to wait even when completions take slightly longer to load.

The plugin uses `libclang` with its python bindings to provide clang-based autocompletions.

This plugin is intended to be easy to use. You should just add the folders your project uses to `include_dirs` list in the settings and everything should just work. If you experience problems - create an issue. I will try to respond as soon as possible.

## How to install ##
Clone this repository into the folder where the packages of your Sublime Text 3 live. Then follow the OS-specific setup below:

##### Ubuntu #####
I have tested it on Ubuntu 14.04 and here the setup should be as simple as:
```bash
sudo apt-get install clang
```
You can also use a specific version of clang, e.g. `clang-3.6`. In this case don't forget to set the correct binary name in the settings, e.g.:
```
"clang_binary" : "clang++-3.6"
```

##### Windows #####
I am not fluent with Windows, so help needed. The plugin should work out of the box provided you have clang set up, but this needs testing and probably minor tweaks. If you are willing to help, either install the package and report errors or educate me of a simple way to install clang on Windows ^_^.

##### Mac  #####
Unfortunately I do not own a mac, but again, everything should just work. If it doesn't - please create an issue and we'll try to resolve it.

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
- `include_dirs`:
    + stores the locations where `clang` should be looking for external headers, e.g. `Boost`, `Ros`, `Eigen`, `OpenCV`, etc.
    + you can use placeholders like `$project_base_name` or `$project_base_path` to make includes more convenient.
    + it is absolutely ok to include a folder that does not exist. `clang` knows how to deal with it and it will neither break anything nor make things slower.
    + See [my own settings](https://github.com/niosus/config-sublime/blob/master/Packages%2FUser%2FEasyClangComplete.sublime-settings#L4) as an example if you wish.
- `std_flag`:
    + sets the standard flag that will be used for compilation. Defaults to `std=c++11`
- `search_clang_complete_file`:
    + seach for `.clang_complete` file up the tree. Project folder is the last one to search for the file.
    + If the file is found, its contents of style `-I<some_local_path>` are appended to include flags.
- `triggers`:
    + defaults are `".", "::", "->"`. The autocompletion does not trigger on `>` or `:`. It also ignores float numbers like `3.14`.

Please see the default settings file in the repo for more settings descriptions. Every setting in [settings file](EasyClangComplete.sublime-settings) should have an understandable comment. Should they not be clear - create an issue.


## Credits ##
The whole work seen here was originally a fork of another repository: https://github.com/pl-ca/ClangAutoComplete

However, with time this plugin has grown quite different from its origin and this is why you see it as a separate package now. Anyway, I encourage you to check out what @pl-ca has to offer and come back if you still like this plugin more.

The trick with multiple `clang.cindex` files is inspired by this repo: https://github.com/griebd/clangHelper Thanks for inspiration!

If you are an experienced python developer and find that something in my code sucks completely - **DO** tell me. Python is not my main language and I am always willing to learn.

## Licence ##
![licence](http://www.wtfpl.net/wp-content/uploads/2012/12/wtfpl-badge-1.png)

Just as the original package by @pl-ca, I decided to adopt the most strict licence we have found:

> DO WHAT THE F*CK YOU WANT TO PUBLIC LICENSE
> Version 2, December 2004
> Copyright (C) 2016 Igor Bogoslavskyi

>Everyone is permitted to copy and distribute verbatim or modified copies of this license document, and changing it is allowed as long as the name is changed.

>DO WHAT THE F*CK YOU WANT TO PUBLIC LICENSE TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION

>0.You just DO WHAT THE F*CK YOU WANT TO.




