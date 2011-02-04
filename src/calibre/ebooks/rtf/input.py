from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, glob, re, textwrap

from lxml import etree

from calibre.customize.conversion import InputFormatPlugin

border_style_map = {
        'single' : 'solid',
        'double-thickness-border' : 'double',
        'shadowed-border': 'outset',
        'double-border': 'double',
        'dotted-border': 'dotted',
        'dashed': 'dashed',
        'hairline': 'solid',
        'inset': 'inset',
        'dash-small': 'dashed',
        'dot-dash': 'dotted',
        'dot-dot-dash': 'dotted',
        'outset': 'outset',
        'tripple': 'double',
        'thick-thin-small': 'solid',
        'thin-thick-small': 'solid',
        'thin-thick-thin-small': 'solid',
        'thick-thin-medium': 'solid',
        'thin-thick-medium': 'solid',
        'thin-thick-thin-medium': 'solid',
        'thick-thin-large': 'solid',
        'thin-thick-thin-large': 'solid',
        'wavy': 'ridge',
        'double-wavy': 'ridge',
        'striped': 'ridge',
        'emboss': 'inset',
        'engrave': 'inset',
        'frame': 'ridge',
}

class InlineClass(etree.XSLTExtension):

    FMTS = ('italics', 'bold', 'underlined', 'strike-through', 'small-caps')

    def __init__(self, log):
        etree.XSLTExtension.__init__(self)
        self.log = log
        self.font_sizes = []
        self.colors = []

    def execute(self, context, self_node, input_node, output_parent):
        classes = ['none']
        for x in self.FMTS:
            if input_node.get(x, None) == 'true':
                classes.append(x)
        fs = input_node.get('font-size', False)
        if fs:
            if fs not in self.font_sizes:
                self.font_sizes.append(fs)
            classes.append('fs%d'%self.font_sizes.index(fs))
        fc = input_node.get('font-color', False)
        if fc:
            if fc not in self.colors:
                self.colors.append(fc)
            classes.append('col%d'%self.colors.index(fc))

        output_parent.text = ' '.join(classes)


class RTFInput(InputFormatPlugin):

    name        = 'RTF Input'
    author      = 'Kovid Goyal'
    description = 'Convert RTF files to HTML'
    file_types  = set(['rtf'])

    def generate_xml(self, stream):
        from calibre.ebooks.rtf2xml.ParseRtf import ParseRtf
        ofile = 'dataxml.xml'
        run_lev, debug_dir = 1, None
        if getattr(self.opts, 'debug_pipeline', None) is not None:
            try:
                os.mkdir(debug_dir)
                debug_dir = 'rtfdebug'
                run_lev = 4
                self.log('Running RTFParser in debug mode')
            except:
                pass
        parser = ParseRtf(
            in_file    = stream,
            out_file   = ofile,
            # Convert symbol fonts to unicode equivalents. Default
            # is 1
            convert_symbol = 1,

            # Convert Zapf fonts to unicode equivalents. Default
            # is 1.
            convert_zapf = 1,

            # Convert Wingding fonts to unicode equivalents.
            # Default is 1.
            convert_wingdings = 1,

            # Convert RTF caps to real caps.
            # Default is 1.
            convert_caps = 1,

            # Indent resulting XML.
            # Default is 0 (no indent).
            indent = 1,

            # Form lists from RTF. Default is 1.
            form_lists = 1,

            # Convert headings to sections. Default is 0.
            headings_to_sections = 1,

            # Group paragraphs with the same style name. Default is 1.
            group_styles = 1,

            # Group borders. Default is 1.
            group_borders = 1,

            # Write or do not write paragraphs. Default is 0.
            empty_paragraphs = 1,

            #debug
            deb_dir = debug_dir,
            run_level = run_lev,
        )
        parser.parse_rtf()
        with open(ofile, 'rb') as f:
            return f.read()

    def extract_images(self, picts):
        import imghdr
        self.log('Extracting images...')

        with open(picts, 'rb') as f:
            raw = f.read()
        picts = filter(len, re.findall(r'\{\\pict([^}]+)\}', raw))
        hex = re.compile(r'[^a-fA-F0-9]')
        encs = [hex.sub('', pict) for pict in picts]

        count = 0
        imap = {}
        for enc in encs:
            if len(enc) % 2 == 1:
                enc = enc[:-1]
            data = enc.decode('hex')
            fmt = imghdr.what(None, data)
            if fmt is None:
                fmt = 'wmf'
            count += 1
            name = '%04d.%s' % (count, fmt)
            with open(name, 'wb') as f:
                f.write(data)
            imap[count] = name
            #open(name+'.hex', 'wb').write(enc)
        return self.convert_images(imap)

    def convert_images(self, imap):
        self.default_img = None
        for count, val in imap.iteritems():
            try:
                imap[count] = self.convert_image(val)
            except:
                self.log.exception('Failed to convert', val)
        return imap

    def convert_image(self, name):
        if not name.endswith('.wmf'):
            return name
        try:
            return self.rasterize_wmf(name)
        except:
            self.log.exception('Failed to convert WMF image %r'%name)
        return self.replace_wmf(name)

    def replace_wmf(self, name):
        from calibre.ebooks import calibre_cover
        if self.default_img is None:
            self.default_img = calibre_cover('Conversion of WMF images is not supported',
            'Use Microsoft Word or OpenOffice to save this RTF file'
            ' as HTML and convert that in calibre.', title_size=36,
            author_size=20)
        name = name.replace('.wmf', '.jpg')
        with open(name, 'wb') as f:
            f.write(self.default_img)
        return name

    def rasterize_wmf(self, name):
        from calibre.utils.wmf.parse import wmf_unwrap
        with open(name, 'rb') as f:
            data = f.read()
        data = wmf_unwrap(data)
        name = name.replace('.wmf', '.png')
        with open(name, 'wb') as f:
            f.write(data)
        return name


    def write_inline_css(self, ic, border_styles):
        font_size_classes = ['span.fs%d { font-size: %spt }'%(i, x) for i, x in
                enumerate(ic.font_sizes)]
        color_classes = ['span.col%d { color: %s }'%(i, x) for i, x in
                enumerate(ic.colors)]
        css = textwrap.dedent('''
        span.none {
            text-decoration: none; font-weight: normal;
            font-style: normal; font-variant: normal
        }

        span.italics { font-style: italic }

        span.bold { font-weight: bold }

        span.small-caps { font-variant: small-caps }

        span.underlined { text-decoration: underline }

        span.strike-through { text-decoration: line-through }

        ''')
        css += '\n'+'\n'.join(font_size_classes)
        css += '\n' +'\n'.join(color_classes)

        for cls, val in border_styles.iteritems():
            css += '\n\n.%s {\n%s\n}'%(cls, val)

        with open('styles.css', 'ab') as f:
            f.write(css)

    def convert_borders(self, doc):
        border_styles = []
        style_map = {}
        for elem in doc.xpath(r'//*[local-name()="cell"]'):
            style = ['border-style: hidden', 'border-width: 1px',
                    'border-color: black']
            for x in ('bottom', 'top', 'left', 'right'):
                bs = elem.get('border-cell-%s-style'%x, None)
                if bs:
                    cbs = border_style_map.get(bs, 'solid')
                    style.append('border-%s-style: %s'%(x, cbs))
                bw = elem.get('border-cell-%s-line-width'%x, None)
                if bw:
                    style.append('border-%s-width: %spt'%(x, bw))
                bc = elem.get('border-cell-%s-color'%x, None)
                if bc:
                    style.append('border-%s-color: %s'%(x, bc))
            style = ';\n'.join(style)
            if style not in border_styles:
                border_styles.append(style)
            idx = border_styles.index(style)
            cls = 'border_style%d'%idx
            style_map[cls] = style
            elem.set('class', cls)
        return style_map

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.metadata.meta import get_metadata
        from calibre.ebooks.metadata.opf2 import OPFCreator
        from calibre.ebooks.rtf2xml.ParseRtf import RtfInvalidCodeException
        self.opts = options
        self.log = log
        self.log('Converting RTF to XML...')
        try:
            xml = self.generate_xml(stream.name)
        except RtfInvalidCodeException, e:
            raise ValueError(_('This RTF file has a feature calibre does not '
            'support. Convert it to HTML first and then try it.\n%s')%e)

        d = glob.glob(os.path.join('*_rtf_pict_dir', 'picts.rtf'))
        if d:
            imap = {}
            try:
                imap = self.extract_images(d[0])
            except:
                self.log.exception('Failed to extract images...')

        self.log('Parsing XML...')
        parser = etree.XMLParser(recover=True, no_network=True)
        doc = etree.fromstring(xml, parser=parser)
        border_styles = self.convert_borders(doc)
        for pict in doc.xpath('//rtf:pict[@num]',
                namespaces={'rtf':'http://rtf2xml.sourceforge.net/'}):
            num = int(pict.get('num'))
            name = imap.get(num, None)
            if name is not None:
                pict.set('num', name)

        self.log('Converting XML to HTML...')
        inline_class = InlineClass(self.log)
        styledoc = etree.fromstring(P('templates/rtf.xsl', data=True))
        extensions = { ('calibre', 'inline-class') : inline_class }
        transform = etree.XSLT(styledoc, extensions=extensions)
        result = transform(doc)
        html = 'index.xhtml'
        with open(html, 'wb') as f:
            res = transform.tostring(result)
            res = res[:100].replace('xmlns:html', 'xmlns') + res[100:]
            # Replace newlines inserted by the 'empty_paragraphs' option in rtf2xml with html blank lines
            res = re.sub('\s*<body>', '<body>', res)
            res = re.sub('(?<=\n)\n{2}',
                    u'<p>\u00a0</p>\n'.encode('utf-8'), res)
            f.write(res)
        self.write_inline_css(inline_class, border_styles)
        stream.seek(0)
        mi = get_metadata(stream, 'rtf')
        if not mi.title:
            mi.title = _('Unknown')
        if not mi.authors:
            mi.authors = [_('Unknown')]
        opf = OPFCreator(os.getcwd(), mi)
        opf.create_manifest([('index.xhtml', None)])
        opf.create_spine(['index.xhtml'])
        opf.render(open('metadata.opf', 'wb'))
        return os.path.abspath('metadata.opf')


