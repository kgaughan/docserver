docserver - a documentation server in the vein of PyPI
======================================================

:Author: Keith Gaughan

**docserver** is a lightweight, user-friendly documentation server.

.. contents::


Installation
------------

To install from PyPI::

    $ pip install docserver

You can use docserver straight out of the box by running the module::

    $ python -m docserver

And to show the help::

    $ python -m docserver --help

The WSGI app itself is exposed as `docserver.DocServer`. If you want to use a
bundle store path or frontpage template other than the default, you can set
the environment variables ``DOCSERVER_STORE`` and ``DOCSERVER_TEMPLATE``
respectively.


Reskinning
----------

If you want to use a skin other than the default skin, you can use he default
skin as the basis for a new one. To print out the default skin::

    python -m docserver --print-template

The template engine used is pystache_.


Testing
-------

Use the following to run the test suite::

    $ python setup.py test

If you're considering contributing back, make sure you run the testsuite
against all the supported versions of Python. You can use tox_ to do this::

    $ tox

Or with detox_::

    $ detox

To install additional versions of Python for testing, I recommend pyenv_.

.. _pystache: https://pypi.python.org/pypi/pystache
.. _tox: http://testrun.org/
.. _detox: https://pypi.python.org/pypi/detox
.. _pyenv: https://github.com/yyuu/pyenv/

.. vim:set ft=rst:
