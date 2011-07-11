#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, cPickle, subprocess
from setup import Command
import __builtin__

def set_builtins(builtins):
    for x in builtins:
        if not hasattr(__builtin__, x):
            setattr(__builtin__, x, True)
            yield x

class Message:

    def __init__(self, filename, lineno, msg):
        self.filename, self.lineno, self.msg = filename, lineno, msg

    def __str__(self):
        return '%s:%s: %s'%(self.filename, self.lineno, self.msg)

def check_for_python_errors(code_string, filename):
    # Since compiler.parse does not reliably report syntax errors, use the
    # built in compiler first to detect those.
    try:
        try:
            compile(code_string, filename, "exec")
        except MemoryError:
            # Python 2.4 will raise MemoryError if the source can't be
            # decoded.
            if sys.version_info[:2] == (2, 4):
                raise SyntaxError(None)
            raise
    except (SyntaxError, IndentationError), value:
        msg = value.args[0]

        (lineno, offset, text) = value.lineno, value.offset, value.text

        # If there's an encoding problem with the file, the text is None.
        if text is None:
            # Avoid using msg, since for the only known case, it contains a
            # bogus message that claims the encoding the file declared was
            # unknown.
            msg = "%s: problem decoding source" % filename
        return [Message(filename, lineno, msg)]
    else:
        # Okay, it's syntactically valid.  Now parse it into an ast and check
        # it.
        import compiler
        checker = __import__('pyflakes.checker').checker
        tree = compiler.parse(code_string)
        w = checker.Checker(tree, filename)
        w.messages.sort(lambda a, b: cmp(a.lineno, b.lineno))
        return [Message(x.filename, x.lineno, x.message%x.message_args) for x in
                w.messages]

class Check(Command):

    description = 'Check for errors in the calibre source code'

    BUILTINS = ['_', '__', 'dynamic_property', 'I', 'P', 'lopen', 'icu_lower',
            'icu_upper', 'icu_title', 'ngettext']
    CACHE = '.check-cache.pickle'

    def get_files(self, cache):
        for x in os.walk(self.j(self.SRC, 'calibre')):
            for f in x[-1]:
                y = self.j(x[0], f)
                mtime = os.stat(y).st_mtime
                if f.endswith('.py') and f not in ('ptempfile.py', 'feedparser.py',
                    'pyparsing.py', 'markdown.py') and \
                    'genshi' not in y and cache.get(y, 0) != mtime and \
                    'prs500/driver.py' not in y:
                        yield y, mtime

        for x in os.walk(self.j(self.d(self.SRC), 'recipes')):
            for f in x[-1]:
                f = self.j(x[0], f)
                mtime = os.stat(f).st_mtime
                if f.endswith('.recipe') and cache.get(f, 0) != mtime:
                    yield f, mtime


    def run(self, opts):
        cache = {}
        if os.path.exists(self.CACHE):
            cache = cPickle.load(open(self.CACHE, 'rb'))
        builtins = list(set_builtins(self.BUILTINS))
        for f, mtime in self.get_files(cache):
            self.info('\tChecking', f)
            w = check_for_python_errors(open(f, 'rb').read(), f)
            if w:
                self.report_errors(w)
                cPickle.dump(cache, open(self.CACHE, 'wb'), -1)
                subprocess.call(['gvim', '-f', f])
                raise SystemExit(1)
            cache[f] = mtime
        for x in builtins:
            delattr(__builtin__, x)
        cPickle.dump(cache, open(self.CACHE, 'wb'), -1)
        wn_path = os.path.expanduser('~/work/servers/src/calibre_servers/main')
        if os.path.exists(wn_path):
            sys.path.insert(0, wn_path)
            self.info('\tChecking Changelog...')
            os.environ['DJANGO_SETTINGS_MODULE'] = 'calibre_servers.status.settings'
            import whats_new
            whats_new.test()
            sys.path.remove(wn_path)

    def report_errors(self, errors):
        for err in errors:
            self.info('\t\t', str(err))

