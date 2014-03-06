#-----------------------------------------------------------------------------
"""
Console IO

Provides non-blocking, non-echoing access to the console interface.
"""
#-----------------------------------------------------------------------------

import os
import select
import termios
import sys

#-----------------------------------------------------------------------------
# when otherwise idle, allow other things to run

_poll_timeout = 0.1 # secs

#-----------------------------------------------------------------------------

CHAR_NULL  = 0x00
CHAR_BELL  = 0x07
CHAR_TAB   = 0x09
CHAR_CR    = 0x0a
CHAR_DOWN  = 0x10
CHAR_UP    = 0x11
CHAR_LEFT  = 0x12
CHAR_RIGHT = 0x13
CHAR_END   = 0x14
CHAR_HOME  = 0x15
CHAR_ESC   = 0x1b
CHAR_SPACE = 0x20
CHAR_QM    = 0x3f
CHAR_BS    = 0x7f
CHAR_DEL   = 0x7e

#-----------------------------------------------------------------------------

class console:

    def __init__(self):
        """set the console to non-blocking, non-echoing"""
        self.fd = os.open(os.ctermid(), os.O_RDWR)
        self.saved = termios.tcgetattr(self.fd)
        new = termios.tcgetattr(self.fd)
        new[3] &= ~termios.ICANON
        new[3] &= ~termios.ECHO
        termios.tcsetattr(self.fd, termios.TCSANOW, new)

    def close(self):
        """restore original console settings"""
        termios.tcsetattr(self.fd, termios.TCSANOW, self.saved)
        os.close(self.fd)

    def anykey(self):
        """poll for any key - return True when pressed"""
        (rd, wr, er) = select.select((self.fd,), (), (), 0)
        if rd:
            # absorb the key press
            os.read(self.fd, 3)
            return True
        else:
            return False

    def get(self):
        """get console input - return ascii code"""
        # block until we can read or we have a timeout
        (rd, wr, er) = select.select((self.fd,), (), (), _poll_timeout)
        if len(rd) == 0:
            # timeout - allow other routines to run
            return CHAR_NULL
        x = os.read(self.fd, 3)
        n = len(x)
        if n == 1:
            return ord(x)
        elif n == 3:
            if x == '\x1b[A':
                return CHAR_UP
            elif x == '\x1b[B':
                return CHAR_DOWN
            elif x == '\x1b[C':
                return CHAR_RIGHT
            elif x == '\x1b[D':
                return CHAR_LEFT
            elif x == '\x1b[F':
                return CHAR_END
            elif x == '\x1b[H':
                return CHAR_HOME
        return CHAR_NULL

    def put(self, data):
        """output a string to console"""
        os.write(self.fd, data)

#-----------------------------------------------------------------------------
