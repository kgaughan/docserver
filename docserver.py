#!/usr/bin/env python
#
# Copyright (c) Keith Gaughan, 2013
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
A PyPI-style documentation server.
"""

import cgi
import glob
import os
import os.path

import pystache
import six
from six.moves import http_client as http


DEFAULT_STORE = '~/docstore'


DEFAULT_FRONTPAGE = six.u("""\
<!DOCTYPE html>
<html>
    <head>
        <title>Documentation</title>
    </head>
    <body>
        <h1>Documentation</h1>
        <ul>
            {{#entries}}
            <li><a href="{{name}}/">{{name}}</a></li>
            {{/entries}}

            {{^entries}}
            <li>No entries</li>
            {{/entries}}
        </ul>
    </body>
</html>
""")


class HTTPError(Exception):
    """
    Application wants to respond with the given HTTP status code.
    """

    def __init__(self, code, message=None):
        if message is None:
            message = http.responses[code]
        super(HTTPError, self).__init__(message)
        self.code = code

    # pylint: disable-msg=R0201
    def headers(self):
        """
        Additional headers to be sent.
        """
        return []


class MethodNotAllowed(HTTPError):
    """
    Method not allowed.
    """

    def __init__(self, allowed=(), message=None):
        super(MethodNotAllowed, self).__init__(http.METHOD_NOT_ALLOWED,
                                               message)
        self.allowed = allowed

    def headers(self):
        return [('Allow', ', '.join(self.allowed))]


class BadPath(Exception):
    """
    Bad path.
    """
    pass


def make_status_line(code):
    """
    Create a HTTP status line.
    """
    return '{0} {1}'.format(code, http.responses[code])


def require_method(environ, allowed=()):
    if environ['REQUEST_METHOD'] not in allowed:
        raise MethodNotAllowed(allowed)


def parse_form(environ):
    try:
        request_size = int(environ.get('CONTENT_LENGTH', 0))
    except ValueError:
        request_size = 0
    return cgi.FieldStorage(
        fp=six.BytesIO(environ['wsgi.input'].read(request_size)),
        environ=environ)


def dictify(key, entries):
    return [{key: value} for value in entries]


class DocServer(object):

    def __init__(self, store=None):
        super(DocServer, self).__init__()
        if store is None:
            store = os.getenv('DOCSERVER_STORE', DEFAULT_STORE)
        store = os.path.realpath(os.path.expanduser(store)).rstrip('/')
        if not os.path.isdir(store):
            raise BadPath('"{0}" not found.'.format(store))
        self.store = store
        self.frontpage = pystache.parse(DEFAULT_FRONTPAGE)

    def __call__(self, environ, start_response):
        try:
            code, headers, content = self.run(environ)
            start_response(make_status_line(code), headers)
            return content
        except HTTPError as exc:
            start_response(make_status_line(exc.code),
                           [('Content-Type', 'text/plain')] + exc.headers())
            return [exc.message]

    def run(self, environ):
        if environ['PATH_INFO'] != '/':
            require_method(environ, ('GET', 'HEAD'))
            return self.display(environ)
        if environ['REQUEST_METHOD'] in ('GET', 'HEAD'):
            return self.contents(environ)
        if environ['REQUEST_METHOD'] == 'POST':
            return self.submit(environ)
        raise MethodNotAllowed(('GET', 'HEAD', 'POST'))

    def display(self, environ):
        return (http.OK,
                [('Content-Type', 'text/plain')],
                [environ['PATH_INFO']])

    def contents(self, environ):
        entries = dictify('name', self.get_entries())
        content = pystache.render(self.frontpage, entries=entries)
        return (http.OK,
                [('Content-Type', 'text/html; charset=utf-8')],
                [content.encode('utf-8')])

    def submit(self, environ):
        return (http.OK,
                [('Content-Type', 'text/plain')],
                [environ['PATH_INFO']])

    def get_entries(self):
        # The first '4' refers to '/??/', the second to '.zip'
        return sorted(entry[len(self.store) + 4:-4]
                      for entry in glob.iglob(os.path.join(self.store,
                                                           '??/*.zip')))


# pylint: disable-msg=W0613
def create_application(global_config=None, **local_conf):
    """
    Create a configured instance of the WSGI application.
    """
    return DocServer(store=local_conf.get('store'))


def main():
    """
    Run the WSGI application using :mod:`wsgiref`.
    """
    from wsgiref.simple_server import make_server
    make_server('localhost', 8080, DocServer()).serve_forever()


if __name__ == '__main__':
    main()
