#-----------------------------------------------------------------------------
"""
Jupiter ACE Emulator
"""
#-----------------------------------------------------------------------------

import memory
import z80da
import z80
import monitor
import util
import pygame
from pygame.locals import *

#-----------------------------------------------------------------------------

_CHAR_NUM = 256
_CHAR_MASK = 0x7f
_CHAR_ADR = 0x2800
_COLS = 32
_ROWS = 24
_PIXELS_H = _COLS * 8
_PIXELS_V = _ROWS * 8
_VIDEO_SIZE = _COLS * _ROWS

_bgnd = (0, 0, 0)
_fgnd = (0xf9, 0xf9, 0xf9)
_border = (0xf9, 0xf9, 0xf9)

_border_x = 20
_border_y = 20

_scale = 2

_keyboard_h = 242
_keyboard_y = (_scale * _PIXELS_V) + (2 * _border_y)

_screen_x = (_scale * _PIXELS_H) + (2 * _border_x)
_screen_y = (_scale * _PIXELS_V) + (2 * _border_y) + _keyboard_h

#-----------------------------------------------------------------------------

class video:
    """video emulation"""

    def __init__(self):
        self.dirty = []
        self.char_cache = [None] * _CHAR_NUM
        self.mem = None
        self.cmem = None

    def adr2xy(self, adr):
        """given a video address return an (x,y) screen pixel position"""
        return (((adr & 0x1f) << 4) + _border_x, ((adr & 0x3e0) >> 1) + _border_y)

    def set_pixel(self, bmp, x, y, color):
        bmp.set_at(((x << 1), (y << 1)), color)
        bmp.set_at(((x << 1) + 1, (y << 1)), color)
        bmp.set_at(((x << 1), (y << 1) + 1), color)
        bmp.set_at(((x << 1) + 1, (y << 1) + 1), color)

    def c2bmp(self, c):
        """create the bitmap surface for a given character"""
        inv = bool(c & 0x80)
        cadr = (c & 0x7f) << 3
        bmp = pygame.Surface((16,16))
        for y in range(8):
            pixels = self.cmem(cadr + y)
            for x in range(8):
                if pixels & 0x80:
                    self.set_pixel(bmp, x, y, (_fgnd, _bgnd)[inv])
                else:
                    self.set_pixel(bmp, x, y, (_bgnd, _fgnd)[inv])
                pixels <<= 1
        bmp = bmp.convert()
        return bmp

    def update(self, screen):
        """update the video display"""
        if self.dirty:
            #print len(self.dirty)
            for adr in self.dirty:
                char = self.mem[adr]
                bmp = self.char_cache[char]
                if bmp == None:
                    bmp = self.c2bmp(char)
                    self.char_cache[char] = bmp
                screen.blit(bmp, self.adr2xy(adr))
            self.dirty = []
            pygame.display.flip()

    def refresh(self, screen):
        """refresh the whole display"""
        bg = pygame.Surface(screen.get_size())
        bg = bg.convert()
        bg.fill(_border)
        screen.blit(bg, (0, 0))
        kb = pygame.image.load('./graphics/keyboard.png')
        kb = kb.convert()
        screen.blit(kb, (0, _keyboard_y))
        pygame.display.flip()

    def char_wr(self, adr):
        """the cpu has written to character memory"""
        # invalidate the character cache entries for this address
        c = (adr >> 3) & _CHAR_MASK
        self.char_cache[c] = None
        self.char_cache[0x80 | c] = None

    def video_wr(self, adr):
        """the cpu has written to video memory"""
        # add the address to the dirty list
        if (adr & 0x3ff) < _VIDEO_SIZE:
            self.dirty.append(adr)

#-----------------------------------------------------------------------------
#;                          LOGICAL VIEW OF KEYBOARD
#;
#;         0     1     2     3     4 -Bits-  4     3     2     1     0
#; PORT                                                                    PORT
#;
#; F7FE  [ 1 ] [ 2 ] [ 3 ] [ 4 ] [ 5 ]  |  [ 6 ] [ 7 ] [ 8 ] [ 9 ] [ 0 ]   EFFE
#;  ^                                   |                                   v
#; FBFE  [ Q ] [ W ] [ E ] [ R ] [ T ]  |  [ Y ] [ U ] [ I ] [ O ] [ P ]   DFFE
#;  ^                                   |                                   v
#; FDFE  [ A ] [ S ] [ D ] [ F ] [ G ]  |  [ H ] [ J ] [ K ] [ L ] [ ENT ] BFFE
#;  ^                                   |                                   v
#; FEFE  [SHI] [SYM] [ Z ] [ X ] [ C ]  |  [ V ] [ B ] [ N ] [ M ] [ SPC ] 7FFE
#;  ^            v                                                ^         v
#; Start         +------------>--------------------->-------------+        End
#;

class keyboard:
    """keyboard emulation"""

    def __init__(self):
        self.ports = {
            0xfefe : 0xff,
            0xfdfe : 0xff,
            0xfbfe : 0xff,
            0xf7fe : 0xff,
            0xeffe : 0xff,
            0xdffe : 0xff,
            0xbffe : 0xff,
            0x7ffe : 0xff,
        }
        self.keys = {
            K_a : (0xfdfe, (1 << 0)),
            K_b : (0x7ffe, (1 << 3)),
            K_c : (0xfefe, (1 << 4)),
            K_d : (0xfdfe, (1 << 2)),
            K_e : (0xfbfe, (1 << 2)),
            K_f : (0xfdfe, (1 << 3)),
            K_g : (0xfdfe, (1 << 4)),
            K_h : (0xbffe, (1 << 4)),
            K_i : (0xdffe, (1 << 2)),
            K_j : (0xbffe, (1 << 3)),
            K_k : (0xbffe, (1 << 2)),
            K_l : (0xbffe, (1 << 1)),
            K_m : (0x7ffe, (1 << 1)),
            K_n : (0x7ffe, (1 << 2)),
            K_o : (0xdffe, (1 << 1)),
            K_p : (0xdffe, (1 << 0)),
            K_q : (0xfbfe, (1 << 0)),
            K_r : (0xfbfe, (1 << 3)),
            K_s : (0xfdfe, (1 << 1)),
            K_t : (0xfbfe, (1 << 4)),
            K_u : (0xdffe, (1 << 3)),
            K_v : (0x7ffe, (1 << 4)),
            K_w : (0xfbfe, (1 << 1)),
            K_x : (0xfefe, (1 << 3)),
            K_y : (0xdffe, (1 << 4)),
            K_z : (0xfefe, (1 << 2)),
            K_0 : (0xeffe, (1 << 0)),
            K_1 : (0xf7fe, (1 << 0)),
            K_2 : (0xf7fe, (1 << 1)),
            K_3 : (0xf7fe, (1 << 2)),
            K_4 : (0xf7fe, (1 << 3)),
            K_5 : (0xf7fe, (1 << 4)),
            K_6 : (0xeffe, (1 << 4)),
            K_7 : (0xeffe, (1 << 3)),
            K_8 : (0xeffe, (1 << 2)),
            K_9 : (0xeffe, (1 << 1)),
            K_LSHIFT : (0xfefe, (1 << 0)),
            K_RSHIFT : (0xfefe, (1 << 1)),
            K_SPACE : (0x7ffe, (1 << 0)),
            K_RETURN : (0xbffe, (1 << 0)),
        }

    def get(self):
        """process keyboard events"""
        for event in pygame.event.get():
            if event.type == KEYDOWN:
                x = self.keys.get(event.key, None)
                if x != None:
                    (port, bits) = x
                    self.ports[port] &= ~bits
                    return True
            elif event.type == KEYUP:
                x = self.keys.get(event.key, None)
                if x != None:
                    (port, bits) = x
                    self.ports[port] |= bits
        return False

    def rd(self, adr):
        """return the current port value"""
        return self.ports.get(adr, None)

#-----------------------------------------------------------------------------

class memmap:
    """memory devices and address map"""

    def __init__(self, romfile = './roms/ace.rom'):
        self.rom = memory.rom(13)
        self.rom.load_file(0, romfile)
        self.video = memory.ram(10)
        self.char = memory.wom(10)
        self.ram = memory.ram(10)
        self.empty = memory.null()

    def select(self, adr):
        """return the memory object selected by this address"""
        # select with 2k granularity
        memmap = (
            self.rom,   # 0x0000 - 0x07ff
            self.rom,   # 0x0800 - 0x0fff
            self.rom,   # 0x1000 - 0x17ff
            self.rom,   # 0x1800 - 0x1fff
            self.video, # 0x2000 - 0x27ff - 1K repeats 2 times
            self.char,  # 0x2800 - 0x2fff - 1K repeats 2 times
            self.ram,   # 0x3000 - 0x37ff - 1K repeats 4 times
            self.ram,   # 0x3800 - 0x3fff
            self.empty, # 0x4000
            self.empty, # 0x4800
            self.empty, # 0x5000
            self.empty, # 0x5800
            self.empty, # 0x6000
            self.empty, # 0x6800
            self.empty, # 0x7000
            self.empty, # 0x7800
            self.empty, # 0x8000
            self.empty, # 0x8800
            self.empty, # 0x9000
            self.empty, # 0x9800
            self.empty, # 0xa000
            self.empty, # 0xa800
            self.empty, # 0xb000
            self.empty, # 0xb800
            self.empty, # 0xc000
            self.empty, # 0xc800
            self.empty, # 0xd000
            self.empty, # 0xd800
            self.empty, # 0xe000
            self.empty, # 0xe800
            self.empty, # 0xf000
            self.empty, # 0xf800
        )
        return memmap[adr >> 11]

    def __getitem__(self, adr):
        adr &= 0xffff
        return self.select(adr)[adr]

    def __setitem__(self, adr, val):
        adr &= 0xffff
        self.select(adr)[adr] = val

#-----------------------------------------------------------------------------

class io:
    """io handler"""

    def __init__(self):
        self.keyboard = None

    def rd(self, adr):
        val = self.keyboard(adr)
        if val == None:
            val = 0xff
        return val

    def wr(self, adr, val):
        pass

#-----------------------------------------------------------------------------

class jace:

    def __init__(self, app):
        self.app = app
        self.video = video()
        self.keyboard = keyboard()
        self.mem = memmap()
        self.io = io()
        self.cpu = z80.cpu(self.mem, self.io)
        self.mon = monitor.monitor(self.cpu)
        self.menu_root = (
            ('..', 'return to main menu', util.cr, self.parent_menu, None),
            ('char', 'display the character memory', util.cr, self.cli_char, None),
            ('da', 'disassemble memory', monitor._help_disassemble, self.mon.cli_disassemble, None),
            ('exit', 'exit the application', util.cr, self.exit, None),
            ('help', 'display general help', util.cr, app.general_help, None),
            ('memory', 'memory functions', None, None, self.mon.menu_memory),
            ('regs', 'display cpu registers', util.cr, self.mon.cli_registers, None),
            ('run', 'run the emulation', util.cr, self.cli_run, None),
            ('step', 'single step the emulation', util.cr, self.cli_step, None),
        )

        # create the hooks between video and memory
        self.mem.char.wr_notify = self.video.char_wr
        self.mem.video.wr_notify = self.video.video_wr
        self.video.mem = self.mem
        self.video.cmem = self.mem.char.rd

        # create the hooks between io and keyboard
        self.io.keyboard = self.keyboard.rd

        # setup the video window
        pygame.init()
        self.screen = pygame.display.set_mode((_screen_x, _screen_y))
        pygame.display.set_caption('Jupiter ACE')
        self.video.refresh(self.screen)

        app.cli.set_poll(pygame.event.pump)
        app.cli.set_root(self.menu_root)
        self.app.cli.set_prompt('\njace> ')

    def cli_char(self, app, args):
        """display the character memory"""
        md = monitor.mem_display(app, _CHAR_ADR)
        for i in range(0x400):
            md.write(self.mem.char.rd(i))

    def cli_run(self, app, args):
        """run the emulation"""
        app.put('\n\npress any key to halt\n')
        cpu_clks = 0
        video_clks = 0
        irq = False
        while True:
            if app.io.anykey():
                return
            try:
                pc = self.cpu._get_pc()
                if (cpu_clks > 5000) or irq:
                    cpu_clks = self.cpu.interrupt()
                    irq = False
                else:
                    cpu_clks += self.cpu.execute()
            except z80.Error, e:
                self.cpu._set_pc(pc)
                app.put('exception: %s\n' % e)
                return
            if video_clks == 500:
                self.video.update(self.screen)
                video_clks = 0
            else:
                video_clks += 1
            irq = self.keyboard.get()

    def current_instruction(self):
        """return a string for the current instruction"""
        pc = self.cpu._get_pc()
        (operation, operands, n) = self.cpu.da(pc)
        return '%04x %-5s %s' % (pc, operation, operands)

    def cli_step(self, app, args):
        """single step the cpu"""
        done = 'done: %s' % self.current_instruction()
        self.cpu.execute()
        self.video.update(self.screen)
        next = 'next: %s' % self.current_instruction()
        app.put('\n\n%s\n' % '\n'.join((done, next)))

    def exit(self, app, args):
        """exit the application"""
        app.exit(app, [])

    def parent_menu(self, app, args):
        """return to parent menu"""
        app.put('\n')
        app.main_menu()

#-----------------------------------------------------------------------------
