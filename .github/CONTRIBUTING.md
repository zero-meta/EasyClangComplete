# Contribute! #
Contributions are welcome! Look at the issue list. If there is something you
think you can tackle, write about it in that issue and submit a Pull Request.

# Don't rush! #
Please don't jump into creating a Pull Request straight away and open an issue
first. This way, we can synchronize our views on the problem, so that everyone
avoids losing time.

# There are two branches: #
- `master`: should be stable and generally following the last release. Used for
  urgent bug fixing
- `dev`: used to develop new features. Merges with master right before a new
  release

# Code style: #
- Line width is `80` characters
- Every public function should be documented
- The code passes linters:
  + `pep8`
  + `pep257`: ignoring `["D209", "D203", "D204"]`
- There is a test that checks this
