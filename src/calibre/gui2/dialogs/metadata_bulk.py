__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''Dialog to edit metadata in bulk'''

import re

from PyQt4.Qt import Qt, QDialog, QGridLayout, QVBoxLayout, QFont, QLabel, \
                     pyqtSignal, QDialogButtonBox
from PyQt4 import QtGui

from calibre.gui2.dialogs.metadata_bulk_ui import Ui_MetadataBulkDialog
from calibre.gui2.dialogs.tag_editor import TagEditor
from calibre.ebooks.metadata import string_to_authors, authors_to_string
from calibre.gui2.custom_column_widgets import populate_metadata_page
from calibre.gui2 import error_dialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.utils.config import dynamic
from calibre.utils.titlecase import titlecase

class MyBlockingBusy(QDialog):

    do_one_signal = pyqtSignal()

    phases = ['',
              _('Title/Author'),
              _('Standard metadata'),
              _('Custom metadata'),
              _('Search/Replace'),
    ]

    def __init__(self, msg, args, db, ids, cc_widgets, s_r_func,
                 parent=None, window_title=_('Working')):
        QDialog.__init__(self, parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self.msg_text = msg
        self.msg = QLabel(msg+'        ') # Ensure dialog is wide enough
        #self.msg.setWordWrap(True)
        self.font = QFont()
        self.font.setPointSize(self.font.pointSize() + 8)
        self.msg.setFont(self.font)
        self.pi = ProgressIndicator(self)
        self.pi.setDisplaySize(100)
        self._layout.addWidget(self.pi, 0, Qt.AlignHCenter)
        self._layout.addSpacing(15)
        self._layout.addWidget(self.msg, 0, Qt.AlignHCenter)
        self.setWindowTitle(window_title)
        self.resize(self.sizeHint())
        self.start()

        self.args = args
        self.series_start_value = None
        self.db = db
        self.ids = ids
        self.error = None
        self.cc_widgets = cc_widgets
        self.s_r_func = s_r_func
        self.do_one_signal.connect(self.do_one_safe, Qt.QueuedConnection)

    def start(self):
        self.pi.startAnimation()

    def stop(self):
        self.pi.stopAnimation()

    def accept(self):
        self.stop()
        return QDialog.accept(self)

    def exec_(self):
        self.current_index = 0
        self.current_phase = 1
        self.do_one_signal.emit()
        return QDialog.exec_(self)

    def do_one_safe(self):
        try:
            if self.current_index >= len(self.ids):
                self.current_phase += 1
                self.current_index = 0
                if self.current_phase > 4:
                    self.db.commit()
                    return self.accept()
            id = self.ids[self.current_index]
            percent = int((self.current_index*100)/float(len(self.ids)))
            self.msg.setText(self.msg_text.format(self.phases[self.current_phase],
                                        percent))
            self.do_one(id)
        except Exception, err:
            import traceback
            try:
                err = unicode(err)
            except:
                err = repr(err)
            self.error = (err, traceback.format_exc())
            return self.accept()

    def do_one(self, id):
        remove_all, remove, add, au, aus, do_aus, rating, pub, do_series, \
            do_autonumber, do_remove_format, remove_format, do_swap_ta, \
            do_remove_conv, do_auto_author, series, do_series_restart, \
            series_start_value, do_title_case, clear_series = self.args


        # first loop: do author and title. These will commit at the end of each
        # operation, because each operation modifies the file system. We want to
        # try hard to keep the DB and the file system in sync, even in the face
        # of exceptions or forced exits.
        if self.current_phase == 1:
            title_set = False
            if do_swap_ta:
                title = self.db.title(id, index_is_id=True)
                aum = self.db.authors(id, index_is_id=True)
                if aum:
                    aum = [a.strip().replace('|', ',') for a in aum.split(',')]
                    new_title = authors_to_string(aum)
                    if do_title_case:
                        new_title = titlecase(new_title)
                    self.db.set_title(id, new_title, notify=False)
                    title_set = True
                if title:
                    new_authors = string_to_authors(title)
                    self.db.set_authors(id, new_authors, notify=False)
            if do_title_case and not title_set:
                title = self.db.title(id, index_is_id=True)
                self.db.set_title(id, titlecase(title), notify=False)
            if au:
                self.db.set_authors(id, string_to_authors(au), notify=False)
        elif self.current_phase == 2:
            # All of these just affect the DB, so we can tolerate a total rollback
            if do_auto_author:
                x = self.db.author_sort_from_book(id, index_is_id=True)
                if x:
                    self.db.set_author_sort(id, x, notify=False, commit=False)

            if aus and do_aus:
                self.db.set_author_sort(id, aus, notify=False, commit=False)

            if rating != -1:
                self.db.set_rating(id, 2*rating, notify=False, commit=False)

            if pub:
                self.db.set_publisher(id, pub, notify=False, commit=False)

            if clear_series:
                self.db.set_series(id, '', notify=False, commit=False)

            if do_series:
                if do_series_restart:
                    if self.series_start_value is None:
                        self.series_start_value = series_start_value
                    next = self.series_start_value
                    self.series_start_value += 1
                else:
                    next = self.db.get_next_series_num_for(series)
                self.db.set_series(id, series, notify=False, commit=False)
                num = next if do_autonumber and series else 1.0
                self.db.set_series_index(id, num, notify=False, commit=False)

            if do_remove_format:
                self.db.remove_format(id, remove_format, index_is_id=True, notify=False, commit=False)

            if do_remove_conv:
                self.db.delete_conversion_options(id, 'PIPE', commit=False)
        elif self.current_phase == 3:
            # both of these are fast enough to just do them all
            for w in self.cc_widgets:
                w.commit(self.ids)
            if remove_all:
                self.db.remove_all_tags(self.ids)
            self.db.bulk_modify_tags(self.ids, add=add, remove=remove,
                                         notify=False)
            self.current_index = len(self.ids)
        elif self.current_phase == 4:
            self.s_r_func(id)
        # do the next one
        self.current_index += 1
        self.do_one_signal.emit()


class MetadataBulkDialog(QDialog, Ui_MetadataBulkDialog):

    s_r_functions = {       ''              : lambda x: x,
                            _('Lower Case') : lambda x: x.lower(),
                            _('Upper Case') : lambda x: x.upper(),
                            _('Title Case') : lambda x: titlecase(x),
                    }

    s_r_match_modes = [     _('Character match'),
                            _('Regular Expression'),
                      ]

    s_r_replace_modes = [   _('Replace field'),
                            _('Prepend to field'),
                            _('Append to field'),
                        ]

    def __init__(self, window, rows, model, tab):
        QDialog.__init__(self, window)
        Ui_MetadataBulkDialog.__init__(self)
        self.setupUi(self)
        self.model = model
        self.db = model.db
        self.ids = [self.db.id(r) for r in rows]
        self.box_title.setText('<p>' +
                _('Editing meta information for <b>%d books</b>') %
                len(rows))
        self.write_series = False
        self.changed = False

        all_tags = self.db.all_tags()
        self.tags.update_tags_cache(all_tags)
        self.remove_tags.update_tags_cache(all_tags)

        self.initialize_combos()

        for f in self.db.all_formats():
            self.remove_format.addItem(f)

        self.remove_format.setCurrentIndex(-1)

        self.series.currentIndexChanged[int].connect(self.series_changed)
        self.series.editTextChanged.connect(self.series_changed)
        self.tag_editor_button.clicked.connect(self.tag_editor)
        self.autonumber_series.stateChanged[int].connect(self.auto_number_changed)

        if len(self.db.custom_field_keys(include_composites=False)) == 0:
            self.central_widget.removeTab(1)
        else:
            self.create_custom_column_editors()

        self.prepare_search_and_replace()

        self.button_box.clicked.connect(self.button_clicked)
        self.button_box.button(QDialogButtonBox.Apply).setToolTip(_(
            'Immediately make all changes without closing the dialog. '
            'This operation cannot be canceled or undone'))
        self.do_again = False
        self.central_widget.setCurrentIndex(tab)
        self.exec_()

    def button_clicked(self, which):
        if which == self.button_box.button(QDialogButtonBox.Apply):
            self.do_again = True
            self.accept()

    def prepare_search_and_replace(self):
        self.search_for.initialize('bulk_edit_search_for')
        self.replace_with.initialize('bulk_edit_replace_with')
        self.test_text.initialize('bulk_edit_test_test')
        self.all_fields = ['']
        self.writable_fields = ['']
        fm = self.db.field_metadata
        for f in fm:
            if (f in ['author_sort'] or
                    (fm[f]['datatype'] in ['text', 'series']
                     and fm[f].get('search_terms', None)
                     and f not in ['formats', 'ondevice', 'sort'])):
                self.all_fields.append(f)
                self.writable_fields.append(f)
            if f in ['sort'] or fm[f]['datatype'] == 'composite':
                self.all_fields.append(f)
        self.all_fields.sort()
        self.writable_fields.sort()
        self.search_field.setMaxVisibleItems(20)
        self.destination_field.setMaxVisibleItems(20)
        offset = 10
        self.s_r_number_of_books = min(10, len(self.ids))
        for i in range(1,self.s_r_number_of_books+1):
            w = QtGui.QLabel(self.tabWidgetPage3)
            w.setText(_('Book %d:')%i)
            self.testgrid.addWidget(w, i+offset, 0, 1, 1)
            w = QtGui.QLineEdit(self.tabWidgetPage3)
            w.setReadOnly(True)
            name = 'book_%d_text'%i
            setattr(self, name, w)
            self.book_1_text.setObjectName(name)
            self.testgrid.addWidget(w, i+offset, 1, 1, 1)
            w = QtGui.QLineEdit(self.tabWidgetPage3)
            w.setReadOnly(True)
            name = 'book_%d_result'%i
            setattr(self, name, w)
            self.book_1_text.setObjectName(name)
            self.testgrid.addWidget(w, i+offset, 2, 1, 1)

        self.main_heading = _(
                 '<b>You can destroy your library using this feature.</b> '
                 'Changes are permanent. There is no undo function. '
                 'You are strongly encouraged to back up your library '
                 'before proceeding.<p>'
                 'Search and replace in text fields using character matching '
                 'or regular expressions. ')

        self.character_heading = _(
                 'In character mode, the field is searched for the entered '
                 'search text. The text is replaced by the specified replacement '
                 'text everywhere it is found in the specified field. After '
                 'replacement is finished, the text can be changed to '
                 'upper-case, lower-case, or title-case. If the case-sensitive '
                 'check box is checked, the search text must match exactly. If '
                 'it is unchecked, the search text will match both upper- and '
                 'lower-case letters'
                 )

        self.regexp_heading = _(
                 'In regular expression mode, the search text is an '
                 'arbitrary python-compatible regular expression. The '
                 'replacement text can contain backreferences to parenthesized '
                 'expressions in the pattern. The search is not anchored, '
                 'and can match and replace multiple times on the same string. '
                 'The modification functions (lower-case etc) are applied to the '
                 'matched text, not to the field as a whole. '
                 'The destination box specifies the field where the result after '
                 'matching and replacement is to be assigned. You can replace '
                 'the text in the field, or prepend or append the matched text. '
                 'See <a href="http://docs.python.org/library/re.html"> '
                 'this reference</a> for more information on python\'s regular '
                 'expressions, and in particular the \'sub\' function.'
                 )

        self.search_mode.addItems(self.s_r_match_modes)
        self.search_mode.setCurrentIndex(dynamic.get('s_r_search_mode', 0))
        self.replace_mode.addItems(self.s_r_replace_modes)
        self.replace_mode.setCurrentIndex(0)

        self.s_r_search_mode = 0
        self.s_r_error = None
        self.s_r_obj = None

        self.replace_func.addItems(sorted(self.s_r_functions.keys()))
        self.search_mode.currentIndexChanged[int].connect(self.s_r_search_mode_changed)
        self.search_field.currentIndexChanged[int].connect(self.s_r_search_field_changed)
        self.destination_field.currentIndexChanged[str].connect(self.s_r_destination_field_changed)

        self.replace_mode.currentIndexChanged[int].connect(self.s_r_paint_results)
        self.replace_func.currentIndexChanged[str].connect(self.s_r_paint_results)
        self.search_for.editTextChanged[str].connect(self.s_r_paint_results)
        self.replace_with.editTextChanged[str].connect(self.s_r_paint_results)
        self.test_text.editTextChanged[str].connect(self.s_r_paint_results)
        self.comma_separated.stateChanged.connect(self.s_r_paint_results)
        self.case_sensitive.stateChanged.connect(self.s_r_paint_results)
        self.central_widget.setCurrentIndex(0)

        self.search_for.completer().setCaseSensitivity(Qt.CaseSensitive)
        self.replace_with.completer().setCaseSensitivity(Qt.CaseSensitive)

        self.s_r_search_mode_changed(self.search_mode.currentIndex())

    def s_r_get_field(self, mi, field):
        if field:
            fm = self.db.metadata_for_field(field)
            if field == 'sort':
                val = mi.get('title_sort', None)
            else:
                val = mi.get(field, None)
            if val is None:
                val = []
            elif not fm['is_multiple']:
                val = [val]
            elif field == 'authors':
                val = [v.replace(',', '|') for v in val]
        else:
            val = []
        return val

    def s_r_search_field_changed(self, idx):
        for i in range(0, self.s_r_number_of_books):
            w = getattr(self, 'book_%d_text'%(i+1))
            mi = self.db.get_metadata(self.ids[i], index_is_id=True)
            src = unicode(self.search_field.currentText())
            t = self.s_r_get_field(mi, src)
            w.setText(''.join(t[0:1]))

        if self.search_mode.currentIndex() == 0:
            self.destination_field.setCurrentIndex(idx)
        else:
            self.s_r_paint_results(None)

    def s_r_destination_field_changed(self, txt):
        txt = unicode(txt)
        self.comma_separated.setEnabled(True)
        if txt:
            fm = self.db.metadata_for_field(txt)
            if fm['is_multiple']:
                self.comma_separated.setEnabled(False)
                self.comma_separated.setChecked(True)
        self.s_r_paint_results(None)

    def s_r_search_mode_changed(self, val):
        self.search_field.clear()
        self.destination_field.clear()
        if val == 0:
            self.search_field.addItems(self.writable_fields)
            self.destination_field.addItems(self.writable_fields)
            self.destination_field.setCurrentIndex(0)
            self.destination_field.setVisible(False)
            self.destination_field_label.setVisible(False)
            self.replace_mode.setCurrentIndex(0)
            self.replace_mode.setVisible(False)
            self.replace_mode_label.setVisible(False)
            self.comma_separated.setVisible(False)
            self.s_r_heading.setText('<p>'+self.main_heading + self.character_heading)
        else:
            self.search_field.addItems(self.all_fields)
            self.destination_field.addItems(self.writable_fields)
            self.destination_field.setVisible(True)
            self.destination_field_label.setVisible(True)
            self.replace_mode.setVisible(True)
            self.replace_mode_label.setVisible(True)
            self.comma_separated.setVisible(True)
            self.s_r_heading.setText('<p>'+self.main_heading + self.regexp_heading)
        self.s_r_paint_results(None)

    def s_r_set_colors(self):
        if self.s_r_error is not None:
            col = 'rgb(255, 0, 0, 20%)'
            self.test_result.setText(self.s_r_error.message)
        else:
            col = 'rgb(0, 255, 0, 20%)'
        self.test_result.setStyleSheet('QLineEdit { color: black; '
                                       'background-color: %s; }'%col)
        for i in range(0,self.s_r_number_of_books):
            getattr(self, 'book_%d_result'%(i+1)).setText('')

    def s_r_func(self, match):
        rfunc = self.s_r_functions[unicode(self.replace_func.currentText())]
        rtext = unicode(self.replace_with.text())
        rtext = match.expand(rtext)
        return rfunc(rtext)

    def s_r_do_regexp(self, mi):
        src_field = unicode(self.search_field.currentText())
        src = self.s_r_get_field(mi, src_field)
        result = []
        rfunc = self.s_r_functions[unicode(self.replace_func.currentText())]
        for s in src:
            t = self.s_r_obj.sub(self.s_r_func, s)
            if self.search_mode.currentIndex() == 0:
                t = rfunc(t)
            result.append(t)
        return result

    def s_r_do_destination(self, mi, val):
        src = unicode(self.search_field.currentText())
        if src == '':
            return ''
        dest = unicode(self.destination_field.currentText())
        if dest == '':
            if self.db.metadata_for_field(src)['datatype'] == 'composite':
                raise Exception(_('You must specify a destination when source is a composite field'))
            dest = src
        dest_mode = self.replace_mode.currentIndex()

        if dest_mode != 0:
            dest_val = mi.get(dest, '')
            if dest_val is None:
                dest_val = []
            elif isinstance(dest_val, list):
                if dest == 'authors':
                    dest_val = [v.replace(',', '|') for v in dest_val]
            else:
                dest_val = [dest_val]
        else:
            dest_val = []

        if len(val) > 0:
            if src == 'authors':
                val = [v.replace(',', '|') for v in val]
        if dest_mode == 1:
            val.extend(dest_val)
        elif dest_mode == 2:
            val[0:0] = dest_val
        return val

    def s_r_replace_mode_separator(self):
        if self.comma_separated.isChecked():
            return ','
        return ''

    def s_r_paint_results(self, txt):
        self.s_r_error = None
        self.s_r_set_colors()

        if self.case_sensitive.isChecked():
            flags = 0
        else:
            flags = re.I

        try:
            if self.search_mode.currentIndex() == 0:
                self.s_r_obj = re.compile(re.escape(unicode(self.search_for.text())), flags)
            else:
                self.s_r_obj = re.compile(unicode(self.search_for.text()), flags)
        except Exception as e:
            self.s_r_obj = None
            self.s_r_error = e
            self.s_r_set_colors()
            return

        try:
            self.test_result.setText(self.s_r_obj.sub(self.s_r_func,
                                     unicode(self.test_text.text())))
        except Exception as e:
            self.s_r_error = e
            self.s_r_set_colors()
            return

        for i in range(0,self.s_r_number_of_books):
            mi = self.db.get_metadata(self.ids[i], index_is_id=True)
            wr = getattr(self, 'book_%d_result'%(i+1))
            try:
                result = self.s_r_do_regexp(mi)
                t = self.s_r_do_destination(mi, result[0:1])
                t = self.s_r_replace_mode_separator().join(t)
                wr.setText(t)
            except Exception as e:
                self.s_r_error = e
                self.s_r_set_colors()
                break

    def do_search_replace(self, id):
        source = unicode(self.search_field.currentText())
        if not source or not self.s_r_obj:
            return
        dest = unicode(self.destination_field.currentText())
        if not dest:
            dest = source
        dfm = self.db.field_metadata[dest]

        mi = self.db.get_metadata(id, index_is_id=True,)
        val = mi.get(source)
        if val is None:
            return
        val = self.s_r_do_regexp(mi)
        val = self.s_r_do_destination(mi, val)
        if dfm['is_multiple']:
            if dfm['is_custom']:
                # The standard tags and authors values want to be lists.
                # All custom columns are to be strings
                val = dfm['is_multiple'].join(val)
            if dest == 'authors' and len(val) == 0:
                error_dialog(self, _('Search/replace invalid'),
                             _('Authors cannot be set to the empty string. '
                               'Book title %s not processed')%mi.title,
                             show=True)
                return
        else:
            val = self.s_r_replace_mode_separator().join(val)
            if dest == 'title' and len(val) == 0:
                error_dialog(self, _('Search/replace invalid'),
                             _('Title cannot be set to the empty string. '
                               'Book title %s not processed')%mi.title,
                             show=True)
                return

        if dfm['is_custom']:
            extra = self.db.get_custom_extra(id, label=dfm['label'], index_is_id=True)
            self.db.set_custom(id, val, label=dfm['label'], extra=extra,
                               commit=False)
        else:
            if dest == 'comments':
                setter = self.db.set_comment
            else:
                setter = getattr(self.db, 'set_'+dest)
            if dest in ['title', 'authors']:
                setter(id, val, notify=False)
            else:
                setter(id, val, notify=False, commit=False)

    def create_custom_column_editors(self):
        w = self.central_widget.widget(1)
        layout = QGridLayout()
        self.custom_column_widgets, self.__cc_spacers = \
            populate_metadata_page(layout, self.db, self.ids, parent=w,
                                   two_column=False, bulk=True)
        w.setLayout(layout)
        self.__custom_col_layouts = [layout]
        ans = self.custom_column_widgets
        for i in range(len(ans)-1):
            w.setTabOrder(ans[i].widgets[-1], ans[i+1].widgets[1])
            for c in range(2, len(ans[i].widgets), 2):
                w.setTabOrder(ans[i].widgets[c-1], ans[i].widgets[c+1])

    def initialize_combos(self):
        self.initalize_authors()
        self.initialize_series()
        self.initialize_publisher()
        for x in ('authors', 'publisher', 'series'):
            x = getattr(self, x)
            x.setSizeAdjustPolicy(x.AdjustToMinimumContentsLengthWithIcon)
            x.setMinimumContentsLength(25)

    def initalize_authors(self):
        all_authors = self.db.all_authors()
        all_authors.sort(cmp=lambda x, y : cmp(x[1].lower(), y[1].lower()))

        for i in all_authors:
            id, name = i
            name = name.strip().replace('|', ',')
            self.authors.addItem(name)
        self.authors.setEditText('')

    def initialize_series(self):
        all_series = self.db.all_series()
        all_series.sort(cmp=lambda x, y : cmp(x[1], y[1]))

        for i in all_series:
            id, name = i
            self.series.addItem(name)
        self.series.setEditText('')

    def initialize_publisher(self):
        all_publishers = self.db.all_publishers()
        all_publishers.sort(cmp=lambda x, y : cmp(x[1], y[1]))

        for i in all_publishers:
            id, name = i
            self.publisher.addItem(name)
        self.publisher.setEditText('')

    def tag_editor(self, *args):
        d = TagEditor(self, self.db, None)
        d.exec_()
        if d.result() == QDialog.Accepted:
            tag_string = ', '.join(d.tags)
            self.tags.setText(tag_string)
            self.tags.update_tags_cache(self.db.all_tags())
            self.remove_tags.update_tags_cache(self.db.all_tags())

    def auto_number_changed(self, state):
        if state:
            self.series_numbering_restarts.setEnabled(True)
            self.series_start_number.setEnabled(True)
        else:
            self.series_numbering_restarts.setEnabled(False)
            self.series_numbering_restarts.setChecked(False)
            self.series_start_number.setEnabled(False)
            self.series_start_number.setValue(1)

    def accept(self):
        if len(self.ids) < 1:
            return QDialog.accept(self)

        if self.s_r_error is not None:
            error_dialog(self, _('Search/replace invalid'),
                    _('Search pattern is invalid: %s')%self.s_r_error.message,
                    show=True)
            return False
        self.changed = bool(self.ids)
        # Cache values from GUI so that Qt widgets are not used in
        # non GUI thread
        for w in getattr(self, 'custom_column_widgets', []):
            w.gui_val

        remove_all = self.remove_all_tags.isChecked()
        remove = []
        if not remove_all:
            remove = unicode(self.remove_tags.text()).strip().split(',')
        add = unicode(self.tags.text()).strip().split(',')
        au = unicode(self.authors.text())
        aus = unicode(self.author_sort.text())
        do_aus = self.author_sort.isEnabled()
        rating = self.rating.value()
        pub = unicode(self.publisher.text())
        do_series = self.write_series
        clear_series = self.clear_series.isChecked()
        series = unicode(self.series.currentText()).strip()
        do_autonumber = self.autonumber_series.isChecked()
        do_series_restart = self.series_numbering_restarts.isChecked()
        series_start_value = self.series_start_number.value()
        do_remove_format = self.remove_format.currentIndex() > -1
        remove_format = unicode(self.remove_format.currentText())
        do_swap_ta = self.swap_title_and_author.isChecked()
        do_remove_conv = self.remove_conversion_settings.isChecked()
        do_auto_author = self.auto_author_sort.isChecked()
        do_title_case = self.change_title_to_title_case.isChecked()

        args = (remove_all, remove, add, au, aus, do_aus, rating, pub, do_series,
                do_autonumber, do_remove_format, remove_format, do_swap_ta,
                do_remove_conv, do_auto_author, series, do_series_restart,
                series_start_value, do_title_case, clear_series)

        bb = MyBlockingBusy(_('Applying changes to %d books.\nPhase {0} {1}%%.')
                %len(self.ids), args, self.db, self.ids,
                getattr(self, 'custom_column_widgets', []),
                self.do_search_replace, parent=self)

        # The metadata backup thread causes database commits
        # which can slow down bulk editing of large numbers of books
        self.model.stop_metadata_backup()
        try:
            bb.exec_()
        finally:
            self.model.start_metadata_backup()

        if bb.error is not None:
            return error_dialog(self, _('Failed'),
                    bb.error[0], det_msg=bb.error[1],
                    show=True)

        dynamic['s_r_search_mode'] = self.search_mode.currentIndex()
        self.db.clean()
        return QDialog.accept(self)

    def series_changed(self, *args):
        self.write_series = True

