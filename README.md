A simple menu for a VT-100 which can be used as a launcher. Menu items are displayed sequentially on the terminal along with their numerical position (starting at 1). A user can select a menu entry by typing an exclaimation mark followed by the number, such as `!1` for the first entry. The ini file format is simple, consisting of the name of the entry as the title, and a single `cmd` entry which is the shell line to execute when selected. If a command takes a user parameter (or more), those can be substituted with `$1`, `$2` and so on and so forth. An example follows:

```
[Entry Number One]
cmd = python3 /home/username/some_great_script.py --some flags

[Entry Number Two]
cmd = /home/username/shell_script "$1"
```

A user would launch the first command by typing `!1`<RETURN>. They would launch the second by typing `!2 param`<RETURN> and then the `param` would be passed as a parameter to the script. Note that params cannot start with a dash and cannot contain the characters `;`, `>`, `<`, `|` or `&`. To include the whole line after the exlaimation mark, use the syntax `$*`.
