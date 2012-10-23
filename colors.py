from collections import namedtuple

RGBColorBase = namedtuple('RGBColorBase', ('r', 'g', 'b'))

class RGBColor(RGBColorBase):
    
    '''
    The usual representation for a color value as a triple of numbers in
    the range [0, 1].

    '''

    fmt = "rgb:{:04x}/{:04x}/{:04x}"
    scale = 0xffff

    def format(self, fmt, scale, fn=int):
        '''
        fmt is a Python format string.  The color components can be
        named in three ways:
            - using the letter names 'r', 'g', and 'b'
            - using the positional names 0, 1, and 2
            - implicitly

        For example, the following values of `fmt' are all equivalent:
            "({:02x}, {:02x}, {:02x})"
            "({0:02x}, {1:02x}, {2:02x})"
            "({r:02x}, {g:02x}, {b:02x})"

        Each components will be multiplied by "scale", and then the 
        optional function "fn" will be applied (default: `int').

        '''
        (rx, gx, bx) = (fn(self.r*scale),
                        fn(self.g*scale),
                        fn(self.b*scale))

        return fmt.format(rx, gx, bx, r=rx, g=gx, b=bx)


    def __str__(self):
        return self.format(self.fmt, self.scale)
