Sublime Text 3 plugin that offers clang-based auto-completion for C++

This plugin aims to provide easy-to-use, minimal-setup autocompletions for C++
for Sublime Text 3. It is built to function in an asynchronous way, so that you
will not have to wait even when completions take slightly longer to load.

The plugin uses `libclang` with its python bindings to provide clang-based
autocompletions. In case `libclang` cannot be initialized or found it will use
completions based on the output of `clang -code-completion-at` run from the
command line.

If you want this as default behavior, set the setting `use_libclang` to
`false`.

This plugin is intended to be easy to use. It should autocomplete STL out of
the box and you should just add the folders your project uses to `include_dirs`
list in the settings to make it autocomplete code all your project. If you
experience problems - create an issue. I will try to respond as soon as
possible.


## IMPORTANT ##
Please be sure to read through the readme installation section to
make everything working here:
https://github.com/niosus/EasyClangComplete/blob/master/README.md#how-to-install

You can find all the relevant settings you can set here:
https://github.com/niosus/EasyClangComplete/blob/master/README.md#settings-highlights