from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, shutil, traceback, functools, sys

from calibre.customize import Plugin, FileTypePlugin, MetadataReaderPlugin, \
                              MetadataWriterPlugin
from calibre.customize.builtins import plugins as builtin_plugins
from calibre.constants import __version__, iswindows, isosx
from calibre.ebooks.metadata import MetaInformation
from calibre.utils.config import make_config_dir, Config, ConfigProxy, \
                                 plugin_dir, OptionParser


version = tuple([int(x) for x in __version__.split('.')])

platform = 'linux'
if iswindows:
    platform = 'windows'
if isosx:
    platform = 'osx'

from zipfile import ZipFile

def _config():
    c = Config('customize')
    c.add_opt('plugins', default={}, help=_('Installed plugins'))
    c.add_opt('filetype_mapping', default={}, help=_('Mapping for filetype plugins'))
    c.add_opt('plugin_customization', default={}, help=_('Local plugin customization'))
    c.add_opt('disabled_plugins', default=set([]), help=_('Disabled plugins'))
    
    return ConfigProxy(c)

config = _config()


class InvalidPlugin(ValueError):
    pass

class PluginNotFound(ValueError):
    pass

def load_plugin(path_to_zip_file):
    '''
    Load plugin from zip file or raise InvalidPlugin error
    
    :return: A :class:`Plugin` instance.
    '''
    print 'Loading plugin from', path_to_zip_file
    if not os.access(path_to_zip_file, os.R_OK):
        raise PluginNotFound
    zf = ZipFile(path_to_zip_file)
    for name in zf.namelist():
        if name.lower().endswith('plugin.py'):
            locals = {}
            exec zf.read(name) in locals
            for x in locals.values():
                if isinstance(x, type) and issubclass(x, Plugin):
                    if x.minimum_calibre_version > version or \
                        platform not in x.supported_platforms:
                        continue
                    
                    return x
            
    raise InvalidPlugin(_('No valid plugin found in ')+path_to_zip_file)

_initialized_plugins = []
_on_import           = {}
_on_preprocess       = {}
_on_postprocess      = {}



def reread_filetype_plugins():
    global _on_import
    global _on_preprocess
    global _on_postprocess
    _on_import           = {}
    _on_preprocess       = {}
    _on_postprocess      = {}

    for plugin in _initialized_plugins:
        if isinstance(plugin, FileTypePlugin):
            for ft in plugin.file_types:
                if plugin.on_import:
                    if not _on_import.has_key(ft):
                        _on_import[ft] = []
                    _on_import[ft].append(plugin)
                if plugin.on_preprocess:
                    if not _on_preprocess.has_key(ft):
                        _on_preprocess[ft] = []
                    _on_preprocess[ft].append(plugin)
                if plugin.on_postprocess:
                    if not _on_postprocess.has_key(ft):
                        _on_postprocess[ft] = []
                    _on_postprocess[ft].append(plugin)

_metadata_readers = {}
_metadata_writers = {}
def reread_metadata_plugins():
    global _metadata_readers
    global _metadata_writers
    _metadata_readers = {}
    for plugin in _initialized_plugins:
        if isinstance(plugin, MetadataReaderPlugin):
            for ft in plugin.file_types:
                if not _metadata_readers.has_key(ft):
                    _metadata_readers[ft] = []
                _metadata_readers[ft].append(plugin)
        elif isinstance(plugin, MetadataWriterPlugin):
            for ft in plugin.file_types:
                if not _metadata_writers.has_key(ft):
                    _metadata_writers[ft] = []
                _metadata_writers[ft].append(plugin) 
                
def metadata_readers():
    ans = set([])
    for plugins in _metadata_readers.values():
        for plugin in plugins:
            ans.add(plugin)
    return ans

def metadata_writers():
    ans = set([])
    for plugins in _metadata_writers.values():
        for plugin in plugins:
            ans.add(plugin)
    return ans    
                
def get_file_type_metadata(stream, ftype):
    mi = MetaInformation(None, None)
    ftype = ftype.lower().strip()
    if _metadata_readers.has_key(ftype):
        for plugin in _metadata_readers[ftype]:
            if not is_disabled(plugin):
                with plugin:
                    try:
                        mi = plugin.get_metadata(stream, ftype.lower().strip())
                        break
                    except:
                        traceback.print_exc()
                        continue
    return mi

def set_file_type_metadata(stream, mi, ftype):
    ftype = ftype.lower().strip()
    if _metadata_writers.has_key(ftype):
        for plugin in _metadata_writers[ftype]:
            if not is_disabled(plugin):
                with plugin:
                    try:
                        plugin.set_metadata(stream, mi, ftype.lower().strip())
                        break
                    except:
                        traceback.print_exc()
    
                
def _run_filetype_plugins(path_to_file, ft=None, occasion='preprocess'):
    occasion = {'import':_on_import, 'preprocess':_on_preprocess, 
                'postprocess':_on_postprocess}[occasion]
    customization = config['plugin_customization']
    if ft is None:
        ft = os.path.splitext(path_to_file)[-1].lower().replace('.', '')        
    nfp = path_to_file
    for plugin in occasion.get(ft, []):
        if is_disabled(plugin):
            continue
        plugin.site_customization = customization.get(plugin.name, '') 
        with plugin:
            try:
                nfp = plugin.run(path_to_file)
            except:
                print 'Running file type plugin %s failed with traceback:'%plugin.name
                traceback.print_exc()
    x = lambda j : os.path.normpath(os.path.normcase(j))
    if occasion == 'postprocess' and x(nfp) != x(path_to_file):
        shutil.copyfile(nfp, path_to_file)
        nfp = path_to_file
    return nfp

run_plugins_on_import      = functools.partial(_run_filetype_plugins, 
                                               occasion='import')
run_plugins_on_preprocess  = functools.partial(_run_filetype_plugins, 
                                               occasion='preprocess')
run_plugins_on_postprocess = functools.partial(_run_filetype_plugins, 
                                               occasion='postprocess')
                

def initialize_plugin(plugin, path_to_zip_file):
    try:
        return plugin(path_to_zip_file)
    except Exception:
        print 'Failed to initialize plugin:', plugin.name, plugin.version
        tb = traceback.format_exc()
        raise InvalidPlugin((_('Initialization of plugin %s failed with traceback:')
                            %tb) + '\n'+tb)
    

def add_plugin(path_to_zip_file):
    make_config_dir()
    plugin = load_plugin(path_to_zip_file)
    plugin = initialize_plugin(plugin, path_to_zip_file)
    plugins = config['plugins']
    zfp = os.path.join(plugin_dir, plugin.name+'.zip')
    if os.path.exists(zfp):
        os.remove(zfp)
    shutil.copyfile(path_to_zip_file, zfp)
    plugins[plugin.name] = zfp
    config['plugins'] = plugins
    initialize_plugins()
    return plugin

def remove_plugin(plugin_or_name):
    name = getattr(plugin_or_name, 'name', plugin_or_name)
    plugins = config['plugins']
    removed = False
    if name in plugins.keys():
        removed = True
        zfp = plugins[name]
        if os.path.exists(zfp):
            os.remove(zfp)
        plugins.pop(name)
    config['plugins'] = plugins
    initialize_plugins()
    return removed

def is_disabled(plugin):
    return plugin.name in config['disabled_plugins']

def find_plugin(name):
    for plugin in _initialized_plugins:
        if plugin.name == name:
            return plugin

def disable_plugin(plugin_or_name):
    x = getattr(plugin_or_name, 'name', plugin_or_name)
    plugin = find_plugin(x)
    if not plugin.can_be_disabled:
        raise ValueError('Plugin %s cannot be disabled'%x)
    dp = config['disabled_plugins']
    dp.add(x)
    config['disabled_plugins'] = dp

def enable_plugin(plugin_or_name):
    x = getattr(plugin_or_name, 'name', plugin_or_name)
    dp = config['disabled_plugins']
    if x in dp:
        dp.remove(x)
    config['disabled_plugins'] = dp

def initialize_plugins():
    global _initialized_plugins
    _initialized_plugins = []
    for zfp in list(config['plugins'].values()) + builtin_plugins:
        try:
            try:
                plugin = load_plugin(zfp) if not isinstance(zfp, type) else zfp
            except PluginNotFound:
                continue
            plugin = initialize_plugin(plugin, zfp if not isinstance(zfp, type) else zfp)
            _initialized_plugins.append(plugin)
        except:
            print 'Failed to initialize plugin...'
            traceback.print_exc()
    _initialized_plugins.sort(cmp=lambda x,y:cmp(x.priority, y.priority), reverse=True)    
    reread_filetype_plugins()
    reread_metadata_plugins()
    
initialize_plugins()

def option_parser():
    parser = OptionParser(usage=_('''\
    %prog options
    
    Customize calibre by loading external plugins.
    '''))
    parser.add_option('-a', '--add-plugin', default=None, 
                      help=_('Add a plugin by specifying the path to the zip file containing it.'))
    parser.add_option('-r', '--remove-plugin', default=None, 
                      help=_('Remove a custom plugin by name. Has no effect on builtin plugins'))
    parser.add_option('--customize-plugin', default=None,
                      help=_('Customize plugin. Specify name of plugin and customization string separated by a comma.'))
    parser.add_option('-l', '--list-plugins', default=False, action='store_true',
                      help=_('List all installed plugins'))
    parser.add_option('--enable-plugin', default=None,
                      help=_('Enable the named plugin'))
    parser.add_option('--disable-plugin', default=None,
                      help=_('Disable the named plugin'))
    return parser

def initialized_plugins():
    return _initialized_plugins

def customize_plugin(plugin, custom):
    d = config['plugin_customization']
    d[plugin.name] = custom.strip()
    config['plugin_customization'] = d

def plugin_customization(plugin):
    return config['plugin_customization'].get(plugin.name, '')

def main(args=sys.argv):
    parser = option_parser()
    if len(args) < 2:
        parser.print_help()
        return 1
    opts, args = parser.parse_args(args)
    if opts.add_plugin is not None:
        plugin = add_plugin(opts.add_plugin)
        print 'Plugin added:', plugin.name, plugin.version
    if opts.remove_plugin is not None:
        if remove_plugin(opts.remove_plugin):
            print 'Plugin removed'
        else:
            print 'No custom pluginnamed', opts.remove_plugin
    if opts.customize_plugin is not None:
        name, custom = opts.customize_plugin.split(',')
        plugin = find_plugin(name.strip())
        if plugin is None:
            print 'No plugin with the name %s exists'%name
            return 1
        customize_plugin(plugin, custom)
    if opts.enable_plugin is not None:
        enable_plugin(opts.enable_plugin.strip())
    if opts.disable_plugin is not None:
        disable_plugin(opts.disable_plugin.strip())
    if opts.list_plugins:
        fmt = '%-15s%-20s%-15s%-15s%s'
        print fmt%tuple(('Type|Name|Version|Disabled|Site Customization'.split('|')))
        print
        for plugin in initialized_plugins():
            print fmt%(
                                plugin.type, plugin.name, 
                                plugin.version, is_disabled(plugin), 
                                plugin_customization(plugin)
                                )
            print '\t', plugin.description
            if plugin.is_customizable():
                print '\t', plugin.customization_help()
            print
        
    return 0
    
if __name__ == '__main__':
    sys.exit(main())
