# `colordemo`

`colordemo` is a Python module implementing RGB queries on xterm-like
terminals.  It includes a demo script for presenting terminal color
schemes, complete with RGB hex codes.

## Usage

    python -m colordemo

    # To see all available options
    python -m colordemo --help

## Overview of functionality

`colordemo` allows you to programmatically determine the RGB values of
some terminals' ANSI colors (or more colors, if the terminal has them).
The functions must be run from the terminal whose colors you want to
determine, and with caveats if within a screen or tmux session (see
below for more on this).  Not all terminal types are supported (see the
next section).

`colordemo` is intended to work on both Python 2.7 and Python 3.x.

## Terminal support

The fundamental requirement for a terminal to be supported by `colordemo`
is for it to support the xterm-like OSC ("Operating System Command") control
sequences, listed under "Operating System Commands" here:

https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Operating-System-Commands

(Sometimes this support can be ascertained from the documentation of
the terminal, but often you just need to try it.)

We call these terminals "xterm-like". If a terminal emulator doesn't
support those sequences, then it won't be supported here.
There may be other ways to obtain RGB values for these terminals, such
as parsing configuration files or perhaps parsing the output of
`xrdb --query`, but we have no plans to implement any of these.
The only way to add support for a currently unsupported terminal is to
patch the terminal with support for the OSC sequences.

There are too many terminals for us to test all of them, so the lists
below are not exhaustive. If a terminal isn't mentioned in one of the
following subsections, attempt at your own risk!

### Fully supported terminals

- xterm
- urxvt
- VTE-based terminals, including:
  - vte
  - Terminal (XFCE)
  - gnome-terminal
  - terminator
  - tilda
  - (etc.)
- kitty
- alacritty
- wezterm
- ttyd

### Unsupported terminals

- Konsole-based terminals, which are buggy:
  - Konsole
  - yakuake
  - (etc.)
- terminology
- Linux basic TTY (text mode without X)

Some terminals (like terminology) don't seem to allow their colors to be
queried dynamically, so all RGB queries will fail, but the failure can
be detected. The demo script will therefore be able to output a color
table, but without RGB values.

Other terminals (like Konsole) seem to support the query codes but are
extremely buggy, returning incorrect values and even segfaulting
sometimes.

In other cases (like the basic TTY), `colordemo` will garble
the TTY and make it unreadable. (Try `tput reset<ENTER>` to restore it
to something usable.)

## Note regarding screen and tmux

It generally doesn't make sense to query a terminal from inside a screen
or tmux session, since a single screen or tmux session can be attached
to multiple terminals.  However, in the special case of being attached
to a single terminal, it is possible because tmux and screen provide
(different) methods to pass control sequences through to the attached
terminal.  Of course, it makes no sense to try this if there are
multiple terminals attached, and you should expect crazy results if you
do.  Thus, forwarding queries through screen or tmux is currently an
opt-in feature (see the `screen_forward` optional argument in
`TerminalQueryContext.__init__` or the
`--screen-forward`/`--tmux-forward` command-line options).
This will fail inside a nested screen or tmux session.

(Not using the optional screen/tmux control-passthrough support, it's
interesting to observe that screen and tmux emulate a 256-color terminal
independently of the terminal(s) to which they are attached, which is
very apparent if you run the script with 256-color output on a screen
session attached to a terminal with 8- or 16-color terminfo (or with
TERM set to such).)

## Overview of code

`colors.py`: defines the `RGBAColor` class, which is currently a simple
`collections.namedtuple`.

`terminal_query.py`: defines `TerminalQueryContext`, the main class for
handling queries to a terminal.  Various terminal properties can be
queried (depending on the terminal), but only queries for RGB values are
supported at the moment, since those are the main focus of this project.

`color_display.py`: defines `ColorDisplay`, a subclass of
`TerminalQueryContext` showing RGB queries put to use in creating color
tables.

`__main__.py`: command-line entry point.

## Credits

- dranjan (Darsh Ranjan): initial implementation
- oblique: improved tmux support
