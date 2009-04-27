# -*- coding: utf-8 -*-
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Write content to PDF.
'''

import os, shutil

from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.ebooks.pdf.pageoptions import unit, paper_size, \
    orientation, size
from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.metadata.opf2 import OPF

from PyQt4 import QtCore
from PyQt4.Qt import QUrl, QEventLoop, SIGNAL, QObject, \
    QApplication, QPrinter, QMetaObject, QSizeF, Qt
from PyQt4.QtWebKit import QWebView

from pyPdf import PdfFileWriter, PdfFileReader

class PDFMetadata(object):
    def __init__(self, oeb_metadata=None):
        self.title = _('Unknown')
        self.author = _('Unknown')

        if oeb_metadata != None:
            if len(oeb_metadata.title) >= 1:
                self.title = oeb_metadata.title[0].value
            if len(oeb_metadata.creator) >= 1:
                self.author = authors_to_string([x.value for x in oeb_metadata.creator])


class PDFWriter(QObject):
    def __init__(self, opts, log):
        if QApplication.instance() is None:
            QApplication([])
        QObject.__init__(self)

        self.logger = log

        self.loop = QEventLoop()
        self.view = QWebView()
        self.connect(self.view, SIGNAL('loadFinished(bool)'), self._render_html)
        self.render_queue = []
        self.combine_queue = []
        self.tmp_path = PersistentTemporaryDirectory('_pdf_output_parts')

        self.custom_size = None
        if opts.custom_size != None:
            width, sep, height = opts.custom_size.partition('x')
            if height != '':
                try:
                    width = int(width)
                    height = int(height)
                    self.custom_size = (width, height)
                except:
                    self.custom_size = None

        self.opts = opts

    def dump(self, opfpath, out_stream, pdf_metadata):
        self.metadata = pdf_metadata
        self._delete_tmpdir()

        opf = OPF(opfpath, os.path.dirname(opfpath))
        self.render_queue = [i.path for i in opf.spine]
        self.combine_queue = []
        self.out_stream = out_stream

        QMetaObject.invokeMethod(self, "_render_book", Qt.QueuedConnection)
        self.loop.exec_()

    @QtCore.pyqtSignature('_render_book()')
    def _render_book(self):
        if len(self.render_queue) == 0:
            self._write()
        else:
            self._render_next()

    def _render_next(self):
        item = str(self.render_queue.pop(0))
        self.combine_queue.append(os.path.join(self.tmp_path, '%i.pdf' % (len(self.combine_queue) + 1)))

        self.logger.info('Processing %s...' % item)

        self.view.load(QUrl(item))

    def _render_html(self, ok):
        if ok:
            item_path = os.path.join(self.tmp_path, '%i.pdf' % len(self.combine_queue))

            self.logger.debug('\tRendering item %s as %i' % (os.path.basename(str(self.view.url().toLocalFile())), len(self.combine_queue)))

            printer = QPrinter(QPrinter.HighResolution)

            if self.opts.output_profile.short_name == 'default':
                if self.custom_size == None:
                    printer.setPaperSize(paper_size(self.opts.paper_size))
                else:
                    printer.setPaperSize(QSizeF(self.custom_size[0], self.custom_size[1]), unit(self.opts.unit))
            else:
                printer.setPaperSize(QSizeF(self.opts.output_profile.width / self.opts.output_profile.dpi, self.opts.output_profile.height / self.opts.output_profile.dpi), QPrinter.Inch)

            printer.setPageMargins(0, 0, 0, 0, QPrinter.Point)
            printer.setOrientation(orientation(self.opts.orientation))
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(item_path)
            self.view.print_(printer)
        self._render_book()

    def _delete_tmpdir(self):
        if os.path.exists(self.tmp_path):
            shutil.rmtree(self.tmp_path, True)
            self.tmp_path = PersistentTemporaryDirectory('_pdf_output_parts')

    def _write(self):
        self.logger.info('Combining individual PDF parts...')

        try:
            outPDF = PdfFileWriter(title=self.metadata.title, author=self.metadata.author)
            for item in self.combine_queue:
                inputPDF = PdfFileReader(open(item, 'rb'))
                for page in inputPDF.pages:
                    outPDF.addPage(page)
            outPDF.write(self.out_stream)
        finally:
            self._delete_tmpdir()
            self.loop.exit(0)


class ImagePDFWriter(object):
    
    def __init__(self, opts, log):
        self.opts, self.log = opts, log
        
