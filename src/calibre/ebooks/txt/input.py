# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks.txt.processor import txt_to_markdown

class TXTInput(InputFormatPlugin):

    name        = 'TXT Input'
    author      = 'John Schember'
    description = 'Convert TXT files to HTML'
    file_types  = set(['txt'])

    options = set([
        OptionRecommendation(name='single_line_paras', recommended_value=False,
            help=_('Each line is a paragraph.')),
    ])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        ienc = stream.encoding if stream.encoding else 'utf-8'
        if options.input_encoding:
            ienc = options.input_encoding
        log.debug('Reading text from file...')
        txt = stream.read().decode(ienc, 'replace')

        if options.single_line_paras:
            txt = txt.replace('\r\n', '\n')
            txt = txt.replace('\r', '\n')
            txt = txt.replace('\n', '\n\n')

        log.debug('Running text though markdown conversion...')
        try:
            html = txt_to_markdown(txt)
        except RuntimeError:
            raise ValueError('This txt file has malformed markup, it cannot be'
                'converted by calibre. See http://daringfireball.net/projects/markdown/syntax')

        from calibre.customize.ui import plugin_for_input_format
        html_input = plugin_for_input_format('html')
        for opt in html_input.options:
            setattr(options, opt.option.name, opt.recommended_value)
        base = os.getcwdu()
        if hasattr(stream, 'name'):
            base = os.path.dirname(stream.name)
        htmlfile = open(os.path.join(base, 'temp_calibre_txt_input_to_html.html'),
                'wb')
        htmlfile.write(html.encode('utf-8'))
        htmlfile.close()
        cwd = os.getcwdu()
        odi = options.debug_input
        options.debug_input = None
        oeb = html_input(open(htmlfile.name, 'rb'), options, 'html', log,
                {}, cwd)
        options.debug_input = odi
        os.remove(htmlfile.name)
        return oeb
