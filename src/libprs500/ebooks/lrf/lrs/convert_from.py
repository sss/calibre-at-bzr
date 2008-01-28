##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''
Compile a LRS file into a LRF file.
'''

import sys, os, logging

from libprs500 import __author__, __appname__, __version__, setup_cli_handlers
from libprs500.ebooks.BeautifulSoup import BeautifulStoneSoup, NavigableString, \
                                           CData, Tag
from libprs500.ebooks.lrf.pylrs.pylrs import Book, PageStyle, TextStyle, \
            BlockStyle, ImageStream, Font, StyleDefault, BookSetting, Header, \
            Image, ImageBlock, Page, TextBlock, Canvas, Paragraph, CR, Span, \
            Italic, Sup, Sub, Bold, EmpLine, JumpButton, CharButton, Plot, \
            DropCaps, Footer, RuledLine

class LrsParser(object):
    
    SELF_CLOSING_TAGS = [i.lower() for i in ['CR', 'Plot', 'NoBR', 'Space', 
                         'PutObj', 'RuledLine', 
                         'Plot', 'SetDefault', 'BookSetting', 'RegistFont',
                         'PageStyle', 'TextStyle', 'BlockStyle', 'JumpTo',
                         'ImageStream', 'Image']]
    
    def __init__(self, stream, logger):
        self.logger = logger
        src = stream.read()
        self.soup = BeautifulStoneSoup(src, selfClosingTags=self.SELF_CLOSING_TAGS)
        self.objects = {}
        for obj in self.soup.findAll(objid=True):
            self.objects[obj['objid']] = obj
        
        self.parsed_objects = {}
        self.first_pass()
        self.second_pass()
        self.third_pass()
        self.fourth_pass()
        self.fifth_pass()
    
    def fifth_pass(self):
        for tag in self.soup.findAll(['canvas', 'header', 'footer']):
            canvas = self.parsed_objects[tag.get('objid')]
            for po in tag.findAll('putobj'):
                canvas.put_object(self.parsed_objects[po.get('refobj')],
                                  po.get('x1'), po.get('y1'))
            
    
    @classmethod
    def attrs_to_dict(cls, tag, exclude=('objid',)):
        result = {}
        for key, val in tag.attrs:
            if key in exclude:
                continue
            result[str(key)] = val
        return result
    
    def text_tag_to_element(self, tag):
        map = {
               'span'    : Span,
               'italic'  : Italic,
               'bold'    : Bold,
               'empline' : EmpLine,
               'sup'     : Sup,
               'sub'     : Sub,
               'cr'      : CR,
               'drawchar': DropCaps,
               }
        if tag.name == 'charbutton':
            return CharButton(self.parsed_objects[tag.get('refobj')], None)
        if tag.name == 'plot':
            return Plot(self.parsed_objects[tag.get('refobj')], **self.attrs_to_dict(tag, ['refobj']))
        return map[tag.name](**self.attrs_to_dict(tag))
    
    def process_text_element(self, tag, elem):
        for item in tag.contents:
            if isinstance(item, NavigableString):
                elem.append(item.string)
            else:
                subelem = self.text_tag_to_element(item)
                elem.append(subelem)
                self.process_text_element(item, subelem)
        
    
    def process_paragraph(self, tag):
        p = Paragraph()
        contents = [i for i in tag.contents]
        if contents:
            if isinstance(contents[0], NavigableString):
                contents[0] = contents[0].string.lstrip()
            for item in contents:
                if isinstance(item, basestring):
                    p.append(item)
                elif isinstance(item, NavigableString):
                    p.append(item.string)
                else:
                    elem = self.text_tag_to_element(item)
                    p.append(elem)
                    self.process_text_element(item, elem)
        return p
    
    def process_text_block(self, tag):
        tb = self.parsed_objects[tag.get('objid')]
        for item in tag.contents:
            if hasattr(item, 'name'):
                if item.name == 'p':
                    tb.append(self.process_paragraph(item))
                elif item.name == 'cr':
                    tb.append(CR())
            
    def fourth_pass(self):
        for tag in self.soup.findAll('page'):
            page = self.parsed_objects[tag.get('objid')]
            self.book.append(page)
            for block_tag in tag.findAll(['canvas', 'imageblock', 'textblock', 'ruledline']):
                if block_tag.name == 'ruledline':
                    page.append(RuledLine(**self.attrs_to_dict(block_tag)))
                else:
                    page.append(self.parsed_objects[block_tag.get('objid')])
                
        for tag in self.soup.find('objects').findAll('button'):
            jt = tag.find('jumpto')
            tb = self.parsed_objects[jt.get('refobj')]
            jb = JumpButton(tb)
            self.book.append(jb)
            self.parsed_objects[tag.get('objid')] = jb
        
        for tag in self.soup.findAll('textblock'):
            self.process_text_block(tag)
        
        toc = self.soup.find('toc')
        if toc:
            for tag in toc.findAll('toclabel'):
                label = self.tag_to_string(tag).encode('ascii', 'ignore') # Bug in SONY reader software cant handle non ascii toc labels
                self.book.addTocEntry(label, self.parsed_objects[tag.get('refobj')])
                
    
    def third_pass(self):
        map = {
               'page'       : (Page, ['pagestyle', 'evenfooterid', 'oddfooterid', 'evenheaderid', 'oddheaderid']),
               'textblock'  : (TextBlock, ['textstyle', 'blockstyle']),
               'imageblock' : (ImageBlock, ['blockstyle', 'refstream']),
               'image'      : (Image, ['refstream']),
               'canvas'     : (Canvas, ['canvaswidth', 'canvasheight']),
               }
        attrmap = {
                   'pagestyle'  : 'pageStyle',
                   'blockstyle' : 'blockStyle',
                   'textstyle'  : 'textStyle',
                   }
        for id, tag in self.objects.items():
            if tag.name in map.keys():
                settings = self.attrs_to_dict(tag, map[tag.name][1]+['objid', 'objlabel'])
                for a in ('pagestyle', 'blockstyle', 'textstyle'):
                    if tag.has_key(a):
                        settings[attrmap[a]] = self.parsed_objects[tag.get(a)]
                for a in ('evenfooterid', 'oddfooterid', 'evenheaderid', 'oddheaderid'):
                    if tag.has_key(a):
                        settings[a.replace('id', '')] = self.parsed_objects[tag.get(a)]
                args = []
                if tag.has_key('refstream'):
                    args.append(self.parsed_objects[tag.get('refstream')])
                if tag.has_key('canvaswidth'):
                    args += [tag.get('canvaswidth'), tag.get('canvasheight')]
                self.parsed_objects[id] = map[tag.name][0](*args, **settings)
                
        
    
    def second_pass(self):
        map = {
               'pagestyle'  : (PageStyle, ['stylelabel', 'evenheaderid', 'oddheaderid', 'evenfooterid', 'oddfooterid']),
               'textstyle'  : (TextStyle, ['stylelabel', 'rubyalignandadjust']),
               'blockstyle' : (BlockStyle, ['stylelabel']),
               'imagestream': (ImageStream, ['imagestreamlabel']),
               'registfont' : (Font, [])
               }
        for id, tag in self.objects.items():
            if tag.name in map.keys():
                settings = self.attrs_to_dict(tag, map[tag.name][1]+['objid'])
                if tag.name == 'pagestyle':
                    for a in ('evenheaderid', 'oddheaderid', 'evenfooterid', 'oddfooterid'):
                        if tag.has_key(a):
                            settings[a.replace('id', '')] = self.parsed_objects[tag.get(a)]
                self.parsed_objects[id] = map[tag.name][0](**settings)
                if tag.name == 'registfont':
                    self.book.append(self.parsed_objects[id])
                    
        
    @classmethod
    def tag_to_string(cls, tag):
        '''
        Convenience method to take a BeautifulSoup Tag and extract the text from it
        recursively.
        @return: A unicode (possibly empty) object
        '''
        if not tag:
            return ''
        strings = []
        for item in tag.contents:
            if isinstance(item, (NavigableString, CData)):
                strings.append(item.string)
            elif isinstance(item, Tag):
                res = cls.tag_to_string(item)
                if res:
                    strings.append(res)
        return u''.join(strings)     
    
    def first_pass(self):
        info = self.soup.find('bbebxylog').find('bookinformation').find('info')
        bookinfo = info.find('bookinfo')
        docinfo  = info.find('docinfo')
        
        def me(base, tagname):
            tag = base.find(tagname.lower())
            tag = (self.tag_to_string(tag), tag.get('reading') if tag.has_key('reading') else '')
            return tag
            
        title          = me(bookinfo, 'Title')
        author         = me(bookinfo, 'Author')
        publisher      = me(bookinfo, 'Publisher')
        category       = me(bookinfo, 'Category')[0]
        classification = me(bookinfo, 'Classification')[0]
        freetext       = me(bookinfo, 'FreeText')[0]
        language       = me(docinfo, 'Language')[0]
        creator        = me(docinfo, 'Creator')[0]
        producer       = me(docinfo, 'Producer')[0]
        bookid         = me(bookinfo, 'BookID')[0]
        
        sd = self.soup.find('setdefault')
        sd = StyleDefault(**self.attrs_to_dict(sd, ['page_tree_id', 'rubyalignandadjust']))
        bs = self.soup.find('booksetting')
        bs = BookSetting(**self.attrs_to_dict(bs, []))
        
        self.book = Book(title=title, author=author, publisher=publisher,
                         category=category, classification=classification,
                         freetext=freetext, language=language, creator=creator,
                         producer=producer, bookid=bookid, setdefault=sd,
                         booksetting=bs)
        
        for hdr in self.soup.findAll(['header', 'footer']):
            elem = Header if hdr.name == 'header' else Footer
            self.parsed_objects[hdr.get('objid')] = elem(**self.attrs_to_dict(hdr))    
        
    def render(self, file, to_lrs=False):
        if to_lrs:
            self.book.renderLrs(file, 'utf-8')
        else:
            self.book.renderLrf(file)
        

def option_parser():
    from optparse import OptionParser
    parser = OptionParser(usage='%prog [options] file.lrs', 
                          version=__appname__+ ' ' + __version__, 
                          epilog='Created by '+__author__)
    parser.add_option('-o', '--output', default=None, help='Path to output file')
    parser.add_option('--verbose', default=False, action='store_true',
                      help='Verbose processing')
    parser.add_option('--lrs', default=False, action='store_true',
                      help='Convert LRS to LRS, useful for debugging.')
    return parser


def main(args=sys.argv, logger=None):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if logger is None:
        level = logging.DEBUG if opts.verbose else logging.INFO
        logger = logging.getLogger('lrs2lrf')
        setup_cli_handlers(logger, level)
    
    if len(args) != 2:
        parser.print_help()
        return 1
    if not opts.output:
        ext = '.lrs' if opts.lrs else '.lrf'
        opts.output = os.path.splitext(os.path.basename(args[1]))[0]+ext
    opts.output = os.path.abspath(opts.output)
    if opts.verbose:
        import warnings
        warnings.defaultaction = 'error'
    
    logger.info('Parsing LRS file...')
    converter =  LrsParser(open(args[1], 'rb'), logger)
    logger.info('Writing to output file...')
    converter.render(opts.output, to_lrs=opts.lrs)
    logger.info('Output written to '+opts.output)
    return 0


if __name__ == '__main__':
    sys.exit(main())