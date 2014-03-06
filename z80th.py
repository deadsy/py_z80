#-----------------------------------------------------------------------------
"""
Z80 CPU Emulation
"""
#-----------------------------------------------------------------------------

import z80da

#-----------------------------------------------------------------------------
# flags

_CF = 0x01 # carry
_NF = 0x02 # subtract
_PF = 0x04 # parity
_VF = _PF  # overflow
_XF = 0x08 # bit3 - undocumented
_HF = 0x10 # half carry (bcd)
_YF = 0x20 # bit5 - undocumented
_ZF = 0x40 # zero
_SF = 0x80 # sign

def _signed(x):
    if x & 0x80:
        x = (x & 0x7f) - 128
    return x

#-----------------------------------------------------------------------------

class Error(Exception):
    pass

#-----------------------------------------------------------------------------

class cpu:

    def _str_f(self):
        """return the flags as a string"""
        flags = []
        flags.append(('.', 'S')[bool(self.f & _SF)])
        flags.append(('.', 'Z')[bool(self.f & _ZF)])
        flags.append(('.', 'H')[bool(self.f & _HF)])
        flags.append(('.', 'P')[bool(self.f & _PF)])
        flags.append(('.', 'V')[bool(self.f & _VF)])
        flags.append(('.', 'N')[bool(self.f & _NF)])
        flags.append(('.', 'C')[bool(self.f & _CF)])
        return ''.join(flags)

    def _add_flags(self, res, val):
        """set the flags for an add operation: result = a + val"""
        self.f = self.f_sz[res & 0xff]
        self.f |= ((res >> 8) & _CF)
        self.f |= ((self.a ^ res ^ val) & _HF)
        self.f |= (((val ^ self.a ^ 0x80) & (val ^ res) & 0x80) >> 5)

    def _add16_flags(self, res, d, s):
        """set the flags for an 16 bit add operation: result = d + s"""
        self.f = self.f & (_SF | _ZF | _VF)
        self.f |= (((d ^ res ^ s) >> 8) & _HF)
        self.f |= (((res >> 16) & _CF) | ((res >> 8) & (_YF | _XF)))

    def _sub16_flags(self, res, d, s):
        """set the flags for a 16 bit sub operation: result = d - s"""
        self.f = (((d ^ res ^ s) >> 8) & _HF)
        self.f |= _NF
        self.f |= ((res >> 16) & _CF)
        self.f |= ((res >> 8) & (_SF | _YF | _XF))
        self.f |= (0, _ZF)[(res & 0xffff) == 0]
        self.f |= (((s ^ d) & (d ^ res) & 0x8000) >> 13)

    def _adc16_flags(self, res, d, s):
        """set the flags for a 16 bit adc operation: result = d + s + cf"""
        self.f = (((d ^ res ^ s) >> 8) & _HF)
        self.f |= ((res >> 16) & _CF)
        self.f |= ((res >> 8) & (_SF | _YF | _XF))
        self.f |= (0, _ZF)[(res & 0xffff) == 0]
        self.f |= (((s ^ d ^ 0x8000) & (d ^ res) & 0x8000) >> 13)

    def _sub_flags(self, res, val):
        """set the flags for a sub operation: result = a - val"""
        self.f = self.f_sz[res & 0xff]
        self.f |= ((res >> 8) & _CF)
        self.f |= _NF
        self.f |= ((self.a ^ res ^ val) & _HF)
        self.f |= (((val ^ self.a) & (self.a ^ res) & 0x80) >> 5)

    def _enter_halt(self):
        """enter halt mode"""
        self.halt = 1
        self._dec_pc(1)

    def _leave_halt(self):
        """leave halt mode"""
        if self.halt:
            self._inc_pc(1)
            self.halt = 0

    def _push(self, val):
        """push a 16 bit quantity onto the stack"""
        self.mem[self.sp - 1] = val >> 8
        self.mem[self.sp - 2] = val & 0xff
        self.sp = (self.sp - 2) & 0xffff

    def _pop(self):
        """pop a 16 bit quantity from the stack"""
        val = (self.mem[self.sp + 1] << 8) | self.mem[self.sp]
        self.sp = (self.sp + 2) & 0xffff
        return val

    def _peek(self, adr):
        """read and return the 16 bit value at mem[adr]"""
        return (self.mem[adr + 1] << 8) + self.mem[adr]

    def _poke(self, adr, val):
        """write the 16 bit value to mem[adr]"""
        self.mem[adr + 1] = val >> 8
        self.mem[adr] = val & 0xff

    def _set_af(self, val):
        """set the a and f registers with a 16 bit value"""
        self.a = (val >> 8) & 0xff
        self.f = val & 0xff

    def _get_af(self):
        """return the 16 bit value of the a and f registers"""
        return (self.a << 8) | self.f

    def _set_bc(self, val):
        """set the b and c registers with a 16 bit value"""
        self.b = (val >> 8) & 0xff
        self.c = val & 0xff

    def _get_bc(self):
        """return the 16 bit value of the b and c registers"""
        return (self.b << 8) | self.c

    def _set_de(self, val):
        """set the d and e registers with a 16 bit value"""
        self.d = (val >> 8) & 0xff
        self.e = val & 0xff

    def _get_de(self):
        """return the 16 bit value of the d and e registers"""
        return (self.d << 8) | self.e

    def _set_hl(self, val):
        """set the h and l registers with a 16 bit value"""
        self.h = (val >> 8) & 0xff
        self.l = val & 0xff

    def _get_hl(self):
        """return the 16 bit value of the h and l registers"""
        return (self.h << 8) | self.l

    def _get_pc(self):
        """return the 16 bit pc register"""
        return self.pc

    def _set_pc(self, val):
        """set the 16 bit pc register"""
        self.pc = val & 0xffff

    def _dec_pc(self, n):
        """decrement pc"""
        self.pc = (self.pc - n) & 0xffff

    def _inc_pc(self, n):
        """increment pc"""
        self.pc = (self.pc + n) & 0xffff

    def _get_nn(self):
        """return the 16 bit immediate at mem[pc], pc += 2"""
        nn = self._peek(self.pc)
        self._inc_pc(2)
        return nn

    def _get_n(self):
        """return the 8 bit immediate at mem[pc], pc += 1"""
        n = self.mem[self.pc]
        self._inc_pc(1)
        return n

    def da(self, adr):
        """
        Disassemble the instruction at mem[adr].
        Return the operation, operands and number of bytes.
        """
        return z80da.disassemble(self.mem, adr)

    def execute(self):
        """
        Execute a single instruction at the current mem[pc] location.
        Return the number of clock cycles taken.
        """
        self.r = (self.r + 1) & 0x7f
        code = self._get_n()
        return self.opcodes[code]()

    def interrupt(self, x = 0):
        """
        Perform interrupt actions
        """
        if self.iff1 == 0:
            return 0
        self._leave_halt()
        self.iff1 = 0
        self.iff2 = 0
        self._push(self.pc)
        if self.im == 0:
            self.pc = x & 0x38
            return 13
        elif self.im == 1:
            self.pc = 0x38
            return 11
        else:
            self._set_pc(self._peek((self.i << 8) + (x & 0xff)))
            return 17

    def reset(self):
        """
        reset the cpu state
        """
        self.a = 0xff
        self.f = 0xff
        self.b = 0xff
        self.c = 0xff
        self.d = 0xff
        self.e = 0xff
        self.h = 0xff
        self.l = 0xff
        self.alt_af = 0xffff
        self.alt_bc = 0xffff
        self.alt_de = 0xffff
        self.alt_hl = 0xffff
        self.sp = 0xffff
        self.ix = 0xffff
        self.iy = 0xffff
        self.i = 0
        self.r = 0
        self.im = 0
        self.iff1 = 0
        self.iff2 = 0
        self.halt = 0
        self.pc = 0

    def _repeated_prefix(self):
        """A prefix code hase been repeated. NOP and re-run the current prefix"""
        self._dec_pc(1)
        return 0

    def _execute_dddd(self):
        self._repeated_prefix()

    def _execute_ddfd(self):
        self._repeated_prefix()

    def _execute_fddd(self):
        self._repeated_prefix()

    def _execute_fdfd(self):
        self._repeated_prefix()

    def _execute_cb(self):
        code = self._get_n()
        return 4 + self.opcodes_cb[code]()

    def _execute_dd(self):
        code = self._get_n()
        return 4 + self.opcodes_dd[code]()

    def _execute_ed(self):
        code = self._get_n()
        return 4 + self.opcodes_ed[code]()

    def _execute_fd(self):
        code = self._get_n()
        return 4 + self.opcodes_fd[code]()

    def _execute_ddcb(self):
        d = _signed(self._get_n())
        code = self._get_n()
        return 8 + self.opcodes_ddcb00[code](d)

    def _execute_fdcb(self):
        d = _signed(self._get_n())
        code = self._get_n()
        return 8 + self.opcodes_fdcb00[code](d)

    def __str__(self):
        """return a string with processor state"""
        regs = []
        regs.append('a    : %02x' % self.a)
        regs.append('f    : %02x %s' % (self.f, self._str_f()))
        regs.append('b c  : %02x %02x' % (self.b, self.c))
        regs.append('d e  : %02x %02x' % (self.d, self.e))
        regs.append('h l  : %02x %02x' % (self.h, self.l))
        regs.append('a\'f\' : %02x %02x' % (self.alt_af >> 8, self.alt_af & 0xff))
        regs.append('b\'c\' : %02x %02x' % (self.alt_bc >> 8, self.alt_bc & 0xff))
        regs.append('d\'e\' : %02x %02x' % (self.alt_de >> 8, self.alt_de & 0xff))
        regs.append('h\'l\' : %02x %02x' % (self.alt_hl >> 8, self.alt_hl & 0xff))
        regs.append('i    : %02x' % self.i)
        regs.append('im   : %d' % self.im)
        regs.append('iff1 : %d' % self.iff1)
        regs.append('iff2 : %d' % self.iff2)
        regs.append('r    : %02x' % self.r)
        regs.append('ix   : %04x' % self.ix)
        regs.append('iy   : %04x' % self.iy)
        regs.append('sp   : %04x' % self.sp)
        regs.append('pc   : %04x' % self.pc)
        return '\n'.join(regs)

    def __init__(self, mem, io):
        self.mem = mem
        self.io = io
        self.reset()
