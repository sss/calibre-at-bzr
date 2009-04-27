# -*- coding: utf-8 -*-
from __future__ import with_statement

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Convert OEB ebook format to PDF.
'''

#unit, papersize, orientation, custom_size, profile

import os, glob

from calibre.customize.conversion import OutputFormatPlugin, \
    OptionRecommendation
from calibre.ebooks.oeb.output import OEBOutput
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.pdf.writer import PDFWriter, PDFMetadata
from calibre.ebooks.pdf.pageoptions import UNITS, PAPER_SIZES, \
    ORIENTATIONS

class PDFOutput(OutputFormatPlugin):

    name = 'PDF Output'
    author = 'John Schember'
    file_type = 'pdf'

    options = set([
                    OptionRecommendation(name='unit', recommended_value='inch',
                        level=OptionRecommendation.LOW, short_switch='u', choices=UNITS.keys(),
                        help=_('The unit of measure. Default is inch. Choices '
                        'are %s '
                        'Note: This does not override the unit for margins!' % UNITS.keys())),
                    OptionRecommendation(name='paper_size', recommended_value='letter',
                        level=OptionRecommendation.LOW, choices=PAPER_SIZES.keys(),
                        help=_('The size of the paper. Default is letter. Choices '
                        'are %s' % PAPER_SIZES.keys())),
                    OptionRecommendation(name='custom_size', recommended_value=None,
                        help=_('Custom size of the document. Use the form widthxheight '
                        'EG. `123x321` to specify the width and height. '
                        'This overrides any specified paper-size.')),
                    OptionRecommendation(name='orientation', recommended_value='portrait',
                        level=OptionRecommendation.LOW, choices=ORIENTATIONS.keys(),
                        help=_('The orientation of the page. Default is portrait. Choices '
                        'are %s' % ORIENTATIONS.keys())),
                 ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        self.input_plugin, self.opts, self.log = input_plugin, opts, log
    
        if input_plugin.is_image_collection:
            self.convert_images(input_plugin.get_images(), output_path)
        else:
            self.convert_text(oeb_book, output_path)
            
    def convert_images(self, images, output_path):
        raise NotImplementedError()
            
    def convert_text(self, oeb_book, output_path):
        with TemporaryDirectory('_pdf_out') as oebdir:
            OEBOutput(None).convert(oeb_book, oebdir, self.input_plugin, self.opts, self.log)

            opf = glob.glob(os.path.join(oebdir, '*.opf'))[0]

            writer = PDFWriter(self.opts, self.log)

            close = False
            if not hasattr(output_path, 'write'):
                close = True
                if not os.path.exists(os.path.dirname(output_path)) and os.path.dirname(output_path) != '':
                    os.makedirs(os.path.dirname(output_path))
                out_stream = open(output_path, 'wb')
            else:
                out_stream = output_path

            out_stream.seek(0)
            out_stream.truncate()
            writer.dump(opf, out_stream, PDFMetadata(oeb_book.metadata))

            if close:
                out_stream.close()

