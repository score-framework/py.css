.. module:: score.css
.. role:: confkey
.. role:: confdefault

*********
score.css
*********

This module manages two :term:`template formats <template format>` for the
:mod:`score.tpl` module: ``css`` and ``scss``.


Quickstart
==========

The module will :meth:`register a template function
<score.tpl.Renderer.add_function>` called ``css`` for html assets with the
following signature:

.. code-block:: python

    css(*paths, inline=False)

Calling this function without arguments will insert a ``link`` tag for *each*
css asset found in the project (as defined by
:meth:`score.css.ConfiguredCssModule.paths`). It is possible to link to specific
assets only:

.. code-block:: python

    css('reset.css', 'blog.scss')

The above might generate the following HTML (depending on the url
configuration):

.. code-block:: html

    <link rel="stylesheet" href="/css/reset.css" type="text/css">
    <link rel="stylesheet" href="/css/blog.scss" type="text/css">

It is also possible to insert the styles in-place, instead of linking to
individual files:

.. code-block:: python

    css('reset.css', 'blog.scss', inline=True)

The above might render the following:

.. code-block:: html

    <style type="text/css">
        /**************************************/
        /*             reset.css              */
        /**************************************/

        body {
            color: blue;
        }

        /**************************************/
        /*             blog.scss              */
        /**************************************/

        .blog-heading {
            font-size: 150%;
        }
    </style>

The comments will be omitted if :attr:`minification
<score.css.ConfiguredCssModule.minify>` is enabled.

API
===

.. autofunction:: score.css.init

.. autoclass:: score.css.ConfiguredCssModule()

    .. attribute:: rootdir

        The *root* folder of css and scss files. Guaranteed to point to an
        existing folder on the file system.

    .. attribute:: cachedir

        Cache folder for css values. This value is either `None` or it
        points to an existing and writable folder on the file system.

    .. attribute:: minify

        Whether css assets should be minified.

    .. attribute:: virtfiles

        :class:`VirtualAssets <score.webassets.VirtualAssets>` object for
        :term:`virtual css assets <virtual asset>`.

    .. attribute:: virtcss

        :meth:`Decorator <score.webassets.VirtualAssets.decorator>` of ``virtfiles``.

    .. automethod:: paths
