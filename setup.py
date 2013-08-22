#!/usr/bin/env python

from setuptools import setup


setup(
    name='docserver',
    version='0.1.0',
    description='Lightweight, user-friendly PyPI-style documentation server',
    long_description=open('README', 'r').read(),
    url='https://github.com/kgaughan/docserver',
    license='Apache Licence v2.0',
    py_modules=['docserver'],
    test_suite='tests',
    zip_safe=True,
    install_requires=[
        'docopt',
        'pystache',
        'six',
    ],

    entry_points={
        'paste.app_factory': (
            'main=docserver:create_application',
        ),
    },

    classifiers=(
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
    ),

    author='Keith Gaughan',
    author_email='k@stereochro.me',
)
