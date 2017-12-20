.. module:: score.css
.. role:: confkey
.. role:: confdefault

*********
score.css
*********

This small module just defines the 'tetx/css' mime type for :mod:`score.tpl`
and configures some parameters for css template processing.


Quickstart
==========

Usually, it is sufficient to add this module to your initialization list:


.. code-block:: ini

    [score.init]
    modules =
        score.tpl
        score.css

API
===

.. autofunction:: score.css.init

.. autoclass:: score.css.ConfiguredCssModule()

    .. automethod:: score_webassets_proxy
