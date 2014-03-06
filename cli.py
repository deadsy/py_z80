#-----------------------------------------------------------------------------
"""
Command Line Interface

Implements a CLI with:

* hierarchical menus
* command completion
* command history
* context sensitive help
* command editing

Notes:

Menu Format: (name, descr, help, leaf, submenu)
Function Help Format: (parm, descr)

"""
#-----------------------------------------------------------------------------

import conio

#-----------------------------------------------------------------------------

class command:

    def __init__(self, app):
        """initialise to an empty command string"""
        self.app = app
        self.clear()

    def clear(self):
        """clear the command string"""
        self.cmd = []
        self.cursor = 0
        self.old_cmd = []
        self.old_cursor = 0

    def repeat(self):
        """repeating the current command on a new line"""
        # set the old command to null
        self.old_cmd = []
        self.old_cursor = 0
        self.end()

    def set(self, cmd):
        """set the command string to a new value"""
        self.cmd = list(cmd)
        self.cursor = len(cmd)

    def get(self):
        """return the current command string"""
        return ''.join(self.cmd)

    def erase(self):
        """erase a character from the tail of the command string"""
        del self.cmd[-1:]
        # ensure the cursor is valid
        self.end()

    def backspace(self):
        """erase the character to the left of the cursor position"""
        if self.cursor > 0:
            del self.cmd[self.cursor - 1]
            self.cursor -= 1

    def delete(self):
        """erase the character at the cursor position"""
        if self.cursor < len(self.cmd):
            del self.cmd[self.cursor]

    def add(self, x):
        """add character(s) to the command string"""
        for c in x:
            self.cmd.insert(self.cursor, c)
            self.cursor += 1

    def left(self):
        """move the cursor left"""
        if self.cursor > 0:
            self.cursor -= 1

    def right(self):
        """move the cursor right"""
        if self.cursor < len(self.cmd):
            self.cursor += 1

    def end(self):
        """move the cursor to the end"""
        self.cursor = len(self.cmd)

    def home(self):
        """move the cursor to the home"""
        self.cursor = 0

    def render(self):
        """render the command line"""
        if (self.old_cmd == self.cmd) and (self.old_cursor == self.cursor):
            return

        # This is the dumbest thing that works
        # Fix it for serial port operation

        # erase the old command
        n1 = self.old_cursor
        n2 = len(self.old_cmd)
        erase = ''.join(['\b' * n1, ' ' * n2, '\b' * n2])
        self.app.io.put(erase)

        # write the new command
        self.app.io.put(self.get())

        # position the cursor
        bs = '\b' * (len(self.cmd) - self.cursor)
        self.app.io.put(bs)

        self.old_cmd = list(self.cmd)
        self.old_cursor = self.cursor

#-----------------------------------------------------------------------------

class cli:

    def __init__(self, app):
        self.app = app
        self.history = []
        self.hidx = 0
        self.cl = command(app)
        self.running = True
        self.prompt = '\n> '
        self.poll = None

    def set_root(self, root):
        """set the menu root"""
        self.root = root

    def set_prompt(self, prompt):
        """set the command prompt"""
        self.prompt = prompt

    def set_poll(self, poll):
        """set the external polling function"""
        self.poll = poll

    def func_help(self, help):
        """print help for a leaf function"""
        self.app.io.put('\n\n')
        for (parm, descr) in help:
            if parm != '':
                self.app.io.put('    %-19s: %s\n' % (parm, descr))
            else:
                self.app.io.put('    %-19s  %s\n' % ('', descr))

    def reset_history(self):
        self.hidx = len(self.history)

    def put_history(self, cmd):
        """put a command into the history list"""
        n = len(self.history)
        if (n == 0) or ((n >= 1) and (self.history[-1] != cmd)):
            self.history.append(cmd)

    def get_history_rev(self):
        """get history in the reverse (up) direction"""
        n = len(self.history)
        if n != 0:
            if self.hidx > 0:
                # go backwards
                self.hidx -= 1
            else:
                # top of list
                self.app.io.put(chr(conio.CHAR_BELL))
            return self.history[self.hidx]
        else:
            # no history - return current command line
            return self.cl.get()

    def get_history_fwd(self):
        """get history in the forward (down) direction"""
        n = len(self.history)
        if self.hidx == n:
            # not in the history list - return current command line
            return self.cl.get()
        elif self.hidx == n - 1:
            # end of history recent - go back to an empty command
            self.hidx = n
            return ''
        else:
            # go forwards
            self.hidx += 1
            return self.history[self.hidx]

    def error_str(self, msg, cmds, idx):
        """return a parse error string"""
        marker = []
        for i in range(len(cmds)):
            l = len(cmds[i])
            if i == idx:
                marker.append('^' * l)
            else:
                marker.append(' ' * l)
        return '\n'.join([msg, ' '.join(cmds), ' '.join(marker)])

    def get_cmd(self):
        """
        accumulate input characters to the command line
        return True when processing is needed
        return False for on going input
        """
        c = self.app.io.get()
        if c == conio.CHAR_NULL:
            return False
        elif (c == conio.CHAR_TAB) or (c == conio.CHAR_QM):
            self.cl.end()
            self.cl.add(chr(c))
            return True
        elif c == conio.CHAR_CR:
            return True
        elif c == conio.CHAR_DOWN:
            self.cl.set(self.get_history_fwd())
            return False
        elif c == conio.CHAR_UP:
            self.cl.set(self.get_history_rev())
            return False
        elif c == conio.CHAR_LEFT:
            self.cl.left()
            return False
        elif c == conio.CHAR_RIGHT:
            self.cl.right()
            return False
        elif c == conio.CHAR_END:
            self.cl.end()
            return False
        elif c == conio.CHAR_HOME:
            self.cl.home()
            return False
        elif c == conio.CHAR_ESC:
            self.cl.clear()
            return True
        elif c == conio.CHAR_BS:
            self.cl.backspace()
            return False
        elif c == conio.CHAR_DEL:
            self.cl.delete()
            return False
        else:
            self.cl.add(chr(c))
            return False

    def parse_cmd(self):
        """
        parse and process the current command line
        return True if we need a new prompt line
        return False if we should reuse the existing one
        """
        # scan the command line into a list of tokens
        cmd_list = [cmd for cmd in self.cl.get().split(' ') if cmd != '']

        # if there are no commands, print a new empty prompt
        if len(cmd_list) == 0:
            self.cl.clear()
            return True

        # trace each command through the menu tree
        menu = self.root
        for idx in range(len(cmd_list)):
            cmd = cmd_list[idx]

            # A trailing '?' means the user wants help for this command
            if cmd[-1] == '?':
                # strip off the '?'
                cmd = cmd[:-1]
                # print the matching items and help strings for this menu
                self.app.io.put('\n\n')
                for (name, descr, help, leaf, submenu) in menu:
                    if name.startswith(cmd):
                        self.app.io.put('    %-19s: %s\n' % (name, descr))
                # strip off the '?' and recycle the command
                self.cl.erase()
                self.cl.repeat()
                return True

            # A trailing tab means the user wants command completion
            if cmd[-1] == '\t':
                # get rid of the tab
                cmd = cmd[:-1]
                self.cl.erase()
                matches = []
                for item in menu:
                    if item[0].startswith(cmd):
                        matches.append(item)
                if len(matches) == 0:
                    # no completions
                    self.app.io.put(chr(conio.CHAR_BELL))
                    return False
                elif len(matches) == 1:
                    # one completion: add it to the command
                    self.cl.add(matches[0][0][len(cmd):] + ' ')
                    self.cl.end()
                    return False
                else:
                    # multiple completions: display them
                    self.app.io.put('\n\n')
                    for (name, descr, help, leaf, submenu) in matches:
                        self.app.io.put('%s ' % name)
                    self.app.io.put('\n')
                    # recycle the command
                    self.cl.repeat()
                    return True

            # try to match the cmd with a unique menu item
            matches = []
            for item in menu:
                if item[0] == cmd:
                    # accept an exact match
                    matches = [item]
                    break;
                if item[0].startswith(cmd):
                    matches.append(item)
            if len(matches) == 0:
                # no matches - unknown command
                self.app.io.put('\n\n%s\n' % self.error_str('unknown command', cmd_list, idx))
                self.cl.repeat()
                return True
            if len(matches) == 1:
                # one match - submenu/leaf
                (name, descr, help, leaf, submenu) = matches[0]
                if submenu != None:
                    # switch to the submenu - continue parsing
                    menu = submenu
                    continue
                else:
                    # process leaf function - get the arguments
                    args = cmd_list[idx:]
                    del args[0]
                    if len(args) != 0:
                        if args[-1][-1] == '?':
                            # display help for the leaf function
                            self.func_help(help)
                            # strip off the '?', repeat the command
                            self.cl.erase()
                            self.cl.repeat()
                            return True
                        elif args[-1][-1] == '\t':
                            # tab happy user: strip off the tab
                            self.cl.erase()
                            self.cl.end()
                            return False
                    # call the leaf function
                    self.put_history(self.cl.get())
                    leaf(self.app, args)
                    self.cl.clear()
                    return True
            else:
                # multiple matches - ambiguous command
                self.app.io.put('\n\n%s\n' % self.error_str('ambiguous command', cmd_list, idx))
                self.cl.clear()
                return True

        # reached the end of the command list with no errors and no leaf function.
        self.app.io.put('\n\nadditional input needed\n')
        self.cl.repeat()
        return True

    def run(self):
        """get and process cli commands in a loop"""
        self.app.io.put(self.prompt)
        while self.running:
            if self.get_cmd():
                if self.parse_cmd():
                    if self.running == True:
                        # create a new prompt line
                        self.reset_history()
                        self.app.io.put('%s' % self.prompt)
                    else:
                        # clean exit
                        self.app.io.put('\n\n')
                        continue
            # run the external polling routine
            if self.poll != None:
                if self.poll() == True:
                    # create a new prompt line
                    self.reset_history()
                    self.app.io.put('%s' % self.prompt)
            self.cl.render()

    def exit(self):
        """exit the cli"""
        self.running = False

#-----------------------------------------------------------------------------
