# termcolors

`termcolors` is a Python module implementing RGB queries on xterm-like
terminals.  It includes a demo script for presenting terminal color
schemes, complete with RGB hex codes.

## Overview of functionality

`termcolors` allows you to programmatically determine the RGB values of
some terminals' ANSI colors (or more colors, if the terminal has them).
The functions must be run from the terminal whose colors you want to
determine, and with caveats if within a screen or tmux session (see
below for more on this).  Not all terminal types are supported.  At the
very minimum, 16-color support is required.

`termcolors` is intended to work on both Python 2.7 and Python 3.x.

## Terminal support

If a terminal isn't mentioned in one of the following subsections, we
probably haven't tried it.  Attempt at your own risk!

### Fully supported terminals

- xterm
- urxvt

For these terminals, all of the query functions work, including
foreground/background colors.

### Mostly supported terminals

- pretty much all VTE-based terminals. This includes:
  -  vte
  -  Terminal (XFCE)
  -  gnome-terminal
  -  terminator
  -  tilda

  and many more.

These are on "mostly" status because `termcolors` cannot query their
foreground and background colors.  Everything else works, though, albeit
with noticeable slowness, which may be beyond our control.

### Unsupported terminals

- apparently most other X-client terminals, including:
  - terminology (Enlightenment)
  - konsole (KDE)
  - Eterm (Enlightenment)

  and others.

These terminals don't seem to allow their colors to be queried
dynamically, so all RGB queries will fail, but the failure can be
detected.  (For terminology, a nonnegative timeout must be used, since
it apparently doesn't support *any* queries, breaking
`TerminalQueryContext.guarded_query`.)  The demo script can therefore
output a color table, but without RGB values.

There may be other ways to obtain RGB values for these terminals, such
as parsing configuration files or perhaps parsing the outpuf of
`xrdb --query`.  We have no plans to implement any of these.

### Really, really unsupported terminals

- ajaxterm
- Linux virtual console

Warning: running the demo script on the virtual console will probably
result in garbled TTY!  You can still type `tput reset` and press Enter
to get back to a usable console, though.  The situtation with ajaxterm
is similar but not as bad.

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
`--screen-forward`/`--tmux-forward` options in `termcolors-demo.py`).
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

`termcolors-demo.py`: executable Python script to show off your terminal
color schemes

## Credits

- dranjan (Darsh Ranjan): initial implementation
- oblique: improved tmux support
