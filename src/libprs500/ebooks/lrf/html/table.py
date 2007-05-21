##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
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
import math, sys

from libprs500.ebooks.lrf.fonts import get_font
from libprs500.ebooks.lrf.pylrs.pylrs import TextBlock, Text, CR, Span, \
                                             CharButton, Plot, Paragraph, \
                                             LrsTextTag

def ceil(num):
    return int(math.ceil(num))

def print_xml(elem):
    from libprs500.ebooks.lrf.pylrs.pylrs import ElementWriter    
    elem = elem.toElement('utf8')
    ew = ElementWriter(elem, sourceEncoding='utf8')
    ew.write(sys.stdout)
    print
    
def cattrs(base, extra):
    new = base.copy()
    new.update(extra)
    return new
    
def tokens(tb):
    '''
    Return the next token. A token is :
    1. A string 
    a block of text that has the same style
    '''        
    def process_element(x, attrs):
        if isinstance(x, CR):
            yield 2, None
        elif isinstance(x, Text):
            yield x.text, cattrs(attrs, {})
        elif isinstance(x, basestring):
            yield x, cattrs(attrs, {})
        elif isinstance(x, (CharButton, LrsTextTag)):
            if x.contents:
                yield x.contents[0].text, cattrs(attrs, {})
        elif isinstance(x, Plot):
            yield x, None
        elif isinstance(x, Span):
            attrs = cattrs(attrs, x.attrs)
            for y in x.contents:
                for z in process_element(y, attrs):
                    yield z
        
            
    for i in tb.contents:
        if isinstance(i, CR):
            yield 1, None
        elif isinstance(i, Paragraph):
            for j in i.contents: 
                attrs = {}
                if hasattr(j, 'attrs'):
                    attrs = j.attrs
                for k in process_element(j, attrs):                    
                    yield k
    

class Cell(object):
    
    def __init__(self, conv, cell, css):
        self.conv = conv
        self.cell = cell
        self.css  = css
        self.text_blocks = []
        self.rowspan = self.colspan = 1
        try:
            self.colspan = int(cell['colspan']) if cell.has_key('colspan') else 1
            self.rowspan = int(cell['rowspan']) if cell.has_key('rowspan') else 1
        except:
            if conv.verbose:
                print >>sys.stderr, "Error reading row/colspan for ", cell
                
        pp = conv.current_page
        conv.book.allow_new_page = False
        conv.anchor_to_previous = pp
        conv.current_page = conv.book.create_page()
        conv.parse_tag(cell, css)
        conv.end_current_block()
        for item in conv.current_page.contents:
            if isinstance(item, TextBlock):
                self.text_blocks.append(item)
        conv.current_page = pp
        conv.book.allow_new_page = True
        conv.anchor_to_previous = None
        if not self.text_blocks:
            tb = conv.book.create_text_block()
            tb.Paragraph(' ')
            self.text_blocks.append(tb)
        for tb in self.text_blocks:
            tb.parent = None
            tb.objId  = 0
            # Needed as we have to eventually change this BlockStyle's width and 
            # height attributes. This blockstyle may be shared with other
            # elements, so doing that causes havoc.
            tb.blockStyle = conv.book.create_block_style()
            ts = conv.book.create_text_style(**tb.textStyle.attrs)
            ts.attrs['parindent'] = 0
            tb.textStyle = ts
            if ts.attrs['align'] == 'foot':
                if isinstance(tb.contents[-1], Paragraph):
                    tb.contents[-1].append(' ')
        
        
        
            
    def pts_to_pixels(self, pts):
        pts = int(pts)
        return ceil((float(self.conv.profile.dpi)/72)*(pts/10.))
    
    def text_block_size(self, tb, maxwidth=sys.maxint, debug=False):
        ts = tb.textStyle.attrs
        default_font = get_font(ts['fontfacename'], self.pts_to_pixels(ts['fontsize']))
        parindent = self.pts_to_pixels(ts['parindent'])
        ls, ws = self.pts_to_pixels(ts['linespace']), self.pts_to_pixels(ts['wordspace'])
        top, bottom, left, right = 0, 0, parindent, parindent
        
        def add_word(width, height, left, right, top, bottom):            
            if left + width > maxwidth:
                left = width + ws
                top += height + ls
                bottom = top+height if top+height > bottom else bottom
            else:
                left += (width + ws)
                right = left if left > right else right                    
                bottom = top+height if top+height > bottom else bottom
            return left, right, top, bottom
        
        for token, attrs in tokens(tb):
            font = default_font
            if isinstance(token, int): # Handle para and line breaks
                top = bottom
                left = parindent if int == 1 else 0
                continue
            if isinstance(token, Plot):
                width, height = self.pts_to_pixels(token.xsize), self.pts_to_pixels(token.ysize)
                left, right, top, bottom = add_word(width, height, left, right, top, bottom)
                continue
            ff = attrs.get('fontfacename', ts['fontfacename'])
            fs = attrs.get('fontsize', ts['fontsize'])
            if (ff, fs) != (ts['fontfacename'], ts['fontsize']):
                font = get_font(ff, self.pts_to_pixels(fs))
            for word in token.split():
                width, height = font.getsize(word)
                left, right, top, bottom = add_word(width, height, left, right, top, bottom)
        return right+3, bottom
                
    def text_block_preferred_width(self, tb, debug=False):
        return self.text_block_size(tb, sys.maxint, debug=debug)[0]
    
    def preferred_width(self, debug=False):
        return ceil(max([self.text_block_preferred_width(i, debug=debug) for i in self.text_blocks]))
    
    def height(self, width):
        return sum([self.text_block_size(i, width)[1] for i in self.text_blocks])
        
            

class Row(object):
    def __init__(self, conv, row, css, colpad):
        self.cells = []
        self.colpad = colpad
        cells = row.findAll('td')
        for cell in cells:
            ccss = conv.tag_css(cell, css)
            self.cells.append(Cell(conv, cell, ccss))        
            
    def number_of_cells(self):
        '''Number of cells in this row. Respects colspan'''
        ans = 0
        for cell in self.cells:
            ans += cell.colspan
        return ans
    
    def height(self, widths):
        i, heights = 0, []
        for cell in self.cells:
            width = sum(widths[i:i+cell.colspan])
            heights.append(cell.height(width))
            i += cell.colspan
        if not heights:
            return 0
        return max(heights)
    
    def preferred_width(self, col):
        i = -1
        cell = None        
        for cell in self.cells:            
            for k in range(0, cell.colspan):
                if i == col:
                    break
                i += 1
            if i == col:
                break
        if not cell:
            return 0
        return 0 if cell.colspan > 1 else cell.preferred_width()
    
    def cell_iterator(self):
        for c in self.cells:
            yield c
        
    
class Table(object):
    def __init__(self, conv, table, css, rowpad=10, colpad=10):
        self.rows = []
        self.conv = conv
        self.rowpad = rowpad
        self.colpad = colpad
        rows = table.findAll('tr')
        for row in rows:            
            rcss = conv.tag_css(row, css)
            self.rows.append(Row(conv, row, rcss, colpad))
            
    def number_of_columns(self):
        max = 0
        for row in self.rows:
            max = row.number_of_cells() if row.number_of_cells() > max else max
        return max
    
    def number_or_rows(self):
        return len(self.rows)
            
    def height(self, maxwidth):
        ''' Return row heights + self.rowpad'''
        widths = self.get_widths(maxwidth)
        return sum([row.height(widths) + self.rowpad for row in self.rows]) - self.rowpad
    
    def get_widths(self, maxwidth):
        '''
        Return widths of columns + sefl.colpad
        '''
        rows, cols = self.number_or_rows(), self.number_of_columns()
        widths = range(cols)
        for c in range(cols):
            cellwidths = [ 0 for i in range(rows)]
            for r in range(rows):
                try:
                    cellwidths[r] = self.rows[r].preferred_width(c)
                except IndexError:
                    continue                 
            widths[c] = max(cellwidths)
        itercount = 0
        while sum(widths) > maxwidth-((len(widths)-1)*self.colpad) and itercount < 100:
            widths = [ceil((95./100.)*w) for w in widths]
            itercount += 1
        return [i+self.colpad for i in widths]
    
    def blocks(self, maxwidth):       
        rows, cols = self.number_or_rows(), self.number_of_columns()
        cellmatrix = [[None for c in range(cols)] for r in range(rows)]        
        rowpos = [0 for i in range(rows)]
        for r in range(rows):
            nc = self.rows[r].cell_iterator()
            try:
                while True:
                    cell = nc.next()
                    cellmatrix[r][rowpos[r]] = cell
                    rowpos[r] += cell.colspan
                    for k in range(1, cell.rowspan):
                        try:
                            rowpos[r+k] += 1
                        except IndexError:
                            break
            except StopIteration: # No more cells in this row
                continue
            
            
        widths = self.get_widths(maxwidth)
        heights = [row.height(widths) for row in self.rows]
                
        xpos = [sum(widths[:i]) for i in range(cols)]
        delta = maxwidth - sum(widths)
        if delta < 0: 
            delta = 0
        for r in range(len(cellmatrix)):
            yield None, 0, heights[r], 0
            for c in range(len(cellmatrix[r])):
                cell = cellmatrix[r][c]
                if not cell:
                    continue
                width = sum(widths[c:c+cell.colspan])
                sypos = 0
                for tb in cell.text_blocks:
                    tb.blockStyle = self.conv.book.create_block_style(
                                    blockwidth=width, 
                                    blockheight=cell.text_block_size(tb, width)[1])
                    
                    yield tb, xpos[c], sypos, delta
                    sypos += tb.blockStyle.attrs['blockheight']
                
            
        
                