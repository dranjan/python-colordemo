import os
import re
import select
import termios
from sys import version_info

from colors import RGBColor

#######################################################################
# Query-related error conditions

class TerminalQueryError(Exception):
    
    '''
    Base class for the other exceptions.

    '''

    def __init__(self, message):
        Exception.__init__(self, message)


class TerminalSetupError(TerminalQueryError):

    '''
    We couldn't set up the terminal properly.

    '''

    def __init__(self, fd):
        TerminalQueryError.__init__(
            self, 
            ("Couldn't set up terminal on file " +
             ("descriptor %d" % fd)))


class InvalidResponseError(TerminalQueryError):

    '''
    The terminal's response couldn't be parsed.

    '''

    def __init__(self, q, r):
        TerminalQueryError.__init__(
            self, 
            ("Couldn't parse response " + repr(r) +
             " to query " + repr(q)))


class NoResponseError(TerminalQueryError):

    '''
    The terminal didn't respond, or we were too impatient.

    '''

    def __init__(self, q):
        TerminalQueryError.__init__(
            self, 
            "Timeout on query " + repr(q))


class TerminalUninitializedError(TerminalQueryError):

    '''
    Someone tried to do something without setting up the terminal
    properly (by calling TerminalQueryContext.__enter__).

    '''
    
    def __init__(self, fd):
        TerminalQueryError.__init__(
            self,
            (("Terminal on file descriptor %d " % fd) +
             "not set up"))


########################################################################

class TerminalQueryContext(object):

    '''
    Context manager for terminal RGB queries.

    '''

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


    def __init__(self, fd):
        '''
        fd: open file descriptor referring to the terminal we care
        about.

        '''
        self.tc_save = None
        self.fd = fd

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

        self.P = select.poll()
        self.P.register(self.fd, select.POLLIN)

        return self


    def __exit__(self, exc_type, exc_value, traceback):
        '''
        Reset the terminal to its original state.

        '''
        self.flush_input()

        if self.tc_save is not None:
            termios.tcsetattr(self.fd, termios.TCSANOW, self.tc_save)

        del self.P

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
        Get the terminal's foreground (text) color.

        '''
        return self.rgb_query([10], timeout)


    def get_bg(self, timeout):
        '''
        Get the terminal's background color.

        '''
        return self.rgb_query([11], timeout)


    def get_indexed_color(self, a, timeout):
        '''
        Get color number `a'.

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
        while self.P.poll(0):
            os.read(self.fd, 4096)


    # This is what we expect the terminal's response to a query for a
    # color to look like.  If we didn't care about urxvt, we could get
    # away with a simpler implementation here, since xterm and vte seem
    # to give pretty consistent and systematic responses.  But I
    # actually use urxvt most of the time, so....
    ndec = "[0-9]+"
    nhex = "[0-9a-fA-F]+"
    crgb = ("\033\\]({ndec};)+rgba?:" +
            "({nhex})/({nhex})/({nhex})(/({nhex}))?").format(**vars())

    re_response = re.compile(crgb)


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

        Return: the color value as an RGBColor instance.

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
        if not hasattr(self, "P"):
            raise TerminalUninitializedError(self.fd)

        query = (self.osc +
                 ';'.join([str(k) for k in q]) + ';?' +
                 self.st)

        self.flush_input()
        os.write(self.fd, query.encode())

        response = ""

        if self.P.poll(timeout):
            while self.P.poll(0):
                s = os.read(self.fd, 4096)
                if version_info.major >= 3:
                    s = s.decode()
                response += s
        else:
            self.num_errors += 1
            raise NoResponseError(query)

        m = self.re_response.search(response)

        if not m:
            self.num_errors += 1
            raise InvalidResponseError(query, response)

        # (possibly overkill, since I've never seen anything but 4-digit
        # RGB components in responses from terminals, in which case `nd'
        # is 4 and `u' is 0xffff
        nd = len(m.group(3))
        u = (1 << (nd << 2)) - 1

        # An "rgba"-type reply (for urxvt) is apparently actually
        #
        #    rgba:{alpha}/{alpha * red}/{alpha * green}/{alpha * blue}
        #
        # I opt to extract the actual RGB values by eliminating alpha.
        # (In other words, the alpha value is discarded completely in
        # the reported color value.)

        if m.group(5):
            # There is an alpha component
            alpha = float(int(m.group(2), 16))/u
            idx = [3, 4, 6]
        else:
            # There is no alpha component
            alpha = 1.0
            idx = [2, 3, 4]

        return RGBColor(*tuple(int(m.group(i), 16)/(alpha*u) 
                               for i in idx))


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
