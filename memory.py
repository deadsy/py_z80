#-----------------------------------------------------------------------------
"""
Memory Devices
"""
#-----------------------------------------------------------------------------

import array

#-----------------------------------------------------------------------------

_empty = 0xff

#-----------------------------------------------------------------------------
# Base Memory Device

class memory:
    """Base Memory Device"""
    def __init__(self, bits = 0):
        """Create a memory device of size bytes."""
        size = 1 << bits
        self.mask = size - 1
        self.mem = array.array('B', (0,) * size)
        self.wr_notify = self.null
        self.rd_notify = self.null

    def null(self, adr):
        """do nothing read/write notification"""
        pass

    def __getitem__(self, adr):
        return _empty

    def __setitem__(self, adr, val):
        pass

    def load(self, adr, data):
        """load bytes into memory starting at a given address"""
        for i, val in enumerate(data):
            self.mem[adr + i] = val

    def load_file(self, adr, filename):
        """load file into memory starting at a given address"""
        for i, val in enumerate(open(filename, "rb").read()):
            self.mem[adr + i] = ord(val)

#-----------------------------------------------------------------------------
# Specific Memory Devices

class ram(memory):
    """Read/Write Memory"""
    def __getitem__(self, adr):
        return self.mem[adr & self.mask]

    def __setitem__(self, adr, val):
        if val != self.mem[adr & self.mask]:
            self.wr_notify(adr)
        self.mem[adr & self.mask] = val

class rom(memory):
    """Read Only Memory"""
    def __getitem__(self, adr):
        return self.mem[adr & self.mask]

class wom(memory):
    """Write Only Memory"""
    def __setitem__(self, adr, val):
        if val != self.mem[adr & self.mask]:
            self.wr_notify(adr)
        self.mem[adr & self.mask] = val

    def rd(self, adr):
        """backdoor read"""
        return self.mem[adr & self.mask]

class null(memory):
    """Unpopulated Memory"""
    pass

#-----------------------------------------------------------------------------
