#   Copyright 2012-2023 Darsh Ranjan
#
#   This file is part of termcolors.
#
#   termcolors is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   termcolors is distributed in the hope that it will be useful, but
#   WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with termcolors.  If not, see
#   <http://www.gnu.org/licenses/>.

from sys import (stdout, stderr)
from argparse import (ArgumentParser, ArgumentError)

from .color_display import ColorDisplay

########################################################################
# Command-line arguments

timeout_dft = -1

parser = ArgumentParser(
        description="Python script to show off terminal colors.",
        epilog="Run this script from the terminal whose colors " +
               "you want to showcase. " +
               "Only xterm-like terminals are supported " +
               "(see the README).")

mode_group = parser.add_mutually_exclusive_group()

p_choices = [16, 88, 256]

arg_p = mode_group.add_argument(
        '-p', '--pretty',
        action='store_true', default=False,
        help="show colors 0 through N-1 in a pretty format.  " +
             ("N must belong to %r.  " % p_choices) +
             "If N > 16, it should be the actual number of colors " +
             "supported by the terminal, or the output will almost " +
             "certainly not be pretty.")

mode_group.add_argument(
        '-f', '--flat',
        action='store_true', default=False,
        help="show a simple table with colors 0 through N-1.  ")

parser.add_argument(
        'n', nargs='?', metavar='N',
        type=int, default=16,
        help="number of colors to show.  " +
             "Unless you explicitly supply -p/--pretty or -f/--flat, " +
             "--pretty is used if possible and --flat is used " +
             "otherwise.  " +
             "N defaults to 16, showing the ANSI colors 0-15.  " +
             "If N is 0, the script will attempt to determine the " +
             "maximum number of colors automatically " +
             "(which may be slow).")

parser.add_argument(
        '--no-fgbg',
        action='store_false', dest='fgbg', default=True,
        help="suppress display of foreground/background colors.")

parser.add_argument(
        '--no-query',
        action='store_false', dest='do_query', default=True,
        help="don't try to query any RGB values from the terminal " +
             "and just use placeholders.")

parser.add_argument(
        '-t', '--timeout', metavar='T',
        type=int, default=timeout_dft,
        help="how long to wait for the terminal to "
             "respond to a query, in milliseconds  " +
             "[default: {0}].  ".format(timeout_dft) +
             "If your output has '?' characters " +
             "instead of RGB values " +
             "or junk printed after the script runs, " +
             "increasing this value may or may not " +
             "help, depending on the terminal.  " +
             "A negative T will behave like infinity.")

parser.add_argument(
        '-l', '--level', metavar='L',
        type=int, default=3,
        help="choose how much color to use in the output.  " +
             "(0 = no color; 3 = most color [default])")

parser.add_argument(
        '--screen-forward', '--tmux-forward',
        action='store_true', default=False,
        help="attempt to pass terminal queries through a tmux " +
             "session (ignored if this is not a tmux session)")

########################################################################


def main():
    args = parser.parse_args()

    assert not (args.pretty and args.flat)

    if args.pretty:
        if args.n not in p_choices:
            raise ArgumentError(
                    arg_p,
                    "N must belong to %r" % p_choices)

    with ColorDisplay(0, args.timeout, args.level, args.do_query,
                      args.screen_forward) as C:

        if args.n == 0:
            args.n = C.get_num_colors(args.timeout)

        if not (args.pretty or args.flat):
            if args.n in p_choices:
                args.pretty = True
            else:
                args.flat = True

        if args.level >= 1:
            stdout.write(C.reset)

        if args.fgbg:
            C.show_fgbg()

        if args.pretty:
            assert args.n in p_choices

            stdout.write('\n    ANSI colors:\n\n')
            C.show_ansi()

            if args.n > 16:
                stdout.write('\n    RGB cube:\n\n')
                C.show_color_cube(args.n)

                stdout.write('    Grayscale ramp:\n\n')
                C.show_grayscale_ramp(args.n)
        else:
            C.show_colors(args.n)

        if C.num_errors > 0:
            stderr.write("Warning: not all queries succeeded\n" +
                         "Warning:     (output contains " +
                         "placeholders and may be inaccurate)\n")


if __name__ == "__main__":
    main()
