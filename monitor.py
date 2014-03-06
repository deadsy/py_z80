#-----------------------------------------------------------------------------
"""
Generic 8-bit/64K Memory Machine Language Monitor
"""
#-----------------------------------------------------------------------------

import util

#-----------------------------------------------------------------------------
# help for cli leaf functions

_help_memdisplay = (
    ('<adr> [len]', 'address (hex)'),
    ( '', 'length (hex) - default is 0x40'),
)

_help_mem2file = (
    ('<adr> <len> [file]', 'address (hex)'),
    ( '', 'length (hex)'),
    ( '', 'filename - default is \"mem.bin\"'),
)

_help_file2mem = (
    ('<adr> [file] [len]', 'address (hex)'),
    ( '', 'filename - default is \"mem.bin\"'),
    ( '', 'length (hex) - default is file length'),
)

_help_memrd = (
    ('<adr>', 'address (hex)'),
)

_help_memwr = (
    ('<adr> <val>', 'address (hex)'),
    ( '', 'value (hex)'),
)

_help_disassemble = (
    ('[adr] [len]', 'address (hex) - default is current pc'),
    ( '', 'length (hex) - default is 0x10'),
)

#-----------------------------------------------------------------------------

class monitor:

    def __init__(self, cpu):
        self.cpu = cpu
        self.menu_memory = (
            ('display', 'dump memory to display', _help_memdisplay, self.cli_mem2display, None),
            ('>file', 'read from memory, write to file', _help_mem2file, self.cli_mem2file, None),
            ('<file', 'read from file, write to memory', _help_file2mem, util.todo, None),
            ('rd08', 'read 8 bits', _help_memrd, self.cli_rd08, None),
            ('rd16', 'read 16 bits', _help_memrd, self.cli_rd16, None),
            ('verify', 'verify memory against a file', _help_file2mem, self.cli_verify, None),
            ('wr08', 'write 8 bits', _help_memwr, self.cli_wr08, None),
            ('wr16', 'write 16 bits', _help_memwr, self.cli_wr16, None),
        )

    def mem2display(self, app, adr, length):
        """dump memory contents to the display"""
        # address is on a 16 byte boundary
        # convert length from bytes to an integral number of 16 bytes
        adr &= ~15
        length = (length + 15) & ~15
        md = mem_display(app, adr)
        for i in range(length):
            md.write(self.cpu.mem[adr + i])

    def cli_registers(self, app, args):
        """display cpu registers"""
        app.put('\n\n%s\n' % self.cpu)

    def cli_disassemble(self, app, args):
        """disassemble memory"""
        if util.wrong_argc(app, args, (0, 1, 2)):
            return
        length = 0x10
        if len(args) == 0:
            adr = self.cpu._get_pc()
        if len(args) >= 1:
            adr = util.int_arg(app, args[0], (0, 0xffff), 16)
            if adr == None:
                return
        if len(args) == 2:
            length = util.int_arg(app, args[1], (1, 0xffff), 16)
            if length == None:
                return
        app.put('\n\n')
        x = adr
        while x < adr + length:
            (operation, operands, n) = self.cpu.da(x)
            bytes = ' '.join(['%02x' % self.cpu.mem[i] for i in range(x, x + n)])
            app.put('%04x %-12s %-5s %s\n' % (x, bytes, operation, operands))
            x += n

    def cli_mem2display(self, app, args):
        """dump memory contents to the display"""
        if util.wrong_argc(app, args, (1, 2)):
            return
        adr = util.int_arg(app, args[0], (0, 0xffff), 16)
        if adr == None:
            return
        if len(args) == 2:
            length = util.int_arg(app, args[1], (1, 0xffff), 16)
            if length == None:
                return
        else:
            length = 0x40
        self.mem2display(app, adr, length)

    def cli_mem2file(self, app, args):
        pass

    def cli_rd08(self, app, args):
        pass

    def cli_rd16(self, app, args):
        pass

    def cli_verify(self, app, args):
        pass

    def cli_wr08(self, app, args):
        pass

    def cli_wr16(self, app, args):
        pass

#-----------------------------------------------------------------------------

class mem_display:
    """stateful object for memory dumps to the display"""

    def __init__(self, app, adr):
        self.app = app
        self.adr = adr
        self.bytes = []
        self.app.put('\n\naddr  0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F\n')

    def byte2char(self, bytes):
        """convert a set of bytes into printable characters"""
        char_str = []
        for b in bytes:
            if (b > 126) or (b < 32):
                char_str.append('.')
            else:
                char_str.append(chr(b))
        return ''.join(char_str)

    def write(self, data):
        """output the memory dump to the console"""
        if self.adr & 0x0f == 0x0f:
            self.bytes.append(data)
            val_str = ' '.join(['%02x' % b for b in self.bytes])
            char_str = self.byte2char(self.bytes)
            self.app.put('%04x: %s %s\n' % (self.adr - 15, val_str, char_str))
            self.bytes = []
        else:
            self.bytes.append(data)
        self.adr += 1

#-----------------------------------------------------------------------------
