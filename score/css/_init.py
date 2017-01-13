# Copyright © 2015,2016 STRG.AT GmbH, Vienna, Austria
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
import textwrap
import urllib
import warnings


defaults = {
    'rootdir': None,
    'cachedir': None,
    'minify': False,
    'combine': False,
}


def init(confdict, webassets, tpl, http):
    """
    Initializes this module acoording to :ref:`our module initialization
    guidelines <module_initialization>` with the following configuration keys:

    :confkey:`rootdir` :confdefault:`None`
        Denotes the root folder containing all css files. Will fall
        back to a sub-folder of the folder in :mod:`score.tpl`'s
        configuration, as described in :func:`score.tpl.init`.

    :confkey:`cachedir` :confdefault:`None`
        A dedicated cache folder for this module. It is generally sufficient
        to provide a ``cachedir`` for :mod:`score.tpl`, as this module will
        use a sub-folder of that by default.

    :confkey:`combine` :confdefault:`False`
        Whether css files should be delivered as a single file. If this
        value is `true` (as defined by :func:`score.init.parse_bool`), the
        default url will point to the combined css file.

    :confkey:`minify` :confdefault:`False`
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
        conf['rootdir'] = os.path.join(tpl.rootdir, 'css')
    conf['minify'] = parse_bool(conf['minify'])
    conf['combine'] = parse_bool(conf['combine'])
    if not conf['cachedir'] and tpl.cachedir:
        conf['cachedir'] = os.path.join(tpl.cachedir, 'css')
    if conf['cachedir']:
        init_cache_folder(conf, 'cachedir', autopurge=True)
    else:
        warnings.warn('No cachedir configured, SCSS rendering will not work.')
    cssconf = ConfiguredCssModule(
        webassets, tpl, http, conf['rootdir'], conf['cachedir'],
        conf['combine'], conf['minify'])
    for name, pathlist in extract_conf(conf, 'group.').items():
        paths = parse_list(pathlist)
        _create_group(cssconf, webassets, name + '.css', paths)
    return cssconf


def _create_group(conf, webassets, name, paths):
    """
    Helper function for :func:`score.css.init`. Will register an :term:`asset
    group` with given *name* for the list of provided *paths*.
    """
    files = list(map(lambda path: os.path.join(conf.rootdir, path), paths))
    file_hasher = webassets.versionmanager.create_file_hasher(files)

    def hasher(ctx):
        return file_hasher()

    @conf.virtcss(name, hasher)
    def group(ctx):
        return conf.render_multiple(ctx, paths)


class CssConverter(TemplateConverter):
    """
    The :class:`score.tpl.TemplateConverter` that will optionally minify css
    files.
    """

    def __init__(self, conf):
        self.conf = conf

    def convert_string(self, ctx, css, path=None):
        if self.conf.minify:
            import csscompressor
            css = csscompressor.compress(css)
        return css

    def convert_file(self, ctx, path):
        if path in self.conf.virtfiles.paths():
            return self.convert_string(
                ctx, self.conf.virtfiles.render(ctx, path))
        file = os.path.join(self.conf.rootdir, path)
        return self.convert_string(
            ctx, open(file, 'r', encoding='utf-8-sig').read(), path=path)


class ScssConverter(TemplateConverter):
    """
    :class:`score.tpl.TemplateConverter` for scss files.
    """

    def __init__(self, conf):
        self.conf = conf

    def convert_string(self, ctx, scss, path=None):
        if path and os.path.basename(path)[0] != '_':
            self._render_includes(ctx)
        output_style = 'expanded'
        source_comments = 'line_numbers'
        if self.conf.minify:
            output_style = 'compressed'
            source_comments = 'none'
        result = sass.compile(string=scss,
                              include_paths=[self.conf.rootdir],
                              output_style=output_style,
                              source_comments=source_comments)
        # Remove BOM from output:
        # https://github.com/dahlia/libsass-python/pull/52
        if result.startswith('\ufeff'):
            result = result[1:]
        return result

    def convert_file(self, ctx, path):
        if os.path.basename(path)[0] != '_':
            self._render_includes(ctx)
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
        result = sass.compile(filename=copy,
                              include_paths=[self.conf.rootdir],
                              output_style=output_style,
                              source_comments=source_comments)
        # Remove BOM from output:
        # https://github.com/dahlia/libsass-python/pull/52
        if result.startswith('\ufeff'):
            result = result[1:]
        return result

    def _render_includes(self, ctx):
        cachedir = os.path.join(self.conf.cachedir, 'scss')
        for original in self.conf.paths(includehidden=True):
            if os.path.basename(original)[0] != '_':
                continue
            if original.endswith('.css') or '.scss' not in original:
                continue
            file = os.path.join(self.conf.rootdir, original)
            copy = os.path.join(cachedir, original)
            try:
                timestamp = os.path.getmtime(file)
                newer_than_newest = (
                    hasattr(self, '_newest_include_file_timestamp') and
                    self._newest_include_file_timestamp < timestamp)
                if newer_than_newest:
                    self._newest_include_file = file
                if timestamp < os.path.getmtime(copy):
                    continue
            except FileNotFoundError:
                pass
            if original in self.conf.virtfiles.paths():
                css = self.conf.virtfiles.render(ctx, original)
            else:
                css = self.conf.tpl.renderer.render_file(
                    ctx, original, {'ctx': self.conf.http.ctx.Context()})
            if not original.endswith('.scss'):
                copy = os.path.join(cachedir, original)
                while not copy.endswith('.scss'):
                    copy = copy[:copy.rindex('.')]
            os.makedirs(os.path.dirname(copy), exist_ok=True)
            open(copy, 'w').write(css)

    def _get_newest_include_file(self, ctx):
        if not hasattr(self, '_newest_include_file'):
            self._newest_include_file = None
            self._newest_include_file_timestamp = 0
            for original in self.conf.paths(includehidden=True):
                if os.path.basename(original)[0] != '_':
                    continue
                if original.endswith('.css') or '.scss' not in original:
                    continue
                if original in self.conf.virtfiles.paths():
                    continue
                file = os.path.join(self.conf.rootdir, original)
                timestamp = os.path.getmtime(file)
                if timestamp > self._newest_include_file_timestamp:
                    self._newest_include_file_timestamp = timestamp
                    self._newest_include_file = file
        return self._newest_include_file


class ConfiguredCssModule(ConfiguredModule):
    """
    This module's :class:`configuration object
    <score.init.ConfiguredModule>`.
    """

    def __init__(self, webassets, tpl, http, rootdir,
                 cachedir, combine, minify):
        super().__init__(__package__)
        self.webassets = webassets
        self.tpl = tpl
        self.http = http
        self.rootdir = rootdir
        self.cachedir = cachedir
        self.combine = combine
        self.minify = minify
        self.css_converter = CssConverter(self)
        self.scss_converter = ScssConverter(self)
        tpl.renderer.register_format('css', rootdir, cachedir,
                                     self.css_converter)
        tpl.renderer.register_format('scss', rootdir, cachedir,
                                     self.scss_converter)
        self.virtfiles = VirtualAssets()
        self.virtcss = self.virtfiles.decorator('css')
        self._add_single_route()
        self._add_combined_route()

    def paths(self, includehidden=False):
        """
        Provides a list of all css files found in the css root folder as
        :term:`paths <asset path>`, as well as the paths of all :term:`virtual
        css files <virtual asset>`.
        """
        return (
            self.tpl.renderer.paths('css', self.virtfiles, includehidden) +
            self.tpl.renderer.paths('scss', None, includehidden))

    def render_multiple(self, ctx, paths):
        """
        Renders multiple *paths* at once, prefixing the contents of each file
        with a css comment (only if minification is disabled).
        """
        parts = []
        for path in paths:
            if not self.minify:
                s = '/*{0}*/\n/*{1:^76}*/\n/*{0}*/'.format('*' * 76, path)
                parts.append(s)
            parts.append(self.tpl.renderer.render_file(ctx, path))
        return '\n\n'.join(parts)

    def render_combined(self, ctx):
        """
        Renders the combined css file.
        """
        return self.render_multiple(ctx, self.paths())

    def _add_single_route(self):

        @self.http.newroute('score.css:single', '/css/{path>.*\.css$}')
        def single(ctx, path):
            versionmanager = self.webassets.versionmanager
            if versionmanager.handle_request(ctx, 'css', path):
                return self._response(ctx)
            path = self._urlpath2path(path)
            if path in self.virtfiles.paths():
                css = self.virtfiles.render(ctx, path)
            else:
                css = self.tpl.renderer.render_file(ctx, path)
            return self._response(ctx, css)

        @single.vars2url
        def url_single(ctx, path):
            """
            Generates the url to a single css *path*.
            """
            urlpath = self._path2urlpath(path)
            url = '/css/' + urllib.parse.quote(urlpath)
            versionmanager = self.webassets.versionmanager
            if path in self.virtfiles.paths():
                def hasher():
                    return self.virtfiles.hash(ctx, path)

                def renderer():
                    return self.virtfiles.render(ctx, path).encode('UTF-8')
            else:
                files = [os.path.join(self.rootdir, path)]
                if '.scss' in path:
                    newest_include_file = self.scss_converter.\
                                          _get_newest_include_file(ctx)
                    if newest_include_file:
                        files.append(newest_include_file)
                hasher = versionmanager.create_file_hasher(files)

                def renderer():
                    content = self.tpl.renderer.render_file(ctx, path)
                    return content.encode('UTF-8')
            hash_ = versionmanager.store('css', urlpath, hasher, renderer)
            if hash_:
                url += '?_v=' + hash_
            return url

    def _add_combined_route(self):

        @self.http.newroute('score.css:combined', '/combined.css')
        def combined(ctx):
            versionmanager = self.webassets.versionmanager
            if versionmanager.handle_request(ctx, 'css', '__combined__'):
                return self._response(ctx)
            return self._response(ctx, self.render_multiple(ctx, self.paths()))

        @combined.vars2url
        def url_combined(ctx):
            """
            Generates the url to the combined css file.
            """
            url = '/combined.css'
            files = []
            vfiles = []
            for path in self.paths():
                if path in self.virtfiles.paths():
                    vfiles.append(path)
                else:
                    files.append(os.path.join(self.rootdir, path))
            versionmanager = self.webassets.versionmanager
            hashers = [versionmanager.create_file_hasher(files)]
            for path in vfiles:
                hashers.append(lambda: self.virtfiles.hash(ctx, path))
            hash_ = versionmanager.store(
                'css', '__combined__', hashers,
                lambda: self.render_combined(ctx).encode('UTF-8'))
            if hash_:
                url += '?_v=' + hash_
            return url

    def _path2urlpath(self, path):
        """
        Converts a :term:`path <asset path>` to the corresponding path to use
        in URLs.
        """
        urlpath = path
        if not (urlpath.endswith('.css') or urlpath.endswith('.scss')):
            urlpath = urlpath[:urlpath.rindex('.')]
        if urlpath.endswith('.scss'):
            urlpath = urlpath[:-4] + 'css'
        assert urlpath.endswith('.css')
        return urlpath

    def _urlpath2path(self, urlpath):
        """
        Converts a *urlpath*, as passed in via the URL, into the actual
        :term:`asset path`.
        """
        assert urlpath.endswith('.css')
        csspath = urlpath
        scsspath = urlpath[:-3] + 'scss'
        if csspath in self.virtfiles.paths():
            return csspath
        if scsspath in self.virtfiles.paths():
            return scsspath
        if os.path.isfile(os.path.join(self.rootdir, csspath)):
            return csspath
        if os.path.isfile(os.path.join(self.rootdir, scsspath)):
            return scsspath
        for ext in self.tpl.renderer.engines:
            file = os.path.join(self.rootdir, csspath + '.' + ext)
            if os.path.isfile(file):
                return csspath + '.' + ext
            file = os.path.join(self.rootdir, scsspath + '.' + ext)
            if os.path.isfile(file):
                return scsspath + '.' + ext
        raise ValueError('Could not determine path for url "%s"' % urlpath)

    def _finalize(self, tpl):
        if 'html' in tpl.renderer.formats:
            tpl.renderer.add_function(
                'html', 'css', self._htmlfunc, escape_output=False)

    def _response(self, ctx, css=None):
        """
        Sets appropriate headers on the http response.
        Will optionally set the response body to the given *css* string.
        """
        ctx.http.response.content_type = 'text/css; charset=UTF-8'
        if css:
            ctx.http.response.text = css
        return ctx.http.response

    def _tags(self, ctx, *paths):
        """
        Generates all ``link`` tags necessary to include all css files.
        It is possible to generate the tags to specific css *paths* only.
        """
        tag = '<link rel="stylesheet" href="%s" type="text/css">'
        if paths:
            links = [tag % self.http.url(ctx, 'score.css:single', path)
                     for path in paths]
            return '\n'.join(links)
        if self.combine:
            return tag % self.http.url(ctx, 'score.css:combined')
        paths = self.paths()
        if not paths:
            return ''
        return self._tags(ctx, *paths)

    def _htmlfunc(self, ctx, *paths, inline=False):
        if not inline:
            return self._tags(ctx, *paths)
        if not paths:
            paths = self.paths()
        return '<style type="text/css">\n' + \
            textwrap.indent(self.render_multiple(ctx, paths), ' ' * 4) + \
            '\n</style>'
