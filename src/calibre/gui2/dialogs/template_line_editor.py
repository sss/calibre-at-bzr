#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial
from collections import defaultdict

from PyQt4.Qt import (QLineEdit, QDialog, QGridLayout, QLabel, QCheckBox, QIcon,
                      QDialogButtonBox, QColor, QComboBox, QPushButton)

from calibre.ebooks.metadata.book.base import composite_formatter
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.complete import MultiCompleteLineEdit
from calibre.gui2 import error_dialog
from calibre.utils.icu import sort_key

class TemplateLineEditor(QLineEdit):

    '''
    Extend the context menu of a QLineEdit to include more actions.
    '''

    def __init__(self, parent):
        QLineEdit.__init__(self, parent)
        self.tags = None
        self.mi   = None
        self.txt = None

    def set_mi(self, mi):
        self.mi = mi

    def set_db(self, db):
        self.db = db

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()

        action_clear_field = menu.addAction(_('Remove any template from the box'))
        action_clear_field.triggered.connect(self.clear_field)
        action_open_editor = menu.addAction(_('Open Template Editor'))
        action_open_editor.triggered.connect(self.open_editor)
        menu.exec_(event.globalPos())

    def clear_field(self):
        self.setText('')
        self.txt = None
        self.setReadOnly(False)
        self.setStyleSheet('TemplateLineEditor { color: black }')

    def open_editor(self):
        if self.txt:
            t = TemplateDialog(self, self.txt, self.mi)
        else:
            t = TemplateDialog(self, self.text(), self.mi)
        t.setWindowTitle(_('Edit template'))
        if t.exec_():
            self.setText(t.textbox.toPlainText())
            self.txt = None

    def show_wizard_button(self, txt):
        if not txt or txt.startswith('program:\n#tag wizard'):
            return True
        return False

    def setText(self, txt):
        txt = unicode(txt)
        if txt and txt.startswith('program:\n#tag wizard'):
            self.txt = txt
            self.setReadOnly(True)
            QLineEdit.setText(self, '')
            QLineEdit.setText(self, _('Template generated by the wizard'))
            self.setStyleSheet('TemplateLineEditor { color: gray }')
        else:
            QLineEdit.setText(self, txt)

    def tag_wizard(self):
        txt = unicode(self.text())
        if txt and not self.txt:
            error_dialog(self, _('Invalid text'),
                 _('The text in the box was not generated by this wizard'),
                 show=True, show_copy_button=False)
            return
        d = TagWizard(self, self.db, unicode(self.txt), self.mi)
        if d.exec_():
            self.setText(d.template)

    def text(self):
        if self.txt:
            return self.txt
        return QLineEdit.text(self)

class TagWizard(QDialog):

    def __init__(self, parent, db, txt, mi):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Coloring Wizard'))
        self.setWindowIcon(QIcon(I('wizard.png')))

        self.mi = mi

        self.columns = []
        self.completion_values = defaultdict(dict)
        for k in db.all_field_keys():
            m = db.metadata_for_field(k)
            if m['datatype'] in ('text', 'enumeration', 'series') and \
                    m['is_category'] and k not in ('identifiers'):
                self.columns.append(k)
                if m['is_custom']:
                    self.completion_values[k]['v'] = db.all_custom(m['label'])
                elif k == 'tags':
                    self.completion_values[k]['v'] = db.all_tags()
                elif k == 'formats':
                    self.completion_values[k]['v'] = db.all_formats()
                else:
                    if k in ('publisher'):
                        ck = k + 's'
                    else:
                        ck = k
                    f = getattr(db, 'all_' + ck, None)
                    if f:
                        if k == 'authors':
                            self.completion_values[k]['v'] = [v[1].\
                                                replace('|', ',') for v in f()]
                        else:
                            self.completion_values[k]['v'] = [v[1] for v in f()]

                if k in self.completion_values:
                    self.completion_values[k]['m'] = m['is_multiple']

        self.columns.sort(key=sort_key)
        self.columns.insert(0, '')

        l = QGridLayout()
        self.setLayout(l)
        l.setColumnStretch(1, 10)
        l.setColumnMinimumWidth(1, 300)

        h = QLabel(_('Column'))
        l.addWidget(h, 0, 0, 1, 1)

        h = QLabel(_('Values (see the popup help for more information)'))
        h.setToolTip('<p>' +
             _('You can enter more than one value per box, separated by commas. '
               'The comparison ignores letter case.<br>'
               'A value can be a regular expression. Check the box to turn '
               'them on. When using regular expressions, note that the wizard '
               'puts anchors (^ and $) around the expression, so you '
               'must ensure your expression matches from the beginning '
               'to the end of the column you are checking.<br>'
               'Regular expression examples:') + '<ul>' +
             _('<li><code><b>.*</b></code> matches anything in the column. No '
               'empty values are checked, so you don\'t need to worry about '
               'empty strings</li>'
               '<li><code><b>A.*</b></code> matches anything beginning with A</li>'
               '<li><code><b>.*mystery.*</b></code> matches anything containing '
               'the word "mystery"</li>') + '</ul></p>')
        l.addWidget(h , 0, 1, 1, 1)

        c = QLabel(_('is RE'))
        c.setToolTip('<p>' +
             _('Check this box if the values box contains regular expressions') + '</p>')
        l.addWidget(c, 0, 2, 1, 1)

        c = QLabel(_('Color if value found'))
        c.setToolTip('<p>' +
             _('At least one of the two color boxes must have a value. Leave '
               'one color box empty if you want the template to use the next '
               'line in this wizard. If both boxes are filled in, the rest of '
               'the lines in this wizard will be ignored.') + '</p>')
        l.addWidget(c, 0, 3, 1, 1)
        c = QLabel(_('Color if value not found'))
        c.setToolTip('<p>' +
             _('This box is usually filled in only on the last test. If it is '
               'filled in before the last test, then the color for value found box '
               'must be empty or all the rest of the tests will be ignored.') + '</p>')
        l.addWidget(c, 0, 4, 1, 1)
        self.tagboxes = []
        self.colorboxes = []
        self.nfcolorboxes = []
        self.reboxes = []
        self.colboxes = []
        self.colors = [unicode(s) for s in list(QColor.colorNames())]
        self.colors.insert(0, '')
        for i in range(0, 10):
            w = QComboBox()
            w.addItems(self.columns)
            l.addWidget(w, i+1, 0, 1, 1)
            self.colboxes.append(w)

            tb = MultiCompleteLineEdit(self)
            tb.set_separator(', ')
            self.tagboxes.append(tb)
            l.addWidget(tb, i+1, 1, 1, 1)
            w.currentIndexChanged[str].connect(partial(self.column_changed, valbox=tb))

            w = QCheckBox(self)
            self.reboxes.append(w)
            l.addWidget(w, i+1, 2, 1, 1)

            w = QComboBox(self)
            w.addItems(self.colors)
            self.colorboxes.append(w)
            l.addWidget(w, i+1, 3, 1, 1)

            w = QComboBox(self)
            w.addItems(self.colors)
            self.nfcolorboxes.append(w)
            l.addWidget(w, i+1, 4, 1, 1)

        if txt:
            lines = txt.split('\n')[3:]
            i = 0
            for line in lines:
                if line.startswith('#'):
                    vals = line[1:].split(':|:')
                    if len(vals) == 2:
                        t, c = vals
                        nc = ''
                        re = False
                        f = 'tags'
                    else:
                        t,c,f,nc,re = vals
                    try:
                        self.colorboxes[i].setCurrentIndex(self.colorboxes[i].findText(c))
                        self.nfcolorboxes[i].setCurrentIndex(self.nfcolorboxes[i].findText(nc))
                        self.tagboxes[i].setText(t)
                        self.reboxes[i].setChecked(re == '2')
                        self.colboxes[i].setCurrentIndex(self.colboxes[i].findText(f))
                    except:
                        pass
                    i += 1

        w = QLabel(_('Preview'))
        l.addWidget(w, 99, 0, 1, 1)
        w = self.test_box = QLineEdit(self)
        w.setReadOnly(True)
        l.addWidget(w, 99, 1, 1, 1)
        w = QPushButton(_('Test'))
        l.addWidget(w, 99, 3, 1, 1)
        w.clicked.connect(self.preview)

        bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel, parent=self)
        l.addWidget(bb, 100, 3, 1, 2)
        bb.accepted.connect(self.accepted)
        bb.rejected.connect(self.reject)
        self.template = ''

    def preview(self):
        if not self.generate_program():
            return
        t = composite_formatter.safe_format(self.template, self.mi,
                                            _('EXCEPTION'), self.mi)
        self.test_box.setText(t)

    def column_changed(self, s, valbox=None):
        k = unicode(s)
        if k in self.completion_values:
            valbox.update_items_cache(self.completion_values[k]['v'])
            if self.completion_values[k]['m']:
                valbox.set_separator(', ')
            else:
                valbox.set_separator(None)
        else:
            valbox.update_items_cache([])
            valbox.set_separator(None)

    def generate_program(self):
        res = ("program:\n#tag wizard -- do not directly edit\n"
               "  first_non_empty(\n")
        lines = []
        for tb, cb, fb, nfcb, reb in zip(self.tagboxes, self.colorboxes,
                        self.colboxes, self.nfcolorboxes, self.reboxes):
            f = unicode(fb.currentText())
            if not f:
                continue
            m = self.completion_values[f]['m']
            c = unicode(cb.currentText()).strip()
            nfc = unicode(nfcb.currentText()).strip()
            re = reb.checkState()
            if m:
                tags = [t.strip() for t in unicode(tb.text()).split(',') if t.strip()]
                if re == 2:
                    tags = '$|^'.join(tags)
                else:
                    tags = ','.join(tags)
            else:
                tags = unicode(tb.text()).strip()

            if not tags or not (c or nfc):
                continue
            if c not in self.colors:
                error_dialog(self, _('Invalid color'),
                             _('The color {0} is not valid').format(c),
                             show=True, show_copy_button=False)
                return False
            if nfc not in self.colors:
                error_dialog(self, _('Invalid color'),
                             _('The color {0} is not valid').format(nfc),
                             show=True, show_copy_button=False)
                return False
            if re == 2:
                if m:
                    lines.append("    in_list(field('{3}'), ',', '^{0}$', '{1}', '{2}')".\
                             format(tags, c, nfc, f))
                else:
                    lines.append("    contains(field('{3}'), '{0}', '{1}', '{2}')".\
                             format(tags, c, nfc, f))
            else:
                if m:
                    lines.append("    str_in_list(field('{3}'), ',', '{0}', '{1}', '{2}')".\
                             format(tags, c, nfc, f))
                else:
                    lines.append("    strcmp(field('{3}'), '{0}', '{2}', '{1}', '{2}')".\
                             format(tags, c, nfc, f))
        res += ',\n'.join(lines)
        res += ')\n'
        self.template = res
        res = ''
        for tb, cb, fb, nfcb, reb in zip(self.tagboxes, self.colorboxes,
                        self.colboxes, self.nfcolorboxes, self.reboxes):
            t = unicode(tb.text()).strip()
            if t.endswith(','):
                t = t[:-1]
            c = unicode(cb.currentText()).strip()
            f = unicode(fb.currentText())
            nfc = unicode(nfcb.currentText()).strip()
            re = unicode(reb.checkState())
            if f and t and c:
                res += '#' + t + ':|:' + c  + ':|:' + f +':|:' + nfc + ':|:' + re + '\n'
        self.template += res
        return True

    def accepted(self):
        if self.generate_program():
            self.accept()
        else:
            self.template = ''
