#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import QAbstractListModel, Qt, QIcon, \
        QVariant, QItemSelectionModel

from calibre.gui2.preferences.toolbar_ui import Ui_Form
from calibre.gui2 import gprefs, NONE, warning_dialog
from calibre.gui2.preferences import ConfigWidgetBase, test_widget


class FakeAction(object):

    def __init__(self, name, icon, tooltip=None,
            dont_add_to=frozenset([]), dont_remove_from=frozenset([])):
        self.name = name
        self.action_spec = (name, icon, tooltip, None)
        self.dont_remove_from = dont_remove_from
        self.dont_add_to = dont_add_to

class BaseModel(QAbstractListModel):

    def name_to_action(self, name, gui):
        if name == 'Donate':
            return FakeAction(name, 'donate.png',
                    dont_add_to=frozenset(['context-menu',
                        'context-menu-device']))
        if name == 'Location Manager':
            return FakeAction(name, None,
                    _('Switch between library and device views'),
                    dont_remove_from=set(['toolbar-device']))
        if name is None:
            return FakeAction('--- '+_('Separator')+' ---', None)
        return gui.iactions[name]

    def rowCount(self, parent):
        return len(self._data)

    def data(self, index, role):
        row = index.row()
        action = self._data[row].action_spec
        if role == Qt.DisplayRole:
            text = action[0]
            text = text.replace('&', '')
            if text == _('%d books'):
                text = _('Choose library')
            return QVariant(text)
        if role == Qt.DecorationRole:
            ic = action[1]
            if ic is None:
                ic = 'blank.png'
            return QVariant(QIcon(I(ic)))
        if role == Qt.ToolTipRole and action[2] is not None:
            return QVariant(action[2])
        return NONE

    def names(self, indexes):
        rows = [i.row() for i in indexes]
        ans = []
        for i in rows:
            n = self._data[i].name
            if n.startswith('---'):
                n = None
            ans.append(n)
        return ans


class AllModel(BaseModel):

    def __init__(self, key, gui):
        BaseModel.__init__(self)
        self.gprefs_name = 'action-layout-'+key
        current = gprefs[self.gprefs_name]
        self.gui = gui
        self.key = key
        self._data = self.get_all_actions(current)

    def get_all_actions(self, current):
        all = list(self.gui.iactions.keys()) + ['Donate']
        all = [x for x in all if x not in current] + [None]
        all = [self.name_to_action(x, self.gui) for x in all]
        all = [x for x in all if self.key not in x.dont_add_to]
        all.sort()
        return all

    def add(self, names):
        actions = []
        for name in names:
            if name is None or name.startswith('---'): continue
            actions.append(self.name_to_action(name, self.gui))
        self._data.extend(actions)
        self._data.sort()
        self.reset()

    def remove(self, indices, allowed):
        rows = [i.row() for i in indices]
        remove = set([])
        for row in rows:
            ac = self._data[row]
            if ac.name.startswith('---'): continue
            if ac.name in allowed:
                remove.add(row)
        ndata = []
        for i, ac in enumerate(self._data):
            if i not in remove:
                ndata.append(ac)
        self._data = ndata
        self.reset()

    def restore_defaults(self):
        current = gprefs.defaults[self.gprefs_name]
        self._data = self.get_all_actions(current)
        self.reset()

class CurrentModel(BaseModel):

    def __init__(self, key, gui):
        BaseModel.__init__(self)
        self.gprefs_name = 'action-layout-'+key
        current = gprefs[self.gprefs_name]
        self._data =  [self.name_to_action(x, gui) for x in current]
        self.key = key
        self.gui = gui

    def move(self, idx, delta):
        row = idx.row()
        if row < 0 or row >= len(self._data):
            return
        nrow = row + delta
        if nrow < 0 or nrow >= len(self._data):
            return
        t = self._data[row]
        self._data[row] = self._data[nrow]
        self._data[nrow] = t
        ni = self.index(nrow)
        self.dataChanged.emit(idx, idx)
        self.dataChanged.emit(ni, ni)
        return ni

    def add(self, names):
        actions = []
        reject = set([])
        for name in names:
            ac = self.name_to_action(name, self.gui)
            if self.key in ac.dont_add_to:
                reject.add(ac)
            else:
                actions.append(ac)

        self._data.extend(actions)
        self.reset()
        return reject

    def remove(self, indices):
        rows = [i.row() for i in indices]
        remove, rejected = set([]), set([])
        for row in rows:
            ac = self._data[row]
            if self.key in ac.dont_remove_from:
                rejected.add(ac)
                continue
            remove.add(row)
        ndata = []
        for i, ac in enumerate(self._data):
            if i not in remove:
                ndata.append(ac)
        self._data = ndata
        self.reset()
        return rejected

    def commit(self):
        old = gprefs[self.gprefs_name]
        new = []
        for x in self._data:
            n = x.name
            if n.startswith('---'):
                n = None
            new.append(n)
        new = tuple(new)
        if new != old:
            defaults = gprefs.defaults[self.gprefs_name]
            if defaults == new:
                del gprefs[self.gprefs_name]
            else:
                gprefs[self.gprefs_name] = new

    def restore_defaults(self):
        current = gprefs.defaults[self.gprefs_name]
        self._data =  [self.name_to_action(x, self.gui) for x in current]
        self.reset()


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    LOCATIONS = [
            ('toolbar', _('The main toolbar')),
            ('toolbar-device', _('The main toolbar when a device is connected')),
            ('context-menu', _('The context menu for the books in the '
                'calibre library')),
            ('context-menu-device', _('The context menu for the books on '
                'the device'))
            ]

    def genesis(self, gui):
        self.models = {}
        for key, text in self.LOCATIONS:
            self.what.addItem(text, key)
            all_model = AllModel(key, gui)
            current_model = CurrentModel(key, gui)
            self.models[key] = (all_model, current_model)
        self.what.setCurrentIndex(0)
        self.what.currentIndexChanged[int].connect(self.what_changed)
        self.what_changed(0)

        self.add_action_button.clicked.connect(self.add_action)
        self.remove_action_button.clicked.connect(self.remove_action)
        self.action_up_button.clicked.connect(partial(self.move, -1))
        self.action_down_button.clicked.connect(partial(self.move, 1))

    def what_changed(self, idx):
        key = unicode(self.what.itemData(idx).toString())
        self.all_actions.setModel(self.models[key][0])
        self.current_actions.setModel(self.models[key][1])

    def add_action(self, *args):
        x = self.all_actions.selectionModel().selectedIndexes()
        names = self.all_actions.model().names(x)
        if names:
            not_added = self.current_actions.model().add(names)
            ns = set([x.name for x in not_added])
            added = set(names) - ns
            self.all_actions.model().remove(x, added)
            if not_added:
                warning_dialog(self, _('Cannot add'),
                        _('Cannot add the actions %s to this location') %
                        ','.join([a.action_spec[0] for a in not_added]),
                        show=True)
            if added:
                ca = self.current_actions
                idx = ca.model().index(ca.model().rowCount(None)-1)
                ca.scrollTo(idx)
                self.changed_signal.emit()

    def remove_action(self, *args):
        x = self.current_actions.selectionModel().selectedIndexes()
        names = self.current_actions.model().names(x)
        if names:
            not_removed = self.current_actions.model().remove(x)
            ns = set([x.name for x in not_removed])
            removed = set(names) - ns
            self.all_actions.model().add(removed)
            if not_removed:
                warning_dialog(self, _('Cannot remove'),
                        _('Cannot remove the actions %s from this location') %
                        ','.join([a.action_spec[0] for a in not_removed]),
                        show=True)
            else:
                self.changed_signal.emit()

    def move(self, delta, *args):
        ci = self.current_actions.currentIndex()
        m = self.current_actions.model()
        if ci.isValid():
            ni = m.move(ci, delta)
            if ni is not None:
                self.current_actions.setCurrentIndex(ni)
                self.current_actions.selectionModel().select(ni,
                        QItemSelectionModel.ClearAndSelect)
                self.changed_signal.emit()

    def commit(self):
        for am, cm in self.models.values():
            cm.commit()
        return False

    def restore_defaults(self):
        for am, cm in self.models.values():
            cm.restore_defaults()
            am.restore_defaults()
        self.changed_signal.emit()


if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Interface', 'Toolbar')

