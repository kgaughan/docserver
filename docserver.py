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

"""\
A PyPI-style documentation server.

Usage:
  docserver [--host=HOST] [--port=PORT] [--store=STORE] [--template=TEMPLATE]
  docserver --help|--version

Option:
  --help               Show this screen
  --version            Show version
  --host=HOST          Hostname or address to bind server to
                       [default: localhost]
  --port=PORT          Port to run server on
                       [default: 8080]
  --store=STORE        Path to bundle store directory
                       [default: ~/docstore]
  --template=TEMPLATE  Path to frontpage template
"""

import cgi
import contextlib
import email.utils
import glob
import logging
import mimetypes
import os
import os.path
import re
import sys
import time
import zipfile

import docopt
import pkg_resources
import pystache
import six
from six.moves import http_client as http


__version__ = pkg_resources.get_distribution('docserver').version


logger = logging.getLogger('docserver')


DEFAULT_STORE = '~/docstore'


DEFAULT_FRONTPAGE = six.u("""\
<!DOCTYPE html>
<html><head>

    <title>Documentation Bundles</title>

</head><body>

<h1>Documentation Bundles</h1>

<ul>
{{#entries}}
<li><a href="{{.}}/">{{.}}</a></li>
{{/entries}}
{{^entries}}
<li>No entries</li>
{{/entries}}
</ul>

<form method="post" enctype="multipart/form-data" action="">
<fieldset>
<legend>Documentation upload</legend>
<input type="hidden" name=":action" value="doc_upload">
<div><label><strong>Distribution name</strong>
     <input type="text" name="name">
     </label></div>
<div><label><strong>Document bundle</strong>
     <input type="file" name="content" required="required"
         accept=".zip,application/zip,application/octet-stream">
     </label></div>
<div><input type="submit" value="Upload"></div>
</fieldset>
</form>

</body></html>
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


class NotModified(HTTPError):
    """
    Resource not modified.
    """

    def __init__(self, expire=None):
        super(NotModified, self).__init__(http.NOT_MODIFIED)
        self.expire = expire

    def headers(self):
        return [('Expire', email.utils.formatdate(self.expire))]


class NotFound(HTTPError):
    """
    Resource not found.
    """

    def __init__(self, message=None):
        super(NotFound, self).__init__(http.NOT_FOUND, message)


class BadRequest(HTTPError):
    """
    Bad request.
    """

    def __init__(self, message=None):
        super(BadRequest, self).__init__(http.BAD_REQUEST, message)


class MovedPermanently(HTTPError):
    """
    Resource moved permanently.
    """

    def __init__(self, location, message=None):
        super(MovedPermanently, self).__init__(http.MOVED_PERMANENTLY,
                                               message)
        self.location = location

    def headers(self):
        return [('Location', self.location)]


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
    """
    Require that the request method is allowed.
    """
    if environ['REQUEST_METHOD'] not in allowed:
        raise MethodNotAllowed(allowed)


def parse_form(environ):
    """
    Parse the submitted request.
    """
    try:
        request_size = int(environ.get('CONTENT_LENGTH', 0))
    except ValueError:
        request_size = 0
    return cgi.FieldStorage(
        fp=six.BytesIO(environ['wsgi.input'].read(request_size)),
        environ=environ)


def absolute(environ, add_slash=False):
    """
    Reconstruct the URL, and append a trailing slash.
    """
    url = '{0}://{1}{2}'.format(environ['wsgi.url_scheme'],
                                environ['HTTP_HOST'],
                                environ['PATH_INFO'])
    if add_slash and url[-1] != '/':
        url += '/'
    return url


def check_if_unmodified(environ, timestamp):
    """
    Check the *If-Modified-Since* header and to see if we need to send a
    '304 Not Modified' response.
    """
    last_modified = environ.get('HTTP_IF_MODIFIED_SINCE')
    if last_modified is None:
        return False
    parsed = email.utils.parsedate(last_modified)
    return timestamp != parsed


def scrub_name(name):
    """
    Clean up a documentation distribution's name.
    """
    return '-'.join(re.findall('[a-z0-9]+', name.lower()))


def get_store(store):
    """
    Get the path of the directory to use for the bundle store.
    """
    if store is None:
        store = os.getenv('DOCSERVER_STORE', DEFAULT_STORE)
    store = os.path.realpath(os.path.expanduser(store)).rstrip('/')
    if not os.path.isdir(store):
        raise BadPath('"{0}" not found.'.format(store))
    return store


def get_template(template):
    """
    Read the template to use to render the frontpage.
    """
    if template is None:
        template = os.getenv('DOCSERVER_TEMPLATE')
    if template is None:
        return DEFAULT_FRONTPAGE
    with open(os.path.realpath(template), 'r') as fp:
        return unicode(fp.read())


class DocServer(object):
    """
    A documentation server.
    """

    def __init__(self, store=None, template=None):
        super(DocServer, self).__init__()
        self.store = get_store(store)
        self.frontpage = pystache.parse(get_template(template))

    def __call__(self, environ, start_response):
        """
        Request convert the WSGI request to a more convenient format.
        """
        try:
            code, headers, content = self.run(environ)
            start_response(make_status_line(code), headers)
            return content
        except HTTPError as exc:
            headers = exc.headers()
            if exc.code in (100, 101, 204, 304):
                # These must not send message bodies.
                content = []
            else:
                headers.append(('Content-Type', 'text/plain'))
                content = [exc.message]
            start_response(make_status_line(exc.code), headers)
            return content

    def run(self, environ):
        """
        Dispatch request.
        """
        if environ['PATH_INFO'] != '/':
            require_method(environ, ('GET', 'HEAD'))
            return self.display(environ)
        if environ['REQUEST_METHOD'] in ('GET', 'HEAD'):
            return self.contents(environ)
        if environ['REQUEST_METHOD'] == 'POST':
            return self.submit(environ)
        raise MethodNotAllowed(('GET', 'HEAD', 'POST'))

    def display(self, environ):
        """
        Display a file from a documentation bundle.
        """
        parts = environ['PATH_INFO'].split('/', 2)
        path = os.path.join(self.store, parts[1][:2], parts[1] + '.zip')
        if len(parts) == 2:
            if os.path.isfile(path):
                raise MovedPermanently(absolute(environ, add_slash=True))
            raise NotFound()

        filename = parts[2]
        if filename == '' or filename[-1] == '/':
            filename += 'index.html'

        mimetype, _ = mimetypes.guess_type(filename)
        if mimetype is None:
            mimetype = 'application/octet-stream'

        with contextlib.closing(zipfile.ZipFile(path, 'r')) as archive:
            try:
                info = archive.getinfo(filename)
            except KeyError:
                raise NotFound()
            timestamp = time.mktime(info.date_time + (0, 0, 0))
            if check_if_unmodified(environ, timestamp):
                # Expire 5m from now.
                raise NotModified(time.time() + 60 * 5)
            content = archive.read(info)

        return (http.OK,
                [('Content-Type', mimetype),
                 ('Last-Modified', email.utils.formatdate(timestamp))],
                [content])

    def contents(self, environ):
        """
        List documentation bundles.
        """
        content = pystache.render(self.frontpage, entries=self.get_entries())
        return (http.OK,
                [('Content-Type', 'text/html; charset=utf-8')],
                [content.encode('utf-8')])

    def submit(self, environ):
        """
        Process a documentation bundle submission.
        """
        form = parse_form(environ)
        if form.getvalue(':action') != 'doc_upload':
            raise BadRequest(":action must be 'doc_upload'")
        if 'content' not in form:
            raise BadRequest("No content submitted")
        content = form['content']
        if isinstance(content, list):
            raise BadRequest("Submit only one documentation bundle.")

        name = form.getvalue('name', '').strip()
        if name == '':
            name = content.filename
            if name.endswith('.zip'):
                name = name[:-4]
        name = scrub_name(name)
        if len(name) < 2:
            raise BadRequest('Name must be at least two characters long.')

        try:
            archive = zipfile.ZipFile(six.BytesIO(content.value))
            if archive.testzip() is not None:
                raise BadRequest("Bad Zip file")
        except zipfile.BadZipfile:
            raise BadRequest("Bad Zip file")

        catalogue = os.path.join(self.store, name[:2])
        if not os.path.isdir(catalogue):
            os.makedirs(catalogue)
        with open(os.path.join(catalogue, name + '.zip'), 'w') as fp:
            fp.write(content.value)

        logger.info('Upload [%s] %s', environ['REMOTE_HOST'], name)

        here = absolute(environ)
        return (http.SEE_OTHER,
                [('Content-Type', 'text/plain'), ('Location', here)],
                [here])

    def get_entries(self):
        """
        Get a list of documentation bundles.
        """
        # The first '4' refers to '/??/', the second to '.zip'
        return sorted(entry[len(self.store) + 4:-4]
                      for entry in glob.iglob(os.path.join(self.store,
                                                           '??/*.zip')))


# pylint: disable-msg=W0613
def create_application(global_config=None, **local_conf):
    """
    Create a configured instance of the WSGI application.
    """
    return DocServer(**local_conf)


def main(argv=sys.argv):
    """
    Run the WSGI application using :mod:`wsgiref`.
    """
    args = docopt.docopt(__doc__, argv[1:], version=__version__)

    host = args['--host']
    port = int(args['--port'])
    store = os.path.realpath(os.path.expanduser(args['--store']))
    template = args['--template']

    if 0 > port > 65535:
        print >> sys.stderr, 'Bad port: {0}'.format(port)
        return 1

    try:
        app = create_application(None, store=store, template=template)
    except BadPath as exc:
        print >> sys.stderr, exc.message
        return 1

    logging.basicConfig()

    print >> sys.stderr, "Serving on http://{0}:{1}/".format(host, port)
    from wsgiref.simple_server import make_server
    make_server(host, port, app).serve_forever()
    return 0


if __name__ == '__main__':
    sys.exit(main())
