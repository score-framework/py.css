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

"""
This package :ref:`integrates <framework_integration>` the module with
pyramid.
"""


import os
from pyramid.request import Request
from score.css import ConfiguredCssModule
from score.init import parse_bool
import textwrap


def init(confdict, configurator, webassets_conf, tpl_conf, html_conf=None):
    """
    Apart from calling the :func:`basic initializer <score.css.init>`, this
    function interprets the following *confdict* keys:

    :confkey:`combine` :faint:`[default=False]`
        Whether css files should be delivered as a single file. If this
        value is `true` (as defined by :func:`score.init.parse_bool`), the
        default url will point to the combined css file.

    :confkey:`dummy_request` :faint:`[default=None]`
        An optional request object to use for creating urls. Will fall back to
        the request object of the :func:`webassets configuration
        <score.webassets.pyramid.init>`.
    """
    import score.css
    cssconf = score.css.init(confdict, webassets_conf, tpl_conf)
    try:
        combine = parse_bool(confdict['combine'])
    except KeyError:
        combine = False
    try:
        assert isinstance(confdict['dummy_request'], Request)
        dummy_request = confdict['dummy_request']
        webassets_conf.dummy_request.registry = configurator.registry
    except KeyError:
        dummy_request = webassets_conf.dummy_request
    return ConfiguredCssPyramidModule(configurator, webassets_conf, tpl_conf,
                                      cssconf, combine, dummy_request)


class ConfiguredCssPyramidModule(ConfiguredCssModule):
    """
    Pyramid-specific configuration of this module.
    """

    def __init__(self, configurator, webconf, tplconf,
                 cssconf, combine, dummy_request):
        self.webconf = webconf
        self.tplconf = tplconf
        self.cssconf = cssconf
        self.combine = combine
        self.dummy_request = dummy_request
        if 'html' in tplconf.renderer.formats:
            tplconf.renderer.add_function('html', 'css',
                                          self._htmlfunc, escape_output=False)
        configurator.add_route('score.css:single', '/css/{path:.*\.css$}')
        configurator.add_route('score.css:combined', '/combined.css')
        configurator.add_view(self.css_single, route_name='score.css:single')
        configurator.add_view(self.css_combined, route_name='score.css:combined')

    def __getattr__(self, attr):
        return getattr(self.cssconf, attr)

    def response(self, request, css=None):
        """
        Returns a pyramid response object with the optional *css* string as its
        body. Will only set the headers, if *css* is `None`.
        """
        request.response.content_type = 'text/css; charset=UTF-8'
        if css:
            request.response.text = css
        return request.response

    def path2urlpath(self, path):
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

    def urlpath2path(self, urlpath):
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
        for ext in self.tplconf.renderer.engines:
            file = os.path.join(self.rootdir, csspath + '.' + ext)
            if os.path.isfile(file):
                return csspath + '.' + ext
            file = os.path.join(self.rootdir, scsspath + '.' + ext)
            if os.path.isfile(file):
                return scsspath + '.' + ext
        raise ValueError('Could not determine path for url "%s"' % urlpath)

    def css_single(self, request):
        """
        Pyramid :term:`route <pyramid:route configuration>` that generates the
        response for a single css asset.
        """
        urlpath = request.matchdict['path']
        versionmanager = self.webconf.versionmanager
        if versionmanager.handle_pyramid_request('css', urlpath, request):
            return self.response(request)
        path = self.urlpath2path(urlpath)
        if path in self.virtfiles.paths():
            css = self.virtfiles.render(path)
        else:
            css = self.tplconf.renderer.render_file(path)
        return self.response(request, css)

    def css_combined(self, request):
        """
        Pyramid :term:`route <pyramid:route configuration>` that generets the
        response for the combined css file.
        """
        versionmanager = self.webconf.versionmanager
        if versionmanager.handle_pyramid_request('css', '__combined__', request):
            return self.response(request)
        return self.response(request, self.render_combined())

    def render_combined(self):
        """
        Renders the combined css file.
        """
        return self.render_multiple(self.paths())

    def url_single(self, path):
        """
        Generates the url to a single css *path*.
        """
        urlpath = self.path2urlpath(path)
        versionmanager = self.webconf.versionmanager
        if path in self.virtfiles.paths():
            hasher = lambda: self.virtfiles.hash(path)
            renderer = lambda: self.virtfiles.render(path).encode('UTF-8')
        else:
            file = os.path.join(self.rootdir, path)
            hasher = versionmanager.create_file_hasher(file)
            renderer = lambda: self.tplconf.renderer.render_file(path).encode('UTF-8')
        hash_ = versionmanager.store('css', urlpath, hasher, renderer)
        _query = {'_v': hash_} if hash_ else None
        genurl = self.dummy_request.route_url
        return genurl('score.css:single', path=urlpath, _query=_query)

    def url_combined(self):
        """
        Generates the url to the combined css file.
        """
        files = []
        vfiles = []
        for path in self.paths():
            if path in self.virtfiles.paths():
                vfiles.append(path)
            else:
                files.append(os.path.join(self.rootdir, path))
        versionmanager = self.webconf.versionmanager
        hashers = [versionmanager.create_file_hasher(files)]
        def add_hasher(path):
            hashers.append(lambda: self.virtfiles.hash(path))
        list(map(add_hasher, vfiles))
        hash_ = versionmanager.store(
            'css', '__combined__', hashers,
            lambda: self.render_combined().encode('UTF-8'))
        _query = {'_v': hash_} if hash_ else None
        genurl = self.dummy_request.route_url
        return genurl('score.css:combined', _query=_query)

    def tags(self, *paths):
        """
        Generates all ``link`` tags necessary to include all css files.
        It is possible to generate the tags to specific css *paths* only.
        """
        tag = '<link rel="stylesheet" href="%s" type="text/css">'
        if len(paths):
            links = [tag % self.url_single(path) for path in paths]
            return '\n'.join(links)
        if self.combine:
            return tag % self.url_combined()
        return self.tags(*self.paths())

    def _htmlfunc(self, *paths, inline=False):
        if not inline:
            return self.tags(*paths)
        if not paths:
            paths = self.paths()
        return '<style type="text/css">\n' + \
            textwrap.indent(self.render_multiple(paths), ' ' * 4) + \
            '\n</style>'
