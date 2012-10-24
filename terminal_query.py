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


    def get_num_colors(self, timeout=-1):
        '''
        Attempt to determine the number of colors we are able to query
        from the terminal.  timeout is measured in milliseconds and has
        the same interpretation as in guarded_query.  A larger timeout
        is safer but will cause this function to take proportionally
        more time.

        '''
        # We won't count failed queries in this function, since we're
        # guaranteed to fail a few.
        num_errors = self.num_errors

        if not self.get_indexed_color(0, timeout):
            return 0

        a = 0
        b = 1
        while self.get_indexed_color(b, timeout):
            a = b
            b += b

        while b - a > 1:
            c = (a + b)>>1
            if self.get_indexed_color(c, timeout):
                a = c
            else:
                b = c

        self.num_errors = num_errors
        return b


    def get_all_indexed_colors(self, limit, timeout=-1):
        '''
        Query as many indexed RGB values as possible up to `limit' 
        and return them all in a list. `timeout' has the same
        interpretation as in guarded_query.  A negative limit behaves
        like infinity.

        '''
        colors = []

        k = 0
        while limit < 0 or k < limit:
            c = get_indexed_color(k)
            if c:
                colors.append(c)
                k += 1
            else:
                break
        
        return colors


    # Wrappers for xterm & urxvt operating system controls.
    #
    # These codes are all common to xterm and urxvt. Their responses
    # aren't always in the same format (xterm generally being more
    # consistent), but the regular expression used to parse the
    # responses is general enough to work for both.
    #
    # Note: none of these functions is remotely thread-safe.


    def get_fg(self, timeout=-1):
        '''
        Get the terminal's foreground (text) color.

        '''
        return self.rgb_query([10], timeout)


    def get_bg(self, timeout=-1):
        '''
        Get the terminal's background color.

        '''
        return self.rgb_query([11], timeout)


    def get_indexed_color(self, a, timeout=-1):
        '''
        Get color number `a'.

        '''
        return self.rgb_query([4, a], timeout)


    def flush_input(self):
        '''
        Discard any input that can be read at this moment.

        '''
        while self.P.poll(0):
            os.read(self.fd, 4096)

    # Patterns matching unsigned decimal and hexadecimal integer
    # literals
    ndec = "[0-9]+"
    nhex = "[0-9a-fA-F]+"

    # The "guard" query and its response pattern
    q_guard = csi + "6n"

    str_guard = "(.*)\033\\[{ndec};{ndec}R".format(**vars())
    re_guard = re.compile(str_guard)

    # This is what we expect the terminal's response to a query for a
    # color to look like.  If we didn't care about urxvt, we could get
    # away with a simpler implementation here, since xterm and vte seem
    # to give pretty consistent and systematic responses.  But I
    # actually use urxvt most of the time, so....
    str_rgb = ("\033\\]({ndec};)+rgba?:(({nhex})/)?" +
               "({nhex})/({nhex})/({nhex})").format(**vars())

    re_rgb = re.compile(str_rgb)
    
    
    def rgb_query(self, q, timeout=-1):
        '''
        Query a color-valued terminal parameter. 

        Arguments:
            q: The query code as a sequence of nonnegative integers,
                i.e., [q0, q1, ...] if the escape sequence in
                pseudo-Python is

                    "\033]{q0};{q1};...;?\007"

            timeout: how long to wait for a response (same
                interpretation as in guarded_query).

        Return: the color value as an RGBColor instance.  If the
            terminal provides an unparseable (or no) response, then None
            will be returned.  

        See 
            http://invisible-island.net/xterm/ctlseqs/ctlseqs.html

        ("Operating System Controls") to see the various queries
        supported by xterm.  Urxvt supports some, but not all, of them,
        and has a number of its own (see man -s7 urxvt). 

        self.__enter__ must be called prior to calling this function, or
        TerminalUninitializedError will be raised.

        '''
        query = (self.osc +
                 ';'.join([str(k) for k in q]) + ';?' +
                 self.st)

        try:
            response = self.guarded_query(query, timeout)
        except NoResponseError:
            return None

        m = self.re_rgb.match(response)

        if not m:
            self.num_errors += 1
            return None

        # (possibly overkill, since I've never seen anything but 4-digit
        # RGB components in responses from terminals, in which case `nd'
        # is 4 and `u' is 0xffff
        nd = len(m.group(4))
        u = (1 << (nd << 2)) - 1

        # An "rgba"-type reply (for urxvt) is apparently actually
        #
        #    rgba:{alpha}/{alpha * red}/{alpha * green}/{alpha * blue}
        #
        # I opt to extract the actual RGB values by eliminating alpha.
        # (In other words, the alpha value is discarded completely in
        # the reported color value.)

        alpha = float(int(m.group(3), 16))/u if m.group(3) else 1.0

        return RGBColor(*tuple(int(m.group(i), 16)/(alpha*u) 
                               for i in [4, 5, 6]))


    # If a terminal sees an escape sequence it doesn't like, it will
    # simply ignore it.  Also, it's hard to predict how long a terminal
    # will take to respond to a query it does like.  However, some
    # escape sequences, like "\033[6n", will produce a predictable
    # response on *most* (but not all) terminals, and this fact can be
    # used to test for the absence of a response to a particular query 
    # on such terminals. 

    def guarded_query(self, q, timeout=-1):
        '''
        Send the terminal query string `q' and return the terminal's
        response.

        Arguments:
            q: the query string to send to the terminal.

            timeout: how many milliseconds to wait for a response, a
                negative number meaning "infinite".  If the terminal
                responds to the "device status report" (DSR) sequence
                "\033[6n", then it is safe to use an infinite timeout
                even if you don't know if query `q' will succeed.

        Return: The terminal's response to the query as a string.

        Errors:
            NoResponseError will be raised if the query times out.

            TerminalUninitializedError will be raised if this instance's
            context has not been __enter__-ed.

        If your terminal gives a nonstandard response to the DSR
        sequence, then you should subclass this class and redefine the
        `re_guard' member variable.  You can also redefine `q_guard' to
        something other than "\033[6n".

        '''
        if not hasattr(self, "P"):
            raise TerminalUninitializedError(self.fd)

        query = q + self.q_guard

        self.flush_input()
        os.write(self.fd, query.encode())

        response = ""

        while self.P.poll(timeout):
            #while self.P.poll(0):
            s = os.read(self.fd, 4096)
            if version_info.major >= 3:
                s = s.decode()
            response += s

            m = self.re_guard.match(response)

            if m:
                return m.group(1)
        else:
            self.num_errors += 1
            raise NoResponseError(query)
