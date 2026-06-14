# -----------------------------------------------------------------------------
"""
Z80 Disassembler
"""
# -----------------------------------------------------------------------------

_r = ("b", "c", "d", "e", "h", "l", "(hl)", "a")
_rp = ("bc", "de", "hl", "sp")
_rp2 = ("bc", "de", "hl", "af")
_cc = ("nz", "z", "nc", "c", "po", "pe", "p", "m")
_alu = ("add", "adc", "sub", "sbc", "and", "xor", "or", "cp")
_alux = ("a,", "a,", "", "a,", "", "", "", "")
_rot = ("rlc", "rrc", "rl", "rr", "sla", "sra", "sll", "srl")
_rota = ("rlca", "rrca", "rla", "rra", "daa", "cpl", "scf", "ccf")
_im = ("0", "0", "1", "2", "0", "0", "1", "2")
_bli = (
    ("ldi", "ldd", "ldir", "lddr"),
    ("cpi", "cpd", "cpir", "cpdr"),
    ("ini", "ind", "inir", "indr"),
    ("outi", "outd", "otir", "otdr"),
)

# -----------------------------------------------------------------------------


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
    n = m1
    nn = (m2 << 8) + m1
    d = m1
    if d & 0x80:
        d = (d & 0x7F) - 128
    d = (pc + d + 2) & 0xFFFF

    if x == 0:
        if z == 0:
            if y == 0:
                return ("nop", "", 1)
            elif y == 1:
                return ("ex", "af,af'", 1)
            elif y == 2:
                return ("djnz", "%04x" % d, 2)
            elif y == 3:
                return ("jr", "%04x" % d, 2)
            else:
                return ("jr", "%s,%04x" % (_cc[y - 4], d), 2)
        elif z == 1:
            if q == 0:
                return ("ld", "%s,%04x" % (_rp[p], nn), 3)
            elif q == 1:
                return ("add", "hl,%s" % _rp[p], 1)
        elif z == 2:
            if q == 0:
                if p == 0:
                    return ("ld", "(bc),a", 1)
                elif p == 1:
                    return ("ld", "(de),a", 1)
                elif p == 2:
                    return ("ld", "(%04x),hl" % nn, 3)
                else:
                    return ("ld", "(%04x),a" % nn, 3)
            else:
                if p == 0:
                    return ("ld", "a,(bc)", 1)
                elif p == 1:
                    return ("ld", "a,(de)", 1)
                elif p == 2:
                    return ("ld", "hl,(%04x)" % nn, 3)
                else:
                    return ("ld", "a,(%04x)" % nn, 3)
        elif z == 3:
            if q == 0:
                return ("inc", _rp[p], 1)
            else:
                return ("dec", _rp[p], 1)
        elif z == 4:
            return ("inc", _r[y], 1)
        elif z == 5:
            return ("dec", _r[y], 1)
        elif z == 6:
            return ("ld", "%s,%02x" % (_r[y], n), 2)
        else:
            return (_rota[y], "", 1)
    elif x == 1:
        if (z == 6) and (y == 6):
            return ("halt", "", 1)
        else:
            return ("ld", "%s,%s" % (_r[y], _r[z]), 1)
    elif x == 2:
        return (_alu[y], "%s%s" % (_alux[y], _r[z]), 1)
    else:
        if z == 0:
            return ("ret", _cc[y], 1)
        elif z == 1:
            if q == 0:
                return ("pop", _rp2[p], 1)
            else:
                if p == 0:
                    return ("ret", "", 1)
                elif p == 1:
                    return ("exx", "", 1)
                elif p == 2:
                    return ("jp", "hl", 1)
                else:
                    return ("ld", "sp,hl", 1)
        elif z == 2:
            return ("jp", "%s,%04x" % (_cc[y], nn), 3)
        elif z == 3:
            if y == 0:
                return ("jp", "%04x" % nn, 3)
            elif y == 2:
                return ("out", "(%02x),a" % n, 2)
            elif y == 3:
                return ("in", "a,(%02x)" % n, 2)
            elif y == 4:
                return ("ex", "(sp),hl", 1)
            elif y == 5:
                return ("ex", "de,hl", 1)
            elif y == 6:
                return ("di", "", 1)
            else:
                return ("ei", "", 1)
        elif z == 4:
            return ("call", "%s,%04x" % (_cc[y], nn), 3)
        elif z == 5:
            if q == 0:
                return ("push", _rp2[p], 1)
            else:
                if p == 0:
                    return ("call", "%04x" % nn, 3)
        elif z == 6:
            return (_alu[y], "%s%02x" % (_alux[y], n), 2)
        else:
            return ("rst", "%02x" % (y << 3), 1)


# -----------------------------------------------------------------------------


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
        d = (d & 0x7F) - 128
    sign = ("", "+")[d >= 0]
    dj = (pc + d + 2) & 0xFFFF

    # if using (hl) then: (hl)->(ix+d), h and l are unaffected.
    alt0_r = list(_r)
    alt0_r[6] = "(%s%s%02x)" % (ir, sign, d)

    # if not using (hl) then: hl->ix, h->ixh, l->ixl
    alt1_r = list(_r)
    alt1_r[4] = "%sh" % ir
    alt1_r[5] = "%sl" % ir

    alt_rp = list(_rp)
    alt_rp[2] = ir
    alt_rp2 = list(_rp2)
    alt_rp2[2] = ir

    if x == 0:
        if z == 0:
            if y == 0:
                return ("nop", "", 2)
            elif y == 1:
                return ("ex", "af,af'", 2)
            elif y == 2:
                return ("djnz", "%04x" % dj, 3)
            elif y == 3:
                return ("jr", "%04x" % dj, 3)
            else:
                return ("jr", "%s,%04x" % (_cc[y - 4], dj), 3)
        elif z == 1:
            if q == 0:
                return ("ld", "%s,%04x" % (alt_rp[p], nn), 4)
            elif q == 1:
                return ("add", "%s,%s" % (ir, alt_rp[p]), 2)
        elif z == 2:
            if q == 0:
                if p == 0:
                    return ("ld", "(bc),a", 2)
                elif p == 1:
                    return ("ld", "(de),a", 2)
                elif p == 2:
                    return ("ld", "(%04x),%s" % (nn, ir), 4)
                else:
                    return ("ld", "(%04x),a" % nn, 4)
            else:
                if p == 0:
                    return ("ld", "a,(bc)", 2)
                elif p == 1:
                    return ("ld", "a,(de)", 2)
                elif p == 2:
                    return ("ld", "%s,(%04x)" % (ir, nn), 4)
                else:
                    return ("ld", "a,(%04x)" % nn, 4)
        elif z == 3:
            if q == 0:
                return ("inc", alt_rp[p], 2)
            else:
                return ("dec", alt_rp[p], 2)
        elif z == 4:
            if y == 6:
                return ("inc", alt0_r[y], 3)
            else:
                return ("inc", alt1_r[y], 2)
        elif z == 5:
            if y == 6:
                return ("dec", alt0_r[y], 3)
            else:
                return ("dec", alt1_r[y], 2)
        elif z == 6:
            if y == 6:
                return ("ld", "%s,%02x" % (alt0_r[y], n1), 4)
            else:
                return ("ld", "%s,%02x" % (alt1_r[y], n0), 3)
        else:
            return (_rota[y], "", 2)
    elif x == 1:
        if (z == 6) and (y == 6):
            return ("halt", "", 2)
        else:
            if (y == 6) or (z == 6):
                return ("ld", "%s,%s" % (alt0_r[y], alt0_r[z]), 3)
            else:
                return ("ld", "%s,%s" % (alt1_r[y], alt1_r[z]), 2)
    elif x == 2:
        if z == 6:
            return (_alu[y], "%s%s" % (_alux[y], alt0_r[z]), 3)
        else:
            return (_alu[y], "%s%s" % (_alux[y], alt1_r[z]), 2)
    else:
        if z == 0:
            return ("ret", _cc[y], 2)
        elif z == 1:
            if q == 0:
                return ("pop", alt_rp2[p], 2)
            else:
                if p == 0:
                    return ("ret", "", 2)
                elif p == 1:
                    return ("exx", "", 2)
                elif p == 2:
                    return ("jp", ir, 2)
                else:
                    return ("ld", "sp,%s" % ir, 2)
        elif z == 2:
            return ("jp", "%s,%04x" % (_cc[y], nn), 4)
        elif z == 3:
            if y == 0:
                return ("jp", "%04x" % nn, 4)
            elif y == 2:
                return ("out", "(%02x),a" % n0, 3)
            elif y == 3:
                return ("in", "a,(%02x)" % n0, 3)
            elif y == 4:
                return ("ex", "(sp),%s" % ir, 2)
            elif y == 5:
                return ("ex", "de,hl", 2)
            elif y == 6:
                return ("di", "", 2)
            else:
                return ("ei", "", 2)
        elif z == 4:
            return ("call", "%s,%04x" % (_cc[y], nn), 4)
        elif z == 5:
            if q == 0:
                return ("push", alt_rp2[p], 2)
            else:
                if p == 0:
                    return ("call", "%04x" % nn, 4)
        elif z == 6:
            return (_alu[y], "%s%02x" % (_alux[y], n0), 3)
        else:
            return ("rst", "%02x" % (y << 3), 2)


# -----------------------------------------------------------------------------


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
        return ("bit", "%d,%s" % (y, _r[z]), 2)
    elif x == 2:
        return ("res", "%d,%s" % (y, _r[z]), 2)
    else:
        return ("set", "%d,%s" % (y, _r[z]), 2)


# -----------------------------------------------------------------------------


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
        d = (d & 0x7F) - 128
    sign = ("", "+")[d >= 0]

    if x == 0:
        if z == 6:
            return (_rot[y], "(%s%s%02x)" % (ir, sign, d), 4)
        else:
            return (_rot[y], "(%s%s%02x),%s" % (ir, sign, d, _r[z]), 4)
    elif x == 1:
        return ("bit", "%d,(%s%s%02x)" % (y, ir, sign, d), 4)
    elif x == 2:
        if z == 6:
            return ("res", "%d,(%s%s%02x)" % (y, ir, sign, d), 4)
        else:
            return ("res", "%d,(%s%s%02x),%s" % (y, ir, sign, d, _r[z]), 4)
    else:
        if z == 6:
            return ("set", "%d,(%s%s%02x)" % (y, ir, sign, d), 4)
        else:
            return ("set", "%d,(%s%s%02x),%s" % (y, ir, sign, d, _r[z]), 4)


# -----------------------------------------------------------------------------


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
                return ("in", "(c)", 2)
            else:
                return ("in", "%s,(c)" % _r[y], 2)
        elif z == 1:
            if y == 6:
                return ("out", "(c)", 2)
            else:
                return ("out", "(c),%s" % _r[y], 2)
        elif z == 2:
            if q == 0:
                return ("sbc", "hl,%s" % _rp[p], 2)
            else:
                return ("adc", "hl,%s" % _rp[p], 2)
        elif z == 3:
            if q == 0:
                return ("ld", "(%04x),%s" % (nn, _rp[p]), 4)
            else:
                return ("ld", "%s,(%04x)" % (_rp[p], nn), 4)
        elif z == 4:
            return ("neg", "", 2)
        elif z == 5:
            if y == 1:
                return ("reti", "", 2)
            else:
                return ("retn", "", 2)
        elif z == 6:
            return ("im", _im[y], 2)
        else:
            if y == 0:
                return ("ld", "i,a", 2)
            elif y == 1:
                return ("ld", "r,a", 2)
            elif y == 2:
                return ("ld", "a,i", 2)
            elif y == 3:
                return ("ld", "a,r", 2)
            elif y == 4:
                return ("rrd", "", 2)
            elif y == 5:
                return ("rld", "", 2)
            else:
                return ("nop", "", 2)
    elif x == 2:
        if (z <= 3) and (y >= 4):
            return (_bli[z][y - 4], "", 2)
    return ("nop", "", 2)


# -----------------------------------------------------------------------------


def _da_dd_fd_prefix(mem, pc, ir):
    """
    0xDD <x>
    0xFD <x>
    """
    m0 = mem[pc]
    if m0 in (0xDD, 0xED, 0xFD):
        return ("nop", "", 1)
    elif m0 == 0xCB:
        return _da_ddcb_fdcb_prefix(mem, pc + 1, ir)
    else:
        return _da_index(mem, pc, ir)


# -----------------------------------------------------------------------------


def disassemble(mem, pc):
    """
    Disassemble z80 opcodes starting at mem[pc].
    Return an (operation, operands, nbytes) tuple.
    """
    m0 = mem[pc]
    if m0 == 0xCB:
        return _da_cb_prefix(mem, pc + 1)
    elif m0 == 0xDD:
        return _da_dd_fd_prefix(mem, pc + 1, "ix")
    elif m0 == 0xED:
        return _da_ed_prefix(mem, pc + 1)
    elif m0 == 0xFD:
        return _da_dd_fd_prefix(mem, pc + 1, "iy")
    else:
        return _da_normal(mem, pc)


# -----------------------------------------------------------------------------
# unit tests

import unittest
import memory


class _da_unit_tests(unittest.TestCase):

    def test_disassembler(self):
        tests = (
            # documented opcodes
            ((((1 << 6) | (0 << 3) | 0),), ("ld", "b,b")),
            ((((1 << 6) | (0 << 3) | 1),), ("ld", "b,c")),
            ((((1 << 6) | (0 << 3) | 2),), ("ld", "b,d")),
            ((((1 << 6) | (0 << 3) | 3),), ("ld", "b,e")),
            ((((1 << 6) | (0 << 3) | 4),), ("ld", "b,h")),
            ((((1 << 6) | (0 << 3) | 5),), ("ld", "b,l")),
            ((((1 << 6) | (0 << 3) | 7),), ("ld", "b,a")),
            ((((1 << 6) | (1 << 3) | 7),), ("ld", "c,a")),
            ((((1 << 6) | (2 << 3) | 2),), ("ld", "d,d")),
            # ((0xdd, 0x52), ('ld', 'd,d')),
            # ((0xfd, 0x52), ('ld', 'd,d')),
            ((((0 << 6) | (0 << 3) | 6), 0x00), ("ld", "b,00")),
            ((((0 << 6) | (7 << 3) | 6), 0xAB), ("ld", "a,ab")),
            ((((1 << 6) | (7 << 3) | 6),), ("ld", "a,(hl)")),
            ((0xDD, ((1 << 6) | (0 << 3) | 6), 0x00), ("ld", "b,(ix+00)")),
            ((0xDD, ((1 << 6) | (0 << 3) | 6), 0x80), ("ld", "b,(ix-80)")),
            ((0xDD, ((1 << 6) | (7 << 3) | 6), 0x82), ("ld", "a,(ix-7e)")),
            ((0xFD, ((1 << 6) | (0 << 3) | 6), 0x00), ("ld", "b,(iy+00)")),
            ((0xFD, ((1 << 6) | (0 << 3) | 6), 0x80), ("ld", "b,(iy-80)")),
            ((0xFD, ((1 << 6) | (7 << 3) | 6), 0x82), ("ld", "a,(iy-7e)")),
            ((0xFD, ((1 << 6) | (6 << 3) | 6), 0x00), ("halt", "", 2)),
            ((0xDD, ((1 << 6) | (6 << 3) | 6), 0x00), ("halt", "", 2)),
            ((((1 << 6) | (6 << 3) | 0),), ("ld", "(hl),b")),
            ((0xDD, ((1 << 6) | (6 << 3) | 0), 0x00), ("ld", "(ix+00),b")),
            ((0xFD, ((1 << 6) | (6 << 3) | 0), 0x00), ("ld", "(iy+00),b")),
            ((((0 << 6) | (6 << 3) | 6), 0x00), ("ld", "(hl),00")),
            ((((0 << 6) | (6 << 3) | 6), 0xFF), ("ld", "(hl),ff")),
            ((0xDD, ((0 << 6) | (6 << 3) | 6), 0x00, 0xAA), ("ld", "(ix+00),aa")),
            ((0xDD, ((0 << 6) | (6 << 3) | 6), 0x80, 0xBB), ("ld", "(ix-80),bb")),
            ((0xFD, ((0 << 6) | (6 << 3) | 6), 0x00, 0xCC), ("ld", "(iy+00),cc")),
            ((0xFD, ((0 << 6) | (6 << 3) | 6), 0x80, 0xDD), ("ld", "(iy-80),dd")),
            ((((0 << 6) | (1 << 3) | 2),), ("ld", "a,(bc)")),
            ((((0 << 6) | (3 << 3) | 2),), ("ld", "a,(de)")),
            ((((0 << 6) | (7 << 3) | 2), 0x00, 0x00), ("ld", "a,(0000)")),
            ((((0 << 6) | (7 << 3) | 2), 0x12, 0x34), ("ld", "a,(3412)")),
            ((((0 << 6) | (0 << 3) | 2),), ("ld", "(bc),a")),
            ((((0 << 6) | (2 << 3) | 2),), ("ld", "(de),a")),
            ((((0 << 6) | (6 << 3) | 2), 0xAB, 0xCD), ("ld", "(cdab),a")),
            ((0xED, ((1 << 6) | (2 << 3) | 7)), ("ld", "a,i")),
            ((0xED, ((1 << 6) | (3 << 3) | 7)), ("ld", "a,r")),
            ((0xED, ((1 << 6) | (0 << 3) | 7)), ("ld", "i,a")),
            ((0xED, ((1 << 6) | (1 << 3) | 7)), ("ld", "r,a")),
            ((((0 << 6) | (0 << 3) | 1), 0x00, 0x00), ("ld", "bc,0000")),
            ((((0 << 6) | (2 << 3) | 1), 0x00, 0x00), ("ld", "de,0000")),
            ((((0 << 6) | (4 << 3) | 1), 0x00, 0x00), ("ld", "hl,0000")),
            ((((0 << 6) | (6 << 3) | 1), 0x00, 0x00), ("ld", "sp,0000")),
            ((((0 << 6) | (6 << 3) | 1), 0x12, 0x34), ("ld", "sp,3412")),
            ((0xDD, ((0 << 6) | (4 << 3) | 1), 0x00, 0x00), ("ld", "ix,0000")),
            ((0xDD, ((0 << 6) | (4 << 3) | 1), 0x12, 0x34), ("ld", "ix,3412")),
            ((0xFD, ((0 << 6) | (4 << 3) | 1), 0xAB, 0xCD), ("ld", "iy,cdab")),
            ((((0 << 6) | (5 << 3) | 2), 0x12, 0x34), ("ld", "hl,(3412)")),
            ((0xED, ((1 << 6) | (1 << 3) | 3), 0x12, 0x34), ("ld", "bc,(3412)")),
            ((0xED, ((1 << 6) | (3 << 3) | 3), 0x12, 0x34), ("ld", "de,(3412)")),
            ((0xDD, ((0 << 6) | (5 << 3) | 2), 0x12, 0x34), ("ld", "ix,(3412)")),
            ((0xFD, ((0 << 6) | (5 << 3) | 2), 0x12, 0x34), ("ld", "iy,(3412)")),
            ((((0 << 6) | (4 << 3) | 2), 0x12, 0x34), ("ld", "(3412),hl")),
            ((0xED, ((1 << 6) | (0 << 3) | 3), 0x12, 0x34), ("ld", "(3412),bc")),
            ((0xED, ((1 << 6) | (6 << 3) | 3), 0x12, 0x34), ("ld", "(3412),sp")),
            ((0xDD, ((0 << 6) | (4 << 3) | 2), 0x12, 0x34), ("ld", "(3412),ix")),
            ((0xFD, ((0 << 6) | (4 << 3) | 2), 0x12, 0x34), ("ld", "(3412),iy")),
            ((((3 << 6) | (7 << 3) | 1),), ("ld", "sp,hl")),
            ((0xDD, ((3 << 6) | (7 << 3) | 1)), ("ld", "sp,ix")),
            ((0xFD, ((3 << 6) | (7 << 3) | 1)), ("ld", "sp,iy")),
            ((((3 << 6) | (0 << 3) | 5),), ("push", "bc")),
            ((((3 << 6) | (2 << 3) | 5),), ("push", "de")),
            ((((3 << 6) | (4 << 3) | 5),), ("push", "hl")),
            ((((3 << 6) | (6 << 3) | 5),), ("push", "af")),
            ((0xDD, ((3 << 6) | (4 << 3) | 5)), ("push", "ix")),
            ((0xFD, ((3 << 6) | (4 << 3) | 5)), ("push", "iy")),
            ((((3 << 6) | (0 << 3) | 1),), ("pop", "bc")),
            ((0xDD, ((3 << 6) | (4 << 3) | 1)), ("pop", "ix")),
            ((0xFD, ((3 << 6) | (4 << 3) | 1)), ("pop", "iy")),
            ((0xEB,), ("ex", "de,hl")),
            (
                (
                    0xDD,
                    0xEB,
                ),
                ("ex", "de,hl"),
            ),
            (
                (
                    0xFD,
                    0xEB,
                ),
                ("ex", "de,hl"),
            ),
            ((0x08,), ("ex", "af,af'")),
            ((0xD9,), ("exx", "")),
            ((0xE3,), ("ex", "(sp),hl")),
            ((0xDD, 0xE3), ("ex", "(sp),ix")),
            ((0xFD, 0xE3), ("ex", "(sp),iy")),
            ((0xED, 0xA0), ("ldi", "")),
            ((0xED, 0xB0), ("ldir", "")),
            ((0xED, 0xA8), ("ldd", "")),
            ((0xED, 0xB8), ("lddr", "")),
            ((0xED, 0xA1), ("cpi", "")),
            ((0xED, 0xB1), ("cpir", "")),
            ((0xED, 0xA9), ("cpd", "")),
            ((0xED, 0xB9), ("cpdr", "")),
            ((((2 << 6) | (0 << 3) | 0),), ("add", "a,b")),
            ((0xC6, 0x00), ("add", "a,00")),
            ((0x86,), ("add", "a,(hl)")),
            ((0xDD, 0x86, 0x00), ("add", "a,(ix+00)")),
            ((0xFD, 0x86, 0x00), ("add", "a,(iy+00)")),
            ((((2 << 6) | (1 << 3) | 0),), ("adc", "a,b")),
            ((0xCE, 0x00), ("adc", "a,00")),
            ((0x8E,), ("adc", "a,(hl)")),
            ((0xDD, 0x8E, 0x00), ("adc", "a,(ix+00)")),
            ((0xFD, 0x8E, 0x00), ("adc", "a,(iy+00)")),
            ((((2 << 6) | (2 << 3) | 0),), ("sub", "b")),
            ((0xD6, 0x00), ("sub", "00")),
            ((0x96,), ("sub", "(hl)")),
            ((0xDD, 0x96, 0x00), ("sub", "(ix+00)")),
            ((0xFD, 0x96, 0x00), ("sub", "(iy+00)")),
            ((((2 << 6) | (3 << 3) | 0),), ("sbc", "a,b")),
            ((0xDE, 0x00), ("sbc", "a,00")),
            ((0x9E,), ("sbc", "a,(hl)")),
            ((0xDD, 0x9E, 0x00), ("sbc", "a,(ix+00)")),
            ((0xFD, 0x9E, 0x00), ("sbc", "a,(iy+00)")),
            ((((2 << 6) | (4 << 3) | 0),), ("and", "b")),
            ((0xE6, 0x00), ("and", "00")),
            ((0xA6,), ("and", "(hl)")),
            ((0xDD, 0xA6, 0x00), ("and", "(ix+00)")),
            ((0xFD, 0xA6, 0x00), ("and", "(iy+00)")),
            ((((2 << 6) | (6 << 3) | 0),), ("or", "b")),
            ((0xF6, 0x00), ("or", "00")),
            ((0xB6,), ("or", "(hl)")),
            ((0xDD, 0xB6, 0x00), ("or", "(ix+00)")),
            ((0xFD, 0xB6, 0x00), ("or", "(iy+00)")),
            ((((2 << 6) | (5 << 3) | 0),), ("xor", "b")),
            ((0xEE, 0x00), ("xor", "00")),
            ((0xAE,), ("xor", "(hl)")),
            ((0xDD, 0xAE, 0x00), ("xor", "(ix+00)")),
            ((0xFD, 0xAE, 0x00), ("xor", "(iy+00)")),
            ((((2 << 6) | (7 << 3) | 0),), ("cp", "b")),
            ((0xFE, 0x00), ("cp", "00")),
            ((0xBE,), ("cp", "(hl)")),
            ((0xDD, 0xBE, 0x00), ("cp", "(ix+00)")),
            ((0xFD, 0xBE, 0x00), ("cp", "(iy+00)")),
            ((((0 << 6) | (0 << 3) | 4),), ("inc", "b")),
            ((0x34,), ("inc", "(hl)")),
            ((0xDD, 0x34, 0x00), ("inc", "(ix+00)")),
            ((0xFD, 0x34, 0x00), ("inc", "(iy+00)")),
            ((((0 << 6) | (0 << 3) | 5),), ("dec", "b")),
            ((0x35,), ("dec", "(hl)")),
            ((0xDD, 0x35, 0x00), ("dec", "(ix+00)")),
            ((0xFD, 0x35, 0x00), ("dec", "(iy+00)")),
            ((0x27,), ("daa", "")),
            ((0x2F,), ("cpl", "")),
            ((0xED, 0x44), ("neg", "")),
            ((0x3F,), ("ccf", "")),
            ((0x37,), ("scf", "")),
            ((0x00,), ("nop", "")),
            ((0x76,), ("halt", "")),
            ((0xF3,), ("di", "")),
            ((0xFB,), ("ei", "")),
            ((0xED, 0x46), ("im", "0")),
            ((0xED, 0x56), ("im", "1")),
            ((0xED, 0x5E), ("im", "2")),
            ((((0 << 6) | (1 << 3) | 1),), ("add", "hl,bc")),
            ((0xED, ((1 << 6) | (1 << 3) | 2)), ("adc", "hl,bc")),
            ((0xED, ((1 << 6) | (0 << 3) | 2)), ("sbc", "hl,bc")),
            ((0xDD, ((0 << 6) | (1 << 3) | 1)), ("add", "ix,bc")),
            ((0xDD, ((0 << 6) | (5 << 3) | 1)), ("add", "ix,ix")),
            ((0xFD, ((0 << 6) | (1 << 3) | 1)), ("add", "iy,bc")),
            ((0xFD, ((0 << 6) | (5 << 3) | 1)), ("add", "iy,iy")),
            ((((0 << 6) | (0 << 3) | 3),), ("inc", "bc")),
            ((0xDD, ((0 << 6) | (4 << 3) | 3)), ("inc", "ix")),
            ((0xFD, ((0 << 6) | (4 << 3) | 3)), ("inc", "iy")),
            ((((0 << 6) | (1 << 3) | 3),), ("dec", "bc")),
            (
                (
                    0xDD,
                    ((0 << 6) | (5 << 3) | 3),
                ),
                ("dec", "ix"),
            ),
            (
                (
                    0xFD,
                    ((0 << 6) | (5 << 3) | 3),
                ),
                ("dec", "iy"),
            ),
            ((0x07,), ("rlca", "")),
            ((0x17,), ("rla", "")),
            ((0x0F,), ("rrca", "")),
            ((0x1F,), ("rra", "")),
            ((0xCB, 0x00), ("rlc", "b")),
            ((0xCB, 0x06), ("rlc", "(hl)")),
            ((0xDD, 0xCB, 0x00, 0x06), ("rlc", "(ix+00)")),
            ((0xFD, 0xCB, 0x00, 0x06), ("rlc", "(iy+00)")),
            ((0xCB, ((0 << 6) | (2 << 3) | 5)), ("rl", "l")),
            ((0xCB, 0x16), ("rl", "(hl)")),
            ((0xDD, 0xCB, 0x12, 0x16), ("rl", "(ix+12)")),
            ((0xFD, 0xCB, 0x34, 0x16), ("rl", "(iy+34)")),
            ((0xCB, ((0 << 6) | (1 << 3) | 5)), ("rrc", "l")),
            ((0xCB, 0x0E), ("rrc", "(hl)")),
            ((0xDD, 0xCB, 0x12, 0x0E), ("rrc", "(ix+12)")),
            ((0xFD, 0xCB, 0x34, 0x0E), ("rrc", "(iy+34)")),
            ((0xCB, ((0 << 6) | (3 << 3) | 5)), ("rr", "l")),
            ((0xCB, 0x1E), ("rr", "(hl)")),
            ((0xDD, 0xCB, 0x12, 0x1E), ("rr", "(ix+12)")),
            ((0xFD, 0xCB, 0x34, 0x1E), ("rr", "(iy+34)")),
            ((0xCB, ((0 << 6) | (4 << 3) | 5)), ("sla", "l")),
            ((0xCB, 0x26), ("sla", "(hl)")),
            ((0xDD, 0xCB, 0x12, 0x26), ("sla", "(ix+12)")),
            ((0xFD, 0xCB, 0x34, 0x26), ("sla", "(iy+34)")),
            ((0xCB, ((0 << 6) | (5 << 3) | 5)), ("sra", "l")),
            ((0xCB, 0x2E), ("sra", "(hl)")),
            ((0xDD, 0xCB, 0x12, 0x2E), ("sra", "(ix+12)")),
            ((0xFD, 0xCB, 0x34, 0x2E), ("sra", "(iy+34)")),
            ((0xCB, ((0 << 6) | (7 << 3) | 5)), ("srl", "l")),
            ((0xCB, 0x3E), ("srl", "(hl)")),
            ((0xDD, 0xCB, 0x12, 0x3E), ("srl", "(ix+12)")),
            ((0xFD, 0xCB, 0x34, 0x3E), ("srl", "(iy+34)")),
            ((0xED, 0x6F), ("rld", "")),
            ((0xED, 0x67), ("rrd", "")),
            ((0xCB, ((1 << 6) | (0 << 3) | 0)), ("bit", "0,b")),
            ((0xCB, ((1 << 6) | (5 << 3) | 1)), ("bit", "5,c")),
            ((0xCB, ((1 << 6) | (5 << 3) | 6)), ("bit", "5,(hl)")),
            ((0xDD, 0xCB, 0x56, ((1 << 6) | (5 << 3) | 6)), ("bit", "5,(ix+56)")),
            ((0xFD, 0xCB, 0x56, ((1 << 6) | (5 << 3) | 6)), ("bit", "5,(iy+56)")),
            ((0xCB, ((3 << 6) | (0 << 3) | 0)), ("set", "0,b")),
            ((0xCB, ((3 << 6) | (0 << 3) | 6)), ("set", "0,(hl)")),
            ((0xDD, 0xCB, 0x89, ((3 << 6) | (0 << 3) | 6)), ("set", "0,(ix-77)")),
            ((0xFD, 0xCB, 0x89, ((3 << 6) | (0 << 3) | 6)), ("set", "0,(iy-77)")),
            ((0xCB, ((2 << 6) | (0 << 3) | 0)), ("res", "0,b")),
            ((0xCB, ((2 << 6) | (0 << 3) | 6)), ("res", "0,(hl)")),
            ((0xDD, 0xCB, 0x89, ((2 << 6) | (0 << 3) | 6)), ("res", "0,(ix-77)")),
            ((0xFD, 0xCB, 0x89, ((2 << 6) | (0 << 3) | 6)), ("res", "0,(iy-77)")),
            ((0xC3, 0x12, 0x34), ("jp", "3412")),
            ((((3 << 6) | (0 << 3) | 2), 0xAB, 0xCD), ("jp", "nz,cdab")),
            ((((3 << 6) | (1 << 3) | 2), 0xAB, 0xCD), ("jp", "z,cdab")),
            ((((3 << 6) | (2 << 3) | 2), 0xAB, 0xCD), ("jp", "nc,cdab")),
            ((((3 << 6) | (3 << 3) | 2), 0xAB, 0xCD), ("jp", "c,cdab")),
            ((((3 << 6) | (4 << 3) | 2), 0xAB, 0xCD), ("jp", "po,cdab")),
            ((((3 << 6) | (5 << 3) | 2), 0xAB, 0xCD), ("jp", "pe,cdab")),
            ((((3 << 6) | (6 << 3) | 2), 0xAB, 0xCD), ("jp", "p,cdab")),
            ((((3 << 6) | (7 << 3) | 2), 0xAB, 0xCD), ("jp", "m,cdab")),
            ((0x18, 0x12), ("jr", "0014")),
            ((0x38, 0x12), ("jr", "c,0014")),
            ((0x30, 0x12), ("jr", "nc,0014")),
            ((0x28, 0x12), ("jr", "z,0014")),
            ((0x20, 0x12), ("jr", "nz,0014")),
            ((0xE9,), ("jp", "hl")),
            (
                (
                    0xDD,
                    0xE9,
                ),
                ("jp", "ix"),
            ),
            (
                (
                    0xFD,
                    0xE9,
                ),
                ("jp", "iy"),
            ),
            ((0x10, 0x12), ("djnz", "0014")),
            ((0xCD, 0x12, 0x34), ("call", "3412")),
            ((((3 << 6) | (4 << 3) | 4), 0xAB, 0xCD), ("call", "po,cdab")),
            ((0xC9,), ("ret", "")),
            ((((3 << 6) | (0 << 3) | 0),), ("ret", "nz")),
            (
                (
                    0xED,
                    0x4D,
                ),
                ("reti", ""),
            ),
            (
                (
                    0xED,
                    0x45,
                ),
                ("retn", ""),
            ),
            ((((3 << 6) | (5 << 3) | 7),), ("rst", "28")),
            ((0xDB, 0x12), ("in", "a,(12)")),
            ((0xED, ((1 << 6) | (0 << 3) | 0)), ("in", "b,(c)")),
            (
                (
                    0xED,
                    0xA2,
                ),
                ("ini", ""),
            ),
            (
                (
                    0xED,
                    0xB2,
                ),
                ("inir", ""),
            ),
            (
                (
                    0xED,
                    0xAA,
                ),
                ("ind", ""),
            ),
            (
                (
                    0xED,
                    0xBA,
                ),
                ("indr", ""),
            ),
            ((0xD3, 0x12), ("out", "(12),a")),
            ((0xED, ((1 << 6) | (0 << 3) | 1)), ("out", "(c),b")),
            (
                (
                    0xED,
                    0xA3,
                ),
                ("outi", ""),
            ),
            (
                (
                    0xED,
                    0xB3,
                ),
                ("otir", ""),
            ),
            (
                (
                    0xED,
                    0xAB,
                ),
                ("outd", ""),
            ),
            (
                (
                    0xED,
                    0xBB,
                ),
                ("otdr", ""),
            ),
            # undocumented Opcodes
            ((0xCB, 0x30), ("sll", "b")),
            ((0xCB, 0x31), ("sll", "c")),
            ((0xCB, 0x32), ("sll", "d")),
            ((0xCB, 0x33), ("sll", "e")),
            ((0xCB, 0x34), ("sll", "h")),
            ((0xCB, 0x35), ("sll", "l")),
            ((0xCB, 0x36), ("sll", "(hl)")),
            ((0xCB, 0x37), ("sll", "a")),
            ((0xED, 0x40), ("in", "b,(c)")),
            ((0xED, 0x41), ("out", "(c),b")),
            ((0xED, 0x42), ("sbc", "hl,bc")),
            ((0xED, 0x43, 0xAB, 0xCD), ("ld", "(cdab),bc")),
            ((0xED, 0x44), ("neg", "")),
            ((0xED, 0x45), ("retn", "")),
            ((0xED, 0x46), ("im", "0")),
            ((0xED, 0x47), ("ld", "i,a")),
            ((0xED, 0x48), ("in", "c,(c)")),
            ((0xED, 0x49), ("out", "(c),c")),
            ((0xED, 0x4A), ("adc", "hl,bc")),
            ((0xED, 0x4B, 0xAB, 0xCD), ("ld", "bc,(cdab)")),
            ((0xED, 0x4C), ("neg", "")),
            ((0xED, 0x4D), ("reti", "")),
            ((0xED, 0x4E), ("im", "0")),
            ((0xED, 0x4F), ("ld", "r,a")),
            ((0xED, 0x50), ("in", "d,(c)")),
            ((0xED, 0x51), ("out", "(c),d")),
            ((0xED, 0x52), ("sbc", "hl,de")),
            ((0xED, 0x53, 0x12, 0x34), ("ld", "(3412),de")),
            ((0xED, 0x54), ("neg", "")),
            ((0xED, 0x55), ("retn", "")),
            ((0xED, 0x56), ("im", "1")),
            ((0xED, 0x57), ("ld", "a,i")),
            ((0xED, 0x58), ("in", "e,(c)")),
            ((0xED, 0x59), ("out", "(c),e")),
            ((0xED, 0x5A), ("adc", "hl,de")),
            ((0xED, 0x5B, 0x12, 0x34), ("ld", "de,(3412)")),
            ((0xED, 0x5C), ("neg", "")),
            ((0xED, 0x5D), ("retn", "")),
            ((0xED, 0x5E), ("im", "2")),
            ((0xED, 0x5F), ("ld", "a,r")),
            ((0xED, 0x60), ("in", "h,(c)")),
            ((0xED, 0x61), ("out", "(c),h")),
            ((0xED, 0x62), ("sbc", "hl,hl")),
            ((0xED, 0x63, 0x12, 0x34), ("ld", "(3412),hl")),
            ((0xED, 0x64), ("neg", "")),
            ((0xED, 0x65), ("retn", "")),
            ((0xED, 0x66), ("im", "0")),
            ((0xED, 0x67), ("rrd", "")),
            ((0xED, 0x68), ("in", "l,(c)")),
            ((0xED, 0x69), ("out", "(c),l")),
            ((0xED, 0x6A), ("adc", "hl,hl")),
            ((0xED, 0x6B, 0xAB, 0xCD), ("ld", "hl,(cdab)")),
            ((0xED, 0x6C), ("neg", "")),
            ((0xED, 0x6D), ("retn", "")),
            ((0xED, 0x6E), ("im", "0")),
            ((0xED, 0x6F), ("rld", "")),
            ((0xED, 0x70), ("in", "(c)")),
            ((0xED, 0x71), ("out", "(c)")),
            ((0xED, 0x72), ("sbc", "hl,sp")),
            ((0xED, 0x73, 0x45, 0x67), ("ld", "(6745),sp")),
            ((0xED, 0x74), ("neg", "")),
            ((0xED, 0x75), ("retn", "")),
            ((0xED, 0x76), ("im", "1")),
            ((0xED, 0x77), ("nop", "")),
            ((0xED, 0x78), ("in", "a,(c)")),
            ((0xED, 0x79), ("out", "(c),a")),
            ((0xED, 0x7A), ("adc", "hl,sp")),
            ((0xED, 0x7B, 0x56, 0x78), ("ld", "sp,(7856)")),
            ((0xED, 0x7C), ("neg", "")),
            ((0xED, 0x7D), ("retn", "")),
            ((0xED, 0x7E), ("im", "2")),
            ((0xED, 0x7F), ("nop", "")),
            ((0xDD, 0xCB, 0x10, 0xC0), ("set", "0,(ix+10),b")),
            ((0xDD, 0xCB, 0x10, 0xC1), ("set", "0,(ix+10),c")),
            ((0xDD, 0xCB, 0x10, 0xC2), ("set", "0,(ix+10),d")),
            ((0xDD, 0xCB, 0x10, 0xC3), ("set", "0,(ix+10),e")),
            ((0xDD, 0xCB, 0x10, 0xC4), ("set", "0,(ix+10),h")),
            ((0xDD, 0xCB, 0x10, 0xC5), ("set", "0,(ix+10),l")),
            ((0xDD, 0xCB, 0x10, 0xC6), ("set", "0,(ix+10)")),
            ((0xDD, 0xCB, 0x10, 0xC7), ("set", "0,(ix+10),a")),
            ((0xDD, 0xCB, 0x10, 0x78), ("bit", "7,(ix+10)")),
            ((0xDD, 0xCB, 0x10, 0x79), ("bit", "7,(ix+10)")),
            ((0xDD, 0xCB, 0x10, 0x7A), ("bit", "7,(ix+10)")),
            ((0xDD, 0xCB, 0x10, 0x7B), ("bit", "7,(ix+10)")),
            ((0xDD, 0xCB, 0x10, 0x7C), ("bit", "7,(ix+10)")),
            ((0xDD, 0xCB, 0x10, 0x7D), ("bit", "7,(ix+10)")),
            ((0xDD, 0xCB, 0x10, 0x7E), ("bit", "7,(ix+10)")),
            ((0xDD, 0xCB, 0x10, 0x7F), ("bit", "7,(ix+10)")),
            ((0xFD, 0xCB, 0x10, 0xC0), ("set", "0,(iy+10),b")),
            ((0xFD, 0xCB, 0x10, 0xC1), ("set", "0,(iy+10),c")),
            ((0xFD, 0xCB, 0x10, 0xC2), ("set", "0,(iy+10),d")),
            ((0xFD, 0xCB, 0x10, 0xC3), ("set", "0,(iy+10),e")),
            ((0xFD, 0xCB, 0x10, 0xC4), ("set", "0,(iy+10),h")),
            ((0xFD, 0xCB, 0x10, 0xC5), ("set", "0,(iy+10),l")),
            ((0xFD, 0xCB, 0x10, 0xC6), ("set", "0,(iy+10)")),
            ((0xFD, 0xCB, 0x10, 0xC7), ("set", "0,(iy+10),a")),
            ((0xFD, 0xCB, 0x10, 0x78), ("bit", "7,(iy+10)")),
            ((0xFD, 0xCB, 0x10, 0x79), ("bit", "7,(iy+10)")),
            ((0xFD, 0xCB, 0x10, 0x7A), ("bit", "7,(iy+10)")),
            ((0xFD, 0xCB, 0x10, 0x7B), ("bit", "7,(iy+10)")),
            ((0xFD, 0xCB, 0x10, 0x7C), ("bit", "7,(iy+10)")),
            ((0xFD, 0xCB, 0x10, 0x7D), ("bit", "7,(iy+10)")),
            ((0xFD, 0xCB, 0x10, 0x7E), ("bit", "7,(iy+10)")),
            ((0xFD, 0xCB, 0x10, 0x7F), ("bit", "7,(iy+10)")),
            # multiple prefix handling
            ((0xFD, 0xDD), ("nop", "", 1)),
            ((0xFD, 0xED), ("nop", "", 1)),
            ((0xFD, 0xFD), ("nop", "", 1)),
            ((0xDD, 0xDD), ("nop", "", 1)),
            ((0xDD, 0xED), ("nop", "", 1)),
            ((0xDD, 0xFD), ("nop", "", 1)),
            # every opcode
            ((0x00,), ("nop", "")),
            ((0x01, 0x00, 0x00), ("ld", "bc,0000")),
            ((0x02,), ("ld", "(bc),a")),
            ((0x03,), ("inc", "bc")),
            ((0x04,), ("inc", "b")),
            ((0x05,), ("dec", "b")),
            ((0x06, 0x00), ("ld", "b,00")),
            ((0x07,), ("rlca", "")),
            ((0x08,), ("ex", "af,af'")),
            ((0x09,), ("add", "hl,bc")),
            ((0x0A,), ("ld", "a,(bc)")),
            ((0x0B,), ("dec", "bc")),
            ((0x0C,), ("inc", "c")),
            ((0x0D,), ("dec", "c")),
            ((0x0E, 0x00), ("ld", "c,00")),
            ((0x0F,), ("rrca", "")),
            ((0x10, 0x00), ("djnz", "0002")),
            ((0x11, 0x00, 0x00), ("ld", "de,0000")),
            ((0x12,), ("ld", "(de),a")),
            ((0x13,), ("inc", "de")),
            ((0x14,), ("inc", "d")),
            ((0x15,), ("dec", "d")),
            ((0x16, 0x00), ("ld", "d,00")),
            ((0x17,), ("rla", "")),
            ((0x18, 0x00), ("jr", "0002")),
            ((0x19,), ("add", "hl,de")),
            ((0x1A,), ("ld", "a,(de)")),
            ((0x1B,), ("dec", "de")),
            ((0x1C,), ("inc", "e")),
            ((0x1D,), ("dec", "e")),
            ((0x1E, 0x00), ("ld", "e,00")),
            ((0x1F,), ("rra", "")),
            ((0x20, 0x00), ("jr", "nz,0002")),
            ((0x21, 0x00, 0x00), ("ld", "hl,0000")),
            ((0x22, 0x00, 0x00), ("ld", "(0000),hl")),
            ((0x23,), ("inc", "hl")),
            ((0x24,), ("inc", "h")),
            ((0x25,), ("dec", "h")),
            ((0x26, 0x00), ("ld", "h,00")),
            ((0x27,), ("daa", "")),
            ((0x28, 0x00), ("jr", "z,0002")),
            ((0x29,), ("add", "hl,hl")),
            ((0x2A, 0x00, 0x00), ("ld", "hl,(0000)")),
            ((0x2B,), ("dec", "hl")),
            ((0x2C,), ("inc", "l")),
            ((0x2D,), ("dec", "l")),
            ((0x2E, 0x00), ("ld", "l,00")),
            ((0x2F,), ("cpl", "")),
            ((0x30, 0x00), ("jr", "nc,0002")),
            ((0x31, 0x00, 0x00), ("ld", "sp,0000")),
            ((0x32, 0x00, 0x00), ("ld", "(0000),a")),
            ((0x33,), ("inc", "sp")),
            ((0x34,), ("inc", "(hl)")),
            ((0x35,), ("dec", "(hl)")),
            ((0x36, 0x00), ("ld", "(hl),00")),
            ((0x37,), ("scf", "")),
            ((0x38, 0x00), ("jr", "c,0002")),
            ((0x39,), ("add", "hl,sp")),
            ((0x3A, 0x00, 0x00), ("ld", "a,(0000)")),
            ((0x3B,), ("dec", "sp")),
            ((0x3C,), ("inc", "a")),
            ((0x3D,), ("dec", "a")),
            ((0x3E, 0x00), ("ld", "a,00")),
            ((0x3F,), ("ccf", "")),
            ((0x40,), ("ld", "b,b")),
            ((0x41,), ("ld", "b,c")),
            ((0x42,), ("ld", "b,d")),
            ((0x43,), ("ld", "b,e")),
            ((0x44,), ("ld", "b,h")),
            ((0x45,), ("ld", "b,l")),
            ((0x46,), ("ld", "b,(hl)")),
            ((0x47,), ("ld", "b,a")),
            ((0x48,), ("ld", "c,b")),
            ((0x49,), ("ld", "c,c")),
            ((0x4A,), ("ld", "c,d")),
            ((0x4B,), ("ld", "c,e")),
            ((0x4C,), ("ld", "c,h")),
            ((0x4D,), ("ld", "c,l")),
            ((0x4E,), ("ld", "c,(hl)")),
            ((0x4F,), ("ld", "c,a")),
            ((0x50,), ("ld", "d,b")),
            ((0x51,), ("ld", "d,c")),
            ((0x52,), ("ld", "d,d")),
            ((0x53,), ("ld", "d,e")),
            ((0x54,), ("ld", "d,h")),
            ((0x55,), ("ld", "d,l")),
            ((0x56,), ("ld", "d,(hl)")),
            ((0x57,), ("ld", "d,a")),
            ((0x58,), ("ld", "e,b")),
            ((0x59,), ("ld", "e,c")),
            ((0x5A,), ("ld", "e,d")),
            ((0x5B,), ("ld", "e,e")),
            ((0x5C,), ("ld", "e,h")),
            ((0x5D,), ("ld", "e,l")),
            ((0x5E,), ("ld", "e,(hl)")),
            ((0x5F,), ("ld", "e,a")),
            ((0x60,), ("ld", "h,b")),
            ((0x61,), ("ld", "h,c")),
            ((0x62,), ("ld", "h,d")),
            ((0x63,), ("ld", "h,e")),
            ((0x64,), ("ld", "h,h")),
            ((0x65,), ("ld", "h,l")),
            ((0x66,), ("ld", "h,(hl)")),
            ((0x67,), ("ld", "h,a")),
            ((0x68,), ("ld", "l,b")),
            ((0x69,), ("ld", "l,c")),
            ((0x6A,), ("ld", "l,d")),
            ((0x6B,), ("ld", "l,e")),
            ((0x6C,), ("ld", "l,h")),
            ((0x6D,), ("ld", "l,l")),
            ((0x6E,), ("ld", "l,(hl)")),
            ((0x6F,), ("ld", "l,a")),
            ((0x70,), ("ld", "(hl),b")),
            ((0x71,), ("ld", "(hl),c")),
            ((0x72,), ("ld", "(hl),d")),
            ((0x73,), ("ld", "(hl),e")),
            ((0x74,), ("ld", "(hl),h")),
            ((0x75,), ("ld", "(hl),l")),
            ((0x76,), ("halt", "")),
            ((0x77,), ("ld", "(hl),a")),
            ((0x78,), ("ld", "a,b")),
            ((0x79,), ("ld", "a,c")),
            ((0x7A,), ("ld", "a,d")),
            ((0x7B,), ("ld", "a,e")),
            ((0x7C,), ("ld", "a,h")),
            ((0x7D,), ("ld", "a,l")),
            ((0x7E,), ("ld", "a,(hl)")),
            ((0x7F,), ("ld", "a,a")),
            ((0x80,), ("add", "a,b")),
            ((0x81,), ("add", "a,c")),
            ((0x82,), ("add", "a,d")),
            ((0x83,), ("add", "a,e")),
            ((0x84,), ("add", "a,h")),
            ((0x85,), ("add", "a,l")),
            ((0x86,), ("add", "a,(hl)")),
            ((0x87,), ("add", "a,a")),
            ((0x88,), ("adc", "a,b")),
            ((0x89,), ("adc", "a,c")),
            ((0x8A,), ("adc", "a,d")),
            ((0x8B,), ("adc", "a,e")),
            ((0x8C,), ("adc", "a,h")),
            ((0x8D,), ("adc", "a,l")),
            ((0x8E,), ("adc", "a,(hl)")),
            ((0x8F,), ("adc", "a,a")),
            ((0x90,), ("sub", "b")),
            ((0x91,), ("sub", "c")),
            ((0x92,), ("sub", "d")),
            ((0x93,), ("sub", "e")),
            ((0x94,), ("sub", "h")),
            ((0x95,), ("sub", "l")),
            ((0x96,), ("sub", "(hl)")),
            ((0x97,), ("sub", "a")),
            ((0x98,), ("sbc", "a,b")),
            ((0x99,), ("sbc", "a,c")),
            ((0x9A,), ("sbc", "a,d")),
            ((0x9B,), ("sbc", "a,e")),
            ((0x9C,), ("sbc", "a,h")),
            ((0x9D,), ("sbc", "a,l")),
            ((0x9E,), ("sbc", "a,(hl)")),
            ((0x9F,), ("sbc", "a,a")),
            ((0xA0,), ("and", "b")),
            ((0xA1,), ("and", "c")),
            ((0xA2,), ("and", "d")),
            ((0xA3,), ("and", "e")),
            ((0xA4,), ("and", "h")),
            ((0xA5,), ("and", "l")),
            ((0xA6,), ("and", "(hl)")),
            ((0xA7,), ("and", "a")),
            ((0xA8,), ("xor", "b")),
            ((0xA9,), ("xor", "c")),
            ((0xAA,), ("xor", "d")),
            ((0xAB,), ("xor", "e")),
            ((0xAC,), ("xor", "h")),
            ((0xAD,), ("xor", "l")),
            ((0xAE,), ("xor", "(hl)")),
            ((0xAF,), ("xor", "a")),
            ((0xB0,), ("or", "b")),
            ((0xB1,), ("or", "c")),
            ((0xB2,), ("or", "d")),
            ((0xB3,), ("or", "e")),
            ((0xB4,), ("or", "h")),
            ((0xB5,), ("or", "l")),
            ((0xB6,), ("or", "(hl)")),
            ((0xB7,), ("or", "a")),
            ((0xB8,), ("cp", "b")),
            ((0xB9,), ("cp", "c")),
            ((0xBA,), ("cp", "d")),
            ((0xBB,), ("cp", "e")),
            ((0xBC,), ("cp", "h")),
            ((0xBD,), ("cp", "l")),
            ((0xBE,), ("cp", "(hl)")),
            ((0xBF,), ("cp", "a")),
            ((0xC0,), ("ret", "nz")),
            ((0xC1,), ("pop", "bc")),
            ((0xC2, 0x00, 0x00), ("jp", "nz,0000")),
            ((0xC3, 0x00, 0x00), ("jp", "0000")),
            ((0xC4, 0x00, 0x00), ("call", "nz,0000")),
            ((0xC5,), ("push", "bc")),
            ((0xC6, 0x00), ("add", "a,00")),
            ((0xC7,), ("rst", "00")),
            ((0xC8,), ("ret", "z")),
            ((0xC9,), ("ret", "")),
            ((0xCA, 0x00, 0x00), ("jp", "z,0000")),
            ((0xCB, 0x00), ("rlc", "b")),
            ((0xCB, 0x01), ("rlc", "c")),
            ((0xCB, 0x02), ("rlc", "d")),
            ((0xCB, 0x03), ("rlc", "e")),
            ((0xCB, 0x04), ("rlc", "h")),
            ((0xCB, 0x05), ("rlc", "l")),
            ((0xCB, 0x06), ("rlc", "(hl)")),
            ((0xCB, 0x07), ("rlc", "a")),
            ((0xCB, 0x08), ("rrc", "b")),
            ((0xCB, 0x09), ("rrc", "c")),
            ((0xCB, 0x0A), ("rrc", "d")),
            ((0xCB, 0x0B), ("rrc", "e")),
            ((0xCB, 0x0C), ("rrc", "h")),
            ((0xCB, 0x0D), ("rrc", "l")),
            ((0xCB, 0x0E), ("rrc", "(hl)")),
            ((0xCB, 0x0F), ("rrc", "a")),
            ((0xCB, 0x10), ("rl", "b")),
            ((0xCB, 0x11), ("rl", "c")),
            ((0xCB, 0x12), ("rl", "d")),
            ((0xCB, 0x13), ("rl", "e")),
            ((0xCB, 0x14), ("rl", "h")),
            ((0xCB, 0x15), ("rl", "l")),
            ((0xCB, 0x16), ("rl", "(hl)")),
            ((0xCB, 0x17), ("rl", "a")),
            ((0xCB, 0x18), ("rr", "b")),
            ((0xCB, 0x19), ("rr", "c")),
            ((0xCB, 0x1A), ("rr", "d")),
            ((0xCB, 0x1B), ("rr", "e")),
            ((0xCB, 0x1C), ("rr", "h")),
            ((0xCB, 0x1D), ("rr", "l")),
            ((0xCB, 0x1E), ("rr", "(hl)")),
            ((0xCB, 0x1F), ("rr", "a")),
            ((0xCB, 0x20), ("sla", "b")),
            ((0xCB, 0x21), ("sla", "c")),
            ((0xCB, 0x22), ("sla", "d")),
            ((0xCB, 0x23), ("sla", "e")),
            ((0xCB, 0x24), ("sla", "h")),
            ((0xCB, 0x25), ("sla", "l")),
            ((0xCB, 0x26), ("sla", "(hl)")),
            ((0xCB, 0x27), ("sla", "a")),
            ((0xCB, 0x28), ("sra", "b")),
            ((0xCB, 0x29), ("sra", "c")),
            ((0xCB, 0x2A), ("sra", "d")),
            ((0xCB, 0x2B), ("sra", "e")),
            ((0xCB, 0x2C), ("sra", "h")),
            ((0xCB, 0x2D), ("sra", "l")),
            ((0xCB, 0x2E), ("sra", "(hl)")),
            ((0xCB, 0x2F), ("sra", "a")),
            ((0xCB, 0x30), ("sll", "b")),
            ((0xCB, 0x31), ("sll", "c")),
            ((0xCB, 0x32), ("sll", "d")),
            ((0xCB, 0x33), ("sll", "e")),
            ((0xCB, 0x34), ("sll", "h")),
            ((0xCB, 0x35), ("sll", "l")),
            ((0xCB, 0x36), ("sll", "(hl)")),
            ((0xCB, 0x37), ("sll", "a")),
            ((0xCB, 0x38), ("srl", "b")),
            ((0xCB, 0x39), ("srl", "c")),
            ((0xCB, 0x3A), ("srl", "d")),
            ((0xCB, 0x3B), ("srl", "e")),
            ((0xCB, 0x3C), ("srl", "h")),
            ((0xCB, 0x3D), ("srl", "l")),
            ((0xCB, 0x3E), ("srl", "(hl)")),
            ((0xCB, 0x3F), ("srl", "a")),
            ((0xCB, 0x40), ("bit", "0,b")),
            ((0xCB, 0x41), ("bit", "0,c")),
            ((0xCB, 0x42), ("bit", "0,d")),
            ((0xCB, 0x43), ("bit", "0,e")),
            ((0xCB, 0x44), ("bit", "0,h")),
            ((0xCB, 0x45), ("bit", "0,l")),
            ((0xCB, 0x46), ("bit", "0,(hl)")),
            ((0xCB, 0x47), ("bit", "0,a")),
            ((0xCB, 0x48), ("bit", "1,b")),
            ((0xCB, 0x49), ("bit", "1,c")),
            ((0xCB, 0x4A), ("bit", "1,d")),
            ((0xCB, 0x4B), ("bit", "1,e")),
            ((0xCB, 0x4C), ("bit", "1,h")),
            ((0xCB, 0x4D), ("bit", "1,l")),
            ((0xCB, 0x4E), ("bit", "1,(hl)")),
            ((0xCB, 0x4F), ("bit", "1,a")),
            ((0xCB, 0x50), ("bit", "2,b")),
            ((0xCB, 0x51), ("bit", "2,c")),
            ((0xCB, 0x52), ("bit", "2,d")),
            ((0xCB, 0x53), ("bit", "2,e")),
            ((0xCB, 0x54), ("bit", "2,h")),
            ((0xCB, 0x55), ("bit", "2,l")),
            ((0xCB, 0x56), ("bit", "2,(hl)")),
            ((0xCB, 0x57), ("bit", "2,a")),
            ((0xCB, 0x58), ("bit", "3,b")),
            ((0xCB, 0x59), ("bit", "3,c")),
            ((0xCB, 0x5A), ("bit", "3,d")),
            ((0xCB, 0x5B), ("bit", "3,e")),
            ((0xCB, 0x5C), ("bit", "3,h")),
            ((0xCB, 0x5D), ("bit", "3,l")),
            ((0xCB, 0x5E), ("bit", "3,(hl)")),
            ((0xCB, 0x5F), ("bit", "3,a")),
            ((0xCB, 0x60), ("bit", "4,b")),
            ((0xCB, 0x61), ("bit", "4,c")),
            ((0xCB, 0x62), ("bit", "4,d")),
            ((0xCB, 0x63), ("bit", "4,e")),
            ((0xCB, 0x64), ("bit", "4,h")),
            ((0xCB, 0x65), ("bit", "4,l")),
            ((0xCB, 0x66), ("bit", "4,(hl)")),
            ((0xCB, 0x67), ("bit", "4,a")),
            ((0xCB, 0x68), ("bit", "5,b")),
            ((0xCB, 0x69), ("bit", "5,c")),
            ((0xCB, 0x6A), ("bit", "5,d")),
            ((0xCB, 0x6B), ("bit", "5,e")),
            ((0xCB, 0x6C), ("bit", "5,h")),
            ((0xCB, 0x6D), ("bit", "5,l")),
            ((0xCB, 0x6E), ("bit", "5,(hl)")),
            ((0xCB, 0x6F), ("bit", "5,a")),
            ((0xCB, 0x70), ("bit", "6,b")),
            ((0xCB, 0x71), ("bit", "6,c")),
            ((0xCB, 0x72), ("bit", "6,d")),
            ((0xCB, 0x73), ("bit", "6,e")),
            ((0xCB, 0x74), ("bit", "6,h")),
            ((0xCB, 0x75), ("bit", "6,l")),
            ((0xCB, 0x76), ("bit", "6,(hl)")),
            ((0xCB, 0x77), ("bit", "6,a")),
            ((0xCB, 0x78), ("bit", "7,b")),
            ((0xCB, 0x79), ("bit", "7,c")),
            ((0xCB, 0x7A), ("bit", "7,d")),
            ((0xCB, 0x7B), ("bit", "7,e")),
            ((0xCB, 0x7C), ("bit", "7,h")),
            ((0xCB, 0x7D), ("bit", "7,l")),
            ((0xCB, 0x7E), ("bit", "7,(hl)")),
            ((0xCB, 0x7F), ("bit", "7,a")),
            ((0xCB, 0x80), ("res", "0,b")),
            ((0xCB, 0x81), ("res", "0,c")),
            ((0xCB, 0x82), ("res", "0,d")),
            ((0xCB, 0x83), ("res", "0,e")),
            ((0xCB, 0x84), ("res", "0,h")),
            ((0xCB, 0x85), ("res", "0,l")),
            ((0xCB, 0x86), ("res", "0,(hl)")),
            ((0xCB, 0x87), ("res", "0,a")),
            ((0xCB, 0x88), ("res", "1,b")),
            ((0xCB, 0x89), ("res", "1,c")),
            ((0xCB, 0x8A), ("res", "1,d")),
            ((0xCB, 0x8B), ("res", "1,e")),
            ((0xCB, 0x8C), ("res", "1,h")),
            ((0xCB, 0x8D), ("res", "1,l")),
            ((0xCB, 0x8E), ("res", "1,(hl)")),
            ((0xCB, 0x8F), ("res", "1,a")),
            ((0xCB, 0x90), ("res", "2,b")),
            ((0xCB, 0x91), ("res", "2,c")),
            ((0xCB, 0x92), ("res", "2,d")),
            ((0xCB, 0x93), ("res", "2,e")),
            ((0xCB, 0x94), ("res", "2,h")),
            ((0xCB, 0x95), ("res", "2,l")),
            ((0xCB, 0x96), ("res", "2,(hl)")),
            ((0xCB, 0x97), ("res", "2,a")),
            ((0xCB, 0x98), ("res", "3,b")),
            ((0xCB, 0x99), ("res", "3,c")),
            ((0xCB, 0x9A), ("res", "3,d")),
            ((0xCB, 0x9B), ("res", "3,e")),
            ((0xCB, 0x9C), ("res", "3,h")),
            ((0xCB, 0x9D), ("res", "3,l")),
            ((0xCB, 0x9E), ("res", "3,(hl)")),
            ((0xCB, 0x9F), ("res", "3,a")),
            ((0xCB, 0xA0), ("res", "4,b")),
            ((0xCB, 0xA1), ("res", "4,c")),
            ((0xCB, 0xA2), ("res", "4,d")),
            ((0xCB, 0xA3), ("res", "4,e")),
            ((0xCB, 0xA4), ("res", "4,h")),
            ((0xCB, 0xA5), ("res", "4,l")),
            ((0xCB, 0xA6), ("res", "4,(hl)")),
            ((0xCB, 0xA7), ("res", "4,a")),
            ((0xCB, 0xA8), ("res", "5,b")),
            ((0xCB, 0xA9), ("res", "5,c")),
            ((0xCB, 0xAA), ("res", "5,d")),
            ((0xCB, 0xAB), ("res", "5,e")),
            ((0xCB, 0xAC), ("res", "5,h")),
            ((0xCB, 0xAD), ("res", "5,l")),
            ((0xCB, 0xAE), ("res", "5,(hl)")),
            ((0xCB, 0xAF), ("res", "5,a")),
            ((0xCB, 0xB0), ("res", "6,b")),
            ((0xCB, 0xB1), ("res", "6,c")),
            ((0xCB, 0xB2), ("res", "6,d")),
            ((0xCB, 0xB3), ("res", "6,e")),
            ((0xCB, 0xB4), ("res", "6,h")),
            ((0xCB, 0xB5), ("res", "6,l")),
            ((0xCB, 0xB6), ("res", "6,(hl)")),
            ((0xCB, 0xB7), ("res", "6,a")),
            ((0xCB, 0xB8), ("res", "7,b")),
            ((0xCB, 0xB9), ("res", "7,c")),
            ((0xCB, 0xBA), ("res", "7,d")),
            ((0xCB, 0xBB), ("res", "7,e")),
            ((0xCB, 0xBC), ("res", "7,h")),
            ((0xCB, 0xBD), ("res", "7,l")),
            ((0xCB, 0xBE), ("res", "7,(hl)")),
            ((0xCB, 0xBF), ("res", "7,a")),
            ((0xCB, 0xC0), ("set", "0,b")),
            ((0xCB, 0xC1), ("set", "0,c")),
            ((0xCB, 0xC2), ("set", "0,d")),
            ((0xCB, 0xC3), ("set", "0,e")),
            ((0xCB, 0xC4), ("set", "0,h")),
            ((0xCB, 0xC5), ("set", "0,l")),
            ((0xCB, 0xC6), ("set", "0,(hl)")),
            ((0xCB, 0xC7), ("set", "0,a")),
            ((0xCB, 0xC8), ("set", "1,b")),
            ((0xCB, 0xC9), ("set", "1,c")),
            ((0xCB, 0xCA), ("set", "1,d")),
            ((0xCB, 0xCB), ("set", "1,e")),
            ((0xCB, 0xCC), ("set", "1,h")),
            ((0xCB, 0xCD), ("set", "1,l")),
            ((0xCB, 0xCE), ("set", "1,(hl)")),
            ((0xCB, 0xCF), ("set", "1,a")),
            ((0xCB, 0xD0), ("set", "2,b")),
            ((0xCB, 0xD1), ("set", "2,c")),
            ((0xCB, 0xD2), ("set", "2,d")),
            ((0xCB, 0xD3), ("set", "2,e")),
            ((0xCB, 0xD4), ("set", "2,h")),
            ((0xCB, 0xD5), ("set", "2,l")),
            ((0xCB, 0xD6), ("set", "2,(hl)")),
            ((0xCB, 0xD7), ("set", "2,a")),
            ((0xCB, 0xD8), ("set", "3,b")),
            ((0xCB, 0xD9), ("set", "3,c")),
            ((0xCB, 0xDA), ("set", "3,d")),
            ((0xCB, 0xDB), ("set", "3,e")),
            ((0xCB, 0xDC), ("set", "3,h")),
            ((0xCB, 0xDD), ("set", "3,l")),
            ((0xCB, 0xDE), ("set", "3,(hl)")),
            ((0xCB, 0xDF), ("set", "3,a")),
            ((0xCB, 0xE0), ("set", "4,b")),
            ((0xCB, 0xE1), ("set", "4,c")),
            ((0xCB, 0xE2), ("set", "4,d")),
            ((0xCB, 0xE3), ("set", "4,e")),
            ((0xCB, 0xE4), ("set", "4,h")),
            ((0xCB, 0xE5), ("set", "4,l")),
            ((0xCB, 0xE6), ("set", "4,(hl)")),
            ((0xCB, 0xE7), ("set", "4,a")),
            ((0xCB, 0xE8), ("set", "5,b")),
            ((0xCB, 0xE9), ("set", "5,c")),
            ((0xCB, 0xEA), ("set", "5,d")),
            ((0xCB, 0xEB), ("set", "5,e")),
            ((0xCB, 0xEC), ("set", "5,h")),
            ((0xCB, 0xED), ("set", "5,l")),
            ((0xCB, 0xEE), ("set", "5,(hl)")),
            ((0xCB, 0xEF), ("set", "5,a")),
            ((0xCB, 0xF0), ("set", "6,b")),
            ((0xCB, 0xF1), ("set", "6,c")),
            ((0xCB, 0xF2), ("set", "6,d")),
            ((0xCB, 0xF3), ("set", "6,e")),
            ((0xCB, 0xF4), ("set", "6,h")),
            ((0xCB, 0xF5), ("set", "6,l")),
            ((0xCB, 0xF6), ("set", "6,(hl)")),
            ((0xCB, 0xF7), ("set", "6,a")),
            ((0xCB, 0xF8), ("set", "7,b")),
            ((0xCB, 0xF9), ("set", "7,c")),
            ((0xCB, 0xFA), ("set", "7,d")),
            ((0xCB, 0xFB), ("set", "7,e")),
            ((0xCB, 0xFC), ("set", "7,h")),
            ((0xCB, 0xFD), ("set", "7,l")),
            ((0xCB, 0xFE), ("set", "7,(hl)")),
            ((0xCB, 0xFF), ("set", "7,a")),
            ((0xCC, 0x00, 0x00), ("call", "z,0000")),
            ((0xCD, 0x00, 0x00), ("call", "0000")),
            ((0xCE, 0x00), ("adc", "a,00")),
            ((0xCF,), ("rst", "08")),
            ((0xD0,), ("ret", "nc")),
            ((0xD1,), ("pop", "de")),
            ((0xD2, 0x00, 0x00), ("jp", "nc,0000")),
            ((0xD3, 0x00), ("out", "(00),a")),
            ((0xD4, 0x00, 0x00), ("call", "nc,0000")),
            ((0xD5,), ("push", "de")),
            ((0xD6, 0x00), ("sub", "00")),
            ((0xD7,), ("rst", "10")),
            ((0xD8,), ("ret", "c")),
            ((0xD9,), ("exx", "")),
            ((0xDA, 0x00, 0x00), ("jp", "c,0000")),
            ((0xDB, 0x00), ("in", "a,(00)")),
            ((0xDC, 0x00, 0x00), ("call", "c,0000")),
            ((0xDD, 0x09), ("add", "ix,bc")),
            ((0xDD, 0x19), ("add", "ix,de")),
            ((0xDD, 0x21, 0x00, 0x00), ("ld", "ix,0000")),
            ((0xDD, 0x22, 0x00, 0x00), ("ld", "(0000),ix")),
            ((0xDD, 0x23), ("inc", "ix")),
            ((0xDD, 0x24), ("inc", "ixh")),
            ((0xDD, 0x25), ("dec", "ixh")),
            ((0xDD, 0x26, 0x00), ("ld", "ixh,00")),
            ((0xDD, 0x29), ("add", "ix,ix")),
            ((0xDD, 0x2A, 0x00, 0x00), ("ld", "ix,(0000)")),
            ((0xDD, 0x2B), ("dec", "ix")),
            ((0xDD, 0x2C), ("inc", "ixl")),
            ((0xDD, 0x2D), ("dec", "ixl")),
            ((0xDD, 0x2E, 0x00), ("ld", "ixl,00")),
            ((0xDD, 0x34, 0x00), ("inc", "(ix+00)")),
            ((0xDD, 0x35, 0x00), ("dec", "(ix+00)")),
            ((0xDD, 0x36, 0x00, 0x00), ("ld", "(ix+00),00")),
            ((0xDD, 0x39), ("add", "ix,sp")),
            ((0xDD, 0x44), ("ld", "b,ixh")),
            ((0xDD, 0x45), ("ld", "b,ixl")),
            ((0xDD, 0x46, 0x00), ("ld", "b,(ix+00)")),
            ((0xDD, 0x4C), ("ld", "c,ixh")),
            ((0xDD, 0x4D), ("ld", "c,ixl")),
            ((0xDD, 0x4E, 0x00), ("ld", "c,(ix+00)")),
            ((0xDD, 0x54), ("ld", "d,ixh")),
            ((0xDD, 0x55), ("ld", "d,ixl")),
            ((0xDD, 0x56, 0x00), ("ld", "d,(ix+00)")),
            ((0xDD, 0x5C), ("ld", "e,ixh")),
            ((0xDD, 0x5D), ("ld", "e,ixl")),
            ((0xDD, 0x5E, 0x00), ("ld", "e,(ix+00)")),
            ((0xDD, 0x60), ("ld", "ixh,b")),
            ((0xDD, 0x61), ("ld", "ixh,c")),
            ((0xDD, 0x62), ("ld", "ixh,d")),
            ((0xDD, 0x63), ("ld", "ixh,e")),
            ((0xDD, 0x64), ("ld", "ixh,ixh")),
            ((0xDD, 0x65), ("ld", "ixh,ixl")),
            ((0xDD, 0x66, 0x00), ("ld", "h,(ix+00)")),
            ((0xDD, 0x67), ("ld", "ixh,a")),
            ((0xDD, 0x68), ("ld", "ixl,b")),
            ((0xDD, 0x69), ("ld", "ixl,c")),
            ((0xDD, 0x6A), ("ld", "ixl,d")),
            ((0xDD, 0x6B), ("ld", "ixl,e")),
            ((0xDD, 0x6C), ("ld", "ixl,ixh")),
            ((0xDD, 0x6D), ("ld", "ixl,ixl")),
            ((0xDD, 0x6E, 0x00), ("ld", "l,(ix+00)")),
            ((0xDD, 0x6F), ("ld", "ixl,a")),
            ((0xDD, 0x70, 0x00), ("ld", "(ix+00),b")),
            ((0xDD, 0x71, 0x00), ("ld", "(ix+00),c")),
            ((0xDD, 0x72, 0x00), ("ld", "(ix+00),d")),
            ((0xDD, 0x73, 0x00), ("ld", "(ix+00),e")),
            ((0xDD, 0x74, 0x00), ("ld", "(ix+00),h")),
            ((0xDD, 0x75, 0x00), ("ld", "(ix+00),l")),
            ((0xDD, 0x77, 0x00), ("ld", "(ix+00),a")),
            ((0xDD, 0x7C), ("ld", "a,ixh")),
            ((0xDD, 0x7D), ("ld", "a,ixl")),
            ((0xDD, 0x7E, 0x00), ("ld", "a,(ix+00)")),
            ((0xDD, 0x84), ("add", "a,ixh")),
            ((0xDD, 0x85), ("add", "a,ixl")),
            ((0xDD, 0x86, 0x00), ("add", "a,(ix+00)")),
            ((0xDD, 0x8C), ("adc", "a,ixh")),
            ((0xDD, 0x8D), ("adc", "a,ixl")),
            ((0xDD, 0x8E, 0x00), ("adc", "a,(ix+00)")),
            ((0xDD, 0x94), ("sub", "ixh")),
            ((0xDD, 0x95), ("sub", "ixl")),
            ((0xDD, 0x96, 0x00), ("sub", "(ix+00)")),
            ((0xDD, 0x9C), ("sbc", "a,ixh")),
            ((0xDD, 0x9D), ("sbc", "a,ixl")),
            ((0xDD, 0x9E, 0x00), ("sbc", "a,(ix+00)")),
            ((0xDD, 0xA4), ("and", "ixh")),
            ((0xDD, 0xA5), ("and", "ixl")),
            ((0xDD, 0xA6, 0x00), ("and", "(ix+00)")),
            ((0xDD, 0xAC), ("xor", "ixh")),
            ((0xDD, 0xAD), ("xor", "ixl")),
            ((0xDD, 0xAE, 0x00), ("xor", "(ix+00)")),
            ((0xDD, 0xB4), ("or", "ixh")),
            ((0xDD, 0xB5), ("or", "ixl")),
            ((0xDD, 0xB6, 0x00), ("or", "(ix+00)")),
            ((0xDD, 0xBC), ("cp", "ixh")),
            ((0xDD, 0xBD), ("cp", "ixl")),
            ((0xDD, 0xBE, 0x00), ("cp", "(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x00), ("rlc", "(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0x01), ("rlc", "(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0x02), ("rlc", "(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0x03), ("rlc", "(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0x04), ("rlc", "(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0x05), ("rlc", "(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0x06), ("rlc", "(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x07), ("rlc", "(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0x08), ("rrc", "(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0x09), ("rrc", "(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0x0A), ("rrc", "(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0x0B), ("rrc", "(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0x0C), ("rrc", "(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0x0D), ("rrc", "(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0x0E), ("rrc", "(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x0F), ("rrc", "(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0x10), ("rl", "(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0x11), ("rl", "(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0x12), ("rl", "(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0x13), ("rl", "(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0x14), ("rl", "(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0x15), ("rl", "(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0x16), ("rl", "(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x17), ("rl", "(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0x18), ("rr", "(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0x19), ("rr", "(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0x1A), ("rr", "(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0x1B), ("rr", "(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0x1C), ("rr", "(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0x1D), ("rr", "(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0x1E), ("rr", "(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x1F), ("rr", "(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0x20), ("sla", "(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0x21), ("sla", "(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0x22), ("sla", "(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0x23), ("sla", "(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0x24), ("sla", "(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0x25), ("sla", "(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0x26), ("sla", "(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x27), ("sla", "(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0x28), ("sra", "(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0x29), ("sra", "(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0x2A), ("sra", "(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0x2B), ("sra", "(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0x2C), ("sra", "(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0x2D), ("sra", "(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0x2E), ("sra", "(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x2F), ("sra", "(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0x30), ("sll", "(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0x31), ("sll", "(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0x32), ("sll", "(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0x33), ("sll", "(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0x34), ("sll", "(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0x35), ("sll", "(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0x36), ("sll", "(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x37), ("sll", "(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0x38), ("srl", "(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0x39), ("srl", "(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0x3A), ("srl", "(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0x3B), ("srl", "(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0x3C), ("srl", "(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0x3D), ("srl", "(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0x3E), ("srl", "(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x3F), ("srl", "(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0x40), ("bit", "0,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x41), ("bit", "0,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x42), ("bit", "0,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x43), ("bit", "0,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x44), ("bit", "0,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x45), ("bit", "0,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x46), ("bit", "0,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x47), ("bit", "0,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x48), ("bit", "1,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x49), ("bit", "1,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x4A), ("bit", "1,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x4B), ("bit", "1,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x4C), ("bit", "1,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x4D), ("bit", "1,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x4E), ("bit", "1,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x4F), ("bit", "1,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x50), ("bit", "2,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x51), ("bit", "2,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x52), ("bit", "2,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x53), ("bit", "2,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x54), ("bit", "2,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x55), ("bit", "2,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x56), ("bit", "2,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x57), ("bit", "2,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x58), ("bit", "3,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x59), ("bit", "3,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x5A), ("bit", "3,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x5B), ("bit", "3,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x5C), ("bit", "3,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x5D), ("bit", "3,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x5E), ("bit", "3,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x5F), ("bit", "3,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x60), ("bit", "4,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x61), ("bit", "4,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x62), ("bit", "4,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x63), ("bit", "4,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x64), ("bit", "4,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x65), ("bit", "4,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x66), ("bit", "4,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x67), ("bit", "4,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x68), ("bit", "5,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x69), ("bit", "5,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x6A), ("bit", "5,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x6B), ("bit", "5,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x6C), ("bit", "5,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x6D), ("bit", "5,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x6E), ("bit", "5,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x6F), ("bit", "5,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x70), ("bit", "6,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x71), ("bit", "6,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x72), ("bit", "6,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x73), ("bit", "6,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x74), ("bit", "6,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x75), ("bit", "6,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x76), ("bit", "6,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x77), ("bit", "6,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x78), ("bit", "7,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x79), ("bit", "7,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x7A), ("bit", "7,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x7B), ("bit", "7,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x7C), ("bit", "7,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x7D), ("bit", "7,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x7E), ("bit", "7,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x7F), ("bit", "7,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x80), ("res", "0,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0x81), ("res", "0,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0x82), ("res", "0,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0x83), ("res", "0,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0x84), ("res", "0,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0x85), ("res", "0,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0x86), ("res", "0,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x87), ("res", "0,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0x88), ("res", "1,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0x89), ("res", "1,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0x8A), ("res", "1,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0x8B), ("res", "1,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0x8C), ("res", "1,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0x8D), ("res", "1,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0x8E), ("res", "1,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x8F), ("res", "1,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0x90), ("res", "2,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0x91), ("res", "2,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0x92), ("res", "2,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0x93), ("res", "2,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0x94), ("res", "2,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0x95), ("res", "2,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0x96), ("res", "2,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x97), ("res", "2,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0x98), ("res", "3,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0x99), ("res", "3,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0x9A), ("res", "3,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0x9B), ("res", "3,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0x9C), ("res", "3,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0x9D), ("res", "3,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0x9E), ("res", "3,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0x9F), ("res", "3,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0xA0), ("res", "4,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0xA1), ("res", "4,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0xA2), ("res", "4,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0xA3), ("res", "4,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0xA4), ("res", "4,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0xA5), ("res", "4,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0xA6), ("res", "4,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0xA7), ("res", "4,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0xA8), ("res", "5,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0xA9), ("res", "5,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0xAA), ("res", "5,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0xAB), ("res", "5,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0xAC), ("res", "5,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0xAD), ("res", "5,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0xAE), ("res", "5,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0xAF), ("res", "5,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0xB0), ("res", "6,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0xB1), ("res", "6,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0xB2), ("res", "6,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0xB3), ("res", "6,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0xB4), ("res", "6,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0xB5), ("res", "6,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0xB6), ("res", "6,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0xB7), ("res", "6,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0xB8), ("res", "7,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0xB9), ("res", "7,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0xBA), ("res", "7,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0xBB), ("res", "7,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0xBC), ("res", "7,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0xBD), ("res", "7,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0xBE), ("res", "7,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0xBF), ("res", "7,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0xC0), ("set", "0,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0xC1), ("set", "0,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0xC2), ("set", "0,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0xC3), ("set", "0,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0xC4), ("set", "0,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0xC5), ("set", "0,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0xC6), ("set", "0,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0xC7), ("set", "0,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0xC8), ("set", "1,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0xC9), ("set", "1,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0xCA), ("set", "1,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0xCB), ("set", "1,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0xCC), ("set", "1,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0xCD), ("set", "1,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0xCE), ("set", "1,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0xCF), ("set", "1,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0xD0), ("set", "2,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0xD1), ("set", "2,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0xD2), ("set", "2,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0xD3), ("set", "2,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0xD4), ("set", "2,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0xD5), ("set", "2,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0xD6), ("set", "2,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0xD7), ("set", "2,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0xD8), ("set", "3,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0xD9), ("set", "3,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0xDA), ("set", "3,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0xDB), ("set", "3,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0xDC), ("set", "3,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0xDD), ("set", "3,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0xDE), ("set", "3,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0xDF), ("set", "3,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0xE0), ("set", "4,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0xE1), ("set", "4,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0xE2), ("set", "4,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0xE3), ("set", "4,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0xE4), ("set", "4,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0xE5), ("set", "4,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0xE6), ("set", "4,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0xE7), ("set", "4,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0xE8), ("set", "5,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0xE9), ("set", "5,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0xEA), ("set", "5,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0xEB), ("set", "5,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0xEC), ("set", "5,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0xED), ("set", "5,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0xEE), ("set", "5,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0xEF), ("set", "5,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0xF0), ("set", "6,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0xF1), ("set", "6,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0xF2), ("set", "6,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0xF3), ("set", "6,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0xF4), ("set", "6,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0xF5), ("set", "6,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0xF6), ("set", "6,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0xF7), ("set", "6,(ix+00),a")),
            ((0xDD, 0xCB, 0x00, 0xF8), ("set", "7,(ix+00),b")),
            ((0xDD, 0xCB, 0x00, 0xF9), ("set", "7,(ix+00),c")),
            ((0xDD, 0xCB, 0x00, 0xFA), ("set", "7,(ix+00),d")),
            ((0xDD, 0xCB, 0x00, 0xFB), ("set", "7,(ix+00),e")),
            ((0xDD, 0xCB, 0x00, 0xFC), ("set", "7,(ix+00),h")),
            ((0xDD, 0xCB, 0x00, 0xFD), ("set", "7,(ix+00),l")),
            ((0xDD, 0xCB, 0x00, 0xFE), ("set", "7,(ix+00)")),
            ((0xDD, 0xCB, 0x00, 0xFF), ("set", "7,(ix+00),a")),
            ((0xDD, 0xE1), ("pop", "ix")),
            ((0xDD, 0xE3), ("ex", "(sp),ix")),
            ((0xDD, 0xE5), ("push", "ix")),
            ((0xDD, 0xE9), ("jp", "ix")),
            ((0xDD, 0xF9), ("ld", "sp,ix")),
            ((0xDE, 0x00), ("sbc", "a,00")),
            ((0xDF,), ("rst", "18")),
            ((0xE0,), ("ret", "po")),
            ((0xE1,), ("pop", "hl")),
            ((0xE2, 0x00, 0x00), ("jp", "po,0000")),
            ((0xE3,), ("ex", "(sp),hl")),
            ((0xE4, 0x00, 0x00), ("call", "po,0000")),
            ((0xE5,), ("push", "hl")),
            ((0xE6, 0x00), ("and", "00")),
            ((0xE7,), ("rst", "20")),
            ((0xE8,), ("ret", "pe")),
            ((0xE9,), ("jp", "hl")),
            ((0xEA, 0x00, 0x00), ("jp", "pe,0000")),
            ((0xEB,), ("ex", "de,hl")),
            ((0xEC, 0x00, 0x00), ("call", "pe,0000")),
            ((0xED, 0x40), ("in", "b,(c)")),
            ((0xED, 0x41), ("out", "(c),b")),
            ((0xED, 0x42), ("sbc", "hl,bc")),
            ((0xED, 0x43, 0x00, 0x00), ("ld", "(0000),bc")),
            ((0xED, 0x44), ("neg", "")),
            ((0xED, 0x45), ("retn", "")),
            ((0xED, 0x46), ("im", "0")),
            ((0xED, 0x47), ("ld", "i,a")),
            ((0xED, 0x48), ("in", "c,(c)")),
            ((0xED, 0x49), ("out", "(c),c")),
            ((0xED, 0x4A), ("adc", "hl,bc")),
            ((0xED, 0x4B, 0x00, 0x00), ("ld", "bc,(0000)")),
            ((0xED, 0x4C), ("neg", "")),
            ((0xED, 0x4D), ("reti", "")),
            ((0xED, 0x4E), ("im", "0")),
            ((0xED, 0x4F), ("ld", "r,a")),
            ((0xED, 0x50), ("in", "d,(c)")),
            ((0xED, 0x51), ("out", "(c),d")),
            ((0xED, 0x52), ("sbc", "hl,de")),
            ((0xED, 0x53, 0x00, 0x00), ("ld", "(0000),de")),
            ((0xED, 0x54), ("neg", "")),
            ((0xED, 0x55), ("retn", "")),
            ((0xED, 0x56), ("im", "1")),
            ((0xED, 0x57), ("ld", "a,i")),
            ((0xED, 0x58), ("in", "e,(c)")),
            ((0xED, 0x59), ("out", "(c),e")),
            ((0xED, 0x5A), ("adc", "hl,de")),
            ((0xED, 0x5B, 0x00, 0x00), ("ld", "de,(0000)")),
            ((0xED, 0x5C), ("neg", "")),
            ((0xED, 0x5D), ("retn", "")),
            ((0xED, 0x5E), ("im", "2")),
            ((0xED, 0x5F), ("ld", "a,r")),
            ((0xED, 0x60), ("in", "h,(c)")),
            ((0xED, 0x61), ("out", "(c),h")),
            ((0xED, 0x62), ("sbc", "hl,hl")),
            ((0xED, 0x63, 0x00, 0x00), ("ld", "(0000),hl")),
            ((0xED, 0x64), ("neg", "")),
            ((0xED, 0x65), ("retn", "")),
            ((0xED, 0x66), ("im", "0")),
            ((0xED, 0x67), ("rrd", "")),
            ((0xED, 0x68), ("in", "l,(c)")),
            ((0xED, 0x69), ("out", "(c),l")),
            ((0xED, 0x6A), ("adc", "hl,hl")),
            ((0xED, 0x6B, 0x00, 0x00), ("ld", "hl,(0000)")),
            ((0xED, 0x6C), ("neg", "")),
            ((0xED, 0x6D), ("retn", "")),
            ((0xED, 0x6E), ("im", "0")),
            ((0xED, 0x6F), ("rld", "")),
            ((0xED, 0x70), ("in", "(c)")),
            ((0xED, 0x71), ("out", "(c)")),
            ((0xED, 0x72), ("sbc", "hl,sp")),
            ((0xED, 0x73, 0x00, 0x00), ("ld", "(0000),sp")),
            ((0xED, 0x74), ("neg", "")),
            ((0xED, 0x75), ("retn", "")),
            ((0xED, 0x76), ("im", "1")),
            ((0xED, 0x78), ("in", "a,(c)")),
            ((0xED, 0x79), ("out", "(c),a")),
            ((0xED, 0x7A), ("adc", "hl,sp")),
            ((0xED, 0x7B, 0x00, 0x00), ("ld", "sp,(0000)")),
            ((0xED, 0x7C), ("neg", "")),
            ((0xED, 0x7D), ("retn", "")),
            ((0xED, 0x7E), ("im", "2")),
            ((0xED, 0xA0), ("ldi", "")),
            ((0xED, 0xA1), ("cpi", "")),
            ((0xED, 0xA2), ("ini", "")),
            ((0xED, 0xA3), ("outi", "")),
            ((0xED, 0xA8), ("ldd", "")),
            ((0xED, 0xA9), ("cpd", "")),
            ((0xED, 0xAA), ("ind", "")),
            ((0xED, 0xAB), ("outd", "")),
            ((0xED, 0xB0), ("ldir", "")),
            ((0xED, 0xB1), ("cpir", "")),
            ((0xED, 0xB2), ("inir", "")),
            ((0xED, 0xB3), ("otir", "")),
            ((0xED, 0xB8), ("lddr", "")),
            ((0xED, 0xB9), ("cpdr", "")),
            ((0xED, 0xBA), ("indr", "")),
            ((0xED, 0xBB), ("otdr", "")),
            ((0xEE, 0x00), ("xor", "00")),
            ((0xEF,), ("rst", "28")),
            ((0xF0,), ("ret", "p")),
            ((0xF1,), ("pop", "af")),
            ((0xF2, 0x00, 0x00), ("jp", "p,0000")),
            ((0xF3,), ("di", "")),
            ((0xF4, 0x00, 0x00), ("call", "p,0000")),
            ((0xF5,), ("push", "af")),
            ((0xF6, 0x00), ("or", "00")),
            ((0xF7,), ("rst", "30")),
            ((0xF8,), ("ret", "m")),
            ((0xF9,), ("ld", "sp,hl")),
            ((0xFA, 0x00, 0x00), ("jp", "m,0000")),
            ((0xFB,), ("ei", "")),
            ((0xFC, 0x00, 0x00), ("call", "m,0000")),
            ((0xFD, 0x09), ("add", "iy,bc")),
            ((0xFD, 0x19), ("add", "iy,de")),
            ((0xFD, 0x21, 0x00, 0x00), ("ld", "iy,0000")),
            ((0xFD, 0x22, 0x00, 0x00), ("ld", "(0000),iy")),
            ((0xFD, 0x23), ("inc", "iy")),
            ((0xFD, 0x24), ("inc", "iyh")),
            ((0xFD, 0x25), ("dec", "iyh")),
            ((0xFD, 0x26, 0x00), ("ld", "iyh,00")),
            ((0xFD, 0x29), ("add", "iy,iy")),
            ((0xFD, 0x2A, 0x00, 0x00), ("ld", "iy,(0000)")),
            ((0xFD, 0x2B), ("dec", "iy")),
            ((0xFD, 0x2C), ("inc", "iyl")),
            ((0xFD, 0x2D), ("dec", "iyl")),
            ((0xFD, 0x2E, 0x00), ("ld", "iyl,00")),
            ((0xFD, 0x34, 0x00), ("inc", "(iy+00)")),
            ((0xFD, 0x35, 0x00), ("dec", "(iy+00)")),
            ((0xFD, 0x36, 0x00, 0x00), ("ld", "(iy+00),00")),
            ((0xFD, 0x39), ("add", "iy,sp")),
            ((0xFD, 0x44), ("ld", "b,iyh")),
            ((0xFD, 0x45), ("ld", "b,iyl")),
            ((0xFD, 0x46, 0x00), ("ld", "b,(iy+00)")),
            ((0xFD, 0x4C), ("ld", "c,iyh")),
            ((0xFD, 0x4D), ("ld", "c,iyl")),
            ((0xFD, 0x4E, 0x00), ("ld", "c,(iy+00)")),
            ((0xFD, 0x54), ("ld", "d,iyh")),
            ((0xFD, 0x55), ("ld", "d,iyl")),
            ((0xFD, 0x56, 0x00), ("ld", "d,(iy+00)")),
            ((0xFD, 0x5C), ("ld", "e,iyh")),
            ((0xFD, 0x5D), ("ld", "e,iyl")),
            ((0xFD, 0x5E, 0x00), ("ld", "e,(iy+00)")),
            ((0xFD, 0x60), ("ld", "iyh,b")),
            ((0xFD, 0x61), ("ld", "iyh,c")),
            ((0xFD, 0x62), ("ld", "iyh,d")),
            ((0xFD, 0x63), ("ld", "iyh,e")),
            ((0xFD, 0x64), ("ld", "iyh,iyh")),
            ((0xFD, 0x65), ("ld", "iyh,iyl")),
            ((0xFD, 0x66, 0x00), ("ld", "h,(iy+00)")),
            ((0xFD, 0x67), ("ld", "iyh,a")),
            ((0xFD, 0x68), ("ld", "iyl,b")),
            ((0xFD, 0x69), ("ld", "iyl,c")),
            ((0xFD, 0x6A), ("ld", "iyl,d")),
            ((0xFD, 0x6B), ("ld", "iyl,e")),
            ((0xFD, 0x6C), ("ld", "iyl,iyh")),
            ((0xFD, 0x6D), ("ld", "iyl,iyl")),
            ((0xFD, 0x6E, 0x00), ("ld", "l,(iy+00)")),
            ((0xFD, 0x6F), ("ld", "iyl,a")),
            ((0xFD, 0x70, 0x00), ("ld", "(iy+00),b")),
            ((0xFD, 0x71, 0x00), ("ld", "(iy+00),c")),
            ((0xFD, 0x72, 0x00), ("ld", "(iy+00),d")),
            ((0xFD, 0x73, 0x00), ("ld", "(iy+00),e")),
            ((0xFD, 0x74, 0x00), ("ld", "(iy+00),h")),
            ((0xFD, 0x75, 0x00), ("ld", "(iy+00),l")),
            ((0xFD, 0x77, 0x00), ("ld", "(iy+00),a")),
            ((0xFD, 0x7C), ("ld", "a,iyh")),
            ((0xFD, 0x7D), ("ld", "a,iyl")),
            ((0xFD, 0x7E, 0x00), ("ld", "a,(iy+00)")),
            ((0xFD, 0x84), ("add", "a,iyh")),
            ((0xFD, 0x85), ("add", "a,iyl")),
            ((0xFD, 0x86, 0x00), ("add", "a,(iy+00)")),
            ((0xFD, 0x8C), ("adc", "a,iyh")),
            ((0xFD, 0x8D), ("adc", "a,iyl")),
            ((0xFD, 0x8E, 0x00), ("adc", "a,(iy+00)")),
            ((0xFD, 0x94), ("sub", "iyh")),
            ((0xFD, 0x95), ("sub", "iyl")),
            ((0xFD, 0x96, 0x00), ("sub", "(iy+00)")),
            ((0xFD, 0x9C), ("sbc", "a,iyh")),
            ((0xFD, 0x9D), ("sbc", "a,iyl")),
            ((0xFD, 0x9E, 0x00), ("sbc", "a,(iy+00)")),
            ((0xFD, 0xA4), ("and", "iyh")),
            ((0xFD, 0xA5), ("and", "iyl")),
            ((0xFD, 0xA6, 0x00), ("and", "(iy+00)")),
            ((0xFD, 0xAC), ("xor", "iyh")),
            ((0xFD, 0xAD), ("xor", "iyl")),
            ((0xFD, 0xAE, 0x00), ("xor", "(iy+00)")),
            ((0xFD, 0xB4), ("or", "iyh")),
            ((0xFD, 0xB5), ("or", "iyl")),
            ((0xFD, 0xB6, 0x00), ("or", "(iy+00)")),
            ((0xFD, 0xBC), ("cp", "iyh")),
            ((0xFD, 0xBD), ("cp", "iyl")),
            ((0xFD, 0xBE, 0x00), ("cp", "(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x00), ("rlc", "(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0x01), ("rlc", "(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0x02), ("rlc", "(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0x03), ("rlc", "(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0x04), ("rlc", "(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0x05), ("rlc", "(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0x06), ("rlc", "(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x07), ("rlc", "(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0x08), ("rrc", "(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0x09), ("rrc", "(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0x0A), ("rrc", "(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0x0B), ("rrc", "(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0x0C), ("rrc", "(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0x0D), ("rrc", "(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0x0E), ("rrc", "(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x0F), ("rrc", "(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0x10), ("rl", "(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0x11), ("rl", "(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0x12), ("rl", "(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0x13), ("rl", "(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0x14), ("rl", "(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0x15), ("rl", "(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0x16), ("rl", "(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x17), ("rl", "(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0x18), ("rr", "(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0x19), ("rr", "(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0x1A), ("rr", "(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0x1B), ("rr", "(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0x1C), ("rr", "(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0x1D), ("rr", "(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0x1E), ("rr", "(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x1F), ("rr", "(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0x20), ("sla", "(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0x21), ("sla", "(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0x22), ("sla", "(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0x23), ("sla", "(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0x24), ("sla", "(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0x25), ("sla", "(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0x26), ("sla", "(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x27), ("sla", "(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0x28), ("sra", "(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0x29), ("sra", "(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0x2A), ("sra", "(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0x2B), ("sra", "(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0x2C), ("sra", "(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0x2D), ("sra", "(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0x2E), ("sra", "(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x2F), ("sra", "(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0x30), ("sll", "(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0x31), ("sll", "(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0x32), ("sll", "(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0x33), ("sll", "(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0x34), ("sll", "(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0x35), ("sll", "(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0x36), ("sll", "(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x37), ("sll", "(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0x38), ("srl", "(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0x39), ("srl", "(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0x3A), ("srl", "(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0x3B), ("srl", "(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0x3C), ("srl", "(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0x3D), ("srl", "(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0x3E), ("srl", "(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x3F), ("srl", "(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0x40), ("bit", "0,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x41), ("bit", "0,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x42), ("bit", "0,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x43), ("bit", "0,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x44), ("bit", "0,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x45), ("bit", "0,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x46), ("bit", "0,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x47), ("bit", "0,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x48), ("bit", "1,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x49), ("bit", "1,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x4A), ("bit", "1,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x4B), ("bit", "1,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x4C), ("bit", "1,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x4D), ("bit", "1,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x4E), ("bit", "1,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x4F), ("bit", "1,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x50), ("bit", "2,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x51), ("bit", "2,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x52), ("bit", "2,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x53), ("bit", "2,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x54), ("bit", "2,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x55), ("bit", "2,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x56), ("bit", "2,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x57), ("bit", "2,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x58), ("bit", "3,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x59), ("bit", "3,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x5A), ("bit", "3,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x5B), ("bit", "3,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x5C), ("bit", "3,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x5D), ("bit", "3,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x5E), ("bit", "3,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x5F), ("bit", "3,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x60), ("bit", "4,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x61), ("bit", "4,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x62), ("bit", "4,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x63), ("bit", "4,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x64), ("bit", "4,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x65), ("bit", "4,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x66), ("bit", "4,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x67), ("bit", "4,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x68), ("bit", "5,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x69), ("bit", "5,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x6A), ("bit", "5,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x6B), ("bit", "5,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x6C), ("bit", "5,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x6D), ("bit", "5,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x6E), ("bit", "5,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x6F), ("bit", "5,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x70), ("bit", "6,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x71), ("bit", "6,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x72), ("bit", "6,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x73), ("bit", "6,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x74), ("bit", "6,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x75), ("bit", "6,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x76), ("bit", "6,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x77), ("bit", "6,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x78), ("bit", "7,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x79), ("bit", "7,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x7A), ("bit", "7,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x7B), ("bit", "7,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x7C), ("bit", "7,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x7D), ("bit", "7,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x7E), ("bit", "7,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x7F), ("bit", "7,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x80), ("res", "0,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0x81), ("res", "0,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0x82), ("res", "0,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0x83), ("res", "0,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0x84), ("res", "0,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0x85), ("res", "0,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0x86), ("res", "0,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x87), ("res", "0,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0x88), ("res", "1,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0x89), ("res", "1,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0x8A), ("res", "1,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0x8B), ("res", "1,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0x8C), ("res", "1,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0x8D), ("res", "1,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0x8E), ("res", "1,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x8F), ("res", "1,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0x90), ("res", "2,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0x91), ("res", "2,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0x92), ("res", "2,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0x93), ("res", "2,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0x94), ("res", "2,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0x95), ("res", "2,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0x96), ("res", "2,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x97), ("res", "2,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0x98), ("res", "3,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0x99), ("res", "3,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0x9A), ("res", "3,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0x9B), ("res", "3,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0x9C), ("res", "3,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0x9D), ("res", "3,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0x9E), ("res", "3,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0x9F), ("res", "3,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0xA0), ("res", "4,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0xA1), ("res", "4,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0xA2), ("res", "4,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0xA3), ("res", "4,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0xA4), ("res", "4,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0xA5), ("res", "4,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0xA6), ("res", "4,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0xA7), ("res", "4,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0xA8), ("res", "5,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0xA9), ("res", "5,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0xAA), ("res", "5,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0xAB), ("res", "5,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0xAC), ("res", "5,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0xAD), ("res", "5,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0xAE), ("res", "5,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0xAF), ("res", "5,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0xB0), ("res", "6,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0xB1), ("res", "6,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0xB2), ("res", "6,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0xB3), ("res", "6,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0xB4), ("res", "6,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0xB5), ("res", "6,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0xB6), ("res", "6,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0xB7), ("res", "6,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0xB8), ("res", "7,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0xB9), ("res", "7,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0xBA), ("res", "7,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0xBB), ("res", "7,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0xBC), ("res", "7,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0xBD), ("res", "7,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0xBE), ("res", "7,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0xBF), ("res", "7,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0xC0), ("set", "0,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0xC1), ("set", "0,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0xC2), ("set", "0,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0xC3), ("set", "0,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0xC4), ("set", "0,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0xC5), ("set", "0,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0xC6), ("set", "0,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0xC7), ("set", "0,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0xC8), ("set", "1,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0xC9), ("set", "1,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0xCA), ("set", "1,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0xCB), ("set", "1,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0xCC), ("set", "1,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0xCD), ("set", "1,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0xCE), ("set", "1,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0xCF), ("set", "1,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0xD0), ("set", "2,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0xD1), ("set", "2,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0xD2), ("set", "2,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0xD3), ("set", "2,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0xD4), ("set", "2,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0xD5), ("set", "2,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0xD6), ("set", "2,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0xD7), ("set", "2,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0xD8), ("set", "3,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0xD9), ("set", "3,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0xDA), ("set", "3,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0xDB), ("set", "3,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0xDC), ("set", "3,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0xDD), ("set", "3,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0xDE), ("set", "3,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0xDF), ("set", "3,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0xE0), ("set", "4,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0xE1), ("set", "4,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0xE2), ("set", "4,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0xE3), ("set", "4,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0xE4), ("set", "4,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0xE5), ("set", "4,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0xE6), ("set", "4,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0xE7), ("set", "4,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0xE8), ("set", "5,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0xE9), ("set", "5,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0xEA), ("set", "5,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0xEB), ("set", "5,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0xEC), ("set", "5,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0xED), ("set", "5,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0xEE), ("set", "5,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0xEF), ("set", "5,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0xF0), ("set", "6,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0xF1), ("set", "6,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0xF2), ("set", "6,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0xF3), ("set", "6,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0xF4), ("set", "6,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0xF5), ("set", "6,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0xF6), ("set", "6,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0xF7), ("set", "6,(iy+00),a")),
            ((0xFD, 0xCB, 0x00, 0xF8), ("set", "7,(iy+00),b")),
            ((0xFD, 0xCB, 0x00, 0xF9), ("set", "7,(iy+00),c")),
            ((0xFD, 0xCB, 0x00, 0xFA), ("set", "7,(iy+00),d")),
            ((0xFD, 0xCB, 0x00, 0xFB), ("set", "7,(iy+00),e")),
            ((0xFD, 0xCB, 0x00, 0xFC), ("set", "7,(iy+00),h")),
            ((0xFD, 0xCB, 0x00, 0xFD), ("set", "7,(iy+00),l")),
            ((0xFD, 0xCB, 0x00, 0xFE), ("set", "7,(iy+00)")),
            ((0xFD, 0xCB, 0x00, 0xFF), ("set", "7,(iy+00),a")),
            ((0xFD, 0xE1), ("pop", "iy")),
            ((0xFD, 0xE3), ("ex", "(sp),iy")),
            ((0xFD, 0xE5), ("push", "iy")),
            ((0xFD, 0xE9), ("jp", "iy")),
            ((0xFD, 0xF9), ("ld", "sp,iy")),
            ((0xFE, 0x00), ("cp", "00")),
            ((0xFF,), ("rst", "38")),
        )
        mem = memory.ram(8)
        for data, decode in tests:
            mem.load(0, data)
            if len(decode) != 3:
                decode = list(decode)
                decode.append(len(data))
                decode = tuple(decode)
            self.assertEqual(disassemble(mem, 0), decode)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()

# -----------------------------------------------------------------------------
