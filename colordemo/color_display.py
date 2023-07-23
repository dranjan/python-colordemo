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

from collections import defaultdict
from sys import stdout

from .terminal_query import TerminalQueryContext


class ColorDisplay(TerminalQueryContext):
    """
    Class for producing a colored display of terminal RGB values.  It's
    best to use this class as a context manager, which will properly set
    and reset the terminal's attributes.
    """

    def __init__(self, tty_fd,
                 timeout=100, color_level=3, do_query=True,
                 screen_forward=False):
        """
        Arguments:
            tty_fd: open file descriptor connected to a terminal.
            timeout: same interpretation as in rgb_query. A larger
                timeout will be used a small number of times to test the
                capabilities of the terminal.
            color_level: how much color should be in the output. Use 0
                to suppress all color and 3 or greater for maximum
                coloredness.
            do_query: whether to attempt to query RGB values from the
                terminal or just use placeholders everywhere.
            screen_forward: whether to attempt to forward queries
                through a screen or tmux session if we are in one.
        """
        TerminalQueryContext.__init__(self, tty_fd, screen_forward)

        self.timeout = timeout
        self.color_level = color_level
        self.do_query = do_query

        def none_factory():
            return None

        # colors for highlighting
        self.hi = defaultdict(none_factory)

        self.hi['['] = 10
        self.hi[']'] = 10
        self.hi['+'] = 9
        self.hi['/'] = 9

        for c in '0123456789ABCDEF':
            self.hi[c] = 12

        # String to use for color values that couldn't be determined
        self.rgb_placeholder = '??????'
        self.fmt = '{:02X}{:02X}{:02X}'
        self.scale = 0xff

    def __enter__(self):
        TerminalQueryContext.__enter__(self)

        # try getting the rgb value for color 0 to decide whether to
        # bother trying to query any more colors.
        self.do_query = (self.do_query and
                         self.get_indexed_color(0, self.timeout*2))

        if self.color_level >= 1:
            stdout.write(self.reset)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.color_level >= 1:
            stdout.write(self.reset)

        TerminalQueryContext.__exit__(self, exc_type, exc_value,
                                      traceback)

    def show_fgbg(self):
        """
        Show the foreground and background colors.

        Errors:
            TerminalUninitializedError: if this instance's context has
                not been entered.
        """
        if self.do_query:
            bg = self.format(self.get_bg(timeout=self.timeout))
            fg = self.format(self.get_fg(timeout=self.timeout))
        else:
            bg = self.rgb_placeholder
            fg = self.rgb_placeholder

        stdout.write("\n    Background: %s\n" % bg)
        stdout.write("    Foreground: %s\n\n" % fg)

    def show_ansi(self):
        """
        Show the 16 ANSI colors (colors 0-15).

        Errors:
            TerminalUninitializedError: if this instance's context has
                not been entered.
        """
        color_order = [0, 1, 3, 2, 6, 4, 5, 7]

        names = ['   Black ', '    Red  ', '   Green ', '  Yellow ',
                 '   Blue  ', '  Magenta', '   Cyan  ', '   White ']

        stdout.write(self.fgcolor('15', 3))

        for k in range(8):
            a = color_order[k]
            stdout.write(names[a])

        stdout.write('\n')
        stdout.write(self.fgcolor(None, 3))

        c = None
        for k in range(8):
            a = color_order[k]
            c = self.hiprint('   [%X/%X] ' % (a, 8 + a), c)
        stdout.write('\n')

        self.show_color_table([0, 8], color_order)

    def show_color_cube(self, n):
        """
        Show the "RGB cube" (xterm colors 16-231 (256-color) or 16-79
        (88-color)).  The cube has sides of length 6 or 4 (for 256-color
        or 88-color, respectively).

        Arguments:
            n: 256 or 88.

        Errors:
            TerminalUninitializedError: if this instance's context has
                not been entered.
        """
        base = {256: 6, 88: 4}[n]

        c = None
        c = self.hiprint('[ + ]   ', c)
        for w in range(base):
            c = self.hiprint('[%X]      ' % w, c)
        stdout.write('\n\n' + self.fgcolor(None, 3))

        for u in range(base):
            for v in range(base):
                stdout.write(' '*v)

                x = (u*base + v)*base
                self.hiprint('  [%02X]  ' % (16 + x))
                stdout.write(self.fgcolor(None, 3))

                for w in range(base):
                    self.show_color(x + w + 16)
                stdout.write('\n')
            stdout.write('\n\n')

    def show_grayscale_ramp(self, end):
        """
        Show the "grayscale ramp" (xterm colors 232-255 (256-color) or
        80-87 (88-color)).

        Arguments:
            n: 256 or 88.

        Errors:
            TerminalUninitializedError: if this instance's context has
                not been entered.
        """
        start = {256: 232, 88: 80}[end]
        n = end - start

        vals = [self.get_color(a) for a in range(start, end)]

        c = None

        c = self.hiprint('[ ', c)
        for v in range(n):
            c = self.hiprint('%02X ' % (start + v), c)
        c = self.hiprint(']\n', c)

        stdout.write('\n ' + self.fgcolor(None, 3))

        for v in range(n):
            stdout.write(' ' + self.block(start + v, 2))
        stdout.write('\n ')

        for u in range(3):
            for v in range(n):
                stdout.write(' ')
                stdout.write(self.fgcolor(start + v, 2))
                stdout.write(vals[v][2*u: 2*(u + 1)])
                stdout.write(self.fgcolor(None, 2))
            stdout.write('\n ')
        stdout.write('\n')

    def show_colors(self, n):
        """
        Make a table showing colors 0 through n-1.

        Arguments:
            n: the number (int) of colors to show.

        Errors:
            TerminalUninitializedError: if this instance's context has
                not been entered.
        """
        self.show_color_table(range(0, n, 8), range(8), n, True)

    def show_color_table(self, rows, cols, stop=-1, label=False):
        """
        Make a color table with all possible color indices of the form
        rows[k] + cols[j] that are less than `stop` (if `stop` is not
        negative). If label is True, then print row and column labels.

        Arguments:
            rows, cols: iterable of int..
            stop: if nonnegative, the upper bound (non-inclusive) on the
                color indices to display.
            label: whether to show row and column labels.

        Errors:
            TerminalUninitializedError: if this instance's context has
                not been entered.
        """
        if label:
            self.hiprint('[ + ]')
            stdout.write(self.fgcolor(None, 3))

            for a in cols:
                stdout.write('   ' + self.octal(a) + '  ')
            stdout.write('\n' + self.fgcolor(None, 1))

        if label:
            stdout.write('     ')

        stdout.write('\n')

        for b in rows:
            if label:
                stdout.write(self.octal(b) + ' ' +
                             self.fgcolor(None, 1))

            for a in cols:
                c = a + b
                if stop < 0 or c < stop:
                    self.show_color(b + a)
                else:
                    stdout.write('         ')
            stdout.write('\n')
        stdout.write('\n')

    def show_color(self, a):
        """
        Make a pretty display of color number `a`, showing a block of
        that color followed by the 6-character hexadecimal code for the
        color.

        Arguments:
            a: color index to show.

        Errors:
            TerminalUninitializedError: if this instance's context has
                not been entered.
        """
        stdout.write(' ' + self.block(a) + ' ')
        stdout.write(self.fgcolor(a, 2) + (self.get_color(a)))
        stdout.write(self.fgcolor(None, 2))

    def hiprint(self, s, last_color=-1):
        """
        Print s to stdout, highlighting digits, brackets, etc. if the
        color level allows it.

        Arguments:
            s: the string to print.
            last_color: the current terminal foreground color.  This
                should be `None` if no color is set, or the current
                color index, or something else (like a negative integer)
                if the color isn't known. (The last option is always
                safe and will force this function to do the right
                thing.)

        Return: the current foreground color, which can be passed as
            last_color to the next call if the color isn't changed in
            between.
        """
        for c in s:
            if c == ' ':
                color = last_color
            else:
                color = self.hi[c]

            if color != last_color:
                stdout.write(self.fgcolor(color, 3))

            stdout.write(c)
            last_color = color

        return last_color

    def octal(self, x):
        """
        Return a base-8 string for the integer x, highlighted if the
        color level allows it.

        Arguments:
            x: integer to convert.

        Return: string representation, possibly with ANSI color codes.
        """
        return (self.fgcolor(self.hi['+'], 3) + '0'
                + self.fgcolor(self.hi['0'], 3) + ('%03o' % x))

    def block(self, c, n=1):
        """
        Return a string that prints as a block of color `c` and size `n`.

        Arguments:
            c: color index of block.
            n: length of block.

        Return: string representation, possibly with ANSI color codes.
        """
        return self.bgcolor(c, 1) + ' '*n + self.bgcolor(None, 1)

    # Changing the foreground and background colors.
    #
    # While the 38;5 and 48;5 SGR codes are less portable than the usual
    # 30-37 and 40-47, these codes seem to be fairly widely implemented
    # (on X-windows terminals, screen, and tmux) and support the whole
    # color range, as opposed to just colors 0-8.  They also make it
    # very easy to set the background to a given color without needing
    # to mess around with bold or reverse video (which are hardly
    # portable themselves).  This is useful even for the 16 ANSI colors.

    def fgcolor(self, a=None, level=-1):
        """
        Return a string designed to set the foreground color to `a` when
        printed to the terminal. None means default.

        Arguments:
            a: color index to set to, or None to reset to default.
            level: minimum colorfulness level for which colors should be
                affected.

        Return: ANSI control sequence as string.
        """
        if self.color_level >= level:
            if a is None:
                return self.csi + '39m'
            else:
                return self.csi + '38;5;' + str(a) + 'm'
        else:
            return ''

    def bgcolor(self, a=None, level=-1):
        """
        Return a string designed to set the background color to `a` when
        printed to the terminal. None means default.

        Arguments:
            a: color index to set to, or None to reset to default.
            level: minimum colorfulness level for which colors should be
                affected.

        Return: ANSI control sequence as string.
        """
        if self.color_level >= level:
            if a is None:
                return self.csi + '49m'
            else:
                return self.csi + '48;5;' + str(a) + 'm'
        else:
            return ''

    def get_color(self, a):
        """
        Return a formatted string representing the given color index,
        if possible.

        Arguments:
            a: color index to convert.

        Return: the color's hex code, or a placeholder.

        Errors:
            TerminalUninitializedError: if this instance's context has
                not been entered.
        """
        if self.do_query:
            c = self.get_indexed_color(a, timeout=self.timeout)
            return self.format(c)
        else:
            return self.rgb_placeholder

    def format(self, c):
        """
        Return a formatted string representing RGBAColor instance c.

        Arguments:
            c: RGBAColor instance to convert, or None.

        Return: hex code of c, or a placeholder.
        """
        if c:
            return "%02X%02X%02X" % (int(c.r * 0xffff) // 256,
                                     int(c.g * 0xffff) // 256,
                                     int(c.b * 0xffff) // 256)
        else:
            return self.rgb_placeholder
