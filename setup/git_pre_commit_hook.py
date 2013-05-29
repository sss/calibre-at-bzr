#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


'''
Hook to make the commit command automatically close bugs when the commit
message contains `Fix #number` or `Implement #number`. Also updates the commit
message with the summary of the closed bug.

'''
import re, urllib, importlib, sys, json

from lxml import html

SENDMAIL = ('/home/kovid/work/env', 'pgp_mail')
LAUNCHPAD_BUG = 'https://bugs.launchpad.net/calibre/+bug/%s'
GITHUB_BUG = 'https://api.github.com/repos/kovidgoyal/calibre/issues/%s'
BUG_PAT = r'(Fix|Implement|Fixes|Fixed|Implemented)\s+#(\d+)'

class Bug:

    def __init__(self):
        self.seen = set()

    def __call__(self, match):
        action, bug = match.group(1), match.group(2)
        summary = ''
        if bug in self.seen:
            return match.group()
        self.seen.add(bug)

        if int(bug) > 100000:  # Launchpad bug
            raw = urllib.urlopen(LAUNCHPAD_BUG % bug).read()
            try:
                h1 = html.fromstring(raw).xpath('//h1[@id="edit-title"]')[0]
                summary = html.tostring(h1, method='text', encoding=unicode).strip()
            except:
                summary = 'Private bug'
        else:
            summary = json.loads(urllib.urlopen(GITHUB_BUG % bug).read())['title']
        if summary:
            print ('Working on bug:', summary)
            if int(bug) > 100000:
                self.close_bug(bug, action)
            return match.group() + ' (%s)' % summary
        return match.group()

    def close_bug(self, bug, action):
        print ('Closing bug #%s'% bug)
        suffix = ('The fix will be in the next release. '
                'calibre is usually released every Friday.')
        action += 'ed'
        msg = '%s in branch %s. %s'%(action, 'master', suffix)
        msg = msg.replace('Fixesed', 'Fixed')
        msg += '\n\n status fixreleased'

        sys.path.insert(0, SENDMAIL[0])

        sendmail = importlib.import_module(SENDMAIL[1])

        to = bug+'@bugs.launchpad.net'
        sendmail.sendmail(msg, to, 'Fixed in master')

def main():
    with open(sys.argv[-1], 'r+b') as f:
        raw = f.read().decode('utf-8')
        bug = Bug()
        msg = re.sub(BUG_PAT, bug, raw)
        if msg != raw:
            f.seek(0)
            f.truncate()
            f.write(msg.encode('utf-8'))

if __name__ == '__main__':
    main()

