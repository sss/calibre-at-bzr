# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import OutputFormatPlugin, \
    OptionRecommendation
from calibre.ebooks.txt.markdownml import MarkdownMLizer
from calibre.ebooks.txt.textileml import TextileMLizer
from calibre.ebooks.txt.txtml import TXTMLizer
from calibre.ebooks.txt.newlines import TxtNewlines, specified_newlines

class TXTOutput(OutputFormatPlugin):

    name = 'TXT Output'
    author = 'John Schember'
    file_type = 'txt'

    options = set([
        OptionRecommendation(name='newline', recommended_value='system',
            level=OptionRecommendation.LOW,
            short_switch='n', choices=TxtNewlines.NEWLINE_TYPES.keys(),
            help=_('Type of newline to use. Options are %s. Default is \'system\'. '
                'Use \'old_mac\' for compatibility with Mac OS 9 and earlier. '
                'For Mac OS X use \'unix\'. \'system\' will default to the newline '
                'type used by this OS.') % sorted(TxtNewlines.NEWLINE_TYPES.keys())),
        OptionRecommendation(name='txt_output_encoding', recommended_value='utf-8',
            level=OptionRecommendation.LOW,
            help=_('Specify the character encoding of the output document. ' \
            'The default is utf-8.')),
        OptionRecommendation(name='inline_toc',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Add Table of Contents to beginning of the book.')),
        OptionRecommendation(name='max_line_length',
            recommended_value=0, level=OptionRecommendation.LOW,
            help=_('The maximum number of characters per line. This splits on '
            'the first space before the specified value. If no space is found '
            'the line will be broken at the space after and will exceed the '
            'specified value. Also, there is a minimum of 25 characters. '
            'Use 0 to disable line splitting.')),
        OptionRecommendation(name='force_max_line_length',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Force splitting on the max-line-length value when no space '
            'is present. Also allows max-line-length to be below the minimum')),
        OptionRecommendation(name='txt_output_formatting',
             recommended_value='plain',
             choices=['plain', 'markdown', 'textile'],
             help=_('Formatting used within the document.\n'
                    '* plain: Produce plain text.\n'
                    '* markdown: Produce Markdown formatted text.\n'
                    '* textile: Produce Textile formatted text.')),
        OptionRecommendation(name='keep_links',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Do not remove links within the document. This is only ' \
            'useful when paired with a txt-output-formatting option that '
            'is not none because links are always removed with plain text output.')),
        OptionRecommendation(name='keep_image_references',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Do not remove image references within the document. This is only ' \
            'useful when paired with a txt-output-formatting option that '
            'is not none because links are always removed with plain text output.')),
     ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        if opts.txt_output_formatting.lower() == 'markdown':
            writer = MarkdownMLizer(log)
        elif opts.txt_output_formatting.lower() == 'textile':
            writer = TextileMLizer(log)
        else:
            writer = TXTMLizer(log)

        txt = writer.extract_content(oeb_book, opts)

        log.debug('\tReplacing newlines with selected type...')
        txt = specified_newlines(TxtNewlines(opts.newline).newline, txt)

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
        out_stream.write(txt.encode(opts.txt_output_encoding, 'replace'))

        if close:
            out_stream.close()

