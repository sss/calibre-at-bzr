__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import re
from PyQt4.QtGui import QDialog, QDialogButtonBox
from PyQt4 import QtCore

from calibre.gui2.dialogs.search_ui import Ui_Dialog
from calibre.library.caches import CONTAINS_MATCH, EQUALS_MATCH

class SearchDialog(QDialog, Ui_Dialog):

    def __init__(self, parent, db, box_values, current_tab):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.mc = ''
        searchables = sorted(db.field_metadata.searchable_fields(),
                             lambda x, y: cmp(x if x[0] != '#' else x[1:],
                                              y if y[0] != '#' else y[1:]))
        self.general_combo.addItems(searchables)

        if (box_values):
            for k,v in box_values.items():
                if k == 'general_index':
                    continue
                getattr(self, k).setText(v)
            self.general_combo.setCurrentIndex(
                    self.general_combo.findText(box_values['general_index']))
        self.box_last_values = box_values

        self.buttonBox.accepted.connect(self.advanced_search_button_pushed)
        self.tab_2_button_box.accepted.connect(self.box_search_accepted)
        self.tab_2_button_box.rejected.connect(self.box_search_rejected)
        self.clear_button.clicked.connect(self.clear_button_pushed)
        self.adv_search_used = False
        self.box_search_used = False

        self.tabWidget.setCurrentIndex(current_tab)
        self.tabWidget.currentChanged[int].connect(self.tab_changed)
        self.tab_changed(current_tab)

    def tab_changed(self, idx):
        if idx == 1:
            self.tab_2_button_box.button(QDialogButtonBox.Ok).setDefault(True)
        else:
            self.buttonBox.button(QDialogButtonBox.Ok).setDefault(True)

    def advanced_search_button_pushed(self):
        self.adv_search_used = True
        self.current_tab = 0
        QDialog.accept(self)

    def box_search_accepted(self):
        self.box_search_used = True
        self.current_tab = 1
        QDialog.accept(self)

    def box_search_rejected(self):
        QDialog.reject(self)

    def clear_button_pushed(self):
        self.title_box.setText('')
        self.authors_box.setText('')
        self.series_box.setText('')
        self.tags_box.setText('')
        self.general_box.setText('')

    def tokens(self, raw):
        phrases = re.findall(r'\s*".*?"\s*', raw)
        for f in phrases:
            raw = raw.replace(f, ' ')
        phrases = [t.strip('" ') for t in phrases]
        return ['"' + self.mc + t + '"' for t in phrases + [r.strip() for r in raw.split()]]

    def search_string(self):
        if self.adv_search_used:
            return self.adv_search_string()
        else:
            return self.box_search_string()

    def adv_search_string(self):
        mk = self.matchkind.currentIndex()
        if mk == CONTAINS_MATCH:
            self.mc = ''
        elif mk == EQUALS_MATCH:
            self.mc = '='
        else:
            self.mc = '~'
        all, any, phrase, none = map(lambda x: unicode(x.text()),
                (self.all, self.any, self.phrase, self.none))
        all, any, none = map(self.tokens, (all, any, none))
        phrase = phrase.strip()
        all = ' and '.join(all)
        any = ' or '.join(any)
        none = ' and not '.join(none)
        ans = ''
        if phrase:
            ans += '"%s"'%phrase
        if all:
            ans += (' and ' if ans else '') + all
        if none:
            ans += (' and not ' if ans else 'not ') + none
        if any:
            ans += (' or ' if ans else '') + any
        return ans

    def token(self):
        txt = unicode(self.text.text()).strip()
        if txt:
            if self.negate.isChecked():
                txt = '!'+txt
            tok = self.FIELDS[unicode(self.field.currentText())]+txt
            if re.search(r'\s', tok):
                tok = '"%s"'%tok
            return tok

    def box_search_string(self):
        ans = []
        self.box_last_values = {}
        title = unicode(self.title_box.text()).strip()
        self.box_last_values['title_box'] = title
        if title:
            ans.append('title:"' + title + '"')
        author = unicode(self.authors_box.text()).strip()
        self.box_last_values['authors_box'] = author
        if author:
            ans.append('author:"' + author + '"')
        series = unicode(self.series_box.text()).strip()
        self.box_last_values['series_box'] = series
        if series:
            ans.append('series:"' + series + '"')
        self.mc = '='
        tags = unicode(self.tags_box.text())
        self.box_last_values['tags_box'] = tags
        tags = self.tokens(tags)
        if tags:
            tags = ['tags:' + t for t in tags]
            ans.append('(' + ' or '.join(tags) + ')')
        general = unicode(self.general_box.text())
        self.box_last_values['general_box'] = general
        general_index = unicode(self.general_combo.currentText())
        self.box_last_values['general_index'] = general_index
        if general:
            ans.append(unicode(self.general_combo.currentText()) + ':"' + general + '"')
        if ans:
            return ' and '.join(ans)
        return ''
