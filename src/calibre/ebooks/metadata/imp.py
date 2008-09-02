__license__   = 'GPL v3'
__copyright__ = '2008, Ashish Kulkarni <kulkarni.ashish@gmail.com>'
'''Read meta information from IMP files'''

import sys, os

from calibre.ebooks.metadata import MetaInformation

MAGIC = ['\x00\x01BOOKDOUG', '\x00\x02BOOKDOUG']

def get_metadata(stream):
    """ Return metadata as a L{MetaInfo} object """
    title = 'Unknown'
    mi = MetaInformation(title, ['Unknown'])
    stream.seek(0)
    try:
        if stream.read(10) not in MAGIC:
            print >>sys.stderr, u'Couldn\'t read IMP header from file'
            return mi
        
        def cString(skip=0):
            result = ''
            while 1:
                data = stream.read(1)
                if data == '\x00':
                    if not skip: return result
                    skip -= 1
                    result, data = '', ''
                result += data

        stream.read(38) # skip past some uninteresting headers
        _, category, title, author = cString(), cString(), cString(1), cString(2)
        
        if title:
            mi.title = title
        if author:
            src = author.split('&')
            authors = []
            for au in src:
                authors += au.split(',')
            mi.authors = authors
            mi.author = author
        if category:
            mi.category = category
    except Exception, err:
        msg = u'Couldn\'t read metadata from imp: %s with error %s'%(mi.title, unicode(err))
        print >>sys.stderr, msg.encode('utf8')
    return mi
        
            
def main(args=sys.argv):
    if len(args) != 2:
        print >>sys.stderr, _('Usage: imp-meta file.imp')
        print >>sys.stderr, _('No filename specified.')
        return 1
    
    path = os.path.abspath(os.path.expanduser(args[1]))
    print get_metadata(open(path, 'rb'))
    return 0

if __name__ == '__main__':
    sys.exit(main())
