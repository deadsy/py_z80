#-----------------------------------------------------------------------------
"""
General Utilities
"""
#-----------------------------------------------------------------------------

import os

#-----------------------------------------------------------------------------
# help for cli leaf functions

cr = (
    ('<cr>', 'perform the function'),
)

general = (
    ( '?', 'display command help - Eg. ?, show ?, s?'),
    ( '<up>', 'go backwards in command history'),
    ( '<dn>', 'go forwards in command history'),
    ( '<tab>', 'auto complete commands'),
    ( '* note', 'commands can be incomplete - Eg. sh = sho = show'),
)

#-----------------------------------------------------------------------------

bad_argc = '\n\nbad number of arguments\n'
inv_arg = '\n\ninvalid argument\n'

#-----------------------------------------------------------------------------

limit_16 = (0, 0xffff)

#-----------------------------------------------------------------------------

def todo(app, args):
    app.put('\n\nnot implemented\n')

#-----------------------------------------------------------------------------

def wrong_argc(app, args, valid):
    """return True if argc is not valid"""
    argc = len(args)
    if argc in valid:
        return False
    else:
        app.put(bad_argc)
        return True

#-----------------------------------------------------------------------------

def int_arg(app, arg, limits, base):
    """convert a number string to an integer - or None"""
    try:
        val = int(arg, base)
    except ValueError:
        app.put(inv_arg)
        return None
    if (val < limits[0]) or (val > limits[1]):
        app.put(inv_arg)
        return None
    return val

#-----------------------------------------------------------------------------

def file_arg(app, name):
    """return True if the file exists and is non-zero in size"""
    if os.path.isfile(name) == False:
        app.put('\n\n%s does not exist\n' % name)
        return False
    if os.path.getsize(name) == 0:
        app.put('\n\n%s has zero size\n' % name)
        return False
    return True

#-----------------------------------------------------------------------------

def parameter_str(parms):
    """return a string with parameters and values"""
    return '\n'.join(['%-23s: %s' % x for x in parms])

#-----------------------------------------------------------------------------
# bit field manipulation

def maskshift(field):
    """return a mask and shift defined by field"""
    if len(field) == 1:
        return (1 << field[0], field[0])
    else:
        return (((1 << (field[0] - field[1] + 1)) - 1) << field[1], field[1])

def bits(val, field):
    """return the bits (masked and shifted) from the value"""
    (mask, shift) = maskshift(field)
    return (val & mask) >> shift

def masked(val, field):
    """return the bits (masked only) from the value"""
    return val & maskshift(field)[0]

#-----------------------------------------------------------------------------

def bitfield_v(val, fields):
    """
    return a string of bit field components formatted vertically
    val: the value to be split into bit fields
    fields: a tuple of (name, format, (bit_hi, bit_lo)) tuples
    """
    l = []
    for (name, format, field) in fields:
        l.append(('%-15s: %s' % (name, format)) % bits(val, field))
    return '\n'.join(l)

#-----------------------------------------------------------------------------

def bitfield_h(val, fields):
    """
    return a string of bit field components formatted horizontally
    val: the value to be split into bit fields
    fields: a tuple of (name, format, (bit_hi, bit_lo)) tuples
    """
    l = []
    for (name, format, field) in fields:
        if name == '':
            l.append(('%s' % format) % bits(val, field))
        else:
            l.append(('%s(%s)' % (name, format)) % bits(val, field))
    return ' '.join(l)

#-----------------------------------------------------------------------------

def group(lst, n):
    """
    Group a list into consecutive n-tuples.
    Incomplete tuples are discarded.
    """
    return zip(*[lst[i::n] for i in range(n)])

#-----------------------------------------------------------------------------

class progress:
    """percent complete and activity indication"""

    def __init__(self, app, div, nmax):
        """
        progress indicator
        div = slash speed, larger is slower
        nmax = maximum value, 100%
        """
        self.app = app
        self.nmax = nmax
        self.progress = ''
        self.div = div
        self.mask = (1 << div) - 1

    def erase(self):
        """erase the progress indication"""
        n = len(self.progress)
        self.app.put(''.join(['\b' * n, ' ' * n, '\b' * n]))

    def update(self, n):
        """update the progress indication"""
        if n & self.mask == 0:
            self.erase()
            istr = '-\\|/'[(n >> self.div) & 3]
            pstr = '%d%% ' % ((100 * n) / self.nmax)
            self.progress = ''.join([pstr, istr])
            self.app.put(self.progress)

#-----------------------------------------------------------------------------
