##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
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
import struct, array, zlib, cStringIO

from libprs500.ebooks.lrf import LRFParseError
from libprs500.ebooks.lrf.tags import Tag

ruby_tags = {
        0xF575: ['rubyAlignAndAdjust', 'W'],
        0xF576: ['rubyoverhang', 'W', {0: 'none', 1:'auto'}],
        0xF577: ['empdotsposition', 'W', {1: 'before', 2:'after'}],
        0xF578: ['','parse_empdots'],
        0xF579: ['emplineposition', 'W', {1: 'before', 2:'after'}],
        0xF57A: ['emplinetype', 'W', {0: 'none', 0x10: 'solid', 0x20: 'dashed', 0x30: 'double', 0x40: 'dotted'}]
}

class LRFObject(object):
    
    tag_map = {
        0xF500: ['', ''],
        0xF502: ['infoLink', 'D'],
        0xF501: ['', ''],
    }
    
    @classmethod
    def descramble_buffer(cls, buf, l, xorKey):
        i = 0
        a = array.array('B',buf)
        while l>0:
            a[i] ^= xorKey
            i+=1
            l-=1
        return a.tostring()

    @classmethod
    def parse_empdots(self, tag, f):
        self.refEmpDotsFont, self.empDotsFontName, self.empDotsCode = tag.contents
        
    @staticmethod
    def tag_to_val(h, obj, tag, stream):
        if h[1] == 'D':
            val = tag.dword
        elif h[1] == 'W':
            val = tag.word
        elif h[1] == 'w':
            val = tag.word
            if val > 0x8000: 
                val -= 0x10000
        elif h[1] == 'B':
            val = tag.byte
        elif h[1] == 'P':
            val = tag.contents
        elif h[1] != '':
            val = getattr(obj, h[1])(tag, stream)
        if len(h) > 2:
            val = h[2](val) if callable(h[2]) else h[2][val]
        return val
    
    def __init__(self, document, stream, id, scramble_key, boundary):
        self._scramble_key = scramble_key
        self._document = document
        self.id = id
                
        while stream.tell() < boundary:
            tag = Tag(stream)
            self.handle_tag(tag, stream)
            
    def parse_bg_image(self, tag, f):
        self.bg_image_mode, self.bg_image_id = struct.unpack("<HI", tag.contents)
    
    def handle_tag(self, tag, stream, tag_map=None):
        if tag_map is None:
            tag_map = self.__class__.tag_map             
        if tag.id in tag_map:
            h = tag_map[tag.id]
            val = LRFObject.tag_to_val(h, self, tag, stream)
            if h[1] != '' and h[0] != '':
                setattr(self, h[0], val)
        else:    
            raise LRFParseError("Unknown tag in %s: %s" % (self.__class__.__name__, str(tag)))
        
    def __iter__(self):
        for i in range(0):
            yield i
        
    def __unicode__(self):
        return unicode(self.__class__.__name__)
        
    def __str__(self):
        return unicode(self).encode('utf-8')

class LRFContentObject(LRFObject):
    
    tag_map = {}
    
    def __init__(self, bytes, objects):
        self.stream = bytes if hasattr(bytes, 'read') else cStringIO.StringIO(bytes)
        length = self.stream_size()
        self.objects = objects
        self._contents = []
        self.current = 0
        self.in_container = True
        self.parse_stream(length)
        
    def parse_stream(self, length):    
        while self.in_container and self.stream.tell() < length:
            tag = Tag(self.stream)
            self.handle_tag(tag)
            
    def stream_size(self):
        pos = self.stream.tell()
        self.stream.seek(0, 2)
        size = self.stream.tell()
        self.stream.seek(pos)
        return size
            
    def handle_tag(self, tag):
        if tag.id in self.tag_map:
            action = self.tag_map[tag.id]
            if isinstance(action, basestring):
                func, args = action, tuple([])
            else:
                func, args = action[0], (action[1],)
            getattr(self, func)(tag, *args)
        else:
            raise LRFParseError("Unknown tag in %s: %s" % (self.__class__.__name__, str(tag)))
        
    def __iter__(self):
        for i in self._contents:
            yield i
        
    

    
class LRFStream(LRFObject):
    tag_map = {
        0xF504: ['', 'read_stream_size'],
        0xF554: ['stream_flags', 'W'],
        0xF505: ['', 'read_stream'],
        0xF506: ['', 'end_stream'],
      }
    tag_map.update(LRFObject.tag_map)
    
    def __init__(self, document, stream, id, scramble_key, boundary):
        self.stream = ''
        self.stream_size = 0
        self.stream_read = False
        LRFObject.__init__(self, document, stream, id, scramble_key, boundary)
        
    def read_stream_size(self, tag, stream):
        self.stream_size = tag.dword
        
    def end_stream(self, tag, stream):
        self.stream_read = True
    
    def read_stream(self, tag, stream):
        if self.stream_read:
            raise LRFParseError('There can be only one stream per object')
        if not hasattr(self, 'stream_flags'):
            raise LRFParseError('Stream flags not initialized')
        self.stream = stream.read(self.stream_size)
        if self.stream_flags & 0x200 !=0:
            l = len(self.stream);
            key = l % self._scramble_key + 0xF;
            if l > 0x400 and (isinstance(self, ImageStream) or isinstance(self, Font) or isinstance(self, SoundStream)):
                l = 0x400;
            self.stream = self.descramble_buffer(self.stream, l, key)
        if self.stream_flags & 0x100 !=0:
            decomp_size = struct.unpack("<I", self.stream[:4])[0]
            self.stream = zlib.decompress(self.stream[4:])
            if len(self.stream) != decomp_size:
                raise LRFParseError("Stream decompressed size is wrong!")
        if stream.read(2) != '\x06\xF5':
            print "Warning: corrupted end-of-stream tag at %08X; skipping it"%stream.tell()-2
        self.end_stream(None, None)


class PageTree(LRFObject):
    tag_map = {
        0xF55C: ['_contents', 'P'],
      }
    tag_map.update(LRFObject.tag_map)
    
    def __iter__(self):
        for id in self._contents:
            yield self._document.objects[id]

class StyleObject(object):
    
    def _tags_to_xml(self):
        s = u''
        for h in self.tag_map.values():
            attr = h[0]
            if hasattr(self, attr):
                s += u'%s="%s" '%(attr, getattr(self, attr))
        return s
    
    def __unicode__(self):
        s = u'<%s objid="%s" stylelabel="%s" '%(self.__class__.__name__.replace('Attr', 'Style'), self.id, self.id)
        s += self._tags_to_xml()
        s += u'/>\n'
        return s
    
    def as_dict(self):
        d = {}
        for h in self.tag_map.values():
            attr = h[0]
            if hasattr(self, attr):
                d[attr] = getattr(self, attr)
        return d

class PageAttr(StyleObject, LRFObject):
    tag_map = {
        0xF507: ['oddheaderid', 'D'],
        0xF508: ['evenheaderid', 'D'],
        0xF509: ['oddfooterid', 'D'],
        0xF50A: ['evenfooterid', 'D'],
        0xF521: ['topmargin', 'W'],
        0xF522: ['headheight', 'W'],
        0xF523: ['headsep', 'W'],
        0xF524: ['oddsidemargin', 'W'],
        0xF52C: ['evensidemargin', 'W'],
        0xF525: ['textheight', 'W'],
        0xF526: ['textwidth', 'W'],
        0xF527: ['footspace', 'W'],
        0xF528: ['footheight', 'W'],
        0xF535: ['layout', 'W', {0x41: 'TbRl', 0x34: 'LrTb'}],
        0xF52B: ['pageposition', 'W', {0: 'any', 1:'upper', 2: 'lower'}],
        0xF52A: ['setemptyview', 'W', {1: 'show', 0: 'empty'}],
        0xF5DA: ['setwaitprop', 'W', {1: 'replay', 2: 'noreplay'}],
        0xF529: ['', "parse_bg_image"],
      }
    tag_map.update(LRFObject.tag_map)


class Color(object):
    def __init__(self, val):
        self.a, self.r, self.g, self.b = val & 0xFF, (val>>8)&0xFF, (val>>16)&0xFF, (val>>24)&0xFF
        
    def __unicode__(self):
        return u'0x%02x%02x%02x%02x'%(self.a, self.r, self.g, self.b)
    
    def __str__(self):
        return unicode(self)
    
    def __len__(self): 
        return 4
    
    def __getitem__(self, i): # Qt compatible ordering and values
        return (self.r, self.g, self.b, 0xff-self.a)[i] # In Qt 0xff is opaque while in LRS 0x00 is opaque
    

class EmptyPageElement(object):
    def __iter__(self):
        for i in range(0):
            yield i
        
    def __str__(self):
        return unicode(self)

class PageDiv(EmptyPageElement):
    
    def __init__(self, pain, spacesize, linewidth, linecolor):
        self.pain, self.spacesize, self.linewidth = pain, spacesize, linewidth
        self.linecolor = Color(linecolor)
        
    def __unicode__(self):
        return u'\n<PageDiv pain="%s" spacesize="%s" linewidth="%s" linecolor="%s" />\n'%\
                (self.pain, self.spacesize, self.linewidth, self.color)
        
        
class RuledLine(EmptyPageElement):
    
    linetype_map = {0x00: 'none', 0x10: 'solid', 0x20: 'dashed', 0x30: 'double', 0x40: 'dotted', 0x13: 'unknown13'}
    
    def __init__(self, linelength, linetype, linewidth, linecolor):
        self.linelength, self.linewidth = linelength, linewidth
        self.linetype = self.linetype_map[linetype]
        self.linecolor = Color(linecolor)
        self.id = -1
        
    def __unicode__(self):
        return u'\n<RuledLine linelength="%s" linetype="%s" linewidth="%s" linecolor="%s" />\n'%\
                (self.linelength, self.linetype, self.linewidth, self.linecolor)
                
class Wait(EmptyPageElement):
    
    def __init__(self, time):
        self.time = time
        
    def __unicode__(self):
        return u'\n<Wait time="%d" />\n'%(self.time)
        
class Locate(EmptyPageElement):
    
    pos_map = {1:'bottomleft', 2:'bottomright',3:'topright',4:'topleft', 5:'base'}
    
    def __init__(self, pos):
        self.pos = self.pos_map[pos]
        
    def __unicode__(self):
        return u'\n<Locate pos="%s" />\n'%(self.pos)
        
class BlockSpace(EmptyPageElement):
    
    def __init__(self, xspace, yspace):
        self.xsace, self.yspace = xspace, yspace
        
    def __unicode__(self):
        return u'\n<BlockSpace xspace="%d" yspace="%d" />\n'%\
                (self.xspace, self.ysapce)

class Page(LRFStream):
    tag_map = {
        0xF503: ['style_id', 'D'],
        0xF50B: ['obj_list', 'P'],
        0xF571: ['', ''],
        0xF57C: ['parent_page_tree','D'],
      }
    tag_map.update(PageAttr.tag_map)
    tag_map.update(LRFStream.tag_map)
    style = property(fget=lambda self : self._document.objects[self.style_id])
    evenheader = property(fget=lambda self : self._document.objects[self.style.evenheaderid])
    evenfooter = property(fget=lambda self : self._document.objects[self.style.evenfooterid])
    oddheader  = property(fget=lambda self : self._document.objects[self.style.oddheaderid])
    oddfooter  = property(fget=lambda self : self._document.objects[self.style.oddfooterid])
    
    class Content(LRFContentObject):
        tag_map = {
           0xF503: 'link',
           0xF54E: 'page_div',
           0xF547: 'x_space',
           0xF546: 'y_space',
           0xF548: 'pos',
           0xF573: 'ruled_line',
           0xF5D4: 'wait',
           0xF5D6: 'sound_stop',
          }
        
        def __init__(self, bytes, objects):
            self.in_blockspace = False
            LRFContentObject.__init__(self, bytes, objects)
        
        def link(self, tag):
            self.close_blockspace()
            self._contents.append(self.objects[tag.dword])
            
        def page_div(self, tag):
            self.close_blockspace()
            pars = struct.unpack("<HIHI", tag.contents)
            self._contents.append(PageDiv(*pars))
            
        def x_space(self, tag):
            self.xspace = tag.word
            self.in_blockspace = True
            
        def y_space(self, tag):
            self.yspace = tag.word
            self.in_blockspace = True
            
        def pos(self, tag):
            self.pos = tag.wordself.pos_map[tag.word]
            self.in_blockspace = True
            
        def ruled_line(self, tag):
            self.close_blockspace()
            pars = struct.unpack("<HHHI", tag.contents)
            self._contents.append(RuledLine(*pars))
            
        def wait(self, tag):
            self.close_blockspace()
            self._contents.append(Wait(tag.word))
            
        def sound_stop(self, tag):
            self.close_blockspace()
            
        def close_blockspace(self):
            if self.in_blockspace:
                if hasattr(self, 'pos'):
                    self._contents.append(Locate(self.pos))
                    delattr(self, 'pos')
                else:
                    xspace = self.xspace if hasattr(self, 'xspace') else 0
                    yspace = self.yspace if hasattr(self, 'yspace') else 0
                    self._contents.append(BlockSpace(xspace, yspace))
                    if hasattr(self, 'xspace'): delattr(self, 'xspace')
                    if hasattr(self, 'yspace'): delattr(self, 'yspace')
    
    def header(self, odd):
        id = self._document.objects[self.style_id].oddheaderid if odd else self._document.objects[self.style_id].evenheaderid
        return self._document.objects[id]
    
    def footer(self, odd):
        id = self._document.objects[self.style_id].oddfooterid if odd else self._document.objects[self.style_id].evenfooterid
        return self._document.objects[id]
    
    def initialize(self):
        self.content = Page.Content(self.stream, self._document.objects)
    
    def __iter__(self):
        for i in self.content:
            yield i
        
    def __unicode__(self):
        s = u'\n<Page pagestyle="%d" objid="%d">\n'%(self.style_id, self.id)
        for i in self:
            s += unicode(i)
        s += '\n</Page>\n'
        return s
    
    def __str__(self):
        return unicode(self)
    
    

class BlockAttr(StyleObject, LRFObject):
    tag_map = {
        0xF531: ['blockwidth', 'W'],
        0xF532: ['blockheight', 'W'],
        0xF533: ['blockrule', 'W', {0x14: "horz-fixed", 0x12: "horz-adjustable", 0x41: "vert-fixed", 0x21: "vert-adjustable", 0x44: "block-fixed", 0x22: "block-adjustable"}],
        0xF534: ['bgcolor', 'D', Color],
        0xF535: ['layout', 'W', {0x41: 'TbRl', 0x34: 'LrTb'}],
        0xF536: ['framewidth', 'W'],
        0xF537: ['framecolor', 'D', Color],
        0xF52E: ['framemode', 'W', {0: 'none', 2: 'curve', 1:'square'}],
        0xF538: ['topskip', 'W'],
        0xF539: ['sidemargin', 'W'],
        0xF53A: ['footskip', 'W'],
        0xF529: ['', 'parse_bg_image'],
      }
    tag_map.update(LRFObject.tag_map)

class TextAttr(StyleObject, LRFObject):
    tag_map = {
        0xF511: ['fontsize', 'w'],
        0xF512: ['fontwidth', 'w'],
        0xF513: ['fontescapement', 'w'],
        0xF514: ['fontorientation', 'w'],
        0xF515: ['fontweight', 'W'],
        0xF516: ['fontfacename', 'P'],
        0xF517: ['textcolor', 'D', Color],
        0xF518: ['textbgcolor', 'D', Color],
        0xF519: ['wordspace', 'w'],
        0xF51A: ['letterspace', 'w'],
        0xF51B: ['baselineskip', 'w'],
        0xF51C: ['linespace', 'w'],
        0xF51D: ['parindent', 'w'],
        0xF51E: ['parskip', 'w'],
        0xF53C: ['align', 'W', {1: 'head', 4: 'center', 8: 'foot'}],
        0xF53D: ['column', 'W'],
        0xF53E: ['columnsep', 'W'],
        0xF5DD: ['charspace', 'w'],
        0xF5F1: ['textlinewidth', 'W'],
        0xF5F2: ['linecolor', 'D', Color],
      }
    tag_map.update(ruby_tags)
    tag_map.update(LRFObject.tag_map)


class Block(LRFStream):
    tag_map = {
        0xF503: ['style_id', 'D'],
      }
    tag_map.update(BlockAttr.tag_map)
    tag_map.update(TextAttr.tag_map)
    tag_map.update(LRFStream.tag_map)
    extra_attrs = [i[0] for i in BlockAttr.tag_map.values()]
    extra_attrs.extend([i[0] for i in TextAttr.tag_map.values()])
    
    style = property(fget=lambda self : self._document.objects[self.style_id])
    textstyle = property(fget=lambda self : self._document.objects[self.textstyle_id])
    
    def initialize(self):
        self.attrs = {}
        stream = cStringIO.StringIO(self.stream)
        tag = Tag(stream)
        if tag.id != 0xF503:
            raise LRFParseError("Bad block content")
        obj = self._document.objects[tag.dword]
        if isinstance(obj, SimpleText):
            self.name = 'SimpleTextBlock'
            self.textstyle_id = obj.style_id
        elif isinstance(obj, Text):
            self.name = 'TextBlock'
            self.textstyle_id = obj.style_id 
        elif isinstance(obj, Image):
            self.name = 'ImageBlock'
            for attr in ('x0', 'x1', 'y0', 'y1', 'xsize', 'ysize', 'refstream'):
                self.attrs[attr] = getattr(obj, attr)
            self.refstream = self._document.objects[self.attrs['refstream']]
        elif isinstance(obj, Button):
            self.name = 'ButtonBlock'
        else:
            raise LRFParseError("Unexpected block type: "+obj.__class__.__name__)
            
        self.content = obj
        
        
        for attr in self.extra_attrs:
            if hasattr(self, attr):
                self.attrs[attr] = getattr(self, attr)
        
    def __iter__(self):
        try:
            for i in iter(self.content):
                yield i
        except TypeError:
            yield self.content
        
    def __unicode__(self):
        s = u'\n<%s objid="%d" blockstyle="%d" '%(self.name, self.id, self.style_id)
        if hasattr(self, 'textstyle_id'):
            s += 'textstyle="%d" '%(self.textstyle_id,)
        for attr in self.attrs:
            s += '%s="%s" '%(attr, self.attrs[attr])
        s = s.rstrip()+'>\n'
        if self.name != 'ImageBlock':
            for i in self:
                s += unicode(i)
        s += '</%s>\n'%(self.name,)
        return s
        

class MiniPage(LRFStream):
    tag_map = {
        0xF541: ['minipagewidth', 'W'],
        0xF542: ['minipageheight', 'W'],
      }
    tag_map.update(LRFStream.tag_map)
    tag_map.update(BlockAttr.tag_map)

class Text(LRFStream):
    tag_map = {
        0xF503: ['style_id', 'D'],
      }
    tag_map.update(TextAttr.tag_map)
    tag_map.update(LRFStream.tag_map)
    
    style = property(fget=lambda self : self._document.objects[self.style_id])
    
    class Content(LRFContentObject):
        tag_map = {
           0xF581: ['simple_container', 'Italic'],
           0xF582: 'end_container',
           0xF5B1: ['simple_container', 'Yoko'],
           0xF5B2: 'end_container',
           0xF5B3: ['simple_container', 'Tate'],
           0xF5B4: 'end_container',
           0xF5B5: ['simple_container', 'Nekase'],
           0xF5B6: 'end_container',
           0xF5A1: 'start_para',
           0xF5A2: 'end_para',
           0xF5A7: 'char_button',
           0xF5A8: 'end_container',
           0xF5A9: ['simple_container', 'Rubi'],
           0xF5AA: 'end_container',
           0xF5AB: ['simple_container', 'Oyamoji'],
           0xF5AC: 'end_container',
           0xF5AD: ['simple_container', 'Rubimoji'],
           0xF5AE: 'end_container',
           0xF5B7: ['simple_container', 'Sup'],
           0xF5B8: 'end_container',
           0xF5B9: ['simple_container', 'Sub'],
           0xF5BA: 'end_container',
           0xF5BB: ['simple_container', 'NoBR'],
           0xF5BC: 'end_container',
           0xF5BD: ['simple_container', 'EmpDots'],
           0xF5BE: 'end_container',
           0xF5C1: 'empline',
           0xF5C2: 'end_container',
           0xF5C3: 'draw_char',
           0xF5C4: 'end_container',
           0xF5C6: 'box',
           0xF5C7: 'end_container',
           0xF5CA: 'space',
           0xF5CC: 'string',
           0xF5D1: 'plot',
           0xF5D2: 'cr',
        }
        
        text_map = { 0x22: u'&quot;', 0x26: u'&amp;', 0x27: u'&squot;', 0x3c: u'&lt;', 0x3e: u'&gt;' }
        linetype_map = {0: 'none', 0x10: 'solid', 0x20: 'dashed', 0x30: 'double', 0x40: 'dotted'}
        adjustment_map = {1: 'top', 2: 'center', 3: 'baseline', 4: 'bottom'}
        lineposition_map = {1:'before', 2:'after'}
        
        def __init__(self, bytes, objects, parent=None, name=None, attrs={}):
            self.parent = parent
            self.name = name
            self.attrs = attrs
            LRFContentObject.__init__(self, bytes, objects)
            
        def parse_stream(self, length):
            offset = self.stream.tell()
            while self.in_container and offset < length:
                buf = self.stream.getvalue()[offset:]
                pos = buf.find('\xf5') - 1
                if pos > 0:
                    self.stream.seek(offset+pos)
                    self.add_text(buf[:pos])
                self.handle_tag(Tag(self.stream))
                offset = self.stream.tell()
            
        def handle_tag(self, tag):
            if tag.id in self.tag_map:
                action = self.tag_map[tag.id]
                if isinstance(action, basestring):
                    func, args = action, tuple([])  
                else:
                    func, args = action[0], (action[1],)
                getattr(self, func)(tag, *args)
            elif tag.id in TextAttr.tag_map:
                h = TextAttr.tag_map[tag.id]
                val = LRFObject.tag_to_val(h, None, tag, self.stream)
                if self.name == 'Span':
                    if h[0] not in self.attrs:
                        self.attrs[h[0]] = val
                    elif val != self.attrs[h[0]]:
                        if self._contents: 
                            self.parent._contents.append(self)
                        Text.Content(self.stream, self.objects, self.parent, 
                                            'Span', {h[0]: val})
                        
                        
                else:
                    Text.Content(self.stream, self.objects, self, 
                                        'Span', {h[0]: val})
                    
            else:
                raise LRFParseError('Unknown tag in text stream %s'&(tag,))
                
            
        def simple_container(self, tag, name):
            cont = Text.Content(self.stream, self.objects, parent=self, name=name)            
            self._contents.append(cont)
            
        def end_container(self, *args):
            self.in_container = False
            if self.name == 'Span' and self._contents and self not in self.parent._contents:
                self.parent._contents.append(self)
            
        def end_to_root(self):
            parent = self
            while parent:
                parent.end_container()
                parent = parent.parent
                
        def root(self):
            root = self
            while root.parent:
                root = root.parent
            return root
                
        def start_para(self, tag):
            self.end_to_root()
            root = self.root()
            root.in_container = True
            
            p = Text.Content(self.stream, self.objects, parent=root, name='P')
            root._contents.append(p)
            
        def end_para(self, tag):
            self.end_to_root()
            root = self.root()
            root.in_container = True
            
        def cr(self, tag):
            self._contents.append(Text.Content('', self.objects, parent=self, name='CR'))
            
        def char_button(self, tag):
            self._contents.append(Text.Content(self.stream, self.objects, parent=self, 
                                    name='CharButton', attrs={'refobj':tag.dword}))
        
        def empline(self, tag):
            
            def invalid(op):
                self.stream.seek(op)
                self.simple_container('EmpLine')
                
            oldpos = self.stream.tell()
            try:
                t = Tag(self.stream)
                if t.id not in [0xF579, 0xF57A]:
                    raise LRFParseError
            except LRFParseError:
                invalid(oldpos)
                return
            h = TextAttr.tag_map[t.id]
            attrs = {}
            attrs[h[0]] = TextAttr.tag_to_val(h, None, t, None)
            oldpos = self.stream.tell() 
            try:
                t = Tag(self.stream)
                if t.id not in [0xF579, 0xF57A]:
                    raise LRFParseError
                h = TextAttr.tag_map[t.id]
                attrs[h[0]] = TextAttr.tag_to_val(h, None, t, None)
            except LRFParseError:
                self.stream.seek(oldpos)
            
            cont = Text.Content(self.stream, self.objects, parent=self, 
                                name='EmpLine', attrs=attrs)
            self._contents.append(cont)
                    
        def space(self, tag):
            self._contents.append(Text.Content('', self.objects, parent=self, 
                                name='Space', attrs={'xsize':tag.sword}))
            
        def string(self, tag):
            strlen = tag.word
            self.add_text(self.stream.read(strlen))
            
        def add_text(self, text):
            s = unicode(text, "utf-16-le")
            self._contents.append(s.translate(self.text_map))
            
        def plot(self, tag):
            xsize, ysize, refobj, adjustment = struct.unpack("<HHII", tag.contents)
            plot = Text.Content('', self.objects, self, 'Plot',
                {'xsize': xsize, 'ysize': ysize, 'refobj':refobj, 
                 'adjustment':self.adjustment_map[adjustment]})
            plot.refobj = self.objects[refobj]
            self._contents.append(plot)
                        
        def draw_char(self, tag):
            self._contents.append(Text.Content(self.stream, self.objects, self, 
                                        'DrawChar', {'line':tag.word}))
            
        def box(self, tag):
            self._contents.append(Text.Content(self.stream, self.objects, self, 
                                        'Box', {'linetype':self.linetype_map[tag.word]}))
            
        def __iter__(self):
            for i in self._contents:
                yield i
            
        def __unicode__(self):
            s = u''
            if self.name is not None:
                s += u'<'+self.name+u' '
                for attr in self.attrs:
                    s += u'%s="%s" '%(attr, self.attrs[attr])
                s = s.rstrip()
            children = u''
            for i in self:
                children += unicode(i)
            if len(children) == 0:
                return s + u' />'
            if self.name is None:
                return children
            return s + u'>' + children + '</%s>'%(self.name,) + ('\n' if self.name == 'P' else '')
        
        def __str__(self):
            return unicode(self).encode('utf-8')
    
    def initialize(self):
        self.content = Text.Content(self.stream, self._document.objects)
                
    def __iter__(self):
        for i in self.content:
            yield i
        
    def __str__(self):
        return unicode(self.content)


class Image(LRFObject):
    tag_map = {
        0xF54A: ['', 'parse_image_rect'],
        0xF54B: ['', 'parse_image_size'],
        0xF54C: ['refstream', 'D'],      
        0xF555: ['comment', 'P'],
      }
    
    def parse_image_rect(self, tag, f):
        self.x0, self.y0, self.x1, self.y1 = struct.unpack("<HHHH", tag.contents)
        
    def parse_image_size(self, tag, f):
        self.xsize, self.ysize = struct.unpack("<HH", tag.contents)
        
    encoding = property(fget=lambda self : self._document.objects[self.refstream].encoding)
    data = property(fget=lambda self : self._document.objects[self.refstream].stream)
    
    
    def __unicode__(self):
        return u'<Image objid="%s" x0="%d" y0="%d" x1="%d" y1="%d" xsize="%d" ysize="%d" refstream="%d" />\n'%\
        (self.id, self.x0, self.y0, self.x1, self.y1, self.xsize, self.ysize, self.refstream)

class PutObj(EmptyPageElement):
    
    def __init__(self, objects, x, y, refobj):
        self.x, self.y, self.refobj = x, y, refobj
        self.object = objects[refobj]
        
    def __unicode__(self):
        return u'<PutObj x="%d" y="%d" refobj="%d" />'%(self.x, self.y, self.refobj)

class Canvas(LRFStream):
    tag_map = {
        0xF551: ['canvaswidth', 'W'],
        0xF552: ['canvasheight', 'W'],
        0xF5DA: ['', 'parse_waits'],
        0xF533: ['blockrule', 'W', {0x44: "block-fixed", 0x22: "block-adjustable"}],
        0xF534: ['bgcolor', 'D', Color],
        0xF535: ['layout', 'W', {0x41: 'TbRl', 0x34: 'LrTb'}],
        0xF536: ['framewidth', 'W'],
        0xF537: ['framecolor', 'D', Color],
        0xF52E: ['framemode', 'W', {0: 'none', 2: 'curve', 1:'square'}],
      }
    tag_map.update(LRFStream.tag_map)
    extra_attrs = ['canvaswidth', 'canvasheight', 'blockrule', 'layout', 
                   'framewidth', 'framecolor', 'framemode']
    
    def parse_waits(self, tag, f):
        val = tag.word
        self.setwaitprop = val&0xF
        self.setwaitsync = val&0xF0
        
    def initialize(self):
        self.attrs = {}
        for attr in self.extra_attrs:
            if hasattr(self, attr):
                self.attrs[attr] = getattr(self, attr)
        self._contents = []
        stream = cStringIO.StringIO(self.stream)
        while stream.tell() < len(self.stream):
            tag = Tag(stream)
            self._contents.append(PutObj(self._document.objects, *struct.unpack("<HHI", tag.contents)))
            
    def __unicode__(self):
        s = '\n<%s objid="%s" '%(self.__class__.__name__, self.id,)
        for attr in self.attrs:
            s += '%s="%s" '%(attr, self.attrs[attr])
        s = s.rstrip() + '>\n'
        for po in self:
            s += unicode(po) + '\n'
        s += '</%s>\n'%(self.__class__.__name__,)
        return s
    
    def __iter__(self):
        for i in self._contents:
            yield i
        
class Header(Canvas):
    pass

class Footer(Canvas):
    pass


class ESound(LRFObject):
    pass

class ImageStream(LRFStream):
    tag_map = {
        0xF555: ['comment', 'P'],
      }
    imgext = {0x11: 'jpeg', 0x12: 'png', 0x13: 'bmp', 0x14: 'gif'}
    
    tag_map.update(LRFStream.tag_map)
    
    encoding = property(fget=lambda self : self.imgext[self.stream_flags & 0xFF].upper())
        
    def end_stream(self, *args):
        LRFStream.end_stream(self, *args)
        self.file = str(self.id) + '.' + self.encoding.lower()
        self._document.image_map[self.id] = self
        
    def __unicode__(self):
        return u'<ImageStream objid="%s" encoding="%s" file="%s" />\n'%\
            (self.id, self.encoding, self.file)

class Import(LRFStream):
    pass

class Button(LRFObject):
    tag_map = {
        0xF503: ['', 'do_ref_image'],
        0xF561: ['button_flags','W'],           #<Button/>
        0xF562: ['','do_base_button'],            #<BaseButton>
        0xF563: ['',''],            #</BaseButton>
        0xF564: ['','do_focusin_button'],            #<FocusinButton>
        0xF565: ['',''],            #</FocusinButton>
        0xF566: ['','do_push_button'],            #<PushButton>
        0xF567: ['',''],            #</PushButton>
        0xF568: ['','do_up_button'],            #<UpButton>
        0xF569: ['',''],            #</UpButton>
        0xF56A: ['','do_start_actions'],            #start actions
        0xF56B: ['',''],            #end actions
        0xF56C: ['','parse_jump_to'], #JumpTo
        0xF56D: ['','parse_send_message'], #<SendMessage
        0xF56E: ['','parse_close_window'],            #<CloseWindow/>
        0xF5D6: ['','parse_sound_stop'],            #<SoundStop/>
        0xF5F9: ['','parse_run'],    #Run
      }
    tag_map.update(LRFObject.tag_map)
    
    def __init__(self, document, stream, id, scramble_key, boundary):
        self.xml = u''
        self.refimage = {}
        self.actions = {}
        self.to_dump = True
        LRFObject.__init__(self, document, stream, id, scramble_key, boundary)
    
    def do_ref_image(self, tag, f):
        self.refimage[self.button_yype] = tag.dword
        
    def do_base_button(self, tag, f):
        self.button_type = 0
        self.actions[self.button_type] = []
        
    def do_focus_in_button(self, tag, f):
        self.button_type = 1
        
    def do_push_button(self, tag, f):
        self.button_type = 2
        
    def do_up_button(self, tag, f):
        self.button_type = 3
        
    def do_start_actions(self, tag, f):
        self.actions[self.button_type] = []
        
    def parse_jump_to(self, tag, f):
        self.actions[self.button_type].append((1, struct.unpack("<II", tag.contents)))
    
    def parse_send_message(self, tag, f):
        params = (tag.word, Tag.string_parser(f), Tag.string_parser(f))
        self.actions[self.button_type].append((2, params))
        
    def parse_close_window(self, tag, f):
        self.actions[self.button_type].append((3,))
        
    def parse_sound_stop(self, tag, f):
        self.actions[self.button_type].append((4,))
    
    def parse_run(self, tag, f):
        self.actions[self.button_type].append((5, struct.unpack("<HI", tag.contents)))
        
    def jump_action(self, button_type):
        for i in self.actions[button_type]:
            if i[0] == 1:
                return i[1:][0]
    
    def __unicode__(self):
        s = u'<Button objid="%s">\n'%(self.id,)
        if self.button_flags & 0x10 != 0:
            s += '<PushButton '
            if 2 in self.refimage:
                s += 'refimage="%s" '%(self.refimage[2],)
            s = s.rstrip() + '>\n'
            s += '<JumpTo refpage="%s" refobj="%s" />\n'% self.jump_action(2)
            s += '</PushButton>\n'
        else:
            raise LRFParseError('Unsupported button type')
        s += '</Button>\n'
        return s
    
    refpage = property(fget=lambda self : self.jump_action(2)[0])
    refobj = property(fget=lambda self : self.jump_action(2)[1])
    

class Window(LRFObject):
    pass

class PopUpWin(LRFObject):
    pass

class Sound(LRFObject):
    pass

class SoundStream(LRFObject):
    pass

class Font(LRFStream):
    tag_map = {
        0xF559: ['fontfilename', 'P'],
        0xF55D: ['fontfacename', 'P'],
      }
    tag_map.update(LRFStream.tag_map)
    data = property(fget=lambda self: self.stream)
    
    def end_stream(self, *args):
        LRFStream.end_stream(self, *args)
        self._document.font_map[self.fontfacename] = self
        self.file = self.fontfacename + '.ttf'
    
    def __unicode__(self):
        s = '<RegistFont objid="%s" fontfilename="%s" fontfacename="%s" encoding="TTF" file="%s" />\n'%\
            (self.id, self.fontfilename, self.fontfacename, self.file)
        return s

class ObjectInfo(LRFObject):
    pass


class BookAttr(StyleObject, LRFObject):
    tag_map = {
        0xF57B: ['page_tree_id', 'D'],
        0xF5D8: ['', 'add_font'],
        0xF5DA: ['setwaitprop', 'W', {1: 'replay', 2: 'noreplay'}],
      }
    tag_map.update(ruby_tags)
    tag_map.update(LRFObject.tag_map)
    binding_map = {1: 'Lr', 16 : 'Rl'}
    
    def __init__(self, document, stream, id, scramble_key, boundary):
        self.font_link_list = []
        LRFObject.__init__(self, document, stream, id, scramble_key, boundary)
        
    def add_font(self, tag, f):
        self.font_link_list.append(tag.dword)
        
    def __unicode__(self):
        s = u'<BookStyle objid="%s" stylelabel="%s">\n'%(self.id, self.id)
        s += u'<SetDefault %s />\n'%(self._tags_to_xml(),)
        doc = self._document
        s += u'<BookSetting bindingdirection="%s" dpi="%s" screenwidth="%s" screenheight="%s" colordepth="%s" />\n'%\
        (self.binding_map[doc.binding], doc.dpi, doc.width, doc.height, doc.color_depth) 
        for font in self._document.font_map.values():
            s += unicode(font)
        s += '</BookStyle>\n'
        return s

class SimpleText(Text):
    pass

class TocLabel(object):
    
    def __init__(self, refpage, refobject, label):
        self.refpage, self.refobject, self.label = refpage, refobject, label
        
    def __unicode__(self):
        return u'<TocLabel refpage="%s" refobj="%s">%s</TocLabel>\n'%(self.refpage, self.refobject, self.label)

class TOCObject(LRFStream):
    
    def initialize(self):
        stream = cStringIO.StringIO(self.stream)
        c = struct.unpack("<H", stream.read(2))[0]
        stream.seek(4*(c+1))
        self._contents = []
        while c > 0:
            refpage = struct.unpack("<I", stream.read(4))[0]
            refobj  = struct.unpack("<I", stream.read(4))[0]
            cnt = struct.unpack("<H", stream.read(2))[0]
            label = unicode(stream.read(cnt), "utf_16")
            self._contents.append(TocLabel(refpage, refobj, label))
            c -= 1
            
    def __iter__(self):
        for i in self._contents:
            yield i
        
    def __unicode__(self):
        s = u'<TOC>\n'
        for i in self:
            s += unicode(i)
        return s + '</TOC>\n'
            

object_map = [
    None,       #00
    PageTree,   #01
    Page,       #02
    Header,     #03
    Footer,     #04
    PageAttr,    #05
    Block,      #06
    BlockAttr,   #07
    MiniPage,   #08
    None,       #09
    Text,       #0A
    TextAttr,    #0B
    Image,      #0C
    Canvas,     #0D
    ESound,     #0E
    None,       #0F
    None,       #10
    ImageStream,#11
    Import,     #12
    Button,     #13
    Window,     #14
    PopUpWin,   #15
    Sound,      #16
    SoundStream,#17
    None,       #18
    Font,       #19
    ObjectInfo, #1A
    None,       #1B
    BookAttr,    #1C
    SimpleText, #1D
    TOCObject,  #1E
]


def get_object(document, stream, id, offset, size, scramble_key):
    stream.seek(offset)
    start_tag = Tag(stream)
    if start_tag.id != 0xF500:
        raise LRFParseError('Bad object start')
    obj_id, obj_type = struct.unpack("<IH", start_tag.contents)
    if obj_type < len(object_map) and object_map[obj_type] is not None:
        return object_map[obj_type](document, stream, obj_id, scramble_key, offset+size-Tag.tags[0][0])
    
    raise LRFParseError("Unknown object type: %02X!" % obj_type)

        
