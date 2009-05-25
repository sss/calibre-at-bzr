#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, cPickle, sys
from multiprocessing.connection import Client
from threading import Thread
from Queue import Queue
from contextlib import closing
from binascii import unhexlify
from calibre import prints

PARALLEL_FUNCS = {
      'lrfviewer'    :
        ('calibre.gui2.lrf_renderer.main', 'main', None),

      'ebook-viewer'    :
        ('calibre.gui2.viewer.main', 'main', None),

      'render_pages' :
        ('calibre.ebooks.comic.input', 'render_pages', 'notification'),

      'gui_convert'     :
        ('calibre.gui2.convert.gui_conversion', 'gui_convert', 'notification'),

      'read_metadata' :
      ('calibre.ebooks.metadata.worker', 'read_metadata_', 'notification'),

      'read_pdf_metadata' :
      ('calibre.utils.podofo.__init__', 'get_metadata_', None),

      'write_pdf_metadata' :
      ('calibre.utils.podofo.__init__', 'set_metadata_', None),


      'save_book' :
      ('calibre.ebooks.metadata.worker', 'save_book', 'notification'),
}

class Progress(Thread):

    def __init__(self, conn):
        Thread.__init__(self)
        self.daemon = True
        self.conn = conn
        self.queue = Queue()

    def __call__(self, percent, msg=''):
        self.queue.put((percent, msg))

    def run(self):
        while True:
            x = self.queue.get()
            if x is None:
                break
            try:
                self.conn.send(x)
            except:
                break



def get_func(name):
    module, func, notification = PARALLEL_FUNCS[name]
    module = __import__(module, fromlist=[1])
    func = getattr(module, func)
    return func, notification

def main():
    address = cPickle.loads(unhexlify(os.environ['CALIBRE_WORKER_ADDRESS']))
    key     = unhexlify(os.environ['CALIBRE_WORKER_KEY'])
    resultf = unhexlify(os.environ['CALIBRE_WORKER_RESULT'])
    with closing(Client(address, authkey=key)) as conn:
        name, args, kwargs, desc = conn.recv()
        if desc:
            prints(desc)
            sys.stdout.flush()
        func, notification = get_func(name)
        notifier = Progress(conn)
        if notification:
            kwargs[notification] = notifier
            notifier.start()

        result = func(*args, **kwargs)
        if result is not None:
            cPickle.dump(result, open(resultf, 'wb'), -1)

        notifier.queue.put(None)

    sys.stdout.flush()
    sys.stderr.flush()
    return 0



if __name__ == '__main__':
    sys.exit(main())
