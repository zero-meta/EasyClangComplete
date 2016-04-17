# EasyClangComplete #

Sublime Text 3 plugin that offers auto-completion for C/C++

![Example](autocomplete_show_off.gif)

This plugin aims to provide easy-to-use, minimal setup helpful autocompletions for c++ for Sublime Text 3. It is built in asynchronous way, so that you will not have to wait even when completions take slightly longer to load.

The plugin uses `libclang` with its python bindings to provide clang-based autocompletions.

This plugin is intended be easy to use. You should just add the folders your project uses to `include_dirs` list in the settings and everything should just work. If you experience problems - create an issue. I will try to respond as soon as possible.

## Installation ##
Clone this repository into the folder where the packages of your Sublime Text 3 live. Then follow the OS-specific setup below:

### Ubuntu ###
I have tested it on Ubuntu 14.04 and here the setup should be as simple as:
```
sudo apt-get install clang
```

### Windows ###
I am not fluent with Windows, so help needed. If you are willing to help, either install the package and report errors or educate me of a simple way to install clang there.

## Settings ##
I will only cover most important settings here.

- `include_dirs`:
    + stores the locations where `clang` should be looking for external headers, e.g. `boost`, `Ros`, `Eigen`, `OpenCV`, etc.
    + you can use placeholders like `$project_base_name` or `$project_base_path` to make includes more convenient.
    + it is absolutely ok to include a folder that does not exist. `clang` knows how to deal with it and it will neither break anything nor make things slower.
    + See [my own settings](https://github.com/niosus/config-sublime/blob/master/Packages%2FUser%2FEasyClangComplete.sublime-settings#L4) as an example if you wish.
- `std_flag`:
    + sets the standard flag that will be used for compilation. Defaults to `std=c++11`
- `triggers`:
    + have you ever been annoyed by typing `3 > 2` only to find yourself waiting for completions after `>`. What about writing `case CONST:`? If you know what I am talking about you will understand how important this is.
    + defaults are `".", "::", "->"`. The autocompletions will not trigger on `>` or `:`. They will also not trigger while typing a number like `3.14`.

Please see the default settings file in the repo for more settings descriptions. Every setting in [settings file](EasyClangComplete.sublime-settings) should have an understandable comment. Should they not be clear - create an issue.


## Credits ##
The whole work seen here was originally a fork of another repository: https://github.com/pl-ca/ClangAutoComplete

However, with time this plugin has grown quite different from its origin and this is why you see it as a separate package now. Anyway, I encourage you to check out what @pl-ca has to offer and come back if you still like this plugin more.

The trick with multiple `clang.cindex` files is inspired by this repo: https://github.com/griebd/clangHelper Thanks for inspiration!

## Licence ##
![licence](http://www.wtfpl.net/wp-content/uploads/2012/12/wtfpl-badge-1.png)

Just as the original package by @pl-ca, I decided to adopt the most strict licence we have found:

> DO WHAT THE F*CK YOU WANT TO PUBLIC LICENSE
> Version 2, December 2004
> Copyright (C) 2016 Igor Bogoslavskyi [igor.bogoslavskyi@gmail.com]

>Everyone is permitted to copy and distribute verbatim or modified copies of this license document, and changing it is allowed as long as the name is changed.

>DO WHAT THE F*CK YOU WANT TO PUBLIC LICENSE TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION

>0.You just DO WHAT THE F*CK YOU WANT TO.




