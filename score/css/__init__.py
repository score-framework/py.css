# Copyright © 2015 STRG.AT GmbH, Vienna, Austria
#
# This file is part of the The SCORE Framework.
#
# The SCORE Framework and all its parts are free software: you can redistribute
# them and/or modify them under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation which is in the
# file named COPYING.LESSER.txt.
#
# The SCORE Framework and all its parts are distributed without any WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. For more details see the GNU Lesser General Public
# License.
#
# If you have not received a copy of the GNU Lesser General Public License see
# http://www.gnu.org/licenses/.
#
# The License-Agreement realised between you as Licensee and STRG.AT GmbH as
# Licenser including the issue of its valid conclusion and its pre- and
# post-contractual effects is governed by the laws of Austria. Any disputes
# concerning this License-Agreement including the issue of its valid conclusion
# and its pre- and post-contractual effects are exclusively decided by the
# competent court, in whose district STRG.AT GmbH has its registered seat, at
# the discretion of STRG.AT GmbH also the competent court, in whose district the
# Licensee has his registered seat, an establishment or assets.

import os
import sass
import shutil
from score.init import (
    parse_bool, parse_list, extract_conf, init_cache_folder, ConfiguredModule)
from score.tpl import TemplateConverter
from score.webassets import VirtualAssets

import logging
log = logging.getLogger(__name__)


defaults = {
    'rootdir': None,
    'cachedir': None,
    'minify': False,
    'combine': False,
}


def init(confdict, webassets_conf, tpl_conf):
    """
    Initializes this module acoording to :ref:`our module initialization
    guidelines <module_initialization>` with the following configuration keys:

    :confkey:`rootdir` :faint:`[default=None]`
        Denotes the root folder containing all css files. Will fall
        back to a sub-folder of the folder in :mod:`score.tpl`'s
        configuration, as described in :func:`score.tpl.init`.

    :confkey:`cachedir` :faint:`[default=None]`
        A dedicated cache folder for this module. It is generally sufficient
        to provide a ``cachedir`` for :mod:`score.tpl`, as this module will
        use a sub-folder of that by default.

    :confkey:`minify` :faint:`[default=False]`
        Whether css assets should be minified.

    :confkey:`group.*`
        Keys starting with ``group.*`` will register :term:`asset groups
        <asset group>`. The following configuration will create a
        :term:`virtual asset` called ``meal`` which has the combined content
        of the assets 'bacon.css' and 'spam.css'::

            group.meal =
                bacon.css
                spam.css

        Note that groups defined this way *must* reference real assets, i.e.
        at the point this value is interpreted, there are no virtual assets
        yet! If you need to add virtual assets to a group, you will need to
        create the asset group after all required virtual assets have been
        registered.

    """
    conf = dict(defaults.items())
    conf.update(confdict)
    if not conf['rootdir']:
        conf['rootdir'] = os.path.join(tpl_conf.rootdir, 'css')
    conf['minify'] = parse_bool(conf['minify'])
    conf['combine'] = parse_bool(conf['combine'])
    if not conf['cachedir'] and tpl_conf.cachedir:
        conf['cachedir'] = os.path.join(tpl_conf.cachedir, 'css')
    if conf['cachedir']:
        init_cache_folder(conf, 'cachedir', autopurge=True)
    else:
        log.warn('No cachedir configured, scss rendering might break.')
    cssconf = ConfiguredCssModule(tpl_conf, conf['rootdir'],
                                  conf['cachedir'], conf['minify'])
    for name, pathlist in extract_conf(conf, 'group.').items():
        paths = parse_list(pathlist)
        _create_group(cssconf, webassets_conf, name + '.css', paths)
    return cssconf


def _create_group(conf, webassets_conf, name, paths):
    """
    Helper function for :func:`score.css.init`. Will register an :term:`asset
    group` with given *name* for the list of provided *paths*.
    """
    files = list(map(lambda path: os.path.join(conf.rootdir, path), paths))
    hasher = webassets_conf.versionmanager.create_file_hasher(files)
    @conf.virtcss(name, hasher)
    def group():
        return conf.render_multiple(paths)


class CssConverter(TemplateConverter):
    """
    The :class:`score.tpl.TemplateConverter` that will optionally minify css
    files.
    """

    def __init__(self, css_conf):
        self.conf = css_conf

    def convert_string(self, css, path=None):
        if self.conf.minify:
            import csscompressor
            css = csscompressor.compress(css)
        return css

    def convert_file(self, path):
        if path in self.conf.virtfiles.paths():
            return self.convert_string(self.conf.virtfiles.render(path))
        file = os.path.join(self.conf.rootdir, path)
        return self.convert_string(open(file, 'r').read(), path=path)


class ScssConverter(TemplateConverter):
    """
    :class:`score.tpl.TemplateConverter` for scss files.
    """

    def __init__(self, css_conf):
        self.conf = css_conf

    def convert_string(self, scss, path=None):
        output_style = 'expanded'
        source_comments = 'line_numbers'
        if self.conf.minify:
            output_style = 'compressed'
            source_comments = 'none'
        return sass.compile(string=scss,
                            include_paths=[self.conf.rootdir],
                            output_style=output_style,
                            source_comments=source_comments)

    def convert_file(self, path):
        if os.path.basename(path)[0] != '_':
            self._render_includes()
        original = os.path.join(self.conf.rootdir, path)
        copy = os.path.join(self.conf.cachedir, 'scss', path)
        if not os.path.isfile(copy) or \
                os.path.getmtime(copy) <= os.path.getmtime(original):
            os.makedirs(os.path.dirname(copy), exist_ok=True)
            shutil.copyfile(original, copy)
        output_style = 'expanded'
        source_comments = 'line_numbers'
        if self.conf.minify:
            output_style = 'compressed'
            source_comments = 'none'
        return sass.compile(filename=copy,
                            include_paths=[self.conf.rootdir],
                            output_style=output_style,
                            source_comments=source_comments)

    def _render_includes(self):
        cachedir = os.path.join(self.conf.cachedir, 'scss')
        for original in self.conf.paths(includehidden=True):
            if os.path.basename(original)[0] != '_':
                continue
            if original.endswith('.css') or '.scss' not in original:
                continue
            if original in self.conf.virtfiles.paths():
                css = self.conf.virtfiles.render(original)
            else:
                css = self.conf.tpl_conf.renderer.render_file(original)
            if not original.endswith('.scss'):
                copy = os.path.join(cachedir, original)
                while not copy.endswith('.scss'):
                    copy = copy[:copy.rindex('.')]
                open(copy, 'w').write(css)


class ConfiguredCssModule(ConfiguredModule):
    """
    This module's :class:`configuration object
    <score.init.ConfiguredModule>`.
    """

    def __init__(self, tpl_conf, rootdir, cachedir, minify):
        super().__init__(__package__)
        self.tpl_conf = tpl_conf
        self.rootdir = rootdir
        self.cachedir = cachedir
        self.minify = minify
        self.css_converter = CssConverter(self)
        self.scss_converter = ScssConverter(self)
        tpl_conf.renderer.register_format('css', rootdir, cachedir,
                                          self.css_converter)
        tpl_conf.renderer.register_format('scss', rootdir, cachedir,
                                          self.scss_converter)
        self.virtfiles = VirtualAssets()
        self.virtcss = self.virtfiles.decorator('css')

    def render_multiple(self, paths):
        """
        Renders multiple *paths* at once, prefixing the contents of each file
        with a css comment (only if minification is disabled).
        """
        parts = []
        for path in paths:
            if not self.minify:
                s = '/*{0}*/\n/*{1:^76}*/\n/*{0}*/'.format('*' * 76, path)
                parts.append(s)
            parts.append(self.tpl_conf.renderer.render_file(path))
        return '\n\n'.join(parts)

    def paths(self, includehidden=False):
        """
        Provides a list of all css files found in the css root folder as
        :term:`paths <asset path>`, as well as the paths of all :term:`virtual
        css files <virtual asset>`.
        """
        return self.tpl_conf.renderer.paths('css', self.virtfiles, includehidden) +\
            self.tpl_conf.renderer.paths('scss', None, includehidden)
