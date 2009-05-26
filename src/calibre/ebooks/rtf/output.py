# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.ebooks.rtf.rtfml import RTFMLizer
from calibre.customize.conversion import OutputFormatPlugin

class RTFOutput(OutputFormatPlugin):

    name = 'RTF Output'
    author = 'John Schember'
    file_type = 'rtf'

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        rtfmlitzer = RTFMLizer(ignore_tables=opts.linearize_tables)
        content = rtfmlitzer.extract_content(oeb_book, opts)

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
        out_stream.write(content.encode('cp1252', 'replace'))

        if close:
            out_stream.close()
