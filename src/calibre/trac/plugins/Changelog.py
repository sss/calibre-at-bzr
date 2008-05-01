'''
Trac Macro to generate an end use Changelog from the svn logs.
'''
import time, re, collections

from bzrlib import log as blog, branch

from cStringIO import StringIO

from trac.wiki.formatter import Formatter
from trac.wiki.macros import WikiMacroBase
from trac.util import Markup


BZR_PATH = '/var/bzr/code/calibre/trunk'

class ChangelogFormatter(blog.LogFormatter):
    
    supports_tags = True
    
    def __init__(self, num_of_versions=10):
        self.num_of_versions = num_of_versions
        self.messages = collections.deque()
        self.entries = []
        self.current_entry = None 
    
    def log_revision(self, r):
        if len(self.entries) > self.num_of_versions-1:
            return
        msg = r.rev.message
        match = re.match(r'version\s+(\d+\.\d+.\d+)', msg)
         
        if match:
            if self.current_entry is not None:
                self.entries.append((self.current_entry, set(self.messages)))
            self.current_entry = match.group(1)
            self.messages = collections.deque()
            
        else:
            if re.search(r'[a-zA-Z]', msg):
                if 'translation' not in msg and not msg.startswith('IGN'):
                    self.messages.append(msg.strip())
                    
    def to_wiki_txt(self):
        txt = ['= Changelog =\n[[PageOutline]]']
        for entry in self.entries:
            txt.append(u'----\n== Version '+entry[0]+' ==')
            for msg in entry[1]:
                txt.append(u'  * ' + msg)
                
        return u'\n'.join(txt)
    
def bzr_log_to_txt():
    b = branch.Branch.open(BZR_PATH)
    lf = ChangelogFormatter()
    blog.show_log(b, lf)
    return lf.to_wiki_txt()

class ChangeLogMacro(WikiMacroBase):

    def expand_macro(self, formatter, name, args):
        txt = bzr_log_to_txt().encode('ascii', 'xmlcharrefreplace')
        out = StringIO()
        Formatter(formatter.env, formatter.context).format(txt, out)
        return Markup(out.getvalue())


if __name__ == '__main__':
    print bzr_log_to_txt() 
        
        