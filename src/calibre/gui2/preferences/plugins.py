#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, os

from PyQt4.Qt import Qt, QModelIndex, QAbstractItemModel, QVariant, QIcon, \
        QBrush

from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.plugins_ui import Ui_Form
from calibre.customize.ui import initialized_plugins, is_disabled, enable_plugin, \
                                 disable_plugin, plugin_customization, add_plugin, \
                                 remove_plugin
from calibre.gui2 import NONE, error_dialog, info_dialog, choose_files, \
        question_dialog

class PluginModel(QAbstractItemModel): # {{{

    def __init__(self, *args):
        QAbstractItemModel.__init__(self, *args)
        self.icon = QVariant(QIcon(I('plugins.png')))
        p = QIcon(self.icon).pixmap(32, 32, QIcon.Disabled, QIcon.On)
        self.disabled_icon = QVariant(QIcon(p))
        self._p = p
        self.populate()

    def populate(self):
        self._data = {}
        for plugin in initialized_plugins():
            if plugin.type not in self._data:
                self._data[plugin.type] = [plugin]
            else:
                self._data[plugin.type].append(plugin)
        self.categories = sorted(self._data.keys())

        for plugins in self._data.values():
            plugins.sort(cmp=lambda x, y: cmp(x.name.lower(), y.name.lower()))

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if parent.isValid():
            return self.createIndex(row, column, 1+parent.row())
        else:
            return self.createIndex(row, column, 0)

    def parent(self, index):
        if not index.isValid() or index.internalId() == 0:
            return QModelIndex()
        return self.createIndex(index.internalId()-1, 0, 0)

    def rowCount(self, parent):
        if not parent.isValid():
            return len(self.categories)
        if parent.internalId() == 0:
            category = self.categories[parent.row()]
            return len(self._data[category])
        return 0

    def columnCount(self, parent):
        return 1

    def index_to_plugin(self, index):
        category = self.categories[index.parent().row()]
        return self._data[category][index.row()]

    def plugin_to_index(self, plugin):
        for i, category in enumerate(self.categories):
            parent = self.index(i, 0, QModelIndex())
            for j, p in enumerate(self._data[category]):
                if plugin == p:
                    return self.index(j, 0, parent)
        return QModelIndex()

    def refresh_plugin(self, plugin, rescan=False):
        if rescan:
            self.populate()
        idx = self.plugin_to_index(plugin)
        self.dataChanged.emit(idx, idx)

    def flags(self, index):
        if not index.isValid():
            return 0
        if index.internalId() == 0:
            return Qt.ItemIsEnabled
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        return flags

    def data(self, index, role):
        if not index.isValid():
            return NONE
        if index.internalId() == 0:
            if role == Qt.DisplayRole:
                category = self.categories[index.row()]
                return QVariant(_("%(plugin_type)s %(plugins)s")%\
                        dict(plugin_type=category, plugins=_('plugins')))
        else:
            plugin = self.index_to_plugin(index)
            if role == Qt.DisplayRole:
                ver = '.'.join(map(str, plugin.version))
                desc = '\n'.join(textwrap.wrap(plugin.description, 100))
                ans='%s (%s) %s %s\n%s'%(plugin.name, ver, _('by'), plugin.author, desc)
                c = plugin_customization(plugin)
                if c:
                    ans += _('\nCustomization: ')+c
                return QVariant(ans)
            if role == Qt.DecorationRole:
                return self.disabled_icon if is_disabled(plugin) else self.icon
            if role == Qt.ForegroundRole and is_disabled(plugin):
                return QVariant(QBrush(Qt.gray))
            if role == Qt.UserRole:
                return plugin
        return NONE

# }}}

class ConfigWidget(ConfigWidgetBase, Ui_Form):

    supports_restoring_to_defaults = False

    def genesis(self, gui):
        self.gui = gui
        self._plugin_model = PluginModel()
        self.plugin_view.setModel(self._plugin_model)
        self.plugin_view.setStyleSheet(
                "QTreeView::item { padding-bottom: 10px;}")
        self.plugin_view.doubleClicked.connect(self.double_clicked)
        self.toggle_plugin_button.clicked.connect(self.toggle_plugin)
        self.customize_plugin_button.clicked.connect(self.customize_plugin)
        self.remove_plugin_button.clicked.connect(self.remove_plugin)
        self.button_plugin_add.clicked.connect(self.add_plugin)

    def toggle_plugin(self, *args):
        self.modify_plugin(op='toggle')

    def double_clicked(self, index):
        if index.parent().isValid():
            self.modify_plugin(op='customize')

    def customize_plugin(self, *args):
        self.modify_plugin(op='customize')

    def remove_plugin(self, *args):
        self.modify_plugin(op='remove')

    def add_plugin(self):
        path = choose_files(self, 'add a plugin dialog', _('Add plugin'),
                filters=[(_('Plugins'), ['zip'])], all_files=False,
                    select_only_single_file=True)
        if not path:
            return
        path = path[0]
        if path and  os.access(path, os.R_OK) and path.lower().endswith('.zip'):
            if not question_dialog(self, _('Are you sure?'), '<p>' + \
                    _('Installing plugins is a <b>security risk</b>. '
                    'Plugins can contain a virus/malware. '
                        'Only install it if you got it from a trusted source.'
                        ' Are you sure you want to proceed?'),
                    show_copy_button=False):
                return
            plugin = add_plugin(path)
            self._plugin_model.populate()
            self._plugin_model.reset()
            self.changed_signal.emit()
            info_dialog(self, _('Success'),
                    _('Plugin <b>{0}</b> successfully installed under <b>'
                        ' {1} plugins</b>. You may have to restart calibre '
                        'for the plugin to take effect.').format(plugin.name, plugin.type),
                    show=True)
        else:
            error_dialog(self, _('No valid plugin path'),
                         _('%s is not a valid plugin path')%path).exec_()


    def modify_plugin(self, op=''):
        index = self.plugin_view.currentIndex()
        if index.isValid():
            plugin = self._plugin_model.index_to_plugin(index)
            if op == 'toggle':
                if not plugin.can_be_disabled:
                    error_dialog(self,_('Plugin cannot be disabled'),
                                 _('The plugin: %s cannot be disabled')%plugin.name).exec_()
                    return
                if is_disabled(plugin):
                    enable_plugin(plugin)
                else:
                    disable_plugin(plugin)
                self._plugin_model.refresh_plugin(plugin)
                self.changed_signal.emit()
            if op == 'customize':
                if not plugin.is_customizable():
                    info_dialog(self, _('Plugin not customizable'),
                        _('Plugin: %s does not need customization')%plugin.name).exec_()
                    return
                self.changed_signal.emit()
                if plugin.do_user_config():
                    self._plugin_model.refresh_plugin(plugin)
            elif op == 'remove':
                if remove_plugin(plugin):
                    self._plugin_model.populate()
                    self._plugin_model.reset()
                    self.changed_signal.emit()
                else:
                    error_dialog(self, _('Cannot remove builtin plugin'),
                         plugin.name + _(' cannot be removed. It is a '
                         'builtin plugin. Try disabling it instead.')).exec_()


if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Advanced', 'Plugins')

