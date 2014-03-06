#-----------------------------------------------------------------------------
"""
Z80 Opcode Emulation Generator
"""
#-----------------------------------------------------------------------------

import sys
import getopt
import z80da
import memory

#-----------------------------------------------------------------------------
# format is (opcode prefix), (links to other prefixes), 'function preamble'

_prefixes = (
    ((), (0xcb, 0xdd, 0xed, 0xfd), '(self):'),
    ((0xcb,), (), '(self):'),
    ((0xdd,), (0xcb, 0xdd, 0xfd), '(self):'),
    ((0xdd, 0xcb, 0x00), (), '(self, d):'),
    ((0xed,), (), '(self):'),
    ((0xfd,), (0xcb, 0xdd, 0xfd), '(self):'),
    ((0xfd, 0xcb, 0x00), (), '(self, d):'),
)

#-----------------------------------------------------------------------------

_indent = 4

class output:
    """class for handling file output with auto indenting"""

    def __init__(self, ofname):
        self.ofile = file('%s' % ofname, 'w')
        self.lhs = 0
        self.col = 0

    def close(self):
        self.ofile.close()

    def put(self, s):
        for c in s:
            if c == '\n':
                self.ofile.write('\n')
                self.col = 0
            else:
                if self.col == 0:
                    self.ofile.write(' ' * self.lhs)
                    self.col = self.lhs
                self.ofile.write(c)
                self.col += 1

    def pad(self, col):
        if self.col < col:
            self.ofile.write(' ' * (col - self.col))
            self.col = col

    def indent(self, n):
        self.lhs += n * _indent

    def outdent(self, n):
        self.lhs -= n * _indent

#-----------------------------------------------------------------------------

_r = ('b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a')
_rp = ('bc', 'de', 'hl', 'sp')
_rp2 = ('bc', 'de', 'hl', 'af')
_direct_rp = ('sp', 'ix', 'iy')
_cc = ('nz', 'z', 'nc', 'c', 'po', 'pe', 'p', 'm')
_alu = ('add', 'adc', 'sub', 'sbc', 'and', 'xor', 'or', 'cp')
_alux = ('a,', 'a,', '', 'a,', '', '', '', '')
_rot = ('rlc', 'rrc', 'rl', 'rr', 'sla', 'sra', 'sll', 'srl')
_rota = ('rlca', 'rrca', 'rla', 'rra', 'daa', 'cpl', 'scf', 'ccf')
_im = ('0', '0', '1', '2', '0', '0', '1', '2')
_bli = (
    ('ldi', 'ldd', 'ldir', 'lddr'), ('cpi', 'cpd', 'cpir', 'cpdr'),
    ('ini', 'ind', 'inir', 'indr'), ('outi', 'outd', 'otir', 'otdr')
)

#-----------------------------------------------------------------------------
# 8-Bit Load Group

def emit_ld_r_n(out, r):
    """load immediate register n"""
    if r == '(hl)':
        out.put('self.mem[self._get_hl()] = self._get_n()\n')
        out.put('return 10\n')
    else:
        out.put('self.%s = self._get_n()\n' % r)
        out.put('return 7\n')

def emit_ld_mem_xx_n(out, r):
    """ld (xx),n where xx is ix+d, iy+d"""
    out.put('d = _signed(self._get_n())\n')
    out.put('self.mem[self.%s + d] = self._get_n()\n' % r)
    out.put('return 15\n')

def emit_ld_r_r(out, rd, rs):
    """load register to register"""
    if rd == '(hl)':
        out.put('self.mem[self._get_hl()] = self.%s\n' % rs)
        out.put('return 7\n')
    elif rd == '(ix+d)':
        out.put('d = _signed(self._get_n())\n')
        out.put('self.mem[self.ix + d] = self.%s\n' % rs)
        out.put('return 15\n')
    elif rd == '(iy+d)':
        out.put('d = _signed(self._get_n())\n')
        out.put('self.mem[self.iy + d] = self.%s\n' % rs)
        out.put('return 15\n')
    elif rs == '(hl)':
        out.put('self.%s = self.mem[self._get_hl()]\n' % rd)
        out.put('return 7\n')
    elif rs == '(ix+d)':
        out.put('d = _signed(self._get_n())\n')
        out.put('self.%s = self.mem[self.ix + d]\n' % rd)
        out.put('return 15\n')
    elif rs == '(iy+d)':
        out.put('d = _signed(self._get_n())\n')
        out.put('self.%s = self.mem[self.iy + d]\n' % rd)
        out.put('return 15\n')
    else:
        out.put('self.%s = self.%s\n' % (rd, rs))
        out.put('return 4\n')

def emit_ld_a_mem_xx(out, xx):
    """ld a,(xx) where xx in (bc,de,nn)"""
    out.put('self.a = self.mem[self._get_%s()]\n' % xx)
    out.put('return %d\n' % (7,13)[xx == 'nn'])

def emit_ld_mem_xx_a(out, xx):
    """ld (xx),a - where xx in (bc,de,nn)"""
    out.put('self.mem[self._get_%s()] = self.a\n' % xx)
    out.put('return %d\n' % (7,13)[xx == 'nn'])

def emit_ld_ira(out, d, s):
    """ld i/r/a, i/r/a"""
    out.put('self.%s = self.%s\n' % (d,s))
    if d == 'a':
        out.put('self.f = (self.f & _CF) | (self.f_sz[self.a]) | (self.iff2 << 2)\n')
    out.put('return 9\n')

#-----------------------------------------------------------------------------
# 16-Bit Load Group

def emit_ld_rp_nn(out, rp):
    """ld rp,nn"""
    if rp in _direct_rp:
        out.put('self.%s = self._get_nn()\n' % rp)
    else:
        out.put('self._set_%s(self._get_nn())\n' % rp)
    out.put('return 10\n')

def emit_ld_mem_nn_rp(out, rp):
    """ld (nn), rp"""
    out.put('nn = self._get_nn()\n')
    if rp in _direct_rp:
        out.put('self.mem[nn] = self.%s & 0xff\n' % rp)
        out.put('self.mem[nn + 1] = self.%s >> 8\n' % rp)
    else:
        out.put('self.mem[nn] = self.%s\n' % rp[1])
        out.put('self.mem[nn + 1] = self.%s\n' % rp[0])
    out.put('return 16\n')

def emit_ld_rp_mem_nn(out, rp):
    """ld rp,(nn)"""
    out.put('nn = self._get_nn()\n')
    if rp in _direct_rp:
        out.put('self.%s = self.mem[nn + 1] << 8\n' % rp)
        out.put('self.%s |= self.mem[nn]\n' % rp)
    else:
        out.put('self.%s = self.mem[nn + 1]\n' % rp[0])
        out.put('self.%s = self.mem[nn]\n' % rp[1])
    out.put('return 16\n')

def emit_ld_sp_hl(out):
    """ld sp, hl"""
    out.put('self.sp = self._get_hl()\n')
    out.put('return 6\n')

def emit_pop_rp(out, rp):
    """pop rp"""
    if rp in _direct_rp:
        out.put('self.%s = self._pop()\n' % rp)
    else:
        out.put('self.%s = self.mem[self.sp + 1]\n' % rp[0])
        out.put('self.%s = self.mem[self.sp]\n' % rp[1])
        out.put('self.sp = (self.sp + 2) & 0xffff\n')
    out.put('return 10\n')

def emit_push_rp(out, rp):
    """pop rp"""
    if rp in _direct_rp:
        out.put('self._push(self.%s)\n' % rp)
    else:
        out.put('self.mem[self.sp - 1] = self.%s\n' % rp[0])
        out.put('self.mem[self.sp - 2] = self.%s\n' % rp[1])
        out.put('self.sp = (self.sp - 2) & 0xffff\n')
    out.put('return 11\n')

#-----------------------------------------------------------------------------
# Exchange, Block Transfer, and Search Group

def emit_ex_de_hl(out):
    """ ex de,hl"""
    out.put('self.d, self.h = self.h, self.d\n')
    out.put('self.e, self.l = self.l, self.e\n')
    out.put('return 6\n')

def emit_ex_af_af(out):
    """ ex af,af'"""
    out.put('tmp = self._get_af()\n')
    out.put('self._set_af(self.alt_af)\n')
    out.put('self.alt_af = tmp\n')
    out.put('return 4\n')

def emit_ldxx(out, op):
    """ldi, ldir, ldd, lddr"""
    dirn = ('-', '+')[op in ('ldi', 'ldir')]
    out.put('d = self._get_de()\n')
    out.put('s = self._get_hl()\n')
    out.put('n = self._get_bc() - 1\n')
    out.put('val = self.mem[s]\n')
    out.put('self.mem[d] = val\n')
    out.put('self.f &= (_SF | _ZF | _CF)\n')
    out.put('if (self.a + val) & 0x02:\n')
    out.put('    self.f |= _YF\n')
    out.put('if (self.a + val) & 0x08:\n')
    out.put('    self.f |= _XF\n')
    out.put('self._set_de(d %s 1)\n' % dirn)
    out.put('self._set_hl(s %s 1)\n' % dirn)
    out.put('self._set_bc(n)\n')
    out.put('if n:\n')
    out.put('    self.f |= _VF\n')
    if op in ('ldir', 'lddr'):
        out.put('    self._dec_pc(2)\n')
        out.put('    return 17\n')
    out.put('return 12\n')

def emit_cpxx(out, op):
    """cpi, cpd, cpir, cpdr"""
    dirn = ('-', '+')[op in ('cpi', 'cpir')]
    out.put('s = self._get_hl()\n')
    out.put('n = self._get_bc() - 1\n')
    out.put('val = self.mem[s]\n')
    out.put('res = self.a - val\n')
    out.put('self.f = (self.f & _CF) | _NF\n')
    out.put('self.f |= (self.f_sz[res] & ~(_YF | _XF))\n')
    out.put('self.f |= ((self.a ^ val ^ res) & _HF)\n')
    out.put('if self.f & _HF:\n')
    out.put('    res -= 1\n')
    out.put('if res & 0x02:\n')
    out.put('    self.f |= _YF\n')
    out.put('if res & 0x08:\n')
    out.put('    self.f |= _XF\n')
    out.put('self._set_hl(s %s 1)\n' % dirn)
    out.put('self._set_bc(n)\n')
    if op in ('cpi', 'cpd'):
        out.put('if n:\n')
        out.put('    self.f |= _VF\n')
        out.put('return 12\n')
    else:
        out.put('if n and (self.f & _ZF == 0):\n')
        out.put('    self._dec_pc(2)\n')
        out.put('    return 17\n')
        out.put('return 12\n')

def emit_bli(out, op):
    """block instructions"""
    if op in ('ldi', 'ldir', 'ldd', 'lddr'):
        return emit_ldxx(out, op)
    if op in ('cpi', 'cpir', 'cpd', 'cpdr'):
        return emit_cpxx(out, op)

    if op == 'ini':
        out.put('assert False, \'unimplemented instruction\'\n')
    elif op == 'ind':
        out.put('assert False, \'unimplemented instruction\'\n')
    elif op == 'inir':
        out.put('assert False, \'unimplemented instruction\'\n')
    elif op == 'indr':
        out.put('assert False, \'unimplemented instruction\'\n')
    elif op == 'outi':
        out.put('assert False, \'unimplemented instruction\'\n')
    elif op == 'outd':
        out.put('assert False, \'unimplemented instruction\'\n')
    elif op == 'otir':
        out.put('assert False, \'unimplemented instruction\'\n')
    elif op == 'otdr':
        out.put('assert False, \'unimplemented instruction\'\n')
    else:
        assert False

def emit_ex_mem_sp_r(out, r):
    """ex (sp),r"""
    out.put('tmp = self._peek(self.sp)\n')
    if r == 'hl':
        out.put('self._poke(self.sp, self._get_hl())\n')
        out.put('self._set_hl(tmp)\n')
    else:
        out.put('self._poke(self.sp, self.%s)\n' % r)
        out.put('self.%s = tmp\n' % r)
    out.put('return 19\n')

def emit_exx(out):
    """exx"""
    out.put('tmp = self._get_bc()\n')
    out.put('self._set_bc(self.alt_bc)\n')
    out.put('self.alt_bc = tmp\n')
    out.put('tmp = self._get_de()\n')
    out.put('self._set_de(self.alt_de)\n')
    out.put('self.alt_de = tmp\n')
    out.put('tmp = self._get_hl()\n')
    out.put('self._set_hl(self.alt_hl)\n')
    out.put('self.alt_hl = tmp\n')
    out.put('return 4\n')

#-----------------------------------------------------------------------------
# 8-Bit Arithmetic Group

def emit_inc_dec_r(out, r, op ):
    """inc/dec register"""
    delta = ('+ 1','- 1')[op == 'dec']
    flags = ('self.f_szhv_inc', 'self.f_szhv_dec')[op == 'dec']
    if r == '(hl)':
        out.put('hl = self._get_hl()\n')
        out.put('n = (self.mem[hl] %s) & 0xff\n' % delta)
        out.put('self.mem[hl] = n\n')
        out.put('self.f = (self.f & _CF) | %s[n]\n' % flags)
        out.put('return 11\n')
    elif r == '(ix+d)':
        out.put('adr = self.ix + _signed(self._get_n())\n')
        out.put('n = (self.mem[adr] %s) & 0xff\n' % delta)
        out.put('self.mem[adr] = n\n')
        out.put('self.f = (self.f & _CF) | %s[n]\n' % flags)
        out.put('return 19\n')
    elif r == '(iy+d)':
        out.put('adr = self.iy + _signed(self._get_n())\n')
        out.put('n = (self.mem[adr] %s) & 0xff\n' % delta)
        out.put('self.mem[adr] = n\n')
        out.put('self.f = (self.f & _CF) | %s[n]\n' % flags)
        out.put('return 19\n')
    else:
        out.put('n = (self.%s %s) & 0xff\n' % (r, delta))
        out.put('self.%s = n\n' % r)
        out.put('self.f = (self.f & _CF) | %s[n]\n' % flags)
        out.put('return 4\n')

def emit_alu_r(out, op, r):
    """alu operation with register"""
    if r == '(ix+d)':
        out.put('val = self.mem[self.ix + _signed(self._get_n())]\n')
        tclks = 15
    elif r == '(iy+d)':
        out.put('val = self.mem[self.iy + _signed(self._get_n())]\n')
        tclks = 15
    elif r == '(hl)':
        out.put('val = self.mem[self._get_hl()]\n')
        tclks = 7
    else:
        out.put('val = self.%s\n' % r)
        tclks = 4
    if op == 'add':
        out.put('result = self.a + val\n')
        out.put('self._add_flags(result, val)\n')
        out.put('self.a = result & 0xff\n')
        out.put('return %d\n' % tclks)
    elif op == 'adc':
        out.put('result = self.a + val + (self.f & _CF)\n')
        out.put('self._add_flags(result, val)\n')
        out.put('self.a = result & 0xff\n')
        out.put('return %d\n' % tclks)
    elif op == 'sub':
        out.put('result = self.a - val\n')
        out.put('self._sub_flags(result, val)\n')
        out.put('self.a = result & 0xff\n')
        out.put('return %d\n' % tclks)
    elif op == 'sbc':
        out.put('result = self.a - val - (self.f & _CF)\n')
        out.put('self._sub_flags(result, val)\n')
        out.put('self.a = result & 0xff\n')
        out.put('return %d\n' % tclks)
    elif op == 'and':
        out.put('self.a &= val\n')
        out.put('self.f = self.f_szp[self.a] | _HF\n')
        out.put('return %d\n' % tclks)
    elif op == 'xor':
        out.put('self.a ^= val\n')
        out.put('self.f = self.f_szp[self.a]\n')
        out.put('return %d\n' % tclks)
    elif op == 'or':
        out.put('self.a |= val\n')
        out.put('self.f = self.f_szp[self.a]\n')
        out.put('return %d\n' % tclks)
    elif op == 'cp':
        out.put('result = self.a - val\n')
        out.put('self._sub_flags(result, val)\n')
        out.put('return %d\n' % tclks)
    else:
        assert False

def emit_alu_n(out, op):
    """alu operation with immediate"""
    out.put('val = self._get_n()\n')
    if op == 'add':
        out.put('result = self.a + val\n')
        out.put('self._add_flags(result, val)\n')
        out.put('self.a = result & 0xff\n')
    elif op == 'adc':
        out.put('result = self.a + val + (self.f & _CF)\n')
        out.put('self._add_flags(result, val)\n')
        out.put('self.a = result & 0xff\n')
    elif op == 'sub':
        out.put('result = self.a - val\n')
        out.put('self._sub_flags(result, val)\n')
        out.put('self.a = result & 0xff\n')
    elif op == 'sbc':
        out.put('result = self.a - val - (self.f & _CF)\n')
        out.put('self._sub_flags(result, val)\n')
        out.put('self.a = result & 0xff\n')
    elif op == 'and':
        out.put('self.a &= val\n')
        out.put('self.f = self.f_szp[self.a] | _HF\n')
    elif op == 'xor':
        out.put('self.a ^= val\n')
        out.put('self.f = self.f_szp[self.a]\n')
    elif op == 'or':
        out.put('self.a |= val\n')
        out.put('self.f = self.f_szp[self.a]\n')
    elif op == 'cp':
        out.put('result = self.a - val\n')
        out.put('self._sub_flags(result, val)\n')
    else:
        assert False
    out.put('return 7\n')

#-----------------------------------------------------------------------------
# General-Purpose Arithmetic and CPU Control Groups

def emit_nop(out):
    """nop"""
    out.put('return 4\n')

def emit_di(out):
    """disable interrupts"""
    out.put('self.iff1 = 0\n')
    out.put('self.iff2 = 0\n')
    out.put('return 4\n')

def emit_ei(out):
    """enable interrupts"""
    out.put('self.iff1 = 1\n')
    out.put('self.iff2 = 1\n')
    out.put('return 4\n')

def emit_im(out, n):
    """im n"""
    out.put('self.im = %s\n' % n)
    out.put('return 4\n')

def emit_halt(out):
    """halt"""
    out.put('self._enter_halt()\n')
    out.put('return 4\n')

def emit_daa(out):
    """daa"""
    out.put('cf = bool(self.f & _CF)\n')
    out.put('nf = bool(self.f & _NF)\n')
    out.put('hf = bool(self.f & _HF)\n')
    out.put('lo = self.a & 0x0f\n')
    out.put('hi = self.a >> 4\n')
    out.put('if cf:\n')
    out.put('    diff = (0x66, 0x60)[(lo <= 9) and (not hf)]\n')
    out.put('else:\n')
    out.put('    if lo >= 10:\n')
    out.put('        diff = (0x66, 0x06)[hi <= 8]\n')
    out.put('    else:\n')
    out.put('        if hi >= 10:\n')
    out.put('            diff = (0x60, 0x66)[hf]\n')
    out.put('        else:\n')
    out.put('            diff = (0x00, 0x06)[hf]\n')
    out.put('if nf:\n')
    out.put('    self.a = (self.a - diff) & 0xff\n')
    out.put('else:\n')
    out.put('    self.a = (self.a + diff) & 0xff\n')
    out.put('self.f = self.f_szp[self.a] | (self.f & _NF)\n')
    out.put('if cf:\n')
    out.put('    self.f |= _CF\n')
    out.put('if (lo <= 9) and (hi >= 10):\n')
    out.put('    self.f |= _CF\n')
    out.put('if (lo > 9) and (hi >= 9):\n')
    out.put('    self.f |= _CF\n')
    out.put('if nf and hf and (lo <= 5):\n')
    out.put('    self.f |= _HF\n')
    out.put('if (not nf) and (lo >= 10):\n')
    out.put('    self.f |= _HF\n')
    out.put('return 4\n')

def emit_neg(out):
    """neg"""
    out.put('result = -self.a\n')
    out.put('self._sub_flags(result, self.a)\n')
    out.put('self.a = result & 0xff\n')
    out.put('return 4\n')

#-----------------------------------------------------------------------------
# 16-Bit Arithmetic Group

def emit_op_rp_rp(out, op, d, s):
    """add/adc/sub hl/ix/iy,rp"""
    if s in _direct_rp:
        out.put('s = self.%s\n' % s)
    else:
        out.put('s = self._get_%s()\n' % s)
    if d in _direct_rp:
        out.put('d = self.%s\n' % d)
    else:
        out.put('d = self._get_%s()\n' % d)
    if op == 'add':
        out.put('res = d + s\n')
        out.put('self._add16_flags(res, d, s)\n')
    elif op == 'sbc':
        out.put('res = d - s - (self.f & _CF)\n')
        out.put('self._sub16_flags(res, d, s)\n')
    elif op == 'adc':
        out.put('res = d + s + (self.f & _CF)\n')
        out.put('self._adc16_flags(res, d, s)\n')
    if d in _direct_rp:
        out.put('self.%s = res\n' % d)
    else:
        out.put('self._set_%s(res)\n' % d)
    out.put('return 11\n')

def emit_dec_rp(out, rp):
    """dec ss"""
    if rp in _direct_rp:
        out.put('self.%s = (self.%s - 1) & 0xffff\n' % (rp, rp))
    else:
        out.put('self._set_%s(self._get_%s() - 1)\n' % (rp, rp))
    out.put('return 6\n')

def emit_inc_rp(out, rp):
    """inc ss"""
    if rp in _direct_rp:
        out.put('self.%s = (self.%s + 1) & 0xffff\n' % (rp, rp))
    else:
        out.put('self._set_%s(self._get_%s() + 1)\n' % (rp, rp))
    out.put('return 6\n')

#-----------------------------------------------------------------------------
# Rotate and Shift Group

def emit_rota(out, op):
    """rotate a"""
    if op == 'rlca':
        out.put('self.a = ((self.a << 1) | (self.a >> 7)) & 0xff\n')
        out.put('self.f = (self.f & (_SF | _ZF | _PF)) | (self.a & (_YF | _XF | _CF))\n')
    elif op == 'rrca':
        out.put('self.f = (self.f & (_SF | _ZF | _PF)) | (self.a & _CF)\n')
        out.put('self.a = ((self.a >> 1) | (self.a << 7)) & 0xff\n')
        out.put('self.f |= (self.a & (_YF | _XF))\n')
    elif op == 'rla':
        out.put('res = (self.a << 1) | (self.f & _CF)\n')
        out.put('c = (0, _CF)[(self.a & 0x80) != 0]\n')
        out.put('self.f = (self.f & (_SF | _ZF | _PF)) | c | (res & (_YF | _XF))\n')
        out.put('self.a = res & 0xff\n')
    elif op == 'rra':
        out.put('res = (self.a >> 1) | (self.f << 7)\n')
        out.put('c = (0, _CF)[(self.a & 0x01) != 0]\n')
        out.put('self.f = (self.f & (_SF | _ZF | _PF)) | c | (res & (_YF | _XF))\n')
        out.put('self.a = res & 0xff\n')
    elif op == 'daa':
        return emit_daa(out)
    elif op == 'cpl':
        out.put('self.a ^= 0xff\n')
        out.put('self.f = (self.f & (_SF | _ZF | _PF | _CF)) | _HF | _NF | (self.a & (_YF | _XF))\n')
    elif op == 'scf':
        out.put('self.f = (self.f & (_SF | _ZF | _PF)) | _CF | (self.a & (_YF | _XF))\n')
    elif op == 'ccf':
        out.put('self.f = ((self.f & (_SF | _ZF | _PF | _CF)) | ((self.f & _CF) << 4) | (self.a & (_YF | _XF))) ^ _CF\n')
    else:
        assert False
    out.put('return 4\n')

def emit_rot_r_x(out, op, r, x):
    """rotate operation on r - optionally store in x also"""
    if r == '(ix+d)':
        out.put('res = self.mem[self.ix + d]\n')
    elif r == '(iy+d)':
        out.put('res = self.mem[self.iy + d]\n')
    elif r == '(hl)':
        out.put('res = self.mem[self._get_hl()]\n')
    else:
        out.put('res = self.%s\n' % r)

    if op == 'rlc':
        out.put('cf = (0, _CF)[(res & 0x80) != 0]\n')
        out.put('res = ((res << 1) | (res >> 7)) & 0xff\n')
    elif op == 'rrc':
        out.put('cf = (0, _CF)[(res & 0x01) != 0]\n')
        out.put('res = ((res >> 1) | (res << 7)) & 0xff\n')
    elif op == 'rl':
        out.put('cf = (0, _CF)[(res & 0x80) != 0]\n')
        out.put('res = ((res << 1) | (self.f & _CF)) & 0xff\n')
    elif op == 'rr':
        out.put('cf = (0, _CF)[(res & 0x01) != 0]\n')
        out.put('res = ((res >> 1) | (self.f << 7)) & 0xff\n')
    elif op == 'sla':
        out.put('cf = (0, _CF)[(res & 0x80) != 0]\n')
        out.put('res = (res << 1) & 0xff\n')
    elif op == 'sra':
        out.put('cf = (0, _CF)[(res & 0x01) != 0]\n')
        out.put('res = ((res >> 1) | (res & 0x80)) & 0xff\n')
    elif op == 'sll':
        out.put('cf = (0, _CF)[(res & 0x80) != 0]\n')
        out.put('res = ((res << 1) | 0x01) & 0xff\n')
    elif op == 'srl':
        out.put('cf = (0, _CF)[(res & 0x01) != 0]\n')
        out.put('res = (res >> 1) & 0xff\n')
    else:
        assert False

    out.put('self.f = self.f_szp[res] | cf\n')
    if x != '':
        out.put('self.%s = res\n' % x)
    if r == '(ix+d)':
        out.put('self.mem[self.ix + d] = res\n')
        out.put('return 11\n')
    elif r == '(iy+d)':
        out.put('self.mem[self.iy + d] = res\n')
        out.put('return 11\n')
    elif r == '(hl)':
        out.put('self.mem[self._get_hl()] = res\n')
        out.put('return 11\n')
    else:
        out.put('self.%s = res\n' % r)
        out.put('return 4\n')

def emit_rxd(out, op):
    """rld, rrd"""
    out.put('adr = self._get_hl()\n')
    out.put('n = self.mem[adr]\n')
    if op == 'rrd':
        out.put('self.mem[adr] = ((n >> 4) | (self.a << 4)) & 0xff\n')
        out.put('self.a = (self.a & 0xf0) | (n & 0x0f)\n')
    elif op == 'rld':
        out.put('self.mem[adr] = ((n << 4) | (self.a & 0x0f)) & 0xff\n')
        out.put('self.a = (self.a & 0xf0) | (n >> 4)\n')
    else:
        assert False
    out.put('self.f = (self.f & _CF) | self.f_szp[self.a]\n')
    out.put('return 14\n')

#-----------------------------------------------------------------------------
# Bit Set, Reset, and Test Group

def emit_bit_b_r(out, b, r):
    """bit test operation on r"""
    if r == '(ix+d)':
        out.put('bit = self.mem[self.ix + d] & (1 << %d)\n' % b)
        t = 8
    elif r == '(iy+d)':
        out.put('bit = self.mem[self.iy + d] & (1 << %d)\n' % b)
        t = 8
    elif r == '(hl)':
        out.put('bit = self.mem[self._get_hl()] & (1 << %d)\n' % b)
        t = 8
    else:
        out.put('bit = self.%s & (1 << %d)\n' % (r, b))
        t = 4
    out.put('zf = (0, _ZF)[bit == 0]\n')
    out.put('self.f = (self.f & _CF) | _HF | zf\n')
    out.put('return %d\n' % t)

def emit_set_b_r(out, b, r, x):
    """bit set operation on r"""
    if r == '(ix+d)':
        out.put('n = self.ix + d\n')
        out.put('val = self.mem[n] | (1 << %d)\n' % b)
        out.put('self.mem[n] = val\n')
        t = 11
    elif r == '(iy+d)':
        out.put('n = self.iy + d\n')
        out.put('val = self.mem[n] | (1 << %d)\n' % b)
        out.put('self.mem[n] = val\n')
        t = 11
    elif r == '(hl)':
        out.put('n = self._get_hl()\n')
        out.put('val = self.mem[n] | (1 << %d)\n' % b)
        out.put('self.mem[n] = val\n')
        t = 11
    else:
        out.put('val = self.%s | (1 << %d)\n' % (r, b))
        out.put('self.%s = val\n' % r)
        t = 4
    if x != '':
        out.put('self.%s = val\n' % x)
    out.put('return %d\n' % t)

def emit_res_b_r(out, b, r, x):
    """bit reset operation on r"""
    if r == '(ix+d)':
        out.put('n = self.ix + d\n')
        out.put('val = self.mem[n] & ~(1 << %d)\n' % b)
        out.put('self.mem[n] = val\n')
        t = 11
    elif r == '(iy+d)':
        out.put('n = self.iy + d\n')
        out.put('val = self.mem[n] & ~(1 << %d)\n' % b)
        out.put('self.mem[n] = val\n')
        t = 11
    elif r == '(hl)':
        out.put('n = self._get_hl()\n')
        out.put('val = self.mem[n] & ~(1 << %d)\n' % b)
        out.put('self.mem[n] = val\n')
        t = 11
    else:
        out.put('val = self.%s & ~(1 << %d)\n' % (r, b))
        out.put('self.%s = val\n' % r)
        t = 4
    if x != '':
        out.put('self.%s = val\n' % x)
    out.put('return %d\n' % t)

#-----------------------------------------------------------------------------
# Jump Group

def emit_jr_e(out):
    """jump relative"""
    out.put('self._inc_pc(_signed(self._get_n()))\n')
    out.put('return 12\n')

def emit_jr_cc_d(out, cc):
    """jump relative on condition"""
    out.put('e = self._get_n()\n')
    if cc == 'nz':
        out.put('if (self.f & _ZF) == 0:\n')
    elif cc == 'z':
        out.put('if self.f & _ZF:\n')
    elif cc == 'nc':
        out.put('if (self.f & _CF) == 0:\n')
    elif cc == 'c':
        out.put('if self.f & _CF:\n')
    else:
        assert False
    out.put('    self._inc_pc(_signed(e))\n')
    out.put('    return 12\n')
    out.put('return 7\n')

def emit_jp_nn(out):
    """jp nn"""
    out.put('self.pc = self._get_nn()\n')
    out.put('return 10\n')

def emit_jp_cc_nn(out, cc):
    """jp cc,nn"""
    out.put('nn = self._get_nn()\n')
    if cc == 'nz':
        out.put('if (self.f & _ZF) == 0:\n')
    elif cc == 'z':
        out.put('if self.f & _ZF:\n')
    elif cc == 'nc':
        out.put('if (self.f & _CF) == 0:\n')
    elif cc == 'c':
        out.put('if self.f & _CF:\n')
    elif cc == 'po':
        out.put('if (self.f & _PF) == 0:\n')
    elif cc == 'pe':
        out.put('if self.f & _PF:\n')
    elif cc == 'p':
        out.put('if (self.f & _SF) == 0:\n')
    elif cc == 'm':
        out.put('if self.f & _SF:\n')
    else:
        assert False
    out.put('    self.pc = nn\n')
    out.put('return 10\n')

def emit_jp_rp(out, rp):
    """jp rp"""
    if rp in _direct_rp:
        out.put('self.pc = self.%s\n' % rp)
    else:
        out.put('self.pc = self._get_%s()\n' % rp)
    out.put('return 4\n')

def emit_djnz(out):
    """djnz e"""
    out.put('e = self._get_n()\n')
    out.put('self.b = (self.b - 1) & 0xff\n')
    out.put('if self.b:\n')
    out.put('    self._inc_pc(_signed(e))\n')
    out.put('    return 13\n')
    out.put('return 8\n')

#-----------------------------------------------------------------------------
# Call And Return Group

def emit_call_nn(out):
    """call nn"""
    out.put('nn = self._get_nn()\n')
    out.put('self._push(self.pc)\n')
    out.put('self.pc = nn\n')
    out.put('return 17\n')

def emit_call_cc_nn(out, cc):
    """call cc,nn"""
    out.put('nn = self._get_nn()\n')
    if cc == 'nz':
        out.put('if (self.f & _ZF) == 0:\n')
    elif cc == 'z':
        out.put('if self.f & _ZF:\n')
    elif cc == 'nc':
        out.put('if (self.f & _CF) == 0:\n')
    elif cc == 'c':
        out.put('if self.f & _CF:\n')
    elif cc == 'po':
        out.put('if (self.f & _PF) == 0:\n')
    elif cc == 'pe':
        out.put('if self.f & _PF:\n')
    elif cc == 'p':
        out.put('if (self.f & _SF) == 0:\n')
    elif cc == 'm':
        out.put('if self.f & _SF:\n')
    else:
        assert False
    out.put('    self._push(self.pc)\n')
    out.put('    self.pc = nn\n')
    out.put('    return 17\n')
    out.put('return 10\n')

def emit_rst(out, p):
    out.put('self._push(self.pc)\n')
    out.put('self.pc = 0x%02x\n' % p)
    out.put('return 11\n')

def emit_ret_cc(out, cc):
    """ret cc"""
    if cc == 'nz':
        out.put('if (self.f & _ZF) == 0:\n')
    elif cc == 'z':
        out.put('if self.f & _ZF:\n')
    elif cc == 'nc':
        out.put('if (self.f & _CF) == 0:\n')
    elif cc == 'c':
        out.put('if self.f & _CF:\n')
    elif cc == 'po':
        out.put('if (self.f & _PF) == 0:\n')
    elif cc == 'pe':
        out.put('if self.f & _PF:\n')
    elif cc == 'p':
        out.put('if (self.f & _SF) == 0:\n')
    elif cc == 'm':
        out.put('if self.f & _SF:\n')
    else:
        assert False
    out.put('    self.pc = self._pop()\n')
    out.put('    return 11\n')
    out.put('return 5\n')

def emit_ret(out):
    """ret"""
    out.put('self.pc = self._pop()\n')
    out.put('return 10\n')

#-----------------------------------------------------------------------------
# Input and Output Group

def emit_in_r_c(out, r):
    """in r,(c)"""
    out.put('val = self.io.rd(self._get_bc())\n')
    if r != '':
        out.put('self.%s = val\n' % r)
    out.put('self.f = (self.f & _CF) | self.f_szp[val]\n')
    out.put('return 8\n')

def emit_in_a_n(out):
    """in a,(n)"""
    out.put('self.a = self.io.rd((self.a << 8) | self._get_n())\n')
    out.put('return 7\n')

def emit_out_n_a(out):
    """out (n),a"""
    out.put('self.io.wr((self.a << 8) | self._get_n(), self.a)\n')
    out.put('return 7\n')

def emit_out_c_r(out, r):
    if r == '':
        out.put('self.io.wr(self._get_bc(), 0)\n')
    else:
        out.put('self.io.wr(self._get_bc(), self.%s)\n' % r)
    out.put('return 8\n')

#-----------------------------------------------------------------------------

def emit_unimplemented(out):
    """unimplemented instruction - crash"""
    out.put('raise Error, \'unimplemented instruction\'\n')

#-----------------------------------------------------------------------------

def emit_normal(out, code):
    """
    Normal decode with no prefixes
    """
    m0 = code[0]
    x = (m0 >> 6) & 3
    y = (m0 >> 3) & 7
    z = (m0 >> 0) & 7
    p = (m0 >> 4) & 3
    q = (m0 >> 3) & 1

    if x == 0:
        if z == 0:
            if y == 0:
                return emit_nop(out)
            elif y == 1:
                return emit_ex_af_af(out)
            elif y == 2:
                return emit_djnz(out)
            elif y == 3:
                return emit_jr_e(out)
            else:
                return emit_jr_cc_d(out, _cc[y - 4])
        elif z == 1:
            if q == 0:
                return emit_ld_rp_nn(out, _rp[p])
            elif q == 1:
                return emit_op_rp_rp(out, 'add', 'hl', _rp[p])
        elif z == 2:
            if q == 0:
                if p == 0:
                    return emit_ld_mem_xx_a(out, 'bc')
                elif p == 1:
                    return emit_ld_mem_xx_a(out, 'de')
                elif p == 2:
                    return emit_ld_mem_nn_rp(out, 'hl')
                else:
                    return emit_ld_mem_xx_a(out, 'nn')
            else:
                if p == 0:
                    return emit_ld_a_mem_xx(out, 'bc')
                elif p == 1:
                    return emit_ld_a_mem_xx(out, 'de')
                elif p == 2:
                    emit_ld_rp_mem_nn(out, 'hl')
                else:
                    return emit_ld_a_mem_xx(out, 'nn')
        elif z == 3:
            if q == 0:
                return emit_inc_rp(out, _rp[p])
            else:
                return emit_dec_rp(out, _rp[p])
        elif z == 4:
            return emit_inc_dec_r(out, _r[y], 'inc')
        elif z == 5:
            return emit_inc_dec_r(out, _r[y], 'dec')
        elif z == 6:
            return emit_ld_r_n(out, _r[y])
        else:
            return emit_rota(out, _rota[y])
    elif x == 1:
        if (z == 6) and (y == 6):
            return emit_halt(out)
        else:
            return emit_ld_r_r(out, _r[y], _r[z])
    elif x == 2:
        return emit_alu_r(out, _alu[y], _r[z])
    else:
        if z == 0:
            return emit_ret_cc(out, _cc[y])
        elif z == 1:
            if q == 0:
                return emit_pop_rp(out, _rp2[p])
            else:
                if p == 0:
                    return emit_ret(out)
                elif p == 1:
                    return emit_exx(out)
                elif p == 2:
                    return emit_jp_rp(out, 'hl')
                else:
                    return emit_ld_sp_hl(out)
        elif z == 2:
            return emit_jp_cc_nn(out, _cc[y])
        elif z == 3:
            if y == 0:
                return emit_jp_nn(out)
            elif y == 2:
                return emit_out_n_a(out)
            elif y == 3:
                return emit_in_a_n(out)
            elif y == 4:
                return emit_ex_mem_sp_r(out, 'hl')
            elif y == 5:
                return emit_ex_de_hl(out)
            elif y == 6:
                return emit_di(out)
            else:
                return emit_ei(out)
        elif z == 4:
            return emit_call_cc_nn(out, _cc[y])
        elif z == 5:
            if q == 0:
                return emit_push_rp(out, _rp2[p])
            else:
                if p == 0:
                    return emit_call_nn(out)
        elif z == 6:
            return emit_alu_n(out, _alu[y])
        else:
            return emit_rst(out, (y << 3))

#-----------------------------------------------------------------------------

def emit_index(out, code, ir):
    """
    Decode with index register substitutions
    """
    m0 = code[0]
    x = (m0 >> 6) & 3
    y = (m0 >> 3) & 7
    z = (m0 >> 0) & 7
    p = (m0 >> 4) & 3
    q = (m0 >> 3) & 1

    # if using (hl) then: (hl)->(ix+d), h and l are unaffected.
    alt0_r = list(_r)
    alt0_r[6] = '(%s+d)' % ir

    # if not using (hl) then: hl->ix, h->ixh, l->ixl
    alt1_r = list(_r)
    alt1_r[4] = '%sh' % ir
    alt1_r[5] = '%sl' % ir

    alt_rp = list(_rp)
    alt_rp[2] = ir
    alt_rp2 = list(_rp2)
    alt_rp2[2] = ir

    if x == 0:
        if z == 0:
            if y == 0:
                return emit_nop(out)
            elif y == 1:
                return emit_ex_af_af(out)
            elif y == 2:
                return emit_djnz(out)
            elif y == 3:
                #return ('jr', '%04x' % dj, 3)
                return emit_unimplemented(out)
            else:
                return emit_jr_cc_d(out, _cc[y - 4])
        elif z == 1:
            if q == 0:
                return emit_ld_rp_nn(out, alt_rp[p])
            elif q == 1:
                return emit_op_rp_rp(out, 'add', ir, alt_rp[p])
        elif z == 2:
            if q == 0:
                if p == 0:
                    #return ('ld', '(bc),a', 2)
                    return emit_unimplemented(out)
                elif p == 1:
                    #return ('ld', '(de),a', 2)
                    return emit_unimplemented(out)
                elif p == 2:
                    return emit_ld_mem_nn_rp(out, ir)
                else:
                    #return ('ld', '(%04x),a' % nn, 4)
                    return emit_unimplemented(out)
            else:
                if p == 0:
                    #return ('ld', 'a,(bc)', 2)
                    return emit_unimplemented(out)
                elif p == 1:
                    #return ('ld', 'a,(de)', 2)
                    return emit_unimplemented(out)
                elif p == 2:
                    return emit_ld_rp_mem_nn(out, ir)
                else:
                    #return ('ld', 'a,(%04x)' % nn, 4)
                    return emit_unimplemented(out)
        elif z == 3:
            if q == 0:
                return emit_inc_rp(out, alt_rp[p])
            else:
                return emit_dec_rp(out, alt_rp[p])
        elif z == 4:
            if y == 6:
                return emit_inc_dec_r(out, alt0_r[y], 'inc')
            else:
                #return ('inc', alt1_r[y], 2)
                return emit_unimplemented(out)
        elif z == 5:
            if y == 6:
                return emit_inc_dec_r(out, alt0_r[y], 'dec')
            else:
                #return ('dec', alt1_r[y], 2)
                return emit_unimplemented(out)
        elif z == 6:
            if y == 6:
                return emit_ld_mem_xx_n(out, ir)
            else:
                #return ('ld', '%s,%02x' % (alt1_r[y], n0), 3)
                return emit_unimplemented(out)
        else:
            #return (_rota[y], '', 2)
            return emit_unimplemented(out)
    elif x == 1:
        if (z == 6) and (y == 6):
            #return ('halt', '', 2)
            return emit_unimplemented(out)
        else:
            if (y == 6) or (z == 6):
                #return ('ld', '%s,%s' % (alt0_r[y], alt0_r[z]), 3)
                return emit_ld_r_r(out, alt0_r[y], alt0_r[z])
            else:
                #return ('ld', '%s,%s' % (alt1_r[y], alt1_r[z]), 2)
                return emit_unimplemented(out)
    elif x == 2:
        if z == 6:
            return emit_alu_r(out, _alu[y], alt0_r[z])
        else:
            #return (_alu[y], '%s%s' % (_alux[y], alt1_r[z]), 2)
            return emit_unimplemented(out)
    else:
        if z == 0:
            #return ('ret', _cc[y], 2)
            return emit_unimplemented(out)
        elif z == 1:
            if q == 0:
                return emit_pop_rp(out, alt_rp2[p])
            else:
                if p == 0:
                    #return ('ret', '', 2)
                    return emit_unimplemented(out)
                elif p == 1:
                    return emit_exx(out)
                elif p == 2:
                    return emit_jp_rp(out, ir)
                else:
                    #return ('ld', 'sp,%s' % ir, 2)
                    return emit_unimplemented(out)
        elif z == 2:
            return emit_jp_cc_nn(out, _cc[y])
        elif z == 3:
            if y == 0:
                #return ('jp', '%04x' % nn, 4)
                return emit_unimplemented(out)
            elif y == 2:
                return emit_out_n_a(out)
            elif y == 3:
                return emit_in_a_n(out)
            elif y == 4:
                return emit_ex_mem_sp_r(out, ir)
            elif y == 5:
                #return ('ex', 'de,hl', 2)
                return emit_unimplemented(out)
            elif y == 6:
                #return ('di', '', 2)
                return emit_unimplemented(out)
            else:
                #return ('ei', '', 2)
                return emit_unimplemented(out)
        elif z == 4:
            return emit_call_cc_nn(out, _cc[y])
        elif z == 5:
            if q == 0:
                return emit_push_rp(out, alt_rp2[p])
            else:
                if p == 0:
                    return emit_call_nn(out)
        elif z == 6:
            #return (_alu[y], '%s%02x' % (_alux[y], n0), 3)
            return emit_unimplemented(out)
        else:
            return emit_rst(out, (y << 3))

#-----------------------------------------------------------------------------

def emit_cb_prefix(out, code):
    """
    0xCB <opcode>
    """
    m0 = code[0]
    x = (m0 >> 6) & 3
    y = (m0 >> 3) & 7
    z = (m0 >> 0) & 7

    if x == 0:
        return emit_rot_r_x(out, _rot[y], _r[z], '')
    elif x == 1:
        return emit_bit_b_r(out, y, _r[z])
    elif x == 2:
        return emit_res_b_r(out, y, _r[z], '')
    else:
        return emit_set_b_r(out, y, _r[z], '')

#-----------------------------------------------------------------------------

def emit_ddcb_fdcb_prefix(out, code, ir):
    """
    0xDDCB <d> <opcode>
    0xFDCB <d> <opcode>
    """
    m1 = code[1]
    x = (m1 >> 6) & 3
    y = (m1 >> 3) & 7
    z = (m1 >> 0) & 7

    if x == 0:
        if z == 6:
            return emit_rot_r_x(out, _rot[y], '(%s+d)' % ir, '')
        else:
            return emit_rot_r_x(out, _rot[y], '(%s+d)' % ir, _r[z])
    elif x == 1:
        return emit_bit_b_r(out, y, '(%s+d)' % ir)
    elif x == 2:
        if z == 6:
            return emit_res_b_r(out, y, '(%s+d)' % ir, '')
        else:
            return emit_res_b_r(out, y, '(%s+d)' % ir, _r[z])
    else:
        if z == 6:
            return emit_set_b_r(out, y, '(%s+d)' % ir, '')
        else:
            return emit_set_b_r(out, y, '(%s+d)' % ir, _r[z])

#-----------------------------------------------------------------------------

def emit_ed_prefix(out, code):
    """
    0xED <opcode>
    0xED <opcode> <nn>
    """
    m0 = code[0]
    #m1 = code[1]
    #m2 = code[2]
    x = (m0 >> 6) & 3
    y = (m0 >> 3) & 7
    z = (m0 >> 0) & 7
    p = (m0 >> 4) & 3
    q = (m0 >> 3) & 1
    #nn = (m2 << 8) + m1

    if x == 1:
        if z == 0:
            if y == 6:
                return emit_in_r_c(out, '')
            else:
                return emit_in_r_c(out, _r[y])
        elif z == 1:
            if y == 6:
                return emit_out_c_r(out, '')
            else:
                return emit_out_c_r(out, _r[y])
        elif z == 2:
            if q == 0:
                return emit_op_rp_rp(out, 'sbc', 'hl', _rp[p])
            else:
                return emit_op_rp_rp(out, 'adc', 'hl', _rp[p])
        elif z == 3:
            if q == 0:
                return emit_ld_mem_nn_rp(out, _rp[p])
            else:
                return emit_ld_rp_mem_nn(out, _rp[p])
        elif z == 4:
            return emit_neg(out)
        elif z == 5:
            if y == 1:
                #return ('reti', '', 2)
                return emit_unimplemented(out)
            else:
                #return ('retn', '', 2)
                return emit_unimplemented(out)
        elif z == 6:
            return emit_im(out, _im[y])
        else:
            if y == 0:
                return emit_ld_ira(out, 'i', 'a')
            elif y == 1:
                return emit_ld_ira(out, 'r', 'a')
            elif y == 2:
                return emit_ld_ira(out, 'a', 'i')
            elif y == 3:
                return emit_ld_ira(out, 'a', 'r')
            elif y == 4:
                return emit_rxd(out, 'rrd')
            elif y == 5:
                return emit_rxd(out, 'rld')
            else:
                return emit_nop(out)
    elif x == 2:
        if (z <= 3) and (y >= 4):
            return emit_bli(out, _bli[z][y - 4])
    return emit_nop(out)

#-----------------------------------------------------------------------------

def emit_dd_fd_prefix(out, code, ir):
    """
    0xDD <x>
    0xFD <x>
    """
    m0 = code[0]
    if m0 in (0xdd, 0xed, 0xfd):
        emit_nop(out)
    elif m0 == 0xcb:
        return emit_ddcb_fdcb_prefix(out, code[1:], ir)
    else:
        return emit_index(out, code, ir)

#-----------------------------------------------------------------------------

def emit_instruction_code(out, code):
    """emit the code for an instruction"""
    m0 = code[0]
    if m0 == 0xcb:
        return emit_cb_prefix(out, code[1:])
    elif m0 == 0xdd:
        return emit_dd_fd_prefix(out, code[1:], 'ix')
    elif m0 == 0xed:
        return emit_ed_prefix(out, code[1:])
    elif m0 == 0xfd:
        return emit_dd_fd_prefix(out, code[1:], 'iy')
    else:
        return emit_normal(out, code)

#-----------------------------------------------------------------------------

def emit_triple_quote(out, comment):
    out.put('"""%s"""\n' % comment)

#-----------------------------------------------------------------------------

def emit_opcode_table(out, idic, prefix, links, preamble):
    """emit a function table for each opcode with this prefix"""
    out.indent(2)
    label = '_%s' % ''.join(['%02x' % byte for byte in prefix])
    out.put('self.opcodes%s = (\n' % (label, '')[len(label) == 1])
    out.indent(1)

    for opcode in range(0x100):
        code = list(prefix)
        code.append(opcode)
        # disassemble the instruction
        mem = memory.ram(4)
        mem.load(0, code)
        (operation, operands, nbytes) = z80da.disassemble(mem, 0)
        # add the instruction to the dictionary
        inst = ' '.join((operation, operands))
        label = ''.join(['%02x' % byte for byte in code])

        if opcode in links:
            out.put('self._execute_%s,' % label)
            out.pad(36)
            out.put('# 0x%02x execute %s prefix\n' % (opcode, label))
        else:
            # add the inst/label to the dictionary if it is unique
            if idic.has_key(inst) == False:
                idic[inst] = (label, code, preamble)
            out.put('self._ins_%s,' % idic[inst][0])
            out.pad(36)
            out.put('# 0x%02x %s\n' % (opcode, inst))

    out.outdent(1)
    out.put(')\n')
    out.outdent(2)

#-----------------------------------------------------------------------------

def emit_instruction_function(out, instruction, x):
    """emit the functon header and code for an instruction"""
    (label, code, preamble) = x
    out.indent(1)
    out.put('def _ins_%s%s # %s\n' % (label, preamble, instruction))
    out.indent(1)
    #emit_triple_quote(out, instruction)
    emit_instruction_code(out, code)
    out.outdent(2)

#-----------------------------------------------------------------------------
# flag lookup tables

_CF = 0x01
_NF = 0x02
_PF = 0x04
_VF = _PF
_XF = 0x08
_HF = 0x10
_YF = 0x20
_ZF = 0x40
_SF = 0x80

def pop(x):
    """return number of 1's in x"""
    p = 0
    while x != 0:
        p += x & 1
        x >>= 1
    return p

def emit_table(out, name, data):
    out.put('self.%s = (\n' % name)
    out.indent(1)
    for x in range(16):
       for y in range(16):
           out.put('0x%02x, ' % data[(x * 16) + y])
       out.put('\n')
    out.outdent(1)
    out.put(')\n')

def emit_flag_tables(out):

    SZ = []
    SZ_BIT = []
    SZP = []
    SZHV_inc = []
    SZHV_dec = []

    for i in range(0x100):
        p = pop(i)
        if i:
            SZ.append(i & _SF)
            SZ_BIT.append(i & _SF)
        else:
            SZ.append(_ZF)
            SZ_BIT.append(_ZF | _PF)
        # undocumented flag bits 5+3
        SZ[i] |= (i & (_YF | _XF))
        SZ_BIT[i] |= (i & (_YF | _XF))
        # parity
        SZP.append(SZ[i])
        if (p & 1) == 0:
            SZP[i] |= _PF
        # increment
        SZHV_inc.append(SZ[i])
        if i == 0x80:
            SZHV_inc[i] |= _VF
        if (i & 0x0f) == 0:
            SZHV_inc[i] |= _HF
        # decrement
        SZHV_dec.append(SZ[i] | _NF)
        if i == 0x7f:
            SZHV_dec[i] |= _VF
        if (i & 0x0f) == 0x0f:
            SZHV_dec[i] |= _HF

    out.indent(2)
    emit_table(out, 'f_sz', SZ)
    emit_table(out, 'f_szp', SZP)
    emit_table(out, 'f_szhv_inc', SZHV_inc)
    emit_table(out, 'f_szhv_dec', SZHV_dec)
    out.outdent(2)

#-----------------------------------------------------------------------------

def generate(ofname):
    """generate the opcode emulation file"""
    out = output(ofname)
    # generate flag tables
    emit_flag_tables(out)
    idic = {}
    # generate the opcode tables
    for (prefix, links, preamble) in _prefixes:
        emit_opcode_table(out, idic, prefix, links, preamble)
    # generate the instruction functions
    for (k, v) in idic.iteritems():
        emit_instruction_function(out, k, v)
    out.close()

#-----------------------------------------------------------------------------

def usage():
    print 'usage:'
    print '%s -o [OUTPUT]' % sys.argv[0]
    sys.exit(2)

#-----------------------------------------------------------------------------

def main():
    ofname = 'z80bh.py'
    try:
        optlist, arglist = getopt.gnu_getopt(sys.argv[1:], 'o:')
    except getopt.GetoptError:
        usage()
    for opt in optlist:
        if opt[0] == '-o':
            ofname = opt[1]
    if len(arglist) != 0:
        usage()
    generate(ofname)

#-----------------------------------------------------------------------------

if __name__ == "__main__":
    main()

#-----------------------------------------------------------------------------
