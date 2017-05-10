# Copyright © 2015-2017 STRG.AT GmbH, Vienna, Austria
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

from score.init import parse_bool, parse_list, ConfiguredModule


defaults = {
    'tpl.extensions': ['css'],
    'tpl.register_minifier': False,
}


def init(confdict, tpl):
    """
    Initializes this module acoording to :ref:`our module initialization
    guidelines <module_initialization>` with the following configuration keys:

    :confkey:`tpl.register_minifier` :confdefault:`False`
        Whether css assets should be minified.
    """
    conf = dict(defaults.items())
    conf.update(confdict)
    filetype = tpl.filetypes['text/css']
    if parse_bool(conf['tpl.register_minifier']):
        import csscompressor
        filetype.postprocessors.append(csscompressor.compress)
    filetype.extensions.extend(parse_list(conf['tpl.extensions']))
    return ConfiguredCssModule(tpl)


class ConfiguredCssModule(ConfiguredModule):
    """
    This module's :class:`configuration object
    <score.init.ConfiguredModule>`.
    """

    def __init__(self, tpl):
        import score.css
        super().__init__(score.css)
        self.tpl = tpl

    def score_webassets_proxy(self):
        from score.webassets import TemplateWebassetsProxy

        class CssWebassetsProxy(TemplateWebassetsProxy):

            def __init__(self, tpl):
                super().__init__(tpl, 'text/css')

            def render_url(self, url):
                tag = '<link rel="stylesheet" href="%s" type="text/css">'
                return tag % (url,)

            def create_bundle(self, paths):
                """
                Renders the combined js file.
                """
                parts = []
                for path in sorted(paths):
                    s = '/*{0}*/\n/*{1:^74}*/\n/*{0}*/'.format('*' * 74, path)
                    parts.append(s)
                    parts.append(self.tpl.render(path,
                                                 apply_postprocessors=False))
                content = '\n\n'.join(parts)
                filetype = self.tpl.filetypes['text/css']
                for postprocessor in filetype.postprocessors:
                    content = postprocessor(content)
                return content

        return CssWebassetsProxy(self.tpl)
