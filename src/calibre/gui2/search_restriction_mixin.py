'''
Created on 10 Jun 2010

@author: charles
'''

from functools import partial

from PyQt4.Qt import (
    Qt, QMenu, QPoint, QIcon, QDialog, QGridLayout, QLabel, QLineEdit,
    QDialogButtonBox, QSize, QVBoxLayout, QListWidget, QStringList)

from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.widgets import ComboBoxWithHelp
from calibre.utils.icu import sort_key
from calibre.utils.pyparsing import ParseException
from calibre.utils.search_query_parser import saved_searches

class SelectNames(QDialog):  # {{{

    def __init__(self, names, txt, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.la = la = QLabel(_('Create a Virtual Library based on %s') % txt)
        l.addWidget(la)

        self._names = QListWidget(self)
        self._names.addItems(QStringList(sorted(names, key=sort_key)))
        self._names.setSelectionMode(self._names.ExtendedSelection)
        l.addWidget(self._names)

        self.bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        l.addWidget(self.bb)

        self.resize(self.sizeHint())

    @property
    def names(self):
        for item in self._names.selectedItems():
            yield unicode(item.data(Qt.DisplayRole).toString())
# }}}

MAX_VIRTUAL_LIBRARY_NAME_LENGTH = 40

def _build_full_search_string(gui):
    search_templates = (
        '',
        '{cl}',
        '{cr}',
        '(({cl}) and ({cr}))',
        '{sb}',
        '(({cl}) and ({sb}))',
        '(({cr}) and ({sb}))',
        '(({cl}) and ({cr}) and ({sb}))'
    )

    sb = gui.search.current_text
    db = gui.current_db
    cr = db.data.get_search_restriction()
    cl = db.data.get_base_restriction()
    dex = 0
    if sb:
        dex += 4
    if cr:
        dex += 2
    if cl:
        dex += 1
    template = search_templates[dex]
    return template.format(cl=cl, cr=cr, sb=sb).strip()

class CreateVirtualLibrary(QDialog):  # {{{

    def __init__(self, gui, existing_names, editing=None):
        QDialog.__init__(self, gui)

        self.gui = gui
        self.existing_names = existing_names

        if editing:
            self.setWindowTitle(_('Edit virtual library'))
        else:
            self.setWindowTitle(_('Create virtual library'))
        self.setWindowIcon(QIcon(I('lt.png')))

        gl = QGridLayout()
        self.setLayout(gl)
        self.la1 = la1 = QLabel(_('Virtual library &name:'))
        gl.addWidget(la1, 0, 0)
        self.vl_name = QLineEdit()
        self.vl_name.setMaxLength(MAX_VIRTUAL_LIBRARY_NAME_LENGTH)
        la1.setBuddy(self.vl_name)
        gl.addWidget(self.vl_name, 0, 1)
        self.editing = editing
        if editing:
            self.vl_name.setText(editing)

        self.la2 = la2 = QLabel(_('&Search expression:'))
        gl.addWidget(la2, 1, 0)
        self.vl_text = QLineEdit()
        la2.setBuddy(self.vl_text)
        gl.addWidget(self.vl_text, 1, 1)
        self.vl_text.setText(_build_full_search_string(self.gui))

        self.sl = sl = QLabel('<p>'+_('Create a virtual library based on: ')+
            ('<a href="author.{0}">{0}</a>, '
            '<a href="tag.{1}">{1}</a>, '
            '<a href="publisher.{2}">{2}</a>, '
            '<a href="series.{3}">{3}</a>.').format(_('Authors'), _('Tags'), _('Publishers'), _('Series')))
        sl.setWordWrap(True)
        sl.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        sl.linkActivated.connect(self.link_activated)
        gl.addWidget(sl, 2, 0, 1, 2)

        self.hl = hl = QLabel(_('''
            <h2>Virtual Libraries</h2>

            <p>Using <i>virtual libraries</i> you can restrict calibre to only show
            you books that match a search. When a virtual library is in effect, calibre
            behaves as though the library contains only the matched books. The Tag Browser
            display only the tags/authors/series/etc. that belong to the matched books and any searches
            you do will only search within the books in the virtual library. This
            is a good way to partition your large library into smaller and easier to work with subsets.</p>

            <p>For example you can use a Virtual Library to only show you books with the Tag <i>"Unread"</i>
            or only books by <i>"My Favorite Author"</i> or only books in a particular series.</p>
            '''))
        hl.setWordWrap(True)
        hl.setFrameStyle(hl.StyledPanel)
        gl.addWidget(hl, 0, 3, 4, 1)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        gl.addWidget(bb, 4, 0, 1, 0)

        if editing:
            db = self.gui.current_db
            virt_libs = db.prefs.get('virtual_libraries', {})
            self.vl_text.setText(virt_libs.get(editing, ''))

        self.resize(self.sizeHint()+QSize(150, 25))

    def link_activated(self, url):
        db = self.gui.current_db
        f, txt = unicode(url).partition('.')[0::2]
        names = getattr(db, 'all_%s_names'%f)()
        d = SelectNames(names, txt, parent=self)
        if d.exec_() == d.Accepted:
            prefix = f+'s' if f in {'tag', 'author'} else f
            search = ['%s:"=%s"'%(prefix, x.replace('"', '\\"')) for x in d.names]
            if search:
                self.vl_name.setText(d.names.next())
                self.vl_text.setText(' or '.join(search))

    def accept(self):
        n = unicode(self.vl_name.text()).strip()
        if not n:
            error_dialog(self.gui, _('No name'),
                         _('You must provide a name for the new virtual library'),
                         show=True)
            return

        if n.startswith('*'):
            error_dialog(self.gui, _('Invalid name'),
                         _('A virtual library name cannot begin with "*"'),
                         show=True)
            return

        if n in self.existing_names and n != self.editing:
            if question_dialog(self.gui, _('Name already in use'),
                         _('That name is already in use. Do you want to replace it '
                           'with the new search?'),
                            default_yes=False) == self.Rejected:
                return

        v = unicode(self.vl_text.text()).strip()
        if not v:
            error_dialog(self.gui, _('No search string'),
                         _('You must provide a search to define the new virtual library'),
                         show=True)
            return

        try:
            db = self.gui.library_view.model().db
            recs = db.data.search_getting_ids('', v, use_virtual_library=False)
        except ParseException as e:
            error_dialog(self.gui, _('Invalid search string'),
                         _('The search string is not a valid search expression'),
                         det_msg=e.msg, show=True)
            return

        if not recs and not question_dialog(
                self.gui, _('Search found no books'),
                _('The search found no books, so the virtual library '
                'will be empty. Do you really want to use that search?'),
                default_yes=False):
                return

        self.library_name = n
        self.library_search = v
        QDialog.accept(self)
# }}}

class SearchRestrictionMixin(object):

    no_restriction = _('<None>')

    def __init__(self):
        self.checked = QIcon(I('ok.png'))
        self.empty = QIcon()
        self.search_based_vl_name = None
        self.search_based_vl = None

        self.virtual_library_menu = QMenu()

        self.virtual_library.clicked.connect(self.virtual_library_clicked)

        self.virtual_library_tooltip = \
            _('Books display will show only those books matching the search')
        self.virtual_library.setToolTip(self.virtual_library_tooltip)

        self.search_restriction = ComboBoxWithHelp(self)
        self.search_restriction.setVisible(False)
        self.search_count.setText(_("(all books)"))
        self.ar_menu = QMenu(_('Additional restriction'))

    def add_virtual_library(self, db, name, search):
        virt_libs = db.prefs.get('virtual_libraries', {})
        virt_libs[name] = search
        db.prefs.set('virtual_libraries', virt_libs)

    def do_create_edit(self, editing=None):
        db = self.library_view.model().db
        virt_libs = db.prefs.get('virtual_libraries', {})
        cd = CreateVirtualLibrary(self, virt_libs.keys(), editing=editing)
        if cd.exec_() == cd.Accepted:
            if editing:
                self._remove_vl(editing, reapply=False)
            self.add_virtual_library(db, cd.library_name, cd.library_search)
            self.apply_virtual_library(cd.library_name)

    def virtual_library_clicked(self):
        m = self.virtual_library_menu
        m.clear()

        a = m.addAction(_('Create Virtual Library'))
        a.triggered.connect(partial(self.do_create_edit, editing=None))

        self.edit_menu = a = QMenu()
        a.setTitle(_('Edit Virtual Library'))
        a.aboutToShow.connect(partial(self.build_virtual_library_list, remove=False))
        m.addMenu(a)

        self.rm_menu = a = QMenu()
        a.setTitle(_('Remove Virtual Library'))
        a.aboutToShow.connect(partial(self.build_virtual_library_list, remove=True))
        m.addMenu(a)

        m.addSeparator()

        db = self.library_view.model().db

        a = self.ar_menu
        a.clear()
        a.setIcon(self.checked if db.data.get_search_restriction_name() else self.empty)
        a.aboutToShow.connect(self.build_search_restriction_list)
        m.addMenu(a)

        m.addSeparator()

        current_lib = db.data.get_base_restriction_name()

        if current_lib == '':
            a = m.addAction(self.checked, self.no_restriction)
        else:
            a = m.addAction(self.empty, self.no_restriction)
        a.triggered.connect(partial(self.apply_virtual_library, library=''))

        a = m.addAction(self.empty, _('*current search'))
        a.triggered.connect(partial(self.apply_virtual_library, library='*'))

        if self.search_based_vl_name:
            a = m.addAction(
                self.checked if db.data.get_base_restriction_name().startswith('*')
                                            else self.empty,
                             self.search_based_vl_name)
            a.triggered.connect(partial(self.apply_virtual_library,
                                library=self.search_based_vl_name))

        virt_libs = db.prefs.get('virtual_libraries', {})
        for vl in sorted(virt_libs.keys(), key=sort_key):
            a = m.addAction(self.checked if vl == current_lib else self.empty, vl)
            a.triggered.connect(partial(self.apply_virtual_library, library=vl))

        p = QPoint(0, self.virtual_library.height())
        self.virtual_library_menu.popup(self.virtual_library.mapToGlobal(p))

    def apply_virtual_library(self, library=None):
        db = self.library_view.model().db
        virt_libs = db.prefs.get('virtual_libraries', {})
        if not library:
            db.data.set_base_restriction('')
            db.data.set_base_restriction_name('')
        elif library == '*':
            if not _build_full_search_string(self):
                error_dialog(self, _('No search'),
                     _('There is no current search to use'), show=True)
                return

            self.search_based_vl = _build_full_search_string(self)
            db.data.set_base_restriction(self.search_based_vl)
            self.search_based_vl_name = self._trim_restriction_name(
                                     '*' + self.search_based_vl)
            db.data.set_base_restriction_name(self.search_based_vl_name)
        elif library == self.search_based_vl_name:
            db.data.set_base_restriction(self.search_based_vl)
            db.data.set_base_restriction_name(self.search_based_vl_name)
        elif library in virt_libs:
            db.data.set_base_restriction(virt_libs[library])
            db.data.set_base_restriction_name(library)
        self._apply_search_restriction(db.data.get_search_restriction(),
                                       db.data.get_search_restriction_name())

    def build_virtual_library_list(self, remove=False):
        db = self.library_view.model().db
        virt_libs = db.prefs.get('virtual_libraries', {})
        if remove:
            m = self.rm_menu
        else:
            m = self.edit_menu
        m.clear()

        def add_action(name, search):
            a = m.addAction(name)
            if remove:
                a.triggered.connect(partial(self.remove_vl_triggered, name=name))
            else:
                a.triggered.connect(partial(self.do_create_edit, editing=name))

        for n in sorted(virt_libs.keys(), key=sort_key):
            add_action(n, virt_libs[n])

    def remove_vl_triggered(self, name=None):
        if not question_dialog(self, _('Are you sure?'),
                     _('Are you sure you want to remove '
                       'the virtual library {0}').format(name),
                        default_yes=False):
            return
        self._remove_vl(name, reapply=True)

    def _remove_vl(self, name, reapply=True):
        db = self.library_view.model().db
        virt_libs = db.prefs.get('virtual_libraries', {})
        virt_libs.pop(name, None)
        db.prefs.set('virtual_libraries', virt_libs)
        if reapply and db.data.get_base_restriction_name() == name:
            self.apply_virtual_library('')

    def _trim_restriction_name(self, name):
        return name[0:MAX_VIRTUAL_LIBRARY_NAME_LENGTH].strip()

    def build_search_restriction_list(self):
        m = self.ar_menu
        m.clear()

        current_restriction_text = None

        if self.search_restriction.count() > 1:
            txt = unicode(self.search_restriction.itemText(2))
            if txt.startswith('*'):
                current_restriction_text = txt
        self.search_restriction.clear()

        current_restriction = self.library_view.model().db.data.get_search_restriction_name()
        m.setIcon(self.checked if current_restriction else self.empty)

        def add_action(txt, index):
            self.search_restriction.addItem(txt)
            txt = self._trim_restriction_name(txt)
            if txt == current_restriction:
                a = m.addAction(self.checked, txt if txt else self.no_restriction)
            else:
                a = m.addAction(self.empty, txt if txt else self.no_restriction)
            a.triggered.connect(partial(self.search_restriction_triggered,
                                        action=a, index=index))

        add_action('', 0)
        add_action(_('*current search'), 1)
        dex = 2
        if current_restriction_text:
            add_action(current_restriction_text, 2)
            dex += 1

        for n in sorted(saved_searches().names(), key=sort_key):
            add_action(n, dex)
            dex += 1

    def search_restriction_triggered(self, action=None, index=None):
        self.search_restriction.setCurrentIndex(index)
        self.apply_search_restriction(index)

    def apply_named_search_restriction(self, name):
        if not name:
            r = 0
        else:
            r = self.search_restriction.findText(name)
            if r < 0:
                r = 0
        self.search_restriction.setCurrentIndex(r)
        self.apply_search_restriction(r)

    def apply_text_search_restriction(self, search):
        search = unicode(search)
        if not search:
            self.search_restriction.setCurrentIndex(0)
            self._apply_search_restriction('', '')
        else:
            s = '*' + search
            if self.search_restriction.count() > 1:
                txt = unicode(self.search_restriction.itemText(2))
                if txt.startswith('*'):
                    self.search_restriction.setItemText(2, s)
                else:
                    self.search_restriction.insertItem(2, s)
            else:
                self.search_restriction.insertItem(2, s)
            self.search_restriction.setCurrentIndex(2)
            self._apply_search_restriction(search, self._trim_restriction_name(s))

    def apply_search_restriction(self, i):
        if i == 1:
            self.apply_text_search_restriction(unicode(self.search.currentText()))
        elif i == 2 and unicode(self.search_restriction.currentText()).startswith('*'):
            self.apply_text_search_restriction(
                                unicode(self.search_restriction.currentText())[1:])
        else:
            r = unicode(self.search_restriction.currentText())
            if r is not None and r != '':
                restriction = 'search:"%s"'%(r)
            else:
                restriction = ''
            self._apply_search_restriction(restriction, r)

    def _apply_search_restriction(self, restriction, name):
        self.saved_search.clear()
        # The order below is important. Set the restriction, force a '' search
        # to apply it, reset the tag browser to take it into account, then set
        # the book count.
        self.library_view.model().db.data.set_search_restriction(restriction)
        self.library_view.model().db.data.set_search_restriction_name(name)
        self.search.clear(emit_search=True)
        self.tags_view.recount()
        self.set_number_of_books_shown()
        self.current_view().setFocus(Qt.OtherFocusReason)
        self.set_window_title()

    def set_number_of_books_shown(self):
        db = self.library_view.model().db
        if self.current_view() == self.library_view and db is not None and \
                                            db.data.search_restriction_applied():
            rows = self.current_view().row_count()
            rbc = max(rows, db.data.get_search_restriction_book_count())
            t = _("({0} of {1})").format(rows, rbc)
            self.search_count.setStyleSheet(
                'QLabel { border-radius: 8px; background-color: yellow; }')
        else:  # No restriction or not library view
            if not self.search.in_a_search():
                t = _("(all books)")
            else:
                t = _("({0} of all)").format(self.current_view().row_count())
            self.search_count.setStyleSheet(
                    'QLabel { background-color: transparent; }')
        self.search_count.setText(t)

if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.gui2.preferences import init_gui
    app = Application([])
    app
    gui = init_gui()
    d = CreateVirtualLibrary(gui, [])
    d.exec_()


