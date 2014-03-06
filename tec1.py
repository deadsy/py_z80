#-----------------------------------------------------------------------------
"""
Talking Electronics Computer Emulator
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

_screen_x = 400
_screen_y = 50

_border = (0, 0, 0)

#-----------------------------------------------------------------------------

class memmap:
    """memory devices and address map"""

    def __init__(self, romfile = './roms/tec1a.rom'):
        self.rom = memory.rom(11)
        self.rom.load_file(0, romfile)
        self.ram = memory.ram(11)
        self.empty = memory.null()

    def select(self, adr):
        """return the memory object selected by this address"""
        # select with 2k granularity
        memmap = (
            self.rom,   # 0x0000 - 0x07ff
            self.ram,   # 0x0800 - 0x0fff
            self.empty, # 0x1000
            self.empty, # 0x1800
            self.empty, # 0x2000
            self.empty, # 0x2800
            self.empty, # 0x3000
            self.empty, # 0x3800
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

class display:
    """6 x 7 segment led displays"""

    def __init__(self):
        pass

    def select(self, val):
        print '%d' % val

    def segments(self, val):
        pass

    def refresh(self, screen):
        """refresh the whole display"""
        bg = pygame.Surface(screen.get_size())
        bg = bg.convert()
        bg.fill(_border)
        screen.blit(bg, (0, 0))
        pygame.display.flip()

    def update(self, screen):
        """update the video display"""
        pygame.display.flip()

#-----------------------------------------------------------------------------

class keyboard:
    """keyboard emulation"""

    def __init__(self):
        pass

    def get(self):
        """process keyboard events"""
        for event in pygame.event.get():
            if event.type == KEYDOWN:
                return True
            elif event.type == KEYUP:
                pass
        return False

    def rd(self, adr):
        """return the current port value"""
        return 0

#-----------------------------------------------------------------------------

class io:
    """io handler"""

    def __init__(self, display, keyboard):
        self.display = display
        self.keyboard = keyboard

    def rd(self, adr):
        print 'rd %04x' % adr
        return 0xff

    def wr(self, adr, val):
        adr &= 0xff
        if adr == 0x01:
            self.display.select(val)
        elif adr == 0x02:
            self.display.segments(val)
        else:
            print 'wr %04x %02x' % (adr, val)

#-----------------------------------------------------------------------------

class tec1:

    def __init__(self, app):
        self.app = app
        self.display = display()
        self.keyboard = keyboard()
        self.mem = memmap()
        self.io = io(self.display, self.keyboard)
        self.cpu = z80.cpu(self.mem, self.io)
        self.mon = monitor.monitor(self.cpu)
        self.menu_root = (
            ('..', 'return to main menu', util.cr, self.parent_menu, None),
            ('da', 'disassemble memory', monitor._help_disassemble, self.mon.cli_disassemble, None),
            ('exit', 'exit the application', util.cr, self.exit, None),
            ('help', 'display general help', util.cr, app.general_help, None),
            ('memory', 'memory functions', None, None, self.mon.menu_memory),
            ('regs', 'display cpu registers', util.cr, self.mon.cli_registers, None),
            ('run', 'run the emulation', util.cr, self.cli_run, None),
            ('step', 'single step the emulation', util.cr, self.cli_step, None),
        )

        # setup the video window
        pygame.init()
        self.screen = pygame.display.set_mode((_screen_x, _screen_y))
        pygame.display.set_caption('Talking Electronics Computer TEC 1')
        self.display.refresh(self.screen)

        app.cli.set_poll(pygame.event.pump)
        app.cli.set_root(self.menu_root)
        self.app.cli.set_prompt('\ntec1> ')

    def cli_run(self, app, args):
        """run the emulation"""
        app.put('\n\npress any key to halt\n')
        irq = False
        x = 0
        while True:
            if app.io.anykey():
                return
            try:
                pc = self.cpu._get_pc()
                if  irq:
                    self.cpu.interrupt(x)
                    irq = False
                    x += 1
                else:
                    self.cpu.execute()
            except z80.Error, e:
                self.cpu._set_pc(pc)
                app.put('exception: %s\n' % e)
                return
            print x
            self.display.update(self.screen)
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
