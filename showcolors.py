#!/usr/bin/python

'''
This is a Python script to show off your terminal ANSI colors (or more
colors, if your terminal has them).  It works on both Python 2.7 and
Python 3.

This script must be run from the terminal whose colors you want to
showcase.  Not all terminal types are supported (see below).  At the
very minimum, 16-color support is required. 

Fully supported terminals:
    
    xterm
    urxvt

For these terminals, this script can show a color table with correct RGB
values for each color.  It queries the RGB values from the terminal
itself, so it works even if you change the colors after starting the
terminal.

Mostly supported terminals: pretty much all VTE-based terminals. This
includes:

    vte
    Terminal (XFCE)
    gnome-terminal
    terminator
    tilda

and many more.  These are on "mostly" status because I don't know how to
query their foreground and background colors.  Everything else works,
though, albeit with noticeable slowness (which may be beyond this
script's control).

Somewhat supported terminals: pretty much all other X-client terminals
I've tried.  These include:

    konsole (KDE)
    terminology (Enlightenment)
    Eterm (Enlightenment)
    (etc.)

For these terminals, the script can output a color table just fine, but
without RGB values.

Unsupported terminals:

    ajaxterm
    Linux virtual console (i.e., basic TTY without X-windows)

Warning: do not run this script on the Linux virtual console unless you
want a garbled TTY!  That said, you can still type `tput reset<Enter>'
afterward to get back to a usable console. :-)  The situation with
ajaxterm is similar, but not as bad.

If a terminal isn't mentioned here, I probably haven't tried it.  Attempt
at your own risk!

Note regarding screen/tmux: this script can theoretically be run from a
screen or tmux session, but you will not get any RGB values in the
output (indeed, a screen session can be opened on multiple terminals
simultaneously, so there typically isn't a well defined color value for
a given index).  However, it's interesting to observe that screen and
tmux emulate a 256 color terminal independently of the terminal(s)
to which they are attached, which is very apparent if you run the script
with 256-color output on a screen session attached to a terminal with 8-
or 16-color terminfo (or with $TERM set to such).

This code is licensed under the terms of the GNU General Public License:
    http://www.gnu.org/licenses/gpl-3.0.html

and with absolutely no warranty.  All use is strictly at your own risk.

'''

import os
from sys import stdin, stdout, stderr, version_info
import re
import select
import termios
from collections import defaultdict
from argparse import (ArgumentParser, ArgumentError)


# Operating system command
osc = "\033]"

# String terminator
#  ("\033\\" is another option, but "\007" seems to be understood by
#  more terminals.  Terminology, for example, doesn't seem to like
#  "\033\\".)
st = "\007"

# Control sequence introducer
csi = "\033["

# ANSI SGR0
reset = csi + 'm'


# This is what we expect the terminal's response to a query for a color
# to look like.  If we didn't care about urxvt, we could get away with a
# simpler implementation here, since xterm and vte seem to give pretty 
# consistent and systematic responses.  But I actually use urxvt most of
# the time, so....
ndec = "[0-9]+"
nhex = "[0-9a-fA-F]+"
crgb = ("\033\\]({ndec};)+rgba?:" +
        "({nhex})/({nhex})/({nhex})(/({nhex}))?").format(**vars())

re_response = re.compile(crgb)


#######################################################################
# Query-related error conditions

class TerminalSetupError(Exception):

    '''
    We couldn't set up the terminal properly.

    '''

    def __init__(self, fd):
        Exception.__init__(self, "Couldn't set up terminal on file " +
                           ("descriptor %d" % fd))


class InvalidResponseError(Exception):

    '''
    The terminal's response couldn't be parsed.

    '''

    def __init__(self, q, r):
        Exception.__init__(self, "Couldn't parse response " + repr(r) +
                           " to query " + repr(q))


class NoResponseError(Exception):

    '''
    The terminal didn't respond, or we were too impatient.

    '''

    def __init__(self, q):
        Exception.__init__(self, "Timeout on query " + repr(q))


########################################################################

class TerminalQueryContext(object):

    '''
    Context manager for terminal RGB queries.

    '''

    def __init__(self, fd):
        '''
        fd: open file descriptor referring to the terminal we care
        about.

        '''
        self.tc_save = None
        self.fd = fd

        self.P = select.poll()
        self.P.register(self.fd, select.POLLIN)

        self.num_errors = 0


    def __enter__(self):
        '''
        Set up the terminal for queries.

        '''
        self.tc_save = termios.tcgetattr(self.fd)

        tc = termios.tcgetattr(self.fd)

        # Don't echo the terminal's responses
        tc[3] &= ~termios.ECHO

        # Noncanonical mode (i.e., disable buffering on the terminal
        # level)
        tc[3] &= ~termios.ICANON

        # Make input non-blocking
        tc[6][termios.VMIN] = 0
        tc[6][termios.VTIME] = 0

        termios.tcsetattr(self.fd, termios.TCSANOW, tc)

        # Check if it succeeded
        if termios.tcgetattr(self.fd) != tc:
            termios.tcsetattr(self.fd, termios.TCSANOW, self.tc_save)
            raise TerminalSetupError(self.fd)

        return self


    def __exit__(self, exc_type, exc_value, traceback):
        '''
        Reset the terminal to its original state.

        '''
        self.flush_input()

        if self.tc_save is not None:
            termios.tcsetattr(self.fd, termios.TCSANOW, self.tc_save)


    # Wrappers for xterm & urxvt operating system controls.
    #
    # These codes are all common to xterm and urxvt. Their responses
    # aren't always in the same format (xterm generally being more
    # consistent), but the regular expression used to parse the
    # responses is general enough to work for both.
    #
    # Note: none of these functions is remotely thread-safe.


    def get_fg(self, timeout):
        '''
        Get the terminal's foreground (text) color as a 6-digit
        hexadecimal string.

        '''
        return self.rgb_query([10], timeout)


    def get_bg(self, timeout):
        '''
        Get the terminal's background color as a 6-digit hexadecimal
        string.

        '''
        return self.rgb_query([11], timeout)


    def get_indexed_color(self, a, timeout):
        '''
        Get color a as a 6-digit hexadecimal string.

        '''
        return self.rgb_query([4, a], timeout)


    def test_fg(self, timeout):
        '''
        Return True if the terminal responds to the "get foreground"
        query within the time limit and False otherwise.

        '''
        return self.test_rgb_query([10], timeout)


    def test_bg(self, timeout):
        '''
        Return True if the terminal responds to the "get background"
        query within the time limit and False otherwise.

        '''
        return self.test_rgb_query([11], timeout)


    def test_color(self, timeout):
        '''
        Return True if the terminal responds to the "get color 0" query
        within the time limit and False otherwise.

        '''
        return self.test_rgb_query([4, 0], timeout)


    def test_rgb_query(self, q, timeout):
        '''
        Determine if the terminal supports query q.

        Arguments: `q' and `timeout' have the same interpretation as in
            rgb_query().

        Return: True if the terminal gives a valid response within the
            time limit and False otherwise.

        This function will not raise InvalidResponseError or
        NoResponseError, but any other errors raised by rgb_query will
        be propagated. 

        '''
        try:
            self.rgb_query(q, timeout)
            return True
        except (InvalidResponseError, NoResponseError):
            return False


    def flush_input(self):
        '''
        Discard any input that can be read at this moment.

        '''
        repeat = True
        while repeat:
            evs = self.P.poll(0)
            if len(evs) > 0:
                os.read(self.fd, 4096)
                repeat = True
            else:
                repeat = False


    # The problem I'm attempting to work around with this complicated
    # implementation is that if you supply a terminal with a query that
    # it does not recognize or does not have a good response to, it will
    # simply not respond *at all* rather than signaling the error in any
    # way.  Moreover, there is a large variation in how long terminals
    # take to respond to valid queries, so it's difficult to know
    # whether the terminal has decided not to respond at all or it needs
    # more time.  This is why rgb_query has a user-settable timeout.


    def rgb_query(self, q, timeout=-1):
        '''
        Query a color-valued terminal parameter. 

        Arguments:
            q: The query code as a sequence of nonnegative integers,
                i.e., [q0, q1, ...] if the escape sequence in
                pseudo-Python is

                    "\033]{q0};{q1};...;?\007"

            timeout: how long to wait for a response.  (negative means
                wait indefinitely if necessary)

        Return: the color value as a 6-digit hexadecimal string.

        Errors:
            NoResponseError will be raised if the query times out.

            InvalidResponseError will be raised if the terminal's
            response can't be parsed.

        See 
            http://invisible-island.net/xterm/ctlseqs/ctlseqs.html

        ("Operating System Controls") to see the various queries
        supported by xterm.  Urxvt supports some, but not all, of them,
        and has a number of its own (see man -s7 urxvt). 

        Warning: before calling this function, make sure the terminal is
        in noncanonical, non-blocking mode.  This can be done easily by
        calling self.__enter__() or instantiating this instance in a
        "with" clause, which will do that automatically.

        '''
        query = osc + ';'.join([str(k) for k in q]) + ';?' + st

        self.flush_input()
        os.write(self.fd, query.encode())

        # This is addmittedly flawed, since it assumes the entire
        # response will appear in one shot.  It seems to work in
        # practice, though.

        evs = self.P.poll(timeout)
        if len(evs) == 0:
            self.num_errors += 1
            raise NoResponseError(query)

        r = os.read(self.fd, 4096)
        if version_info.major >= 3:
            r = r.decode()

        m = re_response.search(r)

        if not m:
            self.num_errors += 1
            raise InvalidResponseError(query, r)

        # (possibly overkill, since I've never seen anything but 4-digit
        # RGB components in responses from terminals, in which case `nd'
        # is 4 and `u' is 0xffff, and the following can be simplified as
        # well (and parse_component can be eliminated))
        nd = len(m.group(2))
        u = (1 << (nd << 2)) - 1

        # An "rgba"-type reply (for urxvt) is apparently actually
        #
        #    rgba:{alpha}/{alpha * red}/{alpha * green}/{alpha * blue}
        #
        # I opt to extract the actual RGB values by eliminating alpha.
        # (In other words, the alpha value is discarded completely in
        # the reported color value, which is a compromise I make in
        # order to get an intuitive and compact output.)

        if m.group(5):
            # There is an alpha component
            alpha = float(int(m.group(2), 16))/u
            idx = [3, 4, 6]
        else:
            # There is no alpha component
            alpha = 1.0
            idx = [2, 3, 4]

        c_fmt = '%0' + ('%d' % nd) + 'x'

        components = [int(m.group(i), 16) for i in idx]
        t = tuple(parse_component(c_fmt % (c/alpha)) 
                  for c in components)

        return "%02X%02X%02X" % t


    def test_num_colors(self, timeout):
        '''
        Attempt to determine the number of colors we are able to query
        from the terminal.  timeout is measured in milliseconds and has
        the same interpretation as in rgb_query.  A larger timeout is
        safer but will cause this function to take proportionally more
        time.

        '''
        # We won't count failed queries in this function, since we're
        # guaranteed to fail a few.
        num_errors = self.num_errors

        if not self.test_color(timeout):
            return 0
        
        a = 0
        b = 1
        while self.test_rgb_query([4, b], timeout):
            a = b
            b += b

        while b - a > 1:
            c = (a + b)>>1
            if self.test_rgb_query([4, c], timeout):
                a = c
            else:
                b = c

        self.num_errors = num_errors
        return b



def parse_component(s):
    '''
    Take a string representation of a hexadecimal integer and transorm
    the two most significant digits into an actual integer (or double
    the string if it has only one character).

    '''
    n = len(s)

    if n == 1:
        s += s
    elif n > 2:
        s = s[:2]

    return int(s, 16)


########################################################################

class ColorDisplay(TerminalQueryContext):

    '''
    Class for producing a colored display of terminal RGB values.  It's
    best to use this class as a context manager, which will properly set
    and reset the terminal's attributes.

    '''

    def __init__(self, tty_fd,
                 timeout=100, color_level=3, do_query=True):
        '''
        tty_fd: open file descriptor connected to a terminal.

        timeout: same interpretation as in rgb_query. A larger timeout
            will be used a small number of times to test the
            capabilities of the terminal.

        color_level: how much color should be in the output. Use 0 to
            suppress all color and 3 or greater for maximum coloredness.

        do_query: whether to attempt to query RGB values from the
            terminal or just use placeholders everywhere

        '''
        TerminalQueryContext.__init__(self, tty_fd)

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


    def __enter__(self):
        TerminalQueryContext.__enter__(self)

        # try getting the rgb value for color 0 to decide whether to
        # bother trying to query any more colors.
        self.do_query = self.do_query and self.test_color(self.timeout*5)

        if self.color_level >= 1:
            stdout.write(reset)

        return self


    def __exit__(self, exc_type, exc_value, traceback):
        if self.color_level >= 1:
            stdout.write(reset)

        TerminalQueryContext.__exit__(self, exc_type, exc_value,
                                      traceback)


    def show_fgbg(self):
        '''
        Show the foreground and background colors.

        '''
        if self.do_query:
            try:
                bg = self.get_bg(timeout=self.timeout)
            except (InvalidResponseError, NoResponseError):
                bg = self.rgb_placeholder

            try:
                fg = self.get_fg(timeout=self.timeout)
            except (InvalidResponseError, NoResponseError):
                fg = self.rgb_placeholder
        else:
            bg = self.rgb_placeholder
            fg = self.rgb_placeholder

        stdout.write("\n    Background: %s\n" % bg)
        stdout.write("    Foreground: %s\n\n" % fg)


    def show_ansi(self):
        '''
        Show the 16 ANSI colors (colors 0-15).

        '''
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

        self.show_color_table([0,8], color_order)


    def show_color_cube(self, n):
        '''
        Show the "RGB cube" (xterm colors 16-231 (256-color) or 16-79
        (88-color)).  The cube has sides of length 6 or 4 (for 256-color
        or 88-color, respectively).

        '''
        base = {256:6, 88:4}[n]

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
        '''
        Show the "grayscale ramp" (xterm colors 232-255 (256-color) or
        80-87 (88-color)).

        '''
        start = {256:232, 88:80}[end]
        n = end - start

        vals = [self.get_color(a) for a in range(start, end)]

        #stdout.write(reset)
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
                stdout.write(vals[v][2*u : 2*(u + 1)])
                stdout.write(self.fgcolor(None, 2))
            stdout.write('\n ')
        stdout.write('\n')


    def show_colors(self, n):
        '''
        Make a table showing colors 0 through n-1.

        '''
        self.show_color_table(range(0,n,8), range(8), n, True)


    def show_color_table(self, rows, cols, stop=-1, label=False):
        '''
        Make a color table with all possible color indices of the form
        rows[k] + cols[j] that are less than `stop' (if `stop' is not
        negative). If label is True, then print row and column labels.

        '''
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
        '''
        Make a pretty display of color number `a', showing a block of
        that color followed by the 6-character hexadecimal code for the
        color.

        '''
        stdout.write(' ' + self.block(a) + ' ')
        stdout.write(self.fgcolor(a, 2) + (self.get_color(a)))
        stdout.write(self.fgcolor(None, 2))


    def hiprint(self, s, last_color=-1):
        '''
        Print s to stdout, highlighting digits, brackets, etc. if the
        color level allows it.

        Arguments:
            s: the string to print.

            last_color: the current terminal foreground color.  This
                should be `None' if no color is set, or the current
                color index, or something else (like a negative integer)
                if the color isn't known.  (The last option is always
                safe and will force this function to do the right
                thing.)

        Return: the current foreground color, which can be passed as
            last_color to the next call if the color isn't changed in
            between.

        '''
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
        '''
        Return a base-8 string for the integer x, highlighted if the
        color level allows it.

        '''
        return self.fgcolor(self.hi['+'], 3) + '0' + \
               self.fgcolor(self.hi['0'], 3) + ('%03o' % x)


    def block(self, c, n=1):
        '''
        Return a string that prints as a block of color `c' and size `n'.

        '''
        return self.bgcolor(c, 1) + ' '*n + self.bgcolor(None, 1)


    # Changing the foreground and background colors.
    #
    # While the 38;5 and 48;5 SGR codes are less portable than the usual
    # 30-37 and 40-47, these codes seem to be fairly widely implemented (on
    # X-windows terminals, screen, and tmux) and support the whole color
    # range, as opposed to just colors 0-8.  They also make it very easy to
    # set the background to a given color without needing to mess around
    # with bold or reverse video (which are hardly portable themselves).
    # This is useful even for the 16 ANSI colors.


    def fgcolor(self, a=None, level=-1):
        '''
        Return a string designed to set the foreground color to `a' when 
        printed to the terminal. None means default.

        '''
        if self.color_level >= level:
            if a is None:
                return csi + '39m'
            else:
                return csi + '38;5;' + str(a) + 'm'
        else:
            return ''


    def bgcolor(self, a=None, level=-1):
        '''
        Return a string designed to set the background color to `a' when 
        printed to the terminal. None means default.

        '''
        if self.color_level >= level:
            if a is None:
                return csi + '49m'
            else:
                return csi + '48;5;' + str(a) + 'm'
        else:
            return ''


    def get_color(self, a):
        if self.do_query:
            try:
                return self.get_indexed_color(a, timeout=self.timeout)
            except (InvalidResponseError, NoResponseError):
                return self.rgb_placeholder
        else:
            return self.rgb_placeholder


########################################################################
# Command-line arguments

timeout_dft = 200

parser = ArgumentParser(
        description="Python script to show off terminal colors.",
        epilog="Run this script from the terminal whose colors " +
               "you want to showcase.  " +
               "For a brief synopsis of which terminal types are " +
               "supported, see the top of the source code.")

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


########################################################################

def color_display(*args):
    return ColorDisplay(*args)


if __name__ == '__main__':
    args = parser.parse_args()

    assert not (args.pretty and args.flat)

    if args.pretty:
        if args.n not in p_choices:
            raise ArgumentError(
                    arg_p,
                    "N must belong to %r" % p_choices)

    with ColorDisplay(0, args.timeout, args.level, args.do_query) as C:
        if args.n == 0:
            args.n = C.test_num_colors(args.timeout)

        if not (args.pretty or args.flat):
            if args.n in p_choices:
                args.pretty = True
            else:
                args.flat = True

        if args.level >= 1:
            stdout.write(reset)

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
