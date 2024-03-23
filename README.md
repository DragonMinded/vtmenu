A simple menu for a VT-100 compatible terminal which can be used as a launcher. Menu items are displayed sequentially on the terminal along with their numerical position (starting at 1). A user can select a menu entry by typing an exclaimation mark followed by the number, such as `!1` for the first entry. This matches what's prompted on the screen. Optionally, if the command takes parameters, the entry will display them and check that they've been provided after the selection. So, if menu entry 2 took two parameters you could type `!2 param1 param2` to launch the entry and provide both params.

The ini file format is simple, consisting of the name of the entry as the title, and a single `cmd` entry which is the program to execute when selected. Note that this is not a full shell command, so built-ins will not work. The command must point to an actual executable script or program on the controlling device itself. If a command takes a user parameter (or more than one), those can be indicated with `$1`, `$2` and so on and so forth in the command. To include a literal `$` character in your command, escape it by writing it twice, such as `$$`. If you want to take zero or more parameters, you can use the special syntax `$*`. If you want the display list to show those params named a specific way, you can include them below the command. An example follows:

```
[Entry Number One]
cmd = python3 /home/username/some_great_script.py --some flags

[Entry Number Two]
cmd = /home/username/shell_script "$1"
$1 = NAMED_PARAM
```

A user would launch the first command by typing `!1`<RETURN>. They would launch the second by typing `!2 param`<RETURN> and then the literal text `param` would be passed as a parameter to the script. Note that params cannot start with a dash and cannot contain the characters `;`, `>`, `<`, `)`, `(`, `|` or `&`.
