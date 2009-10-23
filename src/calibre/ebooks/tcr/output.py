# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import OutputFormatPlugin, \
    OptionRecommendation
from calibre.ebooks.txt.txtml import TXTMLizer
from calibre.ebooks.compression.tcr import compress

class TCROutput(OutputFormatPlugin):

    name = 'TCR Output'
    author = 'John Schember'
    file_type = 'tcr'

    options = set([
        OptionRecommendation(name='output_encoding', recommended_value='utf-8',
            level=OptionRecommendation.LOW,
            help=_('Specify the character encoding of the output document. ' \
            'The default is utf-8.')),
        OptionRecommendation(name='compression_level', recommended_value=5,
            level=OptionRecommendation.LOW,
            help=_('Speciy the compression level to use. Scale 1 - 10. 1 ' \
            'being the lowest compression but the fastest and 10 being the ' \
            'highest compression but the slowest.')),
    ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        close = False
        if not hasattr(output_path, 'write'):
            close = True
            if not os.path.exists(os.path.dirname(output_path)) and os.path.dirname(output_path) != '':
                os.makedirs(os.path.dirname(output_path))
            out_stream = open(output_path, 'wb')
        else:
            out_stream = output_path

        setattr(opts, 'flush_paras', False)
        setattr(opts, 'max_line_length', 0)
        setattr(opts, 'force_max_line_length', False)
        setattr(opts, 'indent_paras', False)

        writer = TXTMLizer(log)
        txt = writer.extract_content(oeb_book, opts).encode(opts.output_encoding, 'replace')

        log.info('Compressing text...')
        txt = compress(txt, opts.compression_level)

        out_stream.seek(0)
        out_stream.truncate()
        out_stream.write(txt)

        if close:
            out_stream.close()
