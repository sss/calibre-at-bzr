#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, re

from calibre.customize.conversion import (OutputFormatPlugin,
        OptionRecommendation)
from calibre.ptempfile import TemporaryDirectory
from calibre import CurrentDir
from calibre.constants import filesystem_encoding

block_level_tags = (
      'address',
      'body',
      'blockquote',
      'center',
      'dir',
      'div',
      'dl',
      'fieldset',
      'form',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'hr',
      'isindex',
      'menu',
      'noframes',
      'noscript',
      'ol',
      'p',
      'pre',
      'table',
      'ul',
      )


class EPUBOutput(OutputFormatPlugin):

    name = 'EPUB Output'
    author = 'Kovid Goyal'
    file_type = 'epub'

    options = set([
        OptionRecommendation(name='extract_to',
            help=_('Extract the contents of the generated EPUB file to the '
                'specified directory. The contents of the directory are first '
                'deleted, so be careful.')),

        OptionRecommendation(name='dont_split_on_page_breaks',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Turn off splitting at page breaks. Normally, input '
                    'files are automatically split at every page break into '
                    'two files. This gives an output ebook that can be '
                    'parsed faster and with less resources. However, '
                    'splitting is slow and if your source file contains a '
                    'very large number of page breaks, you should turn off '
                    'splitting on page breaks.'
                )
        ),

        OptionRecommendation(name='flow_size', recommended_value=260,
            help=_('Split all HTML files larger than this size (in KB). '
                'This is necessary as most EPUB readers cannot handle large '
                'file sizes. The default of %defaultKB is the size required '
                'for Adobe Digital Editions.')
        ),

        OptionRecommendation(name='no_default_epub_cover', recommended_value=False,
            help=_('Normally, if the input file has no cover and you don\'t'
            ' specify one, a default cover is generated with the title, '
            'authors, etc. This option disables the generation of this cover.')
        ),

        OptionRecommendation(name='no_svg_cover', recommended_value=False,
            help=_('Do not use SVG for the book cover. Use this option if '
                'your EPUB is going to be used on a device that does not '
                'support SVG, like the iPhone or the JetBook Lite. '
                'Without this option, such devices will display the cover '
                'as a blank page.')
        ),

        OptionRecommendation(name='preserve_cover_aspect_ratio',
            recommended_value=False, help=_(
            'When using an SVG cover, this option will cause the cover to scale '
            'to cover the available screen area, but still preserve its aspect ratio '
            '(ratio of width to height). That means there may be white borders '
            'at the sides or top and bottom of the image, but the image will '
            'never be distorted. Without this option the image may be slightly '
            'distorted, but there will be no borders.'
            )
        ),

        OptionRecommendation(name='epub_flatten', recommended_value=False,
            help=_('This option is needed only if you intend to use the EPUB'
                ' with FBReaderJ. It will flatten the file system inside the'
                ' EPUB, putting all files into the top level.')
        ),


        ])

    recommendations = set([('pretty_print', True, OptionRecommendation.HIGH)])



    def workaround_webkit_quirks(self): # {{{
        from calibre.ebooks.oeb.base import XPath
        for x in self.oeb.spine:
            root = x.data
            body = XPath('//h:body')(root)
            if body:
                body = body[0]

            if not hasattr(body, 'xpath'):
                continue

            for pre in XPath('//h:pre')(body):
                if not pre.text and len(pre) == 0:
                    pre.tag = 'div'
    # }}}

    def upshift_markup(self): # {{{
        'Upgrade markup to comply with XHTML 1.1 where possible'
        from calibre.ebooks.oeb.base import XPath, XML
        for x in self.oeb.spine:
            root = x.data
            if (not root.get(XML('lang'))) and (root.get('lang')):
               root.set(XML('lang'), root.get('lang'))
            body = XPath('//h:body')(root)
            if body:
                body = body[0]

            if not hasattr(body, 'xpath'):
                continue
            for u in XPath('//h:u')(root):
                u.tag = 'span'
                u.set('style', 'text-decoration:underline')
    # }}}

    def convert(self, oeb, output_path, input_plugin, opts, log):
        self.log, self.opts, self.oeb = log, opts, oeb

        if self.opts.epub_flatten:
            from calibre.ebooks.oeb.transforms.filenames import FlatFilenames
            FlatFilenames()(oeb, opts)
        else:
            from calibre.ebooks.oeb.transforms.filenames import UniqueFilenames
            UniqueFilenames()(oeb, opts)

        self.workaround_ade_quirks()
        self.workaround_webkit_quirks()
        self.upshift_markup()
        from calibre.ebooks.oeb.transforms.rescale import RescaleImages
        RescaleImages()(oeb, opts)

        from calibre.ebooks.oeb.transforms.split import Split
        split = Split(not self.opts.dont_split_on_page_breaks,
                max_flow_size=self.opts.flow_size*1024
                )
        split(self.oeb, self.opts)

        from calibre.ebooks.oeb.transforms.cover import CoverManager
        cm = CoverManager(
                no_default_cover=self.opts.no_default_epub_cover,
                no_svg_cover=self.opts.no_svg_cover,
                preserve_aspect_ratio=self.opts.preserve_cover_aspect_ratio)
        cm(self.oeb, self.opts, self.log)

        self.workaround_sony_quirks()

        if self.oeb.toc.count() == 0:
            self.log.warn('This EPUB file has no Table of Contents. '
                    'Creating a default TOC')
            first = iter(self.oeb.spine).next()
            self.oeb.toc.add(_('Start'), first.href)

        from calibre.ebooks.oeb.base import OPF
        identifiers = oeb.metadata['identifier']
        uuid = None
        for x in identifiers:
            if x.get(OPF('scheme'), None).lower() == 'uuid' or unicode(x).startswith('urn:uuid:'):
                uuid = unicode(x).split(':')[-1]
                break
        encrypted_fonts = getattr(input_plugin, 'encrypted_fonts', [])

        if uuid is None:
            self.log.warn('No UUID identifier found')
            from uuid import uuid4
            uuid = str(uuid4())
            oeb.metadata.add('identifier', uuid, scheme='uuid', id=uuid)

        if encrypted_fonts and not uuid.startswith('urn:uuid:'):
            # Apparently ADE requires this value to start with urn:uuid:
            # for some absurd reason, or it will throw a hissy fit and refuse
            # to use the obfuscated fonts.
            for x in identifiers:
                if unicode(x) == uuid:
                    x.content = 'urn:uuid:'+uuid

        with TemporaryDirectory(u'_epub_output') as tdir:
            from calibre.customize.ui import plugin_for_output_format
            metadata_xml = None
            extra_entries = []
            if self.is_periodical:
                if self.opts.output_profile.epub_periodical_format == 'sony':
                    from calibre.ebooks.epub.periodical import sony_metadata
                    metadata_xml, atom_xml = sony_metadata(oeb)
                    extra_entries = [(u'atom.xml', 'application/atom+xml', atom_xml)]
            oeb_output = plugin_for_output_format('oeb')
            oeb_output.convert(oeb, tdir, input_plugin, opts, log)
            opf = [x for x in os.listdir(tdir) if x.endswith('.opf')][0]
            self.condense_ncx([os.path.join(tdir, x) for x in os.listdir(tdir)\
                    if x.endswith('.ncx')][0])
            encryption = None
            if encrypted_fonts:
                encryption = self.encrypt_fonts(encrypted_fonts, tdir, uuid)

            from calibre.ebooks.epub import initialize_container
            with initialize_container(output_path, os.path.basename(opf),
                    extra_entries=extra_entries) as epub:
                epub.add_dir(tdir)
                if encryption is not None:
                    epub.writestr('META-INF/encryption.xml', encryption)
                if metadata_xml is not None:
                    epub.writestr('META-INF/metadata.xml',
                            metadata_xml.encode('utf-8'))
            if opts.extract_to is not None:
                from calibre.utils.zipfile import ZipFile
                if os.path.exists(opts.extract_to):
                    if os.path.isdir(opts.extract_to):
                        shutil.rmtree(opts.extract_to)
                    else:
                        os.remove(opts.extract_to)
                os.mkdir(opts.extract_to)
                with ZipFile(output_path) as zf:
                    zf.extractall(path=opts.extract_to)
                self.log.info('EPUB extracted to', opts.extract_to)

    def encrypt_fonts(self, uris, tdir, uuid): # {{{
        from binascii import unhexlify

        key = re.sub(r'[^a-fA-F0-9]', '', uuid)
        if len(key) < 16:
            raise ValueError('UUID identifier %r is invalid'%uuid)
        key = unhexlify((key + key)[:32])
        key = tuple(map(ord, key))
        paths = []
        with CurrentDir(tdir):
            paths = [os.path.join(*x.split('/')) for x in uris]
            uris = dict(zip(uris, paths))
            fonts = []
            for uri in list(uris.keys()):
                path = uris[uri]
                if isinstance(path, unicode):
                    path = path.encode(filesystem_encoding)
                if not os.path.exists(path):
                    uris.pop(uri)
                    continue
                self.log.debug('Encrypting font:', uri)
                with open(path, 'r+b') as f:
                    data = f.read(1024)
                    if len(data) >= 1024:
                        f.seek(0)
                        for i in range(1024):
                            f.write(chr(ord(data[i]) ^ key[i%16]))
                    else:
                        self.log.warn('Font', path, 'is invalid, ignoring')
                if not isinstance(uri, unicode):
                    uri = uri.decode('utf-8')
                fonts.append(u'''
                <enc:EncryptedData>
                    <enc:EncryptionMethod Algorithm="http://ns.adobe.com/pdf/enc#RC"/>
                    <enc:CipherData>
                    <enc:CipherReference URI="%s"/>
                    </enc:CipherData>
                </enc:EncryptedData>
                '''%(uri.replace('"', '\\"')))
            if fonts:
                    ans = '''<encryption
                    xmlns="urn:oasis:names:tc:opendocument:xmlns:container"
                    xmlns:enc="http://www.w3.org/2001/04/xmlenc#"
                    xmlns:deenc="http://ns.adobe.com/digitaleditions/enc">
                    '''
                    ans += (u'\n'.join(fonts)).encode('utf-8')
                    ans += '\n</encryption>'
                    return ans
    # }}}

    def condense_ncx(self, ncx_path):
        from lxml import etree
        if not self.opts.pretty_print:
            tree = etree.parse(ncx_path)
            for tag in tree.getroot().iter(tag=etree.Element):
                if tag.text:
                    tag.text = tag.text.strip()
                if tag.tail:
                    tag.tail = tag.tail.strip()
            compressed = etree.tostring(tree.getroot(), encoding='utf-8')
            open(ncx_path, 'wb').write(compressed)

    def workaround_ade_quirks(self): # {{{
        '''
        Perform various markup transforms to get the output to render correctly
        in the quirky ADE.
        '''
        from calibre.ebooks.oeb.base import XPath, XHTML, OEB_STYLES, barename, urlunquote

        stylesheet = None
        for item in self.oeb.manifest:
            if item.media_type.lower() in OEB_STYLES:
                stylesheet = item
                break

        # ADE cries big wet tears when it encounters an invalid fragment
        # identifier in the NCX toc.
        frag_pat = re.compile(r'[-A-Za-z0-9_:.]+$')
        for node in self.oeb.toc.iter():
            href = getattr(node, 'href', None)
            if hasattr(href, 'partition'):
                base, _, frag = href.partition('#')
                frag = urlunquote(frag)
                if frag and frag_pat.match(frag) is None:
                    self.log.warn(
                            'Removing invalid fragment identifier %r from TOC'%frag)
                    node.href = base

        for x in self.oeb.spine:
            root = x.data
            body = XPath('//h:body')(root)
            if body:
                body = body[0]

            if hasattr(body, 'xpath'):
                # remove <img> tags with empty src elements
                bad = []
                for x in XPath('//h:img')(body):
                    src = x.get('src', '').strip()
                    if src in ('', '#') or src.startswith('http:'):
                        bad.append(x)
                for img in bad:
                    img.getparent().remove(img)

                # Add id attribute to <a> tags that have name
                for x in XPath('//h:a[@name]')(body):
                    if not x.get('id', False):
                        x.set('id', x.get('name'))

                # Replace <br> that are children of <body> as ADE doesn't handle them
                for br in XPath('./h:br')(body):
                    if br.getparent() is None:
                        continue
                    try:
                        prior = br.itersiblings(preceding=True).next()
                        priortag = barename(prior.tag)
                        priortext = prior.tail
                    except:
                        priortag = 'body'
                        priortext = body.text
                    if priortext:
                        priortext = priortext.strip()
                    br.tag = XHTML('p')
                    br.text = u'\u00a0'
                    style = br.get('style', '').split(';')
                    style = filter(None, map(lambda x: x.strip(), style))
                    style.append('margin:0pt; border:0pt')
                    # If the prior tag is a block (including a <br> we replaced)
                    # then this <br> replacement should have a 1-line height.
                    # Otherwise it should have no height.
                    if not priortext and priortag in block_level_tags:
                        style.append('height:1em')
                    else:
                        style.append('height:0pt')
                    br.set('style', '; '.join(style))

            for tag in XPath('//h:embed')(root):
                tag.getparent().remove(tag)
            for tag in XPath('//h:object')(root):
                if tag.get('type', '').lower().strip() in ('image/svg+xml',):
                    continue
                tag.getparent().remove(tag)

            for tag in XPath('//h:title|//h:style')(root):
                if not tag.text:
                    tag.getparent().remove(tag)
            for tag in XPath('//h:script')(root):
                if not tag.text and not tag.get('src', False):
                    tag.getparent().remove(tag)
            for tag in XPath('//h:body/descendant::h:script')(root):
                tag.getparent().remove(tag)

            for tag in XPath('//h:form')(root):
                tag.getparent().remove(tag)

            for tag in XPath('//h:center')(root):
                tag.tag = XHTML('div')
                tag.set('style', 'text-align:center')
            # ADE can't handle &amp; in an img url
            for tag in XPath('//h:img[@src]')(root):
                tag.set('src', tag.get('src', '').replace('&', ''))

            # ADE whimpers in fright when it encounters a <td> outside a
            # <table>
            in_table = XPath('ancestor::h:table')
            for tag in XPath('//h:td|//h:tr|//h:th')(root):
                if not in_table(tag):
                    tag.tag = XHTML('div')

            special_chars = re.compile(u'[\u200b\u00ad]')
            for elem in root.iterdescendants():
                if getattr(elem, 'text', False):
                    elem.text = special_chars.sub('', elem.text)
                    elem.text = elem.text.replace(u'\u2011', '-')
                if getattr(elem, 'tail', False):
                    elem.tail = special_chars.sub('', elem.tail)
                    elem.tail = elem.tail.replace(u'\u2011', '-')

            if stylesheet is not None:
                # ADE doesn't render lists correctly if they have left margins
                from cssutils.css import CSSRule
                for lb in XPath('//h:ul[@class]|//h:ol[@class]')(root):
                    sel = '.'+lb.get('class')
                    for rule in stylesheet.data.cssRules.rulesOfType(CSSRule.STYLE_RULE):
                        if sel == rule.selectorList.selectorText:
                            rule.style.removeProperty('margin-left')
                            # padding-left breaks rendering in webkit and gecko
                            rule.style.removeProperty('padding-left')
                # Change whitespace:pre to pre-wrap to accommodate readers that
                # cannot scroll horizontally
                for rule in stylesheet.data.cssRules.rulesOfType(CSSRule.STYLE_RULE):
                    style = rule.style
                    ws = style.getPropertyValue('white-space')
                    if ws == 'pre':
                        style.setProperty('white-space', 'pre-wrap')

    # }}}

    def workaround_sony_quirks(self): # {{{
        '''
        Perform toc link transforms to alleviate slow loading.
        '''
        from calibre.ebooks.oeb.base import urldefrag, XPath

        def frag_is_at_top(root, frag):
            body = XPath('//h:body')(root)
            if body:
                body = body[0]
            else:
                return False
            tree = body.getroottree()
            elem = XPath('//*[@id="%s" or @name="%s"]'%(frag, frag))(root)
            if elem:
                elem = elem[0]
            else:
                return False
            path = tree.getpath(elem)
            for el in body.iterdescendants():
                epath = tree.getpath(el)
                if epath == path:
                    break
                if el.text and el.text.strip():
                    return False
                if not path.startswith(epath):
                    # Only check tail of non-parent elements
                    if el.tail and el.tail.strip():
                        return False
            return True

        def simplify_toc_entry(toc):
            if toc.href:
                href, frag = urldefrag(toc.href)
                if frag:
                    for x in self.oeb.spine:
                        if x.href == href:
                            if frag_is_at_top(x.data, frag):
                                self.log.debug('Removing anchor from TOC href:',
                                        href+'#'+frag)
                                toc.href = href
                            break
            for x in toc:
                simplify_toc_entry(x)

        if self.oeb.toc:
            simplify_toc_entry(self.oeb.toc)

    # }}}

