#-----------------------------------------------------------------------------
"""
Z80 Disassembler
"""
#-----------------------------------------------------------------------------

_r = ('b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a')
_rp = ('bc', 'de', 'hl', 'sp')
_rp2 = ('bc', 'de', 'hl', 'af')
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

def _da_normal(mem, pc):
    """
    Normal decode with no prefixes
    """
    m0 = mem[pc]
    m1 = mem[pc + 1]
    m2 = mem[pc + 2]
    x = (m0 >> 6) & 3
    y = (m0 >> 3) & 7
    z = (m0 >> 0) & 7
    p = (m0 >> 4) & 3
    q = (m0 >> 3) & 1
    n =  m1
    nn = (m2 << 8) + m1
    d = m1
    if d & 0x80:
        d = (d & 0x7f) - 128
    d = (pc + d + 2) & 0xffff

    if x == 0:
        if z == 0:
            if y == 0:
                return ('nop', '', 1)
            elif y == 1:
                return ('ex', 'af,af\'', 1)
            elif y == 2:
                return ('djnz', '%04x' % d, 2)
            elif y == 3:
                return ('jr', '%04x' % d, 2)
            else:
                return ('jr', '%s,%04x' % (_cc[y - 4], d), 2)
        elif z == 1:
            if q == 0:
                return ('ld', '%s,%04x' % (_rp[p], nn), 3)
            elif q == 1:
                return ('add', 'hl,%s' % _rp[p], 1)
        elif z == 2:
            if q == 0:
                if p == 0:
                    return ('ld', '(bc),a', 1)
                elif p == 1:
                    return ('ld', '(de),a', 1)
                elif p == 2:
                    return ('ld', '(%04x),hl' % nn, 3)
                else:
                    return ('ld', '(%04x),a' % nn, 3)
            else:
                if p == 0:
                    return ('ld', 'a,(bc)', 1)
                elif p == 1:
                    return ('ld', 'a,(de)', 1)
                elif p == 2:
                    return ('ld', 'hl,(%04x)' % nn, 3)
                else:
                    return ('ld', 'a,(%04x)' % nn, 3)
        elif z == 3:
            if q == 0:
                return ('inc', _rp[p], 1)
            else:
                return ('dec', _rp[p], 1)
        elif z == 4:
            return ('inc', _r[y], 1)
        elif z == 5:
            return ('dec', _r[y], 1)
        elif z == 6:
            return ('ld', '%s,%02x' % (_r[y], n), 2)
        else:
            return (_rota[y], '', 1)
    elif x == 1:
        if (z == 6) and (y == 6):
            return ('halt', '', 1)
        else:
            return ('ld', '%s,%s' % (_r[y], _r[z]), 1)
    elif x == 2:
        return (_alu[y], '%s%s' % (_alux[y], _r[z]), 1)
    else:
        if z == 0:
            return ('ret', _cc[y], 1)
        elif z == 1:
            if q == 0:
                return ('pop', _rp2[p], 1)
            else:
                if p == 0:
                    return ('ret', '', 1)
                elif p == 1:
                    return ('exx', '', 1)
                elif p == 2:
                    return ('jp', 'hl', 1)
                else:
                    return ('ld', 'sp,hl', 1)
        elif z == 2:
            return ('jp', '%s,%04x' % (_cc[y], nn), 3)
        elif z == 3:
            if y == 0:
                return ('jp', '%04x' % nn, 3)
            elif y == 2:
                return ('out', '(%02x),a' % n, 2)
            elif y == 3:
                return ('in', 'a,(%02x)' % n, 2)
            elif y == 4:
                return ('ex', '(sp),hl', 1)
            elif y == 5:
                return ('ex', 'de,hl', 1)
            elif y == 6:
                return ('di', '', 1)
            else:
                return ('ei', '', 1)
        elif z == 4:
            return ('call', '%s,%04x' % (_cc[y], nn), 3)
        elif z == 5:
            if q == 0:
                return ('push', _rp2[p], 1)
            else:
                if p == 0:
                    return ('call', '%04x' % nn, 3)
        elif z == 6:
            return (_alu[y], '%s%02x' % (_alux[y], n), 2)
        else:
            return ('rst', '%02x' % (y << 3), 1)

#-----------------------------------------------------------------------------

def _da_index(mem, pc, ir):
    """
    Decode with index register substitutions
    """
    m0 = mem[pc]
    m1 = mem[pc + 1]
    m2 = mem[pc + 2]
    x = (m0 >> 6) & 3
    y = (m0 >> 3) & 7
    z = (m0 >> 0) & 7
    p = (m0 >> 4) & 3
    q = (m0 >> 3) & 1
    n0 = m1
    n1 = m2
    nn = (m2 << 8) + m1
    d = m1
    if d & 0x80:
        d = (d & 0x7f) - 128
    sign = ('', '+')[d >= 0]
    dj = (pc + d + 2) & 0xffff

    # if using (hl) then: (hl)->(ix+d), h and l are unaffected.
    alt0_r = list(_r)
    alt0_r[6] = '(%s%s%02x)' % (ir, sign, d)

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
                return ('nop', '', 2)
            elif y == 1:
                return ('ex', 'af,af\'', 2)
            elif y == 2:
                return ('djnz', '%04x' % dj, 3)
            elif y == 3:
                return ('jr', '%04x' % dj, 3)
            else:
                return ('jr', '%s,%04x' % (_cc[y - 4], dj), 3)
        elif z == 1:
            if q == 0:
                return ('ld', '%s,%04x' % (alt_rp[p], nn), 4)
            elif q == 1:
                return ('add', '%s,%s' % (ir, alt_rp[p]), 2)
        elif z == 2:
            if q == 0:
                if p == 0:
                    return ('ld', '(bc),a', 2)
                elif p == 1:
                    return ('ld', '(de),a', 2)
                elif p == 2:
                    return ('ld', '(%04x),%s' % (nn, ir), 4)
                else:
                    return ('ld', '(%04x),a' % nn, 4)
            else:
                if p == 0:
                    return ('ld', 'a,(bc)', 2)
                elif p == 1:
                    return ('ld', 'a,(de)', 2)
                elif p == 2:
                    return ('ld', '%s,(%04x)' % (ir, nn), 4)
                else:
                    return ('ld', 'a,(%04x)' % nn, 4)
        elif z == 3:
            if q == 0:
                return ('inc', alt_rp[p], 2)
            else:
                return ('dec', alt_rp[p], 2)
        elif z == 4:
            if y == 6:
                return ('inc', alt0_r[y], 3)
            else:
                return ('inc', alt1_r[y], 2)
        elif z == 5:
            if y == 6:
                return ('dec', alt0_r[y], 3)
            else:
                return ('dec', alt1_r[y], 2)
        elif z == 6:
            if y == 6:
                return ('ld', '%s,%02x' % (alt0_r[y], n1), 4)
            else:
                return ('ld', '%s,%02x' % (alt1_r[y], n0), 3)
        else:
            return (_rota[y], '', 2)
    elif x == 1:
        if (z == 6) and (y == 6):
            return ('halt', '', 2)
        else:
            if (y == 6) or (z == 6):
                return ('ld', '%s,%s' % (alt0_r[y], alt0_r[z]), 3)
            else:
                return ('ld', '%s,%s' % (alt1_r[y], alt1_r[z]), 2)
    elif x == 2:
        if z == 6:
            return (_alu[y], '%s%s' % (_alux[y], alt0_r[z]), 3)
        else:
            return (_alu[y], '%s%s' % (_alux[y], alt1_r[z]), 2)
    else:
        if z == 0:
            return ('ret', _cc[y], 2)
        elif z == 1:
            if q == 0:
                return ('pop', alt_rp2[p], 2)
            else:
                if p == 0:
                    return ('ret', '', 2)
                elif p == 1:
                    return ('exx', '', 2)
                elif p == 2:
                    return ('jp', ir, 2)
                else:
                    return ('ld', 'sp,%s' % ir, 2)
        elif z == 2:
            return ('jp', '%s,%04x' % (_cc[y], nn), 4)
        elif z == 3:
            if y == 0:
                return ('jp', '%04x' % nn, 4)
            elif y == 2:
                return ('out', '(%02x),a' % n0, 3)
            elif y == 3:
                return ('in', 'a,(%02x)' % n0, 3)
            elif y == 4:
                return ('ex', '(sp),%s' % ir, 2)
            elif y == 5:
                return ('ex', 'de,hl', 2)
            elif y == 6:
                return ('di', '', 2)
            else:
                return ('ei', '', 2)
        elif z == 4:
            return ('call', '%s,%04x' % (_cc[y], nn), 4)
        elif z == 5:
            if q == 0:
                return ('push', alt_rp2[p], 2)
            else:
                if p == 0:
                    return ('call', '%04x' % nn, 4)
        elif z == 6:
            return (_alu[y], '%s%02x' % (_alux[y], n0), 3)
        else:
            return ('rst', '%02x' % (y << 3), 2)

#-----------------------------------------------------------------------------

def _da_cb_prefix(mem, pc):
    """
    0xCB <opcode>
    """
    m0 = mem[pc]
    x = (m0 >> 6) & 3
    y = (m0 >> 3) & 7
    z = (m0 >> 0) & 7

    if x == 0:
        return (_rot[y], _r[z], 2)
    elif x == 1:
        return ('bit', '%d,%s' % (y, _r[z]), 2)
    elif x == 2:
        return ('res', '%d,%s' % (y, _r[z]), 2)
    else:
        return ('set', '%d,%s' % (y, _r[z]), 2)

#-----------------------------------------------------------------------------

def _da_ddcb_fdcb_prefix(mem, pc, ir):
    """
    0xDDCB <d> <opcode>
    0xFDCB <d> <opcode>
    """
    m0 = mem[pc]
    m1 = mem[pc + 1]
    x = (m1 >> 6) & 3
    y = (m1 >> 3) & 7
    z = (m1 >> 0) & 7
    d = m0
    if d & 0x80:
        d = (d & 0x7f) - 128
    sign = ('', '+')[d >= 0]

    if x == 0:
        if z == 6:
            return(_rot[y], '(%s%s%02x)' % (ir, sign, d), 4)
        else:
            return(_rot[y], '(%s%s%02x),%s' % (ir, sign, d, _r[z]), 4)
    elif x == 1:
        return ('bit', '%d,(%s%s%02x)' % (y, ir, sign, d), 4)
    elif x == 2:
        if z == 6:
            return ('res', '%d,(%s%s%02x)' % (y, ir, sign, d), 4)
        else:
            return ('res', '%d,(%s%s%02x),%s' % (y, ir, sign, d, _r[z]), 4)
    else:
        if z == 6:
            return ('set', '%d,(%s%s%02x)' % (y, ir, sign, d), 4)
        else:
            return ('set', '%d,(%s%s%02x),%s' % (y, ir, sign, d, _r[z]), 4)

#-----------------------------------------------------------------------------

def _da_ed_prefix(mem, pc):
    """
    0xED <opcode>
    0xED <opcode> <nn>
    """
    m0 = mem[pc]
    m1 = mem[pc + 1]
    m2 = mem[pc + 2]
    x = (m0 >> 6) & 3
    y = (m0 >> 3) & 7
    z = (m0 >> 0) & 7
    p = (m0 >> 4) & 3
    q = (m0 >> 3) & 1
    nn = (m2 << 8) + m1

    if x == 1:
        if z == 0:
            if y == 6:
                return ('in', '(c)', 2)
            else:
                return ('in', '%s,(c)' % _r[y], 2)
        elif z == 1:
            if y == 6:
                return ('out', '(c)', 2)
            else:
                return ('out', '(c),%s' % _r[y], 2)
        elif z == 2:
            if q == 0:
                return ('sbc', 'hl,%s' % _rp[p], 2)
            else:
                return ('adc', 'hl,%s' % _rp[p], 2)
        elif z == 3:
            if q == 0:
                return ('ld', '(%04x),%s' % (nn, _rp[p]), 4)
            else:
                return ('ld', '%s,(%04x)' % (_rp[p], nn), 4)
        elif z == 4:
            return ('neg', '', 2)
        elif z == 5:
            if y == 1:
                return ('reti', '', 2)
            else:
                return ('retn', '', 2)
        elif z == 6:
            return ('im', _im[y], 2)
        else:
            if y == 0:
                return ('ld', 'i,a', 2)
            elif y == 1:
                return ('ld', 'r,a', 2)
            elif y == 2:
                return ('ld', 'a,i', 2)
            elif y == 3:
                return ('ld', 'a,r', 2)
            elif y == 4:
                return ('rrd', '', 2)
            elif y == 5:
                return ('rld', '', 2)
            else:
                return ('nop', '', 2)
    elif x == 2:
        if (z <= 3) and (y >= 4):
            return (_bli[z][y - 4], '', 2)
    return ('nop', '', 2)

#-----------------------------------------------------------------------------

def _da_dd_fd_prefix(mem, pc, ir):
    """
    0xDD <x>
    0xFD <x>
    """
    m0 = mem[pc]
    if m0 in (0xdd, 0xed, 0xfd):
        return ('nop', '', 1)
    elif m0 == 0xcb:
        return _da_ddcb_fdcb_prefix(mem, pc + 1, ir)
    else:
        return _da_index(mem, pc, ir)

#-----------------------------------------------------------------------------

def disassemble(mem, pc):
    """
    Disassemble z80 opcodes starting at mem[pc].
    Return an (operation, operands, nbytes) tuple.
    """
    m0 = mem[pc]
    if m0 == 0xcb:
        return _da_cb_prefix(mem, pc + 1)
    elif m0 == 0xdd:
        return _da_dd_fd_prefix(mem, pc + 1, 'ix')
    elif m0 == 0xed:
        return _da_ed_prefix(mem, pc + 1)
    elif m0 == 0xfd:
        return _da_dd_fd_prefix(mem, pc + 1, 'iy')
    else:
        return _da_normal(mem, pc)

#-----------------------------------------------------------------------------
# unit tests

import unittest
import memory

class _da_unit_tests(unittest.TestCase):

    def test_disassembler(self):
        tests = (
            # documented opcodes
            ((((1<<6)|(0<<3)|0),), ('ld', 'b,b')),
            ((((1<<6)|(0<<3)|1),), ('ld', 'b,c')),
            ((((1<<6)|(0<<3)|2),), ('ld', 'b,d')),
            ((((1<<6)|(0<<3)|3),), ('ld', 'b,e')),
            ((((1<<6)|(0<<3)|4),), ('ld', 'b,h')),
            ((((1<<6)|(0<<3)|5),), ('ld', 'b,l')),
            ((((1<<6)|(0<<3)|7),), ('ld', 'b,a')),
            ((((1<<6)|(1<<3)|7),), ('ld', 'c,a')),
            ((((1<<6)|(2<<3)|2),), ('ld', 'd,d')),
            #((0xdd, 0x52), ('ld', 'd,d')),
            #((0xfd, 0x52), ('ld', 'd,d')),
            ((((0<<6)|(0<<3)|6), 0x00), ('ld', 'b,00')),
            ((((0<<6)|(7<<3)|6), 0xab), ('ld', 'a,ab')),
            ((((1<<6)|(7<<3)|6),), ('ld', 'a,(hl)')),
            ((0xdd, ((1<<6)|(0<<3)|6), 0x00), ('ld', 'b,(ix+00)')),
            ((0xdd, ((1<<6)|(0<<3)|6), 0x80), ('ld', 'b,(ix-80)')),
            ((0xdd, ((1<<6)|(7<<3)|6), 0x82), ('ld', 'a,(ix-7e)')),
            ((0xfd, ((1<<6)|(0<<3)|6), 0x00), ('ld', 'b,(iy+00)')),
            ((0xfd, ((1<<6)|(0<<3)|6), 0x80), ('ld', 'b,(iy-80)')),
            ((0xfd, ((1<<6)|(7<<3)|6), 0x82), ('ld', 'a,(iy-7e)')),
            ((0xfd, ((1<<6)|(6<<3)|6), 0x00), ('halt', '', 2)),
            ((0xdd, ((1<<6)|(6<<3)|6), 0x00), ('halt', '', 2)),
            ((((1<<6)|(6<<3)|0),), ('ld', '(hl),b')),
            ((0xdd, ((1<<6)|(6<<3)|0), 0x00), ('ld', '(ix+00),b')),
            ((0xfd, ((1<<6)|(6<<3)|0), 0x00), ('ld', '(iy+00),b')),
            ((((0<<6)|(6<<3)|6), 0x00), ('ld', '(hl),00')),
            ((((0<<6)|(6<<3)|6), 0xff), ('ld', '(hl),ff')),
            ((0xdd, ((0<<6)|(6<<3)|6), 0x00, 0xaa), ('ld', '(ix+00),aa')),
            ((0xdd, ((0<<6)|(6<<3)|6), 0x80, 0xbb), ('ld', '(ix-80),bb')),
            ((0xfd, ((0<<6)|(6<<3)|6), 0x00, 0xcc), ('ld', '(iy+00),cc')),
            ((0xfd, ((0<<6)|(6<<3)|6), 0x80, 0xdd), ('ld', '(iy-80),dd')),
            ((((0<<6)|(1<<3)|2),), ('ld', 'a,(bc)')),
            ((((0<<6)|(3<<3)|2),), ('ld', 'a,(de)')),
            ((((0<<6)|(7<<3)|2), 0x00, 0x00), ('ld', 'a,(0000)')),
            ((((0<<6)|(7<<3)|2), 0x12, 0x34), ('ld', 'a,(3412)')),
            ((((0<<6)|(0<<3)|2),), ('ld', '(bc),a')),
            ((((0<<6)|(2<<3)|2),), ('ld', '(de),a')),
            ((((0<<6)|(6<<3)|2), 0xab, 0xcd), ('ld', '(cdab),a')),
            ((0xed, ((1<<6)|(2<<3)|7)), ('ld', 'a,i')),
            ((0xed, ((1<<6)|(3<<3)|7)), ('ld', 'a,r')),
            ((0xed, ((1<<6)|(0<<3)|7)), ('ld', 'i,a')),
            ((0xed, ((1<<6)|(1<<3)|7)), ('ld', 'r,a')),
            ((((0<<6)|(0<<3)|1), 0x00, 0x00), ('ld', 'bc,0000')),
            ((((0<<6)|(2<<3)|1), 0x00, 0x00), ('ld', 'de,0000')),
            ((((0<<6)|(4<<3)|1), 0x00, 0x00), ('ld', 'hl,0000')),
            ((((0<<6)|(6<<3)|1), 0x00, 0x00), ('ld', 'sp,0000')),
            ((((0<<6)|(6<<3)|1), 0x12, 0x34), ('ld', 'sp,3412')),
            ((0xdd, ((0<<6)|(4<<3)|1), 0x00, 0x00), ('ld', 'ix,0000')),
            ((0xdd, ((0<<6)|(4<<3)|1), 0x12, 0x34), ('ld', 'ix,3412')),
            ((0xfd, ((0<<6)|(4<<3)|1), 0xab, 0xcd), ('ld', 'iy,cdab')),
            ((((0<<6)|(5<<3)|2), 0x12, 0x34), ('ld', 'hl,(3412)')),
            ((0xed, ((1<<6)|(1<<3)|3), 0x12, 0x34), ('ld', 'bc,(3412)')),
            ((0xed, ((1<<6)|(3<<3)|3), 0x12, 0x34), ('ld', 'de,(3412)')),
            ((0xdd, ((0<<6)|(5<<3)|2), 0x12, 0x34), ('ld', 'ix,(3412)')),
            ((0xfd, ((0<<6)|(5<<3)|2), 0x12, 0x34), ('ld', 'iy,(3412)')),
            ((((0 << 6)|(4<<3)|2), 0x12, 0x34), ('ld', '(3412),hl')),
            ((0xed, ((1<<6)|(0<<3)|3), 0x12, 0x34), ('ld', '(3412),bc')),
            ((0xed, ((1<<6)|(6<<3)|3), 0x12, 0x34), ('ld', '(3412),sp')),
            ((0xdd, ((0<<6)|(4<<3)|2), 0x12, 0x34), ('ld', '(3412),ix')),
            ((0xfd, ((0<<6)|(4<<3)|2), 0x12, 0x34), ('ld', '(3412),iy')),
            ((((3<<6)|(7<<3)|1),), ('ld', 'sp,hl')),
            ((0xdd, ((3<<6)|(7<<3)|1)), ('ld', 'sp,ix')),
            ((0xfd, ((3<<6)|(7<<3)|1)), ('ld', 'sp,iy')),
            ((((3<<6)|(0<<3)|5),), ('push', 'bc')),
            ((((3<<6)|(2<<3)|5),), ('push', 'de')),
            ((((3<<6)|(4<<3)|5),), ('push', 'hl')),
            ((((3<<6)|(6<<3)|5),), ('push', 'af')),
            ((0xdd, ((3<<6)|(4<<3)|5)), ('push', 'ix')),
            ((0xfd, ((3<<6)|(4<<3)|5)), ('push', 'iy')),
            ((((3<<6)|(0<<3)|1),), ('pop', 'bc')),
            ((0xdd, ((3<<6)|(4<<3)|1)), ('pop', 'ix')),
            ((0xfd, ((3<<6)|(4<<3)|1)), ('pop', 'iy')),
            ((0xeb,), ('ex', 'de,hl')),
            ((0xdd, 0xeb,), ('ex', 'de,hl')),
            ((0xfd, 0xeb,), ('ex', 'de,hl')),
            ((0x08,), ('ex', 'af,af\'')),
            ((0xd9,), ('exx', '')),
            ((0xe3,), ('ex', '(sp),hl')),
            ((0xdd, 0xe3), ('ex', '(sp),ix')),
            ((0xfd, 0xe3), ('ex', '(sp),iy')),
            ((0xed, 0xa0), ('ldi', '')),
            ((0xed, 0xb0), ('ldir', '')),
            ((0xed, 0xa8), ('ldd', '')),
            ((0xed, 0xb8), ('lddr', '')),
            ((0xed, 0xa1), ('cpi', '')),
            ((0xed, 0xb1), ('cpir', '')),
            ((0xed, 0xa9), ('cpd', '')),
            ((0xed, 0xb9), ('cpdr', '')),
            ((((2<<6)|(0<<3)|0),), ('add', 'a,b')),
            ((0xc6, 0x00), ('add', 'a,00')),
            ((0x86,), ('add', 'a,(hl)')),
            ((0xdd, 0x86, 0x00), ('add', 'a,(ix+00)')),
            ((0xfd, 0x86, 0x00), ('add', 'a,(iy+00)')),
            ((((2<<6)|(1<<3)|0),), ('adc', 'a,b')),
            ((0xce, 0x00), ('adc', 'a,00')),
            ((0x8e,), ('adc', 'a,(hl)')),
            ((0xdd, 0x8e, 0x00), ('adc', 'a,(ix+00)')),
            ((0xfd, 0x8e, 0x00), ('adc', 'a,(iy+00)')),
            ((((2<<6)|(2<<3)|0),), ('sub', 'b')),
            ((0xd6, 0x00), ('sub', '00')),
            ((0x96,), ('sub', '(hl)')),
            ((0xdd, 0x96, 0x00), ('sub', '(ix+00)')),
            ((0xfd, 0x96, 0x00), ('sub', '(iy+00)')),
            ((((2<<6)|(3<<3)|0),), ('sbc', 'a,b')),
            ((0xde, 0x00), ('sbc', 'a,00')),
            ((0x9e,), ('sbc', 'a,(hl)')),
            ((0xdd, 0x9e, 0x00), ('sbc', 'a,(ix+00)')),
            ((0xfd, 0x9e, 0x00), ('sbc', 'a,(iy+00)')),
            ((((2<<6)|(4<<3)|0),), ('and', 'b')),
            ((0xe6, 0x00), ('and', '00')),
            ((0xa6,), ('and', '(hl)')),
            ((0xdd, 0xa6, 0x00), ('and', '(ix+00)')),
            ((0xfd, 0xa6, 0x00), ('and', '(iy+00)')),
            ((((2<<6)|(6<<3)|0),), ('or', 'b')),
            ((0xf6, 0x00), ('or', '00')),
            ((0xb6,), ('or', '(hl)')),
            ((0xdd, 0xb6, 0x00), ('or', '(ix+00)')),
            ((0xfd, 0xb6, 0x00), ('or', '(iy+00)')),
            ((((2<<6)|(5<<3)|0),), ('xor', 'b')),
            ((0xee, 0x00), ('xor', '00')),
            ((0xae,), ('xor', '(hl)')),
            ((0xdd, 0xae, 0x00), ('xor', '(ix+00)')),
            ((0xfd, 0xae, 0x00), ('xor', '(iy+00)')),
            ((((2<<6)|(7<<3)|0),), ('cp', 'b')),
            ((0xfe, 0x00), ('cp', '00')),
            ((0xbe,), ('cp', '(hl)')),
            ((0xdd, 0xbe, 0x00), ('cp', '(ix+00)')),
            ((0xfd, 0xbe, 0x00), ('cp', '(iy+00)')),
            ((((0<<6)|(0<<3)|4),), ('inc', 'b')),
            ((0x34,), ('inc', '(hl)')),
            ((0xdd, 0x34, 0x00), ('inc', '(ix+00)')),
            ((0xfd, 0x34, 0x00), ('inc', '(iy+00)')),
            ((((0<<6)|(0<<3)|5),), ('dec', 'b')),
            ((0x35,), ('dec', '(hl)')),
            ((0xdd, 0x35, 0x00), ('dec', '(ix+00)')),
            ((0xfd, 0x35, 0x00), ('dec', '(iy+00)')),
            ((0x27,), ('daa', '')),
            ((0x2f,), ('cpl', '')),
            ((0xed, 0x44), ('neg', '')),
            ((0x3f,), ('ccf', '')),
            ((0x37,), ('scf', '')),
            ((0x00,), ('nop', '')),
            ((0x76,), ('halt', '')),
            ((0xf3,), ('di', '')),
            ((0xfb,), ('ei', '')),
            ((0xed, 0x46), ('im', '0')),
            ((0xed, 0x56), ('im', '1')),
            ((0xed, 0x5e), ('im', '2')),
            ((((0<<6)|(1<<3)|1),), ('add', 'hl,bc')),
            ((0xed, ((1<<6)|(1<<3)|2)), ('adc', 'hl,bc')),
            ((0xed, ((1<<6)|(0<<3)|2)), ('sbc', 'hl,bc')),
            ((0xdd, ((0<<6)|(1<<3)|1)), ('add', 'ix,bc')),
            ((0xdd, ((0<<6)|(5<<3)|1)), ('add', 'ix,ix')),
            ((0xfd, ((0<<6)|(1<<3)|1)), ('add', 'iy,bc')),
            ((0xfd, ((0<<6)|(5<<3)|1)), ('add', 'iy,iy')),
            ((((0<<6)|(0<<3)|3),), ('inc', 'bc')),
            ((0xdd, ((0<<6)|(4<<3)|3)), ('inc', 'ix')),
            ((0xfd, ((0<<6)|(4<<3)|3)), ('inc', 'iy')),
            ((((0<<6)|(1<<3)|3),), ('dec', 'bc')),
            ((0xdd, ((0<<6)|(5<<3)|3),), ('dec', 'ix')),
            ((0xfd, ((0<<6)|(5<<3)|3),), ('dec', 'iy')),
            ((0x07,), ('rlca', '')),
            ((0x17,), ('rla', '')),
            ((0x0f,), ('rrca', '')),
            ((0x1f,), ('rra', '')),
            ((0xcb, 0x00), ('rlc', 'b')),
            ((0xcb, 0x06), ('rlc', '(hl)')),
            ((0xdd, 0xcb, 0x00, 0x06), ('rlc', '(ix+00)')),
            ((0xfd, 0xcb, 0x00, 0x06), ('rlc', '(iy+00)')),
            ((0xcb, ((0<<6)|(2<<3)|5)), ('rl', 'l')),
            ((0xcb, 0x16), ('rl', '(hl)')),
            ((0xdd, 0xcb, 0x12, 0x16), ('rl', '(ix+12)')),
            ((0xfd, 0xcb, 0x34, 0x16), ('rl', '(iy+34)')),
            ((0xcb, ((0<<6)|(1<<3)|5)), ('rrc', 'l')),
            ((0xcb, 0x0e), ('rrc', '(hl)')),
            ((0xdd, 0xcb, 0x12, 0x0e), ('rrc', '(ix+12)')),
            ((0xfd, 0xcb, 0x34, 0x0e), ('rrc', '(iy+34)')),
            ((0xcb, ((0<<6)|(3<<3)|5)), ('rr', 'l')),
            ((0xcb, 0x1e), ('rr', '(hl)')),
            ((0xdd, 0xcb, 0x12, 0x1e), ('rr', '(ix+12)')),
            ((0xfd, 0xcb, 0x34, 0x1e), ('rr', '(iy+34)')),
            ((0xcb, ((0<<6)|(4<<3)|5)), ('sla', 'l')),
            ((0xcb, 0x26), ('sla', '(hl)')),
            ((0xdd, 0xcb, 0x12, 0x26), ('sla', '(ix+12)')),
            ((0xfd, 0xcb, 0x34, 0x26), ('sla', '(iy+34)')),
            ((0xcb, ((0<<6)|(5<<3)|5)), ('sra', 'l')),
            ((0xcb, 0x2e), ('sra', '(hl)')),
            ((0xdd, 0xcb, 0x12, 0x2e), ('sra', '(ix+12)')),
            ((0xfd, 0xcb, 0x34, 0x2e), ('sra', '(iy+34)')),
            ((0xcb, ((0<<6)|(7<<3)|5)), ('srl', 'l')),
            ((0xcb, 0x3e), ('srl', '(hl)')),
            ((0xdd, 0xcb, 0x12, 0x3e), ('srl', '(ix+12)')),
            ((0xfd, 0xcb, 0x34, 0x3e), ('srl', '(iy+34)')),
            ((0xed, 0x6f), ('rld', '')),
            ((0xed, 0x67), ('rrd', '')),
            ((0xcb, ((1<<6)|(0<<3)|0)), ('bit', '0,b')),
            ((0xcb, ((1<<6)|(5<<3)|1)), ('bit', '5,c')),
            ((0xcb, ((1<<6)|(5<<3)|6)), ('bit', '5,(hl)')),
            ((0xdd, 0xcb, 0x56, ((1 << 6)|(5<<3)|6)), ('bit', '5,(ix+56)')),
            ((0xfd, 0xcb, 0x56, ((1 << 6)|(5<<3)|6)), ('bit', '5,(iy+56)')),
            ((0xcb, ((3<<6)|(0<<3)|0)), ('set', '0,b')),
            ((0xcb, ((3<<6)|(0<<3)|6)), ('set', '0,(hl)')),
            ((0xdd, 0xcb, 0x89, ((3<<6)|(0<<3)|6)), ('set', '0,(ix-77)')),
            ((0xfd, 0xcb, 0x89, ((3<<6)|(0<<3)|6)), ('set', '0,(iy-77)')),
            ((0xcb, ((2<<6)|(0<<3)|0)), ('res', '0,b')),
            ((0xcb, ((2<<6)|(0<<3)|6)), ('res', '0,(hl)')),
            ((0xdd, 0xcb, 0x89, ((2<<6)|(0<<3)|6)), ('res', '0,(ix-77)')),
            ((0xfd, 0xcb, 0x89, ((2<<6)|(0<<3)|6)), ('res', '0,(iy-77)')),
            ((0xc3, 0x12, 0x34), ('jp', '3412')),
            ((((3<<6)|(0<<3)|2), 0xab, 0xcd), ('jp', 'nz,cdab')),
            ((((3<<6)|(1<<3)|2), 0xab, 0xcd), ('jp', 'z,cdab')),
            ((((3<<6)|(2<<3)|2), 0xab, 0xcd), ('jp', 'nc,cdab')),
            ((((3<<6)|(3<<3)|2), 0xab, 0xcd), ('jp', 'c,cdab')),
            ((((3<<6)|(4<<3)|2), 0xab, 0xcd), ('jp', 'po,cdab')),
            ((((3<<6)|(5<<3)|2), 0xab, 0xcd), ('jp', 'pe,cdab')),
            ((((3<<6)|(6<<3)|2), 0xab, 0xcd), ('jp', 'p,cdab')),
            ((((3<<6)|(7<<3)|2), 0xab, 0xcd), ('jp', 'm,cdab')),
            ((0x18, 0x12), ('jr', '0014')),
            ((0x38, 0x12), ('jr', 'c,0014')),
            ((0x30, 0x12), ('jr', 'nc,0014')),
            ((0x28, 0x12), ('jr', 'z,0014')),
            ((0x20, 0x12), ('jr', 'nz,0014')),
            ((0xe9,), ('jp', 'hl')),
            ((0xdd, 0xe9,), ('jp', 'ix')),
            ((0xfd, 0xe9,), ('jp', 'iy')),
            ((0x10, 0x12), ('djnz', '0014')),
            ((0xcd, 0x12, 0x34), ('call', '3412')),
            ((((3<<6)|(4<<3)|4), 0xab, 0xcd), ('call', 'po,cdab')),
            ((0xc9,), ('ret', '')),
            ((((3<<6)|(0<<3)|0),), ('ret', 'nz')),
            ((0xed, 0x4d,), ('reti', '')),
            ((0xed, 0x45,), ('retn', '')),
            ((((3<<6)|(5<<3)|7),), ('rst', '28')),
            ((0xdb, 0x12), ('in', 'a,(12)')),
            ((0xed, ((1<<6)|(0<<3)|0)), ('in', 'b,(c)')),
            ((0xed, 0xa2,), ('ini', '')),
            ((0xed, 0xb2,), ('inir', '')),
            ((0xed, 0xaa,), ('ind', '')),
            ((0xed, 0xba,), ('indr', '')),
            ((0xd3, 0x12), ('out', '(12),a')),
            ((0xed, ((1<<6)|(0<<3)|1)), ('out', '(c),b')),
            ((0xed, 0xa3,), ('outi', '')),
            ((0xed, 0xb3,), ('otir', '')),
            ((0xed, 0xab,), ('outd', '')),
            ((0xed, 0xbb,), ('otdr', '')),

            # undocumented Opcodes
            ((0xcb, 0x30), ('sll', 'b')),
            ((0xcb, 0x31), ('sll', 'c')),
            ((0xcb, 0x32), ('sll', 'd')),
            ((0xcb, 0x33), ('sll', 'e')),
            ((0xcb, 0x34), ('sll', 'h')),
            ((0xcb, 0x35), ('sll', 'l')),
            ((0xcb, 0x36), ('sll', '(hl)')),
            ((0xcb, 0x37), ('sll', 'a')),
            ((0xed, 0x40), ('in', 'b,(c)')),
            ((0xed, 0x41), ('out', '(c),b')),
            ((0xed, 0x42), ('sbc', 'hl,bc')),
            ((0xed, 0x43, 0xab, 0xcd), ('ld', '(cdab),bc')),
            ((0xed, 0x44), ('neg', '')),
            ((0xed, 0x45), ('retn', '')),
            ((0xed, 0x46), ('im', '0')),
            ((0xed, 0x47), ('ld', 'i,a')),
            ((0xed, 0x48), ('in', 'c,(c)')),
            ((0xed, 0x49), ('out', '(c),c')),
            ((0xed, 0x4a), ('adc', 'hl,bc')),
            ((0xed, 0x4b, 0xab, 0xcd), ('ld', 'bc,(cdab)')),
            ((0xed, 0x4c), ('neg', '')),
            ((0xed, 0x4d), ('reti', '')),
            ((0xed, 0x4e), ('im', '0')),
            ((0xed, 0x4f), ('ld', 'r,a')),
            ((0xed, 0x50), ('in', 'd,(c)')),
            ((0xed, 0x51), ('out', '(c),d')),
            ((0xed, 0x52), ('sbc', 'hl,de')),
            ((0xed, 0x53, 0x12, 0x34), ('ld', '(3412),de')),
            ((0xed, 0x54), ('neg', '')),
            ((0xed, 0x55), ('retn', '')),
            ((0xed, 0x56), ('im', '1')),
            ((0xed, 0x57), ('ld', 'a,i')),
            ((0xed, 0x58), ('in', 'e,(c)')),
            ((0xed, 0x59), ('out', '(c),e')),
            ((0xed, 0x5a), ('adc', 'hl,de')),
            ((0xed, 0x5b, 0x12, 0x34), ('ld', 'de,(3412)')),
            ((0xed, 0x5c), ('neg', '')),
            ((0xed, 0x5d), ('retn', '')),
            ((0xed, 0x5e), ('im', '2')),
            ((0xed, 0x5f), ('ld', 'a,r')),
            ((0xed, 0x60), ('in', 'h,(c)')),
            ((0xed, 0x61), ('out', '(c),h')),
            ((0xed, 0x62), ('sbc', 'hl,hl')),
            ((0xed, 0x63, 0x12, 0x34), ('ld', '(3412),hl')),
            ((0xed, 0x64), ('neg', '')),
            ((0xed, 0x65), ('retn', '')),
            ((0xed, 0x66), ('im', '0')),
            ((0xed, 0x67), ('rrd', '')),
            ((0xed, 0x68), ('in', 'l,(c)')),
            ((0xed, 0x69), ('out', '(c),l')),
            ((0xed, 0x6a), ('adc', 'hl,hl')),
            ((0xed, 0x6b, 0xab, 0xcd), ('ld', 'hl,(cdab)')),
            ((0xed, 0x6c), ('neg', '')),
            ((0xed, 0x6d), ('retn', '')),
            ((0xed, 0x6e), ('im', '0')),
            ((0xed, 0x6f), ('rld', '')),
            ((0xed, 0x70), ('in', '(c)')),
            ((0xed, 0x71), ('out', '(c)')),
            ((0xed, 0x72), ('sbc', 'hl,sp')),
            ((0xed, 0x73, 0x45, 0x67), ('ld', '(6745),sp')),
            ((0xed, 0x74), ('neg', '')),
            ((0xed, 0x75), ('retn', '')),
            ((0xed, 0x76), ('im', '1')),
            ((0xed, 0x77), ('nop', '')),
            ((0xed, 0x78), ('in', 'a,(c)')),
            ((0xed, 0x79), ('out', '(c),a')),
            ((0xed, 0x7a), ('adc', 'hl,sp')),
            ((0xed, 0x7b, 0x56, 0x78), ('ld', 'sp,(7856)')),
            ((0xed, 0x7c), ('neg', '')),
            ((0xed, 0x7d), ('retn', '')),
            ((0xed, 0x7e), ('im', '2')),
            ((0xed, 0x7f), ('nop', '')),
            ((0xdd, 0xcb, 0x10, 0xc0), ('set', '0,(ix+10),b')),
            ((0xdd, 0xcb, 0x10, 0xc1), ('set', '0,(ix+10),c')),
            ((0xdd, 0xcb, 0x10, 0xc2), ('set', '0,(ix+10),d')),
            ((0xdd, 0xcb, 0x10, 0xc3), ('set', '0,(ix+10),e')),
            ((0xdd, 0xcb, 0x10, 0xc4), ('set', '0,(ix+10),h')),
            ((0xdd, 0xcb, 0x10, 0xc5), ('set', '0,(ix+10),l')),
            ((0xdd, 0xcb, 0x10, 0xc6), ('set', '0,(ix+10)')),
            ((0xdd, 0xcb, 0x10, 0xc7), ('set', '0,(ix+10),a')),
            ((0xdd, 0xcb, 0x10, 0x78), ('bit', '7,(ix+10)')),
            ((0xdd, 0xcb, 0x10, 0x79), ('bit', '7,(ix+10)')),
            ((0xdd, 0xcb, 0x10, 0x7a), ('bit', '7,(ix+10)')),
            ((0xdd, 0xcb, 0x10, 0x7b), ('bit', '7,(ix+10)')),
            ((0xdd, 0xcb, 0x10, 0x7c), ('bit', '7,(ix+10)')),
            ((0xdd, 0xcb, 0x10, 0x7d), ('bit', '7,(ix+10)')),
            ((0xdd, 0xcb, 0x10, 0x7e), ('bit', '7,(ix+10)')),
            ((0xdd, 0xcb, 0x10, 0x7f), ('bit', '7,(ix+10)')),
            ((0xfd, 0xcb, 0x10, 0xc0), ('set', '0,(iy+10),b')),
            ((0xfd, 0xcb, 0x10, 0xc1), ('set', '0,(iy+10),c')),
            ((0xfd, 0xcb, 0x10, 0xc2), ('set', '0,(iy+10),d')),
            ((0xfd, 0xcb, 0x10, 0xc3), ('set', '0,(iy+10),e')),
            ((0xfd, 0xcb, 0x10, 0xc4), ('set', '0,(iy+10),h')),
            ((0xfd, 0xcb, 0x10, 0xc5), ('set', '0,(iy+10),l')),
            ((0xfd, 0xcb, 0x10, 0xc6), ('set', '0,(iy+10)')),
            ((0xfd, 0xcb, 0x10, 0xc7), ('set', '0,(iy+10),a')),
            ((0xfd, 0xcb, 0x10, 0x78), ('bit', '7,(iy+10)')),
            ((0xfd, 0xcb, 0x10, 0x79), ('bit', '7,(iy+10)')),
            ((0xfd, 0xcb, 0x10, 0x7a), ('bit', '7,(iy+10)')),
            ((0xfd, 0xcb, 0x10, 0x7b), ('bit', '7,(iy+10)')),
            ((0xfd, 0xcb, 0x10, 0x7c), ('bit', '7,(iy+10)')),
            ((0xfd, 0xcb, 0x10, 0x7d), ('bit', '7,(iy+10)')),
            ((0xfd, 0xcb, 0x10, 0x7e), ('bit', '7,(iy+10)')),
            ((0xfd, 0xcb, 0x10, 0x7f), ('bit', '7,(iy+10)')),

            # multiple prefix handling
            ((0xfd, 0xdd), ('nop', '', 1)),
            ((0xfd, 0xed), ('nop', '', 1)),
            ((0xfd, 0xfd), ('nop', '', 1)),
            ((0xdd, 0xdd), ('nop', '', 1)),
            ((0xdd, 0xed), ('nop', '', 1)),
            ((0xdd, 0xfd), ('nop', '', 1)),

            # every opcode
            ((0x00,), ('nop', '')),
            ((0x01, 0x00, 0x00), ('ld', 'bc,0000')),
            ((0x02,), ('ld', '(bc),a')),
            ((0x03,), ('inc', 'bc')),
            ((0x04,), ('inc', 'b')),
            ((0x05,), ('dec', 'b')),
            ((0x06, 0x00), ('ld', 'b,00')),
            ((0x07,), ('rlca', '')),
            ((0x08,), ('ex', 'af,af\'')),
            ((0x09,), ('add', 'hl,bc')),
            ((0x0a,), ('ld', 'a,(bc)')),
            ((0x0b,), ('dec', 'bc')),
            ((0x0c,), ('inc', 'c')),
            ((0x0d,), ('dec', 'c')),
            ((0x0e, 0x00), ('ld', 'c,00')),
            ((0x0f,), ('rrca', '')),
            ((0x10, 0x00), ('djnz', '0002')),
            ((0x11, 0x00, 0x00), ('ld', 'de,0000')),
            ((0x12,), ('ld', '(de),a')),
            ((0x13,), ('inc', 'de')),
            ((0x14,), ('inc', 'd')),
            ((0x15,), ('dec', 'd')),
            ((0x16, 0x00), ('ld', 'd,00')),
            ((0x17,), ('rla', '')),
            ((0x18, 0x00), ('jr', '0002')),
            ((0x19,), ('add', 'hl,de')),
            ((0x1a,), ('ld', 'a,(de)')),
            ((0x1b,), ('dec', 'de')),
            ((0x1c,), ('inc', 'e')),
            ((0x1d,), ('dec', 'e')),
            ((0x1e, 0x00), ('ld', 'e,00')),
            ((0x1f,), ('rra', '')),
            ((0x20, 0x00), ('jr', 'nz,0002')),
            ((0x21, 0x00, 0x00), ('ld', 'hl,0000')),
            ((0x22, 0x00, 0x00), ('ld', '(0000),hl')),
            ((0x23,), ('inc', 'hl')),
            ((0x24,), ('inc', 'h')),
            ((0x25,), ('dec', 'h')),
            ((0x26, 0x00), ('ld', 'h,00')),
            ((0x27,), ('daa', '')),
            ((0x28, 0x00), ('jr', 'z,0002')),
            ((0x29,), ('add', 'hl,hl')),
            ((0x2a, 0x00, 0x00), ('ld', 'hl,(0000)')),
            ((0x2b,), ('dec', 'hl')),
            ((0x2c,), ('inc', 'l')),
            ((0x2d,), ('dec', 'l')),
            ((0x2e, 0x00), ('ld', 'l,00')),
            ((0x2f,), ('cpl', '')),
            ((0x30, 0x00), ('jr', 'nc,0002')),
            ((0x31, 0x00, 0x00), ('ld', 'sp,0000')),
            ((0x32, 0x00, 0x00), ('ld', '(0000),a')),
            ((0x33,), ('inc', 'sp')),
            ((0x34,), ('inc', '(hl)')),
            ((0x35,), ('dec', '(hl)')),
            ((0x36, 0x00), ('ld', '(hl),00')),
            ((0x37,), ('scf', '')),
            ((0x38, 0x00), ('jr', 'c,0002')),
            ((0x39,), ('add', 'hl,sp')),
            ((0x3a, 0x00, 0x00), ('ld', 'a,(0000)')),
            ((0x3b,), ('dec', 'sp')),
            ((0x3c,), ('inc', 'a')),
            ((0x3d,), ('dec', 'a')),
            ((0x3e, 0x00), ('ld', 'a,00')),
            ((0x3f,), ('ccf', '')),
            ((0x40,), ('ld', 'b,b')),
            ((0x41,), ('ld', 'b,c')),
            ((0x42,), ('ld', 'b,d')),
            ((0x43,), ('ld', 'b,e')),
            ((0x44,), ('ld', 'b,h')),
            ((0x45,), ('ld', 'b,l')),
            ((0x46,), ('ld', 'b,(hl)')),
            ((0x47,), ('ld', 'b,a')),
            ((0x48,), ('ld', 'c,b')),
            ((0x49,), ('ld', 'c,c')),
            ((0x4a,), ('ld', 'c,d')),
            ((0x4b,), ('ld', 'c,e')),
            ((0x4c,), ('ld', 'c,h')),
            ((0x4d,), ('ld', 'c,l')),
            ((0x4e,), ('ld', 'c,(hl)')),
            ((0x4f,), ('ld', 'c,a')),
            ((0x50,), ('ld', 'd,b')),
            ((0x51,), ('ld', 'd,c')),
            ((0x52,), ('ld', 'd,d')),
            ((0x53,), ('ld', 'd,e')),
            ((0x54,), ('ld', 'd,h')),
            ((0x55,), ('ld', 'd,l')),
            ((0x56,), ('ld', 'd,(hl)')),
            ((0x57,), ('ld', 'd,a')),
            ((0x58,), ('ld', 'e,b')),
            ((0x59,), ('ld', 'e,c')),
            ((0x5a,), ('ld', 'e,d')),
            ((0x5b,), ('ld', 'e,e')),
            ((0x5c,), ('ld', 'e,h')),
            ((0x5d,), ('ld', 'e,l')),
            ((0x5e,), ('ld', 'e,(hl)')),
            ((0x5f,), ('ld', 'e,a')),
            ((0x60,), ('ld', 'h,b')),
            ((0x61,), ('ld', 'h,c')),
            ((0x62,), ('ld', 'h,d')),
            ((0x63,), ('ld', 'h,e')),
            ((0x64,), ('ld', 'h,h')),
            ((0x65,), ('ld', 'h,l')),
            ((0x66,), ('ld', 'h,(hl)')),
            ((0x67,), ('ld', 'h,a')),
            ((0x68,), ('ld', 'l,b')),
            ((0x69,), ('ld', 'l,c')),
            ((0x6a,), ('ld', 'l,d')),
            ((0x6b,), ('ld', 'l,e')),
            ((0x6c,), ('ld', 'l,h')),
            ((0x6d,), ('ld', 'l,l')),
            ((0x6e,), ('ld', 'l,(hl)')),
            ((0x6f,), ('ld', 'l,a')),
            ((0x70,), ('ld', '(hl),b')),
            ((0x71,), ('ld', '(hl),c')),
            ((0x72,), ('ld', '(hl),d')),
            ((0x73,), ('ld', '(hl),e')),
            ((0x74,), ('ld', '(hl),h')),
            ((0x75,), ('ld', '(hl),l')),
            ((0x76,), ('halt', '')),
            ((0x77,), ('ld', '(hl),a')),
            ((0x78,), ('ld', 'a,b')),
            ((0x79,), ('ld', 'a,c')),
            ((0x7a,), ('ld', 'a,d')),
            ((0x7b,), ('ld', 'a,e')),
            ((0x7c,), ('ld', 'a,h')),
            ((0x7d,), ('ld', 'a,l')),
            ((0x7e,), ('ld', 'a,(hl)')),
            ((0x7f,), ('ld', 'a,a')),
            ((0x80,), ('add', 'a,b')),
            ((0x81,), ('add', 'a,c')),
            ((0x82,), ('add', 'a,d')),
            ((0x83,), ('add', 'a,e')),
            ((0x84,), ('add', 'a,h')),
            ((0x85,), ('add', 'a,l')),
            ((0x86,), ('add', 'a,(hl)')),
            ((0x87,), ('add', 'a,a')),
            ((0x88,), ('adc', 'a,b')),
            ((0x89,), ('adc', 'a,c')),
            ((0x8a,), ('adc', 'a,d')),
            ((0x8b,), ('adc', 'a,e')),
            ((0x8c,), ('adc', 'a,h')),
            ((0x8d,), ('adc', 'a,l')),
            ((0x8e,), ('adc', 'a,(hl)')),
            ((0x8f,), ('adc', 'a,a')),
            ((0x90,), ('sub', 'b')),
            ((0x91,), ('sub', 'c')),
            ((0x92,), ('sub', 'd')),
            ((0x93,), ('sub', 'e')),
            ((0x94,), ('sub', 'h')),
            ((0x95,), ('sub', 'l')),
            ((0x96,), ('sub', '(hl)')),
            ((0x97,), ('sub', 'a')),
            ((0x98,), ('sbc', 'a,b')),
            ((0x99,), ('sbc', 'a,c')),
            ((0x9a,), ('sbc', 'a,d')),
            ((0x9b,), ('sbc', 'a,e')),
            ((0x9c,), ('sbc', 'a,h')),
            ((0x9d,), ('sbc', 'a,l')),
            ((0x9e,), ('sbc', 'a,(hl)')),
            ((0x9f,), ('sbc', 'a,a')),
            ((0xa0,), ('and', 'b')),
            ((0xa1,), ('and', 'c')),
            ((0xa2,), ('and', 'd')),
            ((0xa3,), ('and', 'e')),
            ((0xa4,), ('and', 'h')),
            ((0xa5,), ('and', 'l')),
            ((0xa6,), ('and', '(hl)')),
            ((0xa7,), ('and', 'a')),
            ((0xa8,), ('xor', 'b')),
            ((0xa9,), ('xor', 'c')),
            ((0xaa,), ('xor', 'd')),
            ((0xab,), ('xor', 'e')),
            ((0xac,), ('xor', 'h')),
            ((0xad,), ('xor', 'l')),
            ((0xae,), ('xor', '(hl)')),
            ((0xaf,), ('xor', 'a')),
            ((0xb0,), ('or', 'b')),
            ((0xb1,), ('or', 'c')),
            ((0xb2,), ('or', 'd')),
            ((0xb3,), ('or', 'e')),
            ((0xb4,), ('or', 'h')),
            ((0xb5,), ('or', 'l')),
            ((0xb6,), ('or', '(hl)')),
            ((0xb7,), ('or', 'a')),
            ((0xb8,), ('cp', 'b')),
            ((0xb9,), ('cp', 'c')),
            ((0xba,), ('cp', 'd')),
            ((0xbb,), ('cp', 'e')),
            ((0xbc,), ('cp', 'h')),
            ((0xbd,), ('cp', 'l')),
            ((0xbe,), ('cp', '(hl)')),
            ((0xbf,), ('cp', 'a')),
            ((0xc0,), ('ret', 'nz')),
            ((0xc1,), ('pop', 'bc')),
            ((0xc2, 0x00, 0x00), ('jp', 'nz,0000')),
            ((0xc3, 0x00, 0x00), ('jp', '0000')),
            ((0xc4, 0x00, 0x00), ('call', 'nz,0000')),
            ((0xc5,), ('push', 'bc')),
            ((0xc6, 0x00), ('add', 'a,00')),
            ((0xc7,), ('rst', '00')),
            ((0xc8,), ('ret', 'z')),
            ((0xc9,), ('ret', '')),
            ((0xca, 0x00, 0x00), ('jp', 'z,0000')),
            ((0xcb, 0x00), ('rlc', 'b')),
            ((0xcb, 0x01), ('rlc', 'c')),
            ((0xcb, 0x02), ('rlc', 'd')),
            ((0xcb, 0x03), ('rlc', 'e')),
            ((0xcb, 0x04), ('rlc', 'h')),
            ((0xcb, 0x05), ('rlc', 'l')),
            ((0xcb, 0x06), ('rlc', '(hl)')),
            ((0xcb, 0x07), ('rlc', 'a')),
            ((0xcb, 0x08), ('rrc', 'b')),
            ((0xcb, 0x09), ('rrc', 'c')),
            ((0xcb, 0x0a), ('rrc', 'd')),
            ((0xcb, 0x0b), ('rrc', 'e')),
            ((0xcb, 0x0c), ('rrc', 'h')),
            ((0xcb, 0x0d), ('rrc', 'l')),
            ((0xcb, 0x0e), ('rrc', '(hl)')),
            ((0xcb, 0x0f), ('rrc', 'a')),
            ((0xcb, 0x10), ('rl', 'b')),
            ((0xcb, 0x11), ('rl', 'c')),
            ((0xcb, 0x12), ('rl', 'd')),
            ((0xcb, 0x13), ('rl', 'e')),
            ((0xcb, 0x14), ('rl', 'h')),
            ((0xcb, 0x15), ('rl', 'l')),
            ((0xcb, 0x16), ('rl', '(hl)')),
            ((0xcb, 0x17), ('rl', 'a')),
            ((0xcb, 0x18), ('rr', 'b')),
            ((0xcb, 0x19), ('rr', 'c')),
            ((0xcb, 0x1a), ('rr', 'd')),
            ((0xcb, 0x1b), ('rr', 'e')),
            ((0xcb, 0x1c), ('rr', 'h')),
            ((0xcb, 0x1d), ('rr', 'l')),
            ((0xcb, 0x1e), ('rr', '(hl)')),
            ((0xcb, 0x1f), ('rr', 'a')),
            ((0xcb, 0x20), ('sla', 'b')),
            ((0xcb, 0x21), ('sla', 'c')),
            ((0xcb, 0x22), ('sla', 'd')),
            ((0xcb, 0x23), ('sla', 'e')),
            ((0xcb, 0x24), ('sla', 'h')),
            ((0xcb, 0x25), ('sla', 'l')),
            ((0xcb, 0x26), ('sla', '(hl)')),
            ((0xcb, 0x27), ('sla', 'a')),
            ((0xcb, 0x28), ('sra', 'b')),
            ((0xcb, 0x29), ('sra', 'c')),
            ((0xcb, 0x2a), ('sra', 'd')),
            ((0xcb, 0x2b), ('sra', 'e')),
            ((0xcb, 0x2c), ('sra', 'h')),
            ((0xcb, 0x2d), ('sra', 'l')),
            ((0xcb, 0x2e), ('sra', '(hl)')),
            ((0xcb, 0x2f), ('sra', 'a')),
            ((0xcb, 0x30), ('sll', 'b')),
            ((0xcb, 0x31), ('sll', 'c')),
            ((0xcb, 0x32), ('sll', 'd')),
            ((0xcb, 0x33), ('sll', 'e')),
            ((0xcb, 0x34), ('sll', 'h')),
            ((0xcb, 0x35), ('sll', 'l')),
            ((0xcb, 0x36), ('sll', '(hl)')),
            ((0xcb, 0x37), ('sll', 'a')),
            ((0xcb, 0x38), ('srl', 'b')),
            ((0xcb, 0x39), ('srl', 'c')),
            ((0xcb, 0x3a), ('srl', 'd')),
            ((0xcb, 0x3b), ('srl', 'e')),
            ((0xcb, 0x3c), ('srl', 'h')),
            ((0xcb, 0x3d), ('srl', 'l')),
            ((0xcb, 0x3e), ('srl', '(hl)')),
            ((0xcb, 0x3f), ('srl', 'a')),
            ((0xcb, 0x40), ('bit', '0,b')),
            ((0xcb, 0x41), ('bit', '0,c')),
            ((0xcb, 0x42), ('bit', '0,d')),
            ((0xcb, 0x43), ('bit', '0,e')),
            ((0xcb, 0x44), ('bit', '0,h')),
            ((0xcb, 0x45), ('bit', '0,l')),
            ((0xcb, 0x46), ('bit', '0,(hl)')),
            ((0xcb, 0x47), ('bit', '0,a')),
            ((0xcb, 0x48), ('bit', '1,b')),
            ((0xcb, 0x49), ('bit', '1,c')),
            ((0xcb, 0x4a), ('bit', '1,d')),
            ((0xcb, 0x4b), ('bit', '1,e')),
            ((0xcb, 0x4c), ('bit', '1,h')),
            ((0xcb, 0x4d), ('bit', '1,l')),
            ((0xcb, 0x4e), ('bit', '1,(hl)')),
            ((0xcb, 0x4f), ('bit', '1,a')),
            ((0xcb, 0x50), ('bit', '2,b')),
            ((0xcb, 0x51), ('bit', '2,c')),
            ((0xcb, 0x52), ('bit', '2,d')),
            ((0xcb, 0x53), ('bit', '2,e')),
            ((0xcb, 0x54), ('bit', '2,h')),
            ((0xcb, 0x55), ('bit', '2,l')),
            ((0xcb, 0x56), ('bit', '2,(hl)')),
            ((0xcb, 0x57), ('bit', '2,a')),
            ((0xcb, 0x58), ('bit', '3,b')),
            ((0xcb, 0x59), ('bit', '3,c')),
            ((0xcb, 0x5a), ('bit', '3,d')),
            ((0xcb, 0x5b), ('bit', '3,e')),
            ((0xcb, 0x5c), ('bit', '3,h')),
            ((0xcb, 0x5d), ('bit', '3,l')),
            ((0xcb, 0x5e), ('bit', '3,(hl)')),
            ((0xcb, 0x5f), ('bit', '3,a')),
            ((0xcb, 0x60), ('bit', '4,b')),
            ((0xcb, 0x61), ('bit', '4,c')),
            ((0xcb, 0x62), ('bit', '4,d')),
            ((0xcb, 0x63), ('bit', '4,e')),
            ((0xcb, 0x64), ('bit', '4,h')),
            ((0xcb, 0x65), ('bit', '4,l')),
            ((0xcb, 0x66), ('bit', '4,(hl)')),
            ((0xcb, 0x67), ('bit', '4,a')),
            ((0xcb, 0x68), ('bit', '5,b')),
            ((0xcb, 0x69), ('bit', '5,c')),
            ((0xcb, 0x6a), ('bit', '5,d')),
            ((0xcb, 0x6b), ('bit', '5,e')),
            ((0xcb, 0x6c), ('bit', '5,h')),
            ((0xcb, 0x6d), ('bit', '5,l')),
            ((0xcb, 0x6e), ('bit', '5,(hl)')),
            ((0xcb, 0x6f), ('bit', '5,a')),
            ((0xcb, 0x70), ('bit', '6,b')),
            ((0xcb, 0x71), ('bit', '6,c')),
            ((0xcb, 0x72), ('bit', '6,d')),
            ((0xcb, 0x73), ('bit', '6,e')),
            ((0xcb, 0x74), ('bit', '6,h')),
            ((0xcb, 0x75), ('bit', '6,l')),
            ((0xcb, 0x76), ('bit', '6,(hl)')),
            ((0xcb, 0x77), ('bit', '6,a')),
            ((0xcb, 0x78), ('bit', '7,b')),
            ((0xcb, 0x79), ('bit', '7,c')),
            ((0xcb, 0x7a), ('bit', '7,d')),
            ((0xcb, 0x7b), ('bit', '7,e')),
            ((0xcb, 0x7c), ('bit', '7,h')),
            ((0xcb, 0x7d), ('bit', '7,l')),
            ((0xcb, 0x7e), ('bit', '7,(hl)')),
            ((0xcb, 0x7f), ('bit', '7,a')),
            ((0xcb, 0x80), ('res', '0,b')),
            ((0xcb, 0x81), ('res', '0,c')),
            ((0xcb, 0x82), ('res', '0,d')),
            ((0xcb, 0x83), ('res', '0,e')),
            ((0xcb, 0x84), ('res', '0,h')),
            ((0xcb, 0x85), ('res', '0,l')),
            ((0xcb, 0x86), ('res', '0,(hl)')),
            ((0xcb, 0x87), ('res', '0,a')),
            ((0xcb, 0x88), ('res', '1,b')),
            ((0xcb, 0x89), ('res', '1,c')),
            ((0xcb, 0x8a), ('res', '1,d')),
            ((0xcb, 0x8b), ('res', '1,e')),
            ((0xcb, 0x8c), ('res', '1,h')),
            ((0xcb, 0x8d), ('res', '1,l')),
            ((0xcb, 0x8e), ('res', '1,(hl)')),
            ((0xcb, 0x8f), ('res', '1,a')),
            ((0xcb, 0x90), ('res', '2,b')),
            ((0xcb, 0x91), ('res', '2,c')),
            ((0xcb, 0x92), ('res', '2,d')),
            ((0xcb, 0x93), ('res', '2,e')),
            ((0xcb, 0x94), ('res', '2,h')),
            ((0xcb, 0x95), ('res', '2,l')),
            ((0xcb, 0x96), ('res', '2,(hl)')),
            ((0xcb, 0x97), ('res', '2,a')),
            ((0xcb, 0x98), ('res', '3,b')),
            ((0xcb, 0x99), ('res', '3,c')),
            ((0xcb, 0x9a), ('res', '3,d')),
            ((0xcb, 0x9b), ('res', '3,e')),
            ((0xcb, 0x9c), ('res', '3,h')),
            ((0xcb, 0x9d), ('res', '3,l')),
            ((0xcb, 0x9e), ('res', '3,(hl)')),
            ((0xcb, 0x9f), ('res', '3,a')),
            ((0xcb, 0xa0), ('res', '4,b')),
            ((0xcb, 0xa1), ('res', '4,c')),
            ((0xcb, 0xa2), ('res', '4,d')),
            ((0xcb, 0xa3), ('res', '4,e')),
            ((0xcb, 0xa4), ('res', '4,h')),
            ((0xcb, 0xa5), ('res', '4,l')),
            ((0xcb, 0xa6), ('res', '4,(hl)')),
            ((0xcb, 0xa7), ('res', '4,a')),
            ((0xcb, 0xa8), ('res', '5,b')),
            ((0xcb, 0xa9), ('res', '5,c')),
            ((0xcb, 0xaa), ('res', '5,d')),
            ((0xcb, 0xab), ('res', '5,e')),
            ((0xcb, 0xac), ('res', '5,h')),
            ((0xcb, 0xad), ('res', '5,l')),
            ((0xcb, 0xae), ('res', '5,(hl)')),
            ((0xcb, 0xaf), ('res', '5,a')),
            ((0xcb, 0xb0), ('res', '6,b')),
            ((0xcb, 0xb1), ('res', '6,c')),
            ((0xcb, 0xb2), ('res', '6,d')),
            ((0xcb, 0xb3), ('res', '6,e')),
            ((0xcb, 0xb4), ('res', '6,h')),
            ((0xcb, 0xb5), ('res', '6,l')),
            ((0xcb, 0xb6), ('res', '6,(hl)')),
            ((0xcb, 0xb7), ('res', '6,a')),
            ((0xcb, 0xb8), ('res', '7,b')),
            ((0xcb, 0xb9), ('res', '7,c')),
            ((0xcb, 0xba), ('res', '7,d')),
            ((0xcb, 0xbb), ('res', '7,e')),
            ((0xcb, 0xbc), ('res', '7,h')),
            ((0xcb, 0xbd), ('res', '7,l')),
            ((0xcb, 0xbe), ('res', '7,(hl)')),
            ((0xcb, 0xbf), ('res', '7,a')),
            ((0xcb, 0xc0), ('set', '0,b')),
            ((0xcb, 0xc1), ('set', '0,c')),
            ((0xcb, 0xc2), ('set', '0,d')),
            ((0xcb, 0xc3), ('set', '0,e')),
            ((0xcb, 0xc4), ('set', '0,h')),
            ((0xcb, 0xc5), ('set', '0,l')),
            ((0xcb, 0xc6), ('set', '0,(hl)')),
            ((0xcb, 0xc7), ('set', '0,a')),
            ((0xcb, 0xc8), ('set', '1,b')),
            ((0xcb, 0xc9), ('set', '1,c')),
            ((0xcb, 0xca), ('set', '1,d')),
            ((0xcb, 0xcb), ('set', '1,e')),
            ((0xcb, 0xcc), ('set', '1,h')),
            ((0xcb, 0xcd), ('set', '1,l')),
            ((0xcb, 0xce), ('set', '1,(hl)')),
            ((0xcb, 0xcf), ('set', '1,a')),
            ((0xcb, 0xd0), ('set', '2,b')),
            ((0xcb, 0xd1), ('set', '2,c')),
            ((0xcb, 0xd2), ('set', '2,d')),
            ((0xcb, 0xd3), ('set', '2,e')),
            ((0xcb, 0xd4), ('set', '2,h')),
            ((0xcb, 0xd5), ('set', '2,l')),
            ((0xcb, 0xd6), ('set', '2,(hl)')),
            ((0xcb, 0xd7), ('set', '2,a')),
            ((0xcb, 0xd8), ('set', '3,b')),
            ((0xcb, 0xd9), ('set', '3,c')),
            ((0xcb, 0xda), ('set', '3,d')),
            ((0xcb, 0xdb), ('set', '3,e')),
            ((0xcb, 0xdc), ('set', '3,h')),
            ((0xcb, 0xdd), ('set', '3,l')),
            ((0xcb, 0xde), ('set', '3,(hl)')),
            ((0xcb, 0xdf), ('set', '3,a')),
            ((0xcb, 0xe0), ('set', '4,b')),
            ((0xcb, 0xe1), ('set', '4,c')),
            ((0xcb, 0xe2), ('set', '4,d')),
            ((0xcb, 0xe3), ('set', '4,e')),
            ((0xcb, 0xe4), ('set', '4,h')),
            ((0xcb, 0xe5), ('set', '4,l')),
            ((0xcb, 0xe6), ('set', '4,(hl)')),
            ((0xcb, 0xe7), ('set', '4,a')),
            ((0xcb, 0xe8), ('set', '5,b')),
            ((0xcb, 0xe9), ('set', '5,c')),
            ((0xcb, 0xea), ('set', '5,d')),
            ((0xcb, 0xeb), ('set', '5,e')),
            ((0xcb, 0xec), ('set', '5,h')),
            ((0xcb, 0xed), ('set', '5,l')),
            ((0xcb, 0xee), ('set', '5,(hl)')),
            ((0xcb, 0xef), ('set', '5,a')),
            ((0xcb, 0xf0), ('set', '6,b')),
            ((0xcb, 0xf1), ('set', '6,c')),
            ((0xcb, 0xf2), ('set', '6,d')),
            ((0xcb, 0xf3), ('set', '6,e')),
            ((0xcb, 0xf4), ('set', '6,h')),
            ((0xcb, 0xf5), ('set', '6,l')),
            ((0xcb, 0xf6), ('set', '6,(hl)')),
            ((0xcb, 0xf7), ('set', '6,a')),
            ((0xcb, 0xf8), ('set', '7,b')),
            ((0xcb, 0xf9), ('set', '7,c')),
            ((0xcb, 0xfa), ('set', '7,d')),
            ((0xcb, 0xfb), ('set', '7,e')),
            ((0xcb, 0xfc), ('set', '7,h')),
            ((0xcb, 0xfd), ('set', '7,l')),
            ((0xcb, 0xfe), ('set', '7,(hl)')),
            ((0xcb, 0xff), ('set', '7,a')),
            ((0xcc, 0x00, 0x00), ('call', 'z,0000')),
            ((0xcd, 0x00, 0x00), ('call', '0000')),
            ((0xce, 0x00), ('adc', 'a,00')),
            ((0xcf,), ('rst', '08')),
            ((0xd0,), ('ret', 'nc')),
            ((0xd1,), ('pop', 'de')),
            ((0xd2, 0x00, 0x00), ('jp', 'nc,0000')),
            ((0xd3, 0x00), ('out', '(00),a')),
            ((0xd4, 0x00, 0x00), ('call', 'nc,0000')),
            ((0xd5,), ('push', 'de')),
            ((0xd6, 0x00), ('sub', '00')),
            ((0xd7,), ('rst', '10')),
            ((0xd8,), ('ret', 'c')),
            ((0xd9,), ('exx', '')),
            ((0xda, 0x00, 0x00), ('jp', 'c,0000')),
            ((0xdb, 0x00), ('in', 'a,(00)')),
            ((0xdc, 0x00, 0x00), ('call', 'c,0000')),
            ((0xdd, 0x09), ('add', 'ix,bc')),
            ((0xdd, 0x19), ('add', 'ix,de')),
            ((0xdd, 0x21, 0x00, 0x00), ('ld', 'ix,0000')),
            ((0xdd, 0x22, 0x00, 0x00), ('ld', '(0000),ix')),
            ((0xdd, 0x23), ('inc', 'ix')),
            ((0xdd, 0x24), ('inc', 'ixh')),
            ((0xdd, 0x25), ('dec', 'ixh')),
            ((0xdd, 0x26, 0x00), ('ld', 'ixh,00')),
            ((0xdd, 0x29), ('add', 'ix,ix')),
            ((0xdd, 0x2a, 0x00, 0x00), ('ld', 'ix,(0000)')),
            ((0xdd, 0x2b), ('dec', 'ix')),
            ((0xdd, 0x2c), ('inc', 'ixl')),
            ((0xdd, 0x2d), ('dec', 'ixl')),
            ((0xdd, 0x2e, 0x00), ('ld', 'ixl,00')),
            ((0xdd, 0x34, 0x00), ('inc', '(ix+00)')),
            ((0xdd, 0x35, 0x00), ('dec', '(ix+00)')),
            ((0xdd, 0x36, 0x00, 0x00), ('ld', '(ix+00),00')),
            ((0xdd, 0x39), ('add', 'ix,sp')),
            ((0xdd, 0x44), ('ld', 'b,ixh')),
            ((0xdd, 0x45), ('ld', 'b,ixl')),
            ((0xdd, 0x46, 0x00), ('ld', 'b,(ix+00)')),
            ((0xdd, 0x4c), ('ld', 'c,ixh')),
            ((0xdd, 0x4d), ('ld', 'c,ixl')),
            ((0xdd, 0x4e, 0x00), ('ld', 'c,(ix+00)')),
            ((0xdd, 0x54), ('ld', 'd,ixh')),
            ((0xdd, 0x55), ('ld', 'd,ixl')),
            ((0xdd, 0x56, 0x00), ('ld', 'd,(ix+00)')),
            ((0xdd, 0x5c), ('ld', 'e,ixh')),
            ((0xdd, 0x5d), ('ld', 'e,ixl')),
            ((0xdd, 0x5e, 0x00), ('ld', 'e,(ix+00)')),
            ((0xdd, 0x60), ('ld', 'ixh,b')),
            ((0xdd, 0x61), ('ld', 'ixh,c')),
            ((0xdd, 0x62), ('ld', 'ixh,d')),
            ((0xdd, 0x63), ('ld', 'ixh,e')),
            ((0xdd, 0x64), ('ld', 'ixh,ixh')),
            ((0xdd, 0x65), ('ld', 'ixh,ixl')),
            ((0xdd, 0x66, 0x00), ('ld', 'h,(ix+00)')),
            ((0xdd, 0x67), ('ld', 'ixh,a')),
            ((0xdd, 0x68), ('ld', 'ixl,b')),
            ((0xdd, 0x69), ('ld', 'ixl,c')),
            ((0xdd, 0x6a), ('ld', 'ixl,d')),
            ((0xdd, 0x6b), ('ld', 'ixl,e')),
            ((0xdd, 0x6c), ('ld', 'ixl,ixh')),
            ((0xdd, 0x6d), ('ld', 'ixl,ixl')),
            ((0xdd, 0x6e, 0x00), ('ld', 'l,(ix+00)')),
            ((0xdd, 0x6f), ('ld', 'ixl,a')),
            ((0xdd, 0x70, 0x00), ('ld', '(ix+00),b')),
            ((0xdd, 0x71, 0x00), ('ld', '(ix+00),c')),
            ((0xdd, 0x72, 0x00), ('ld', '(ix+00),d')),
            ((0xdd, 0x73, 0x00), ('ld', '(ix+00),e')),
            ((0xdd, 0x74, 0x00), ('ld', '(ix+00),h')),
            ((0xdd, 0x75, 0x00), ('ld', '(ix+00),l')),
            ((0xdd, 0x77, 0x00), ('ld', '(ix+00),a')),
            ((0xdd, 0x7c), ('ld', 'a,ixh')),
            ((0xdd, 0x7d), ('ld', 'a,ixl')),
            ((0xdd, 0x7e, 0x00), ('ld', 'a,(ix+00)')),
            ((0xdd, 0x84), ('add', 'a,ixh')),
            ((0xdd, 0x85), ('add', 'a,ixl')),
            ((0xdd, 0x86, 0x00), ('add', 'a,(ix+00)')),
            ((0xdd, 0x8c), ('adc', 'a,ixh')),
            ((0xdd, 0x8d), ('adc', 'a,ixl')),
            ((0xdd, 0x8e, 0x00), ('adc', 'a,(ix+00)')),
            ((0xdd, 0x94), ('sub', 'ixh')),
            ((0xdd, 0x95), ('sub', 'ixl')),
            ((0xdd, 0x96, 0x00), ('sub', '(ix+00)')),
            ((0xdd, 0x9c), ('sbc', 'a,ixh')),
            ((0xdd, 0x9d), ('sbc', 'a,ixl')),
            ((0xdd, 0x9e, 0x00), ('sbc', 'a,(ix+00)')),
            ((0xdd, 0xa4), ('and', 'ixh')),
            ((0xdd, 0xa5), ('and', 'ixl')),
            ((0xdd, 0xa6, 0x00), ('and', '(ix+00)')),
            ((0xdd, 0xac), ('xor', 'ixh')),
            ((0xdd, 0xad), ('xor', 'ixl')),
            ((0xdd, 0xae, 0x00), ('xor', '(ix+00)')),
            ((0xdd, 0xb4), ('or', 'ixh')),
            ((0xdd, 0xb5), ('or', 'ixl')),
            ((0xdd, 0xb6, 0x00), ('or', '(ix+00)')),
            ((0xdd, 0xbc), ('cp', 'ixh')),
            ((0xdd, 0xbd), ('cp', 'ixl')),
            ((0xdd, 0xbe, 0x00), ('cp', '(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x00), ('rlc', '(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0x01), ('rlc', '(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0x02), ('rlc', '(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0x03), ('rlc', '(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0x04), ('rlc', '(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0x05), ('rlc', '(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0x06), ('rlc', '(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x07), ('rlc', '(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0x08), ('rrc', '(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0x09), ('rrc', '(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0x0a), ('rrc', '(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0x0b), ('rrc', '(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0x0c), ('rrc', '(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0x0d), ('rrc', '(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0x0e), ('rrc', '(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x0f), ('rrc', '(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0x10), ('rl', '(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0x11), ('rl', '(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0x12), ('rl', '(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0x13), ('rl', '(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0x14), ('rl', '(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0x15), ('rl', '(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0x16), ('rl', '(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x17), ('rl', '(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0x18), ('rr', '(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0x19), ('rr', '(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0x1a), ('rr', '(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0x1b), ('rr', '(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0x1c), ('rr', '(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0x1d), ('rr', '(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0x1e), ('rr', '(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x1f), ('rr', '(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0x20), ('sla', '(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0x21), ('sla', '(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0x22), ('sla', '(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0x23), ('sla', '(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0x24), ('sla', '(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0x25), ('sla', '(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0x26), ('sla', '(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x27), ('sla', '(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0x28), ('sra', '(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0x29), ('sra', '(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0x2a), ('sra', '(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0x2b), ('sra', '(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0x2c), ('sra', '(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0x2d), ('sra', '(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0x2e), ('sra', '(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x2f), ('sra', '(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0x30), ('sll', '(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0x31), ('sll', '(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0x32), ('sll', '(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0x33), ('sll', '(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0x34), ('sll', '(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0x35), ('sll', '(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0x36), ('sll', '(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x37), ('sll', '(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0x38), ('srl', '(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0x39), ('srl', '(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0x3a), ('srl', '(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0x3b), ('srl', '(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0x3c), ('srl', '(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0x3d), ('srl', '(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0x3e), ('srl', '(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x3f), ('srl', '(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0x40), ('bit', '0,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x41), ('bit', '0,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x42), ('bit', '0,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x43), ('bit', '0,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x44), ('bit', '0,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x45), ('bit', '0,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x46), ('bit', '0,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x47), ('bit', '0,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x48), ('bit', '1,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x49), ('bit', '1,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x4a), ('bit', '1,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x4b), ('bit', '1,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x4c), ('bit', '1,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x4d), ('bit', '1,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x4e), ('bit', '1,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x4f), ('bit', '1,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x50), ('bit', '2,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x51), ('bit', '2,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x52), ('bit', '2,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x53), ('bit', '2,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x54), ('bit', '2,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x55), ('bit', '2,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x56), ('bit', '2,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x57), ('bit', '2,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x58), ('bit', '3,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x59), ('bit', '3,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x5a), ('bit', '3,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x5b), ('bit', '3,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x5c), ('bit', '3,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x5d), ('bit', '3,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x5e), ('bit', '3,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x5f), ('bit', '3,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x60), ('bit', '4,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x61), ('bit', '4,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x62), ('bit', '4,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x63), ('bit', '4,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x64), ('bit', '4,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x65), ('bit', '4,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x66), ('bit', '4,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x67), ('bit', '4,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x68), ('bit', '5,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x69), ('bit', '5,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x6a), ('bit', '5,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x6b), ('bit', '5,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x6c), ('bit', '5,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x6d), ('bit', '5,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x6e), ('bit', '5,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x6f), ('bit', '5,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x70), ('bit', '6,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x71), ('bit', '6,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x72), ('bit', '6,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x73), ('bit', '6,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x74), ('bit', '6,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x75), ('bit', '6,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x76), ('bit', '6,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x77), ('bit', '6,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x78), ('bit', '7,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x79), ('bit', '7,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x7a), ('bit', '7,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x7b), ('bit', '7,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x7c), ('bit', '7,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x7d), ('bit', '7,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x7e), ('bit', '7,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x7f), ('bit', '7,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x80), ('res', '0,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0x81), ('res', '0,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0x82), ('res', '0,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0x83), ('res', '0,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0x84), ('res', '0,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0x85), ('res', '0,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0x86), ('res', '0,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x87), ('res', '0,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0x88), ('res', '1,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0x89), ('res', '1,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0x8a), ('res', '1,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0x8b), ('res', '1,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0x8c), ('res', '1,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0x8d), ('res', '1,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0x8e), ('res', '1,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x8f), ('res', '1,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0x90), ('res', '2,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0x91), ('res', '2,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0x92), ('res', '2,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0x93), ('res', '2,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0x94), ('res', '2,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0x95), ('res', '2,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0x96), ('res', '2,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x97), ('res', '2,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0x98), ('res', '3,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0x99), ('res', '3,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0x9a), ('res', '3,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0x9b), ('res', '3,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0x9c), ('res', '3,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0x9d), ('res', '3,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0x9e), ('res', '3,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0x9f), ('res', '3,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0xa0), ('res', '4,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0xa1), ('res', '4,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0xa2), ('res', '4,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0xa3), ('res', '4,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0xa4), ('res', '4,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0xa5), ('res', '4,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0xa6), ('res', '4,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0xa7), ('res', '4,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0xa8), ('res', '5,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0xa9), ('res', '5,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0xaa), ('res', '5,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0xab), ('res', '5,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0xac), ('res', '5,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0xad), ('res', '5,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0xae), ('res', '5,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0xaf), ('res', '5,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0xb0), ('res', '6,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0xb1), ('res', '6,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0xb2), ('res', '6,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0xb3), ('res', '6,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0xb4), ('res', '6,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0xb5), ('res', '6,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0xb6), ('res', '6,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0xb7), ('res', '6,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0xb8), ('res', '7,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0xb9), ('res', '7,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0xba), ('res', '7,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0xbb), ('res', '7,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0xbc), ('res', '7,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0xbd), ('res', '7,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0xbe), ('res', '7,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0xbf), ('res', '7,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0xc0), ('set', '0,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0xc1), ('set', '0,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0xc2), ('set', '0,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0xc3), ('set', '0,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0xc4), ('set', '0,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0xc5), ('set', '0,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0xc6), ('set', '0,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0xc7), ('set', '0,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0xc8), ('set', '1,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0xc9), ('set', '1,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0xca), ('set', '1,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0xcb), ('set', '1,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0xcc), ('set', '1,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0xcd), ('set', '1,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0xce), ('set', '1,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0xcf), ('set', '1,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0xd0), ('set', '2,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0xd1), ('set', '2,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0xd2), ('set', '2,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0xd3), ('set', '2,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0xd4), ('set', '2,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0xd5), ('set', '2,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0xd6), ('set', '2,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0xd7), ('set', '2,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0xd8), ('set', '3,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0xd9), ('set', '3,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0xda), ('set', '3,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0xdb), ('set', '3,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0xdc), ('set', '3,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0xdd), ('set', '3,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0xde), ('set', '3,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0xdf), ('set', '3,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0xe0), ('set', '4,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0xe1), ('set', '4,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0xe2), ('set', '4,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0xe3), ('set', '4,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0xe4), ('set', '4,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0xe5), ('set', '4,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0xe6), ('set', '4,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0xe7), ('set', '4,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0xe8), ('set', '5,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0xe9), ('set', '5,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0xea), ('set', '5,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0xeb), ('set', '5,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0xec), ('set', '5,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0xed), ('set', '5,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0xee), ('set', '5,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0xef), ('set', '5,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0xf0), ('set', '6,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0xf1), ('set', '6,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0xf2), ('set', '6,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0xf3), ('set', '6,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0xf4), ('set', '6,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0xf5), ('set', '6,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0xf6), ('set', '6,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0xf7), ('set', '6,(ix+00),a')),
            ((0xdd, 0xcb, 0x00, 0xf8), ('set', '7,(ix+00),b')),
            ((0xdd, 0xcb, 0x00, 0xf9), ('set', '7,(ix+00),c')),
            ((0xdd, 0xcb, 0x00, 0xfa), ('set', '7,(ix+00),d')),
            ((0xdd, 0xcb, 0x00, 0xfb), ('set', '7,(ix+00),e')),
            ((0xdd, 0xcb, 0x00, 0xfc), ('set', '7,(ix+00),h')),
            ((0xdd, 0xcb, 0x00, 0xfd), ('set', '7,(ix+00),l')),
            ((0xdd, 0xcb, 0x00, 0xfe), ('set', '7,(ix+00)')),
            ((0xdd, 0xcb, 0x00, 0xff), ('set', '7,(ix+00),a')),
            ((0xdd, 0xe1), ('pop', 'ix')),
            ((0xdd, 0xe3), ('ex', '(sp),ix')),
            ((0xdd, 0xe5), ('push', 'ix')),
            ((0xdd, 0xe9), ('jp', 'ix')),
            ((0xdd, 0xf9), ('ld', 'sp,ix')),
            ((0xde, 0x00), ('sbc', 'a,00')),
            ((0xdf,), ('rst', '18')),
            ((0xe0,), ('ret', 'po')),
            ((0xe1,), ('pop', 'hl')),
            ((0xe2, 0x00, 0x00), ('jp', 'po,0000')),
            ((0xe3,), ('ex', '(sp),hl')),
            ((0xe4, 0x00, 0x00), ('call', 'po,0000')),
            ((0xe5,), ('push', 'hl')),
            ((0xe6, 0x00), ('and', '00')),
            ((0xe7,), ('rst', '20')),
            ((0xe8,), ('ret', 'pe')),
            ((0xe9,), ('jp', 'hl')),
            ((0xea, 0x00, 0x00), ('jp', 'pe,0000')),
            ((0xeb,), ('ex', 'de,hl')),
            ((0xec, 0x00, 0x00), ('call', 'pe,0000')),
            ((0xed, 0x40), ('in', 'b,(c)')),
            ((0xed, 0x41), ('out', '(c),b')),
            ((0xed, 0x42), ('sbc', 'hl,bc')),
            ((0xed, 0x43, 0x00, 0x00), ('ld', '(0000),bc')),
            ((0xed, 0x44), ('neg', '')),
            ((0xed, 0x45), ('retn', '')),
            ((0xed, 0x46), ('im', '0')),
            ((0xed, 0x47), ('ld', 'i,a')),
            ((0xed, 0x48), ('in', 'c,(c)')),
            ((0xed, 0x49), ('out', '(c),c')),
            ((0xed, 0x4a), ('adc', 'hl,bc')),
            ((0xed, 0x4b, 0x00, 0x00), ('ld', 'bc,(0000)')),
            ((0xed, 0x4c), ('neg', '')),
            ((0xed, 0x4d), ('reti', '')),
            ((0xed, 0x4e), ('im', '0')),
            ((0xed, 0x4f), ('ld', 'r,a')),
            ((0xed, 0x50), ('in', 'd,(c)')),
            ((0xed, 0x51), ('out', '(c),d')),
            ((0xed, 0x52), ('sbc', 'hl,de')),
            ((0xed, 0x53, 0x00, 0x00), ('ld', '(0000),de')),
            ((0xed, 0x54), ('neg', '')),
            ((0xed, 0x55), ('retn', '')),
            ((0xed, 0x56), ('im', '1')),
            ((0xed, 0x57), ('ld', 'a,i')),
            ((0xed, 0x58), ('in', 'e,(c)')),
            ((0xed, 0x59), ('out', '(c),e')),
            ((0xed, 0x5a), ('adc', 'hl,de')),
            ((0xed, 0x5b, 0x00, 0x00), ('ld', 'de,(0000)')),
            ((0xed, 0x5c), ('neg', '')),
            ((0xed, 0x5d), ('retn', '')),
            ((0xed, 0x5e), ('im', '2')),
            ((0xed, 0x5f), ('ld', 'a,r')),
            ((0xed, 0x60), ('in', 'h,(c)')),
            ((0xed, 0x61), ('out', '(c),h')),
            ((0xed, 0x62), ('sbc', 'hl,hl')),
            ((0xed, 0x63, 0x00, 0x00), ('ld', '(0000),hl')),
            ((0xed, 0x64), ('neg', '')),
            ((0xed, 0x65), ('retn', '')),
            ((0xed, 0x66), ('im', '0')),
            ((0xed, 0x67), ('rrd', '')),
            ((0xed, 0x68), ('in', 'l,(c)')),
            ((0xed, 0x69), ('out', '(c),l')),
            ((0xed, 0x6a), ('adc', 'hl,hl')),
            ((0xed, 0x6b, 0x00, 0x00), ('ld', 'hl,(0000)')),
            ((0xed, 0x6c), ('neg', '')),
            ((0xed, 0x6d), ('retn', '')),
            ((0xed, 0x6e), ('im', '0')),
            ((0xed, 0x6f), ('rld', '')),
            ((0xed, 0x70), ('in', '(c)')),
            ((0xed, 0x71), ('out', '(c)')),
            ((0xed, 0x72), ('sbc', 'hl,sp')),
            ((0xed, 0x73, 0x00, 0x00), ('ld', '(0000),sp')),
            ((0xed, 0x74), ('neg', '')),
            ((0xed, 0x75), ('retn', '')),
            ((0xed, 0x76), ('im', '1')),
            ((0xed, 0x78), ('in', 'a,(c)')),
            ((0xed, 0x79), ('out', '(c),a')),
            ((0xed, 0x7a), ('adc', 'hl,sp')),
            ((0xed, 0x7b, 0x00, 0x00), ('ld', 'sp,(0000)')),
            ((0xed, 0x7c), ('neg', '')),
            ((0xed, 0x7d), ('retn', '')),
            ((0xed, 0x7e), ('im', '2')),
            ((0xed, 0xa0), ('ldi', '')),
            ((0xed, 0xa1), ('cpi', '')),
            ((0xed, 0xa2), ('ini', '')),
            ((0xed, 0xa3), ('outi', '')),
            ((0xed, 0xa8), ('ldd', '')),
            ((0xed, 0xa9), ('cpd', '')),
            ((0xed, 0xaa), ('ind', '')),
            ((0xed, 0xab), ('outd', '')),
            ((0xed, 0xb0), ('ldir', '')),
            ((0xed, 0xb1), ('cpir', '')),
            ((0xed, 0xb2), ('inir', '')),
            ((0xed, 0xb3), ('otir', '')),
            ((0xed, 0xb8), ('lddr', '')),
            ((0xed, 0xb9), ('cpdr', '')),
            ((0xed, 0xba), ('indr', '')),
            ((0xed, 0xbb), ('otdr', '')),
            ((0xee, 0x00), ('xor', '00')),
            ((0xef,), ('rst', '28')),
            ((0xf0,), ('ret', 'p')),
            ((0xf1,), ('pop', 'af')),
            ((0xf2, 0x00, 0x00), ('jp', 'p,0000')),
            ((0xf3,), ('di', '')),
            ((0xf4, 0x00, 0x00), ('call', 'p,0000')),
            ((0xf5,), ('push', 'af')),
            ((0xf6, 0x00), ('or', '00')),
            ((0xf7,), ('rst', '30')),
            ((0xf8,), ('ret', 'm')),
            ((0xf9,), ('ld', 'sp,hl')),
            ((0xfa, 0x00, 0x00), ('jp', 'm,0000')),
            ((0xfb,), ('ei', '')),
            ((0xfc, 0x00, 0x00), ('call', 'm,0000')),
            ((0xfd, 0x09), ('add', 'iy,bc')),
            ((0xfd, 0x19), ('add', 'iy,de')),
            ((0xfd, 0x21, 0x00, 0x00), ('ld', 'iy,0000')),
            ((0xfd, 0x22, 0x00, 0x00), ('ld', '(0000),iy')),
            ((0xfd, 0x23), ('inc', 'iy')),
            ((0xfd, 0x24), ('inc', 'iyh')),
            ((0xfd, 0x25), ('dec', 'iyh')),
            ((0xfd, 0x26, 0x00), ('ld', 'iyh,00')),
            ((0xfd, 0x29), ('add', 'iy,iy')),
            ((0xfd, 0x2a, 0x00, 0x00), ('ld', 'iy,(0000)')),
            ((0xfd, 0x2b), ('dec', 'iy')),
            ((0xfd, 0x2c), ('inc', 'iyl')),
            ((0xfd, 0x2d), ('dec', 'iyl')),
            ((0xfd, 0x2e, 0x00), ('ld', 'iyl,00')),
            ((0xfd, 0x34, 0x00), ('inc', '(iy+00)')),
            ((0xfd, 0x35, 0x00), ('dec', '(iy+00)')),
            ((0xfd, 0x36, 0x00, 0x00), ('ld', '(iy+00),00')),
            ((0xfd, 0x39), ('add', 'iy,sp')),
            ((0xfd, 0x44), ('ld', 'b,iyh')),
            ((0xfd, 0x45), ('ld', 'b,iyl')),
            ((0xfd, 0x46, 0x00), ('ld', 'b,(iy+00)')),
            ((0xfd, 0x4c), ('ld', 'c,iyh')),
            ((0xfd, 0x4d), ('ld', 'c,iyl')),
            ((0xfd, 0x4e, 0x00), ('ld', 'c,(iy+00)')),
            ((0xfd, 0x54), ('ld', 'd,iyh')),
            ((0xfd, 0x55), ('ld', 'd,iyl')),
            ((0xfd, 0x56, 0x00), ('ld', 'd,(iy+00)')),
            ((0xfd, 0x5c), ('ld', 'e,iyh')),
            ((0xfd, 0x5d), ('ld', 'e,iyl')),
            ((0xfd, 0x5e, 0x00), ('ld', 'e,(iy+00)')),
            ((0xfd, 0x60), ('ld', 'iyh,b')),
            ((0xfd, 0x61), ('ld', 'iyh,c')),
            ((0xfd, 0x62), ('ld', 'iyh,d')),
            ((0xfd, 0x63), ('ld', 'iyh,e')),
            ((0xfd, 0x64), ('ld', 'iyh,iyh')),
            ((0xfd, 0x65), ('ld', 'iyh,iyl')),
            ((0xfd, 0x66, 0x00), ('ld', 'h,(iy+00)')),
            ((0xfd, 0x67), ('ld', 'iyh,a')),
            ((0xfd, 0x68), ('ld', 'iyl,b')),
            ((0xfd, 0x69), ('ld', 'iyl,c')),
            ((0xfd, 0x6a), ('ld', 'iyl,d')),
            ((0xfd, 0x6b), ('ld', 'iyl,e')),
            ((0xfd, 0x6c), ('ld', 'iyl,iyh')),
            ((0xfd, 0x6d), ('ld', 'iyl,iyl')),
            ((0xfd, 0x6e, 0x00), ('ld', 'l,(iy+00)')),
            ((0xfd, 0x6f), ('ld', 'iyl,a')),
            ((0xfd, 0x70, 0x00), ('ld', '(iy+00),b')),
            ((0xfd, 0x71, 0x00), ('ld', '(iy+00),c')),
            ((0xfd, 0x72, 0x00), ('ld', '(iy+00),d')),
            ((0xfd, 0x73, 0x00), ('ld', '(iy+00),e')),
            ((0xfd, 0x74, 0x00), ('ld', '(iy+00),h')),
            ((0xfd, 0x75, 0x00), ('ld', '(iy+00),l')),
            ((0xfd, 0x77, 0x00), ('ld', '(iy+00),a')),
            ((0xfd, 0x7c), ('ld', 'a,iyh')),
            ((0xfd, 0x7d), ('ld', 'a,iyl')),
            ((0xfd, 0x7e, 0x00), ('ld', 'a,(iy+00)')),
            ((0xfd, 0x84), ('add', 'a,iyh')),
            ((0xfd, 0x85), ('add', 'a,iyl')),
            ((0xfd, 0x86, 0x00), ('add', 'a,(iy+00)')),
            ((0xfd, 0x8c), ('adc', 'a,iyh')),
            ((0xfd, 0x8d), ('adc', 'a,iyl')),
            ((0xfd, 0x8e, 0x00), ('adc', 'a,(iy+00)')),
            ((0xfd, 0x94), ('sub', 'iyh')),
            ((0xfd, 0x95), ('sub', 'iyl')),
            ((0xfd, 0x96, 0x00), ('sub', '(iy+00)')),
            ((0xfd, 0x9c), ('sbc', 'a,iyh')),
            ((0xfd, 0x9d), ('sbc', 'a,iyl')),
            ((0xfd, 0x9e, 0x00), ('sbc', 'a,(iy+00)')),
            ((0xfd, 0xa4), ('and', 'iyh')),
            ((0xfd, 0xa5), ('and', 'iyl')),
            ((0xfd, 0xa6, 0x00), ('and', '(iy+00)')),
            ((0xfd, 0xac), ('xor', 'iyh')),
            ((0xfd, 0xad), ('xor', 'iyl')),
            ((0xfd, 0xae, 0x00), ('xor', '(iy+00)')),
            ((0xfd, 0xb4), ('or', 'iyh')),
            ((0xfd, 0xb5), ('or', 'iyl')),
            ((0xfd, 0xb6, 0x00), ('or', '(iy+00)')),
            ((0xfd, 0xbc), ('cp', 'iyh')),
            ((0xfd, 0xbd), ('cp', 'iyl')),
            ((0xfd, 0xbe, 0x00), ('cp', '(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x00), ('rlc', '(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0x01), ('rlc', '(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0x02), ('rlc', '(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0x03), ('rlc', '(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0x04), ('rlc', '(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0x05), ('rlc', '(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0x06), ('rlc', '(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x07), ('rlc', '(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0x08), ('rrc', '(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0x09), ('rrc', '(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0x0a), ('rrc', '(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0x0b), ('rrc', '(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0x0c), ('rrc', '(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0x0d), ('rrc', '(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0x0e), ('rrc', '(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x0f), ('rrc', '(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0x10), ('rl', '(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0x11), ('rl', '(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0x12), ('rl', '(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0x13), ('rl', '(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0x14), ('rl', '(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0x15), ('rl', '(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0x16), ('rl', '(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x17), ('rl', '(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0x18), ('rr', '(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0x19), ('rr', '(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0x1a), ('rr', '(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0x1b), ('rr', '(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0x1c), ('rr', '(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0x1d), ('rr', '(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0x1e), ('rr', '(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x1f), ('rr', '(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0x20), ('sla', '(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0x21), ('sla', '(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0x22), ('sla', '(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0x23), ('sla', '(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0x24), ('sla', '(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0x25), ('sla', '(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0x26), ('sla', '(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x27), ('sla', '(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0x28), ('sra', '(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0x29), ('sra', '(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0x2a), ('sra', '(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0x2b), ('sra', '(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0x2c), ('sra', '(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0x2d), ('sra', '(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0x2e), ('sra', '(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x2f), ('sra', '(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0x30), ('sll', '(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0x31), ('sll', '(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0x32), ('sll', '(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0x33), ('sll', '(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0x34), ('sll', '(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0x35), ('sll', '(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0x36), ('sll', '(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x37), ('sll', '(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0x38), ('srl', '(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0x39), ('srl', '(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0x3a), ('srl', '(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0x3b), ('srl', '(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0x3c), ('srl', '(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0x3d), ('srl', '(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0x3e), ('srl', '(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x3f), ('srl', '(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0x40), ('bit', '0,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x41), ('bit', '0,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x42), ('bit', '0,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x43), ('bit', '0,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x44), ('bit', '0,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x45), ('bit', '0,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x46), ('bit', '0,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x47), ('bit', '0,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x48), ('bit', '1,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x49), ('bit', '1,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x4a), ('bit', '1,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x4b), ('bit', '1,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x4c), ('bit', '1,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x4d), ('bit', '1,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x4e), ('bit', '1,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x4f), ('bit', '1,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x50), ('bit', '2,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x51), ('bit', '2,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x52), ('bit', '2,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x53), ('bit', '2,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x54), ('bit', '2,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x55), ('bit', '2,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x56), ('bit', '2,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x57), ('bit', '2,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x58), ('bit', '3,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x59), ('bit', '3,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x5a), ('bit', '3,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x5b), ('bit', '3,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x5c), ('bit', '3,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x5d), ('bit', '3,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x5e), ('bit', '3,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x5f), ('bit', '3,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x60), ('bit', '4,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x61), ('bit', '4,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x62), ('bit', '4,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x63), ('bit', '4,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x64), ('bit', '4,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x65), ('bit', '4,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x66), ('bit', '4,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x67), ('bit', '4,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x68), ('bit', '5,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x69), ('bit', '5,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x6a), ('bit', '5,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x6b), ('bit', '5,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x6c), ('bit', '5,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x6d), ('bit', '5,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x6e), ('bit', '5,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x6f), ('bit', '5,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x70), ('bit', '6,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x71), ('bit', '6,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x72), ('bit', '6,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x73), ('bit', '6,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x74), ('bit', '6,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x75), ('bit', '6,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x76), ('bit', '6,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x77), ('bit', '6,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x78), ('bit', '7,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x79), ('bit', '7,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x7a), ('bit', '7,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x7b), ('bit', '7,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x7c), ('bit', '7,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x7d), ('bit', '7,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x7e), ('bit', '7,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x7f), ('bit', '7,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x80), ('res', '0,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0x81), ('res', '0,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0x82), ('res', '0,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0x83), ('res', '0,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0x84), ('res', '0,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0x85), ('res', '0,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0x86), ('res', '0,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x87), ('res', '0,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0x88), ('res', '1,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0x89), ('res', '1,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0x8a), ('res', '1,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0x8b), ('res', '1,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0x8c), ('res', '1,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0x8d), ('res', '1,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0x8e), ('res', '1,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x8f), ('res', '1,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0x90), ('res', '2,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0x91), ('res', '2,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0x92), ('res', '2,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0x93), ('res', '2,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0x94), ('res', '2,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0x95), ('res', '2,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0x96), ('res', '2,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x97), ('res', '2,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0x98), ('res', '3,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0x99), ('res', '3,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0x9a), ('res', '3,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0x9b), ('res', '3,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0x9c), ('res', '3,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0x9d), ('res', '3,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0x9e), ('res', '3,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0x9f), ('res', '3,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0xa0), ('res', '4,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0xa1), ('res', '4,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0xa2), ('res', '4,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0xa3), ('res', '4,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0xa4), ('res', '4,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0xa5), ('res', '4,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0xa6), ('res', '4,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0xa7), ('res', '4,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0xa8), ('res', '5,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0xa9), ('res', '5,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0xaa), ('res', '5,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0xab), ('res', '5,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0xac), ('res', '5,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0xad), ('res', '5,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0xae), ('res', '5,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0xaf), ('res', '5,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0xb0), ('res', '6,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0xb1), ('res', '6,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0xb2), ('res', '6,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0xb3), ('res', '6,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0xb4), ('res', '6,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0xb5), ('res', '6,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0xb6), ('res', '6,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0xb7), ('res', '6,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0xb8), ('res', '7,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0xb9), ('res', '7,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0xba), ('res', '7,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0xbb), ('res', '7,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0xbc), ('res', '7,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0xbd), ('res', '7,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0xbe), ('res', '7,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0xbf), ('res', '7,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0xc0), ('set', '0,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0xc1), ('set', '0,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0xc2), ('set', '0,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0xc3), ('set', '0,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0xc4), ('set', '0,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0xc5), ('set', '0,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0xc6), ('set', '0,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0xc7), ('set', '0,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0xc8), ('set', '1,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0xc9), ('set', '1,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0xca), ('set', '1,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0xcb), ('set', '1,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0xcc), ('set', '1,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0xcd), ('set', '1,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0xce), ('set', '1,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0xcf), ('set', '1,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0xd0), ('set', '2,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0xd1), ('set', '2,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0xd2), ('set', '2,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0xd3), ('set', '2,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0xd4), ('set', '2,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0xd5), ('set', '2,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0xd6), ('set', '2,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0xd7), ('set', '2,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0xd8), ('set', '3,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0xd9), ('set', '3,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0xda), ('set', '3,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0xdb), ('set', '3,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0xdc), ('set', '3,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0xdd), ('set', '3,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0xde), ('set', '3,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0xdf), ('set', '3,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0xe0), ('set', '4,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0xe1), ('set', '4,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0xe2), ('set', '4,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0xe3), ('set', '4,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0xe4), ('set', '4,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0xe5), ('set', '4,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0xe6), ('set', '4,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0xe7), ('set', '4,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0xe8), ('set', '5,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0xe9), ('set', '5,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0xea), ('set', '5,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0xeb), ('set', '5,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0xec), ('set', '5,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0xed), ('set', '5,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0xee), ('set', '5,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0xef), ('set', '5,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0xf0), ('set', '6,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0xf1), ('set', '6,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0xf2), ('set', '6,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0xf3), ('set', '6,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0xf4), ('set', '6,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0xf5), ('set', '6,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0xf6), ('set', '6,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0xf7), ('set', '6,(iy+00),a')),
            ((0xfd, 0xcb, 0x00, 0xf8), ('set', '7,(iy+00),b')),
            ((0xfd, 0xcb, 0x00, 0xf9), ('set', '7,(iy+00),c')),
            ((0xfd, 0xcb, 0x00, 0xfa), ('set', '7,(iy+00),d')),
            ((0xfd, 0xcb, 0x00, 0xfb), ('set', '7,(iy+00),e')),
            ((0xfd, 0xcb, 0x00, 0xfc), ('set', '7,(iy+00),h')),
            ((0xfd, 0xcb, 0x00, 0xfd), ('set', '7,(iy+00),l')),
            ((0xfd, 0xcb, 0x00, 0xfe), ('set', '7,(iy+00)')),
            ((0xfd, 0xcb, 0x00, 0xff), ('set', '7,(iy+00),a')),
            ((0xfd, 0xe1), ('pop', 'iy')),
            ((0xfd, 0xe3), ('ex', '(sp),iy')),
            ((0xfd, 0xe5), ('push', 'iy')),
            ((0xfd, 0xe9), ('jp', 'iy')),
            ((0xfd, 0xf9), ('ld', 'sp,iy')),
            ((0xfe, 0x00), ('cp', '00')),
            ((0xff,), ('rst', '38')),
        )
        mem = memory.ram(8)
        for data, decode  in tests:
            mem.load(0, data)
            if len(decode) != 3:
                decode = list(decode)
                decode.append(len(data))
                decode = tuple(decode)
            self.assertEqual(disassemble(mem, 0), decode)

#-----------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()

#-----------------------------------------------------------------------------



