#   Copyright 2012 Darsh Ranjan
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

from collections import namedtuple

RGBAColorBase = namedtuple('RGBAColorBase', ('r', 'g', 'b', 'a'))

class RGBAColor(RGBAColorBase):
    
    '''
    The usual representation for a color value plus alpha 
    as a quadruple of numbers in the range [0, 1].

    '''

    def format(self, fmt, scale, fn=round):
        '''
        fmt is a Python format string.  The color components can be
        named in three ways:
            - using the letter names 'r', 'g', 'b', and 'a'
            - using the positional names 0, 1, 2, and 3
            - implicitly

        For example, the following values of `fmt' are all equivalent:
            "({:02x}, {:02x}, {:02x})"
            "({0:02x}, {1:02x}, {2:02x})"
            "({r:02x}, {g:02x}, {b:02x})"

        Each component will be multiplied by "scale", and then the 
        optional function "fn" will be applied (default: `round').

        '''
        (rx, gx, bx) = (fn(self.r*scale),
                        fn(self.g*scale),
                        fn(self.b*scale))

        return fmt.format(rx, gx, bx, r=rx, g=gx, b=bx)


    def __bool__(self):
        return (self.r >= 0 and self.r <= 1 and
                self.g >= 0 and self.g <= 1 and
                self.b >= 0 and self.b <= 1)
