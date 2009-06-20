# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.ebooks.pdf.pdftohtml import pdftohtml
from calibre.ebooks.metadata.opf2 import OPFCreator

class PDFInput(InputFormatPlugin):

    name        = 'PDF Input'
    author      = 'John Schember'
    description = 'Convert PDF files to HTML'
    file_types  = set(['pdf'])

    options = set([
        OptionRecommendation(name='no_images', recommended_value=False,
            help=_('Do not extract images from the document')),
    ])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        # The main html file will be named index.html
        pdftohtml(os.getcwd(), stream.name, options.no_images)

        from calibre.ebooks.metadata.meta import get_metadata
        mi = get_metadata(stream, 'pdf')
        opf = OPFCreator(os.getcwd(), mi)

        manifest = [('index.html', None)]

        images = os.listdir(os.getcwd())
        images.remove('index.html')
        for i in images:
            # Remove the - from the file name because it causes problems.
            # The referenec to the image with the - will be changed to not
            # include it later in the conversion process.
            new_i = i.replace('-', '')
            os.rename(i, new_i)
            manifest.append((new_i, None))
        opf.create_manifest(manifest)

        opf.create_spine(['index.html'])
        with open('metadata.opf', 'wb') as opffile:
            opf.render(opffile)

        return os.path.join(os.getcwd(), 'metadata.opf')
