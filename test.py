#-----------------------------------------------------------------------------

import unittest

#-----------------------------------------------------------------------------

import memory
import jace
import z80da
import z80

#-----------------------------------------------------------------------------

class memory_testing(unittest.TestCase):

    def test_rom(self):
        val = 0xab
        rom = memory.rom(13)
        self.assertEqual(rom[0], 0)
        rom[0] = val
        self.assertEqual(rom[0], 0)
        rom.load(2, (7,8,9,10))
        self.assertEqual(rom[2], 7)
        self.assertEqual(rom[3], 8)
        self.assertEqual(rom[4], 9)
        self.assertEqual(rom[5], 10)
        rom[2] = val
        self.assertEqual(rom[2], 7)
        rom.load_file(0, './roms/ace.rom')
        self.assertEqual(rom[0], 0xf3)
        self.assertEqual(rom[1], 0x21)
        self.assertEqual(rom[8190], 0x1d)
        self.assertEqual(rom[8191], 0x00)

    def test_ram(self):
        bits = 10
        size = 1 << bits
        val = 0xab
        ram = memory.ram(bits)
        self.assertEqual(ram[0], 0)
        ram[0] = val
        self.assertEqual(ram[0], val)
        self.assertEqual(ram[0 + size], val)
        self.assertEqual(ram[10], 0)
        ram[10] = val
        self.assertEqual(ram[10 + size], val)

    def test_wom(self):
        bits = 10
        size = 1 << bits
        val = 0xab
        wom = memory.wom(bits)
        self.assertEqual(wom[0], memory._empty)
        self.assertEqual(wom.rd(0), 0)
        wom[0] = val
        self.assertEqual(wom[0], memory._empty)
        self.assertEqual(wom.rd(0), val)
        wom[10] = val
        self.assertEqual(wom[10 + size], memory._empty)
        self.assertEqual(wom.rd(10 + size), val)

    def test_null(self):
        null = memory.null()
        self.assertEqual(null[0], memory._empty)
        self.assertEqual(null[10], memory._empty)
        null[20] = 0xff
        self.assertEqual(null[20], memory._empty)

#-----------------------------------------------------------------------------

class jace_memmap_testing(unittest.TestCase):

    def test_memmap(self):
        val = 0xaa
        mem = jace.memmap('./roms/ace.rom')
        # rom testing
        self.assertEqual(mem[0x0000], 0xf3)
        self.assertEqual(mem[0x0001], 0x21)
        self.assertEqual(mem[0x1ffe], 0x1d)
        self.assertEqual(mem[0x1fff], 0x00)
        mem[0x1fff] = val
        self.assertEqual(mem[0x1fff], 0x00)
        # video ram testing
        self.assertEqual(mem[0x2000], 0x00)
        mem[0x2000] = val
        self.assertEqual(mem[0x2000], val)
        self.assertEqual(mem[0x2400], val)
        # character wom testing
        self.assertEqual(mem[0x2800], memory._empty)
        mem[0x2800] = val
        self.assertEqual(mem[0x2800], memory._empty)
        self.assertEqual(mem.select(0x2800).rd(0x2800), val)
        self.assertEqual(mem[0x2C00], memory._empty)
        self.assertEqual(mem.select(0x2C00).rd(0x2C00), val)
        # ram testing
        self.assertEqual(mem[0x3000], 0x00)
        mem[0x3000] = val
        self.assertEqual(mem[0x3000], val)
        self.assertEqual(mem[0x3400], val)
        self.assertEqual(mem[0x3800], val)
        self.assertEqual(mem[0x3c00], val)
        # empty testing
        self.assertEqual(mem[0xf800], memory._empty)
        mem[0xf800] = val
        self.assertEqual(mem[0xf800], memory._empty)

#-----------------------------------------------------------------------------

class z80_regs_test(unittest.TestCase):

    def test_regs(self):
        mem = memory.ram(4)
        cpu = z80.cpu(mem, None)
        cpu.set_af(0x0123)
        cpu.set_bc(0x4567)
        cpu.set_de(0x89ab)
        cpu.set_hl(0xcdef)
        self.assertEqual(cpu.a, 0x01)
        self.assertEqual(cpu.f.get(), 0x23)
        self.assertEqual(cpu.b, 0x45)
        self.assertEqual(cpu.c, 0x67)
        self.assertEqual(cpu.d, 0x89)
        self.assertEqual(cpu.e, 0xab)
        self.assertEqual(cpu.h, 0xcd)
        self.assertEqual(cpu.l, 0xef)



#-----------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()

#-----------------------------------------------------------------------------
