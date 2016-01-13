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
  docserver --print-template
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
  --print-template     Print out the default frontpage template
"""

import cgi
import contextlib
import datetime
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
import humanize
import pkg_resources
import pystache
import six
from six.moves import http_client as http


# pylint: disable-msg=E1103
__version__ = pkg_resources.get_distribution('docserver').version


logger = logging.getLogger('docserver')


DEFAULT_STORE = '~/docstore'


DEFAULT_FRONTPAGE = six.u("""\
<!DOCTYPE html>
<html><head>

    <title>Documentation Bundles</title>

    <link href="https://fonts.googleapis.com/css?family=Open+Sans:400,600,400italic" rel="stylesheet" type="text/css" crossorigin="anonymous">
    <link href="https://maxcdn.bootstrapcdn.com/font-awesome/4.4.0/css/font-awesome.min.css" rel="stylesheet" type="text/css" integrity="sha256-k2/8zcNbxVIh5mnQ52A0r3a6jAgMGxFJFE2707UxGCk= sha512-ZV9KawG2Legkwp3nAlxLIVFudTauWuBpC10uEafMHYL0Sarrz5A7G79kXh5+5+woxQ5HM559XX2UZjMJ36Wplg==" crossorigin="anonymous">

    <style type="text/css" media="all">
    body {
        width: 60em;
        margin: 1em auto;
        font-family: "Open Sans", "Helvetica Neue", Arial, sans-serif;
        line-height: 1.5;
        color: #444;
    }
    address {
        margin-top: 1em;
        border-top: 1px solid #888;
        font-size: 80%;
        padding: 0.625ex 0;
        text-align: right;
    }
    h1 {
        margin: 0;
        border-bottom: 1px solid #888;
        font-size: 100%;
    }
    ul {
        border-bottom: 1px solid #888;
        margin: 0;
        padding: 0;
        list-style: none;
    }
    ul li {
        padding: 0.5ex 1ex;
        transition-duration: 0.2s;
    }
    ul li + li {
        border-top: 1px solid #DDD;
    }
    ul a.manual {
        display: block;
        color: inherit;
        font-weight: bold;
        text-decoration: none;
        font-size: 125%;
    }
    ul li:hover {
        background: #EEE;
    }
    .stats {
        font-size: 80%;
        display: block;
        padding: 0 0 1ex 0;
        color: #888;
    }
    a.download,
    form input[type=submit] {
        background: #4479ba;
        color: #EEE;
        text-decoration: none;
        font: inherit;
        font-weight: bold;
        padding: 0.375ex 1ex 0.25ex;
        border-radius: 0.5ex;
        border: 1px solid #20538d;
        box-shadow: 1px 1px 0 rgba(255, 255, 255, 0.3) inset,
                    1px 1px 0 rgba(0, 0, 0, 0.2);
        text-shadow: 0 -1px 0 rgba(0, 0, 0, 0.4);
        transition-duration: 0.2s;
        user-select: none;
    }
    a.download:hover,
    form input[type=submit]:hover {
        border: solid 1px #2A4E77;
        background: #356094;
    }
    a.download:active,
    form input[type=submit]:active {
        box-shadow: inset 0 1px 4px rgba(0, 0, 0, 0.6);
        background: #2E5481;
        border: solid 1px #203E5F;
    }
    a.download {
        float: right;
    }
    form input[type=submit] {
        font-size: 80%;
    }
    form input[type=submit]::-moz-focus-inner {
        border: 0;
        padding: 0;
    }
    form {
        width: 36em;
        margin: 4em auto 4em auto;
    }
    fieldset {
        position: relative;
        border: solid #888;
        border-width: 1px 0 0 0;
        background: linear-gradient(to bottom,
                                    rgba(  0,   0,   0, 0.10) 0%,
                                    rgba(  0,   0,   0, 0.00) 100%);
    }
    fieldset legend {
        position: absolute;
        top: -1.5em;
        left: 0;
        font-weight: bold;
    }
    form div {
        position: relative;
        margin: 1ex 0 1ex 13em;
    }
    label strong {
        position: absolute;
        left: -13em;
        width: 12.5em;
        display: block;
        text-align: right;
    }
    label span.note {
        display: block;
        font-size: 80%;
    }
    </style>

</head><body>

<h1>Documentation Bundles</h1>

<ul>
{{#entries}}
<li><a class="manual" href="{{name}}/">{{name}}</a>
    <span class="stats">
    <a class="download" href="{{name}}.zip"><i class="fa fa-download"></i> Download</a>
    Size: {{size}}; Modified: {{modified}}
    </span></li>
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
     <span class="note">Defaults to document bundle archive name</span>
     </label></div>
<div><label><strong>Document bundle</strong>
     <input type="file" name="content" required="required"
         accept=".zip,application/zip,application/octet-stream">
     </label></div>
<div><input type="submit" value="Upload"></div>
</fieldset>
</form>

<address>
Powered by
<a href="https://github.com/kgaughan/docserver/">docserver</a>/{{version}}
</address>

</body></html>
""")

POST_REDIRECT = six.u("""\
<!DOCTYPE html>
<html><head>

    <title>See: {{url}}</title>
    <meta http-equiv="refresh" content="1; url={{url}}">

</head><body>

<p>See: <a href="{{url}}">{{url}}</a></p>

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
    def headers(self):  # pragma: no cover
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


class _Redirect(HTTPError):
    """
    A redirect. Subclass to set the code.
    """

    code = None

    def __init__(self, location, message=None):
        super(_Redirect, self).__init__(self.code, message)
        self.location = location

    def headers(self):
        return [('Location', self.location)]


class MovedPermanently(_Redirect):
    """
    Resource moved permanently.
    """
    code = http.MOVED_PERMANENTLY


class Found(_Redirect):
    """
    Temporary redirect.
    """
    code = http.FOUND


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


def parse_form(environ):  # pragma: no cover
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


class App(object):
    """
    Application base class.
    """

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


class BadPath(Exception):
    """
    Bad path.
    """
    pass


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


class DocServer(App):
    """
    A documentation server.
    """

    def __init__(self, store=None, template=None):
        super(DocServer, self).__init__()
        self.store = get_store(store)
        self.frontpage = pystache.parse(get_template(template))
        self.refresh = pystache.parse(POST_REDIRECT)

    def run(self, environ):
        """
        Dispatch request.
        """
        if re.match(r'/[a-z0-9.\-]+\.zip$', environ['PATH_INFO'], re.I):
            require_method(environ, ('GET', 'HEAD'))
            return self.download(environ)
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

        try:
            with contextlib.closing(zipfile.ZipFile(path, 'r')) as archive:
                try:
                    info = archive.getinfo(filename)
                except KeyError:
                    # No such file in the bundle.
                    raise NotFound()
                timestamp = time.mktime(info.date_time + (0, 0, 0))
                if check_if_unmodified(environ, timestamp):
                    # Expire 5m from now.
                    raise NotModified(time.time() + 60 * 5)
                content = archive.read(info)
        except IOError:
            # No such bundle.
            raise NotFound()

        return (http.OK,
                [('Content-Type', mimetype),
                 ('Last-Modified', email.utils.formatdate(timestamp))],
                [content])

    # pylint: disable-msg=W0613
    def contents(self, environ):
        """
        List documentation bundles.
        """
        content = pystache.render(self.frontpage,
                                  entries=list(self.get_entries()),
                                  version=__version__)
        return (http.OK,
                [('Content-Type', 'text/html; charset=utf-8')],
                [content.encode('utf-8')])

    def download(self, environ):
        parts = environ['PATH_INFO'].split('/', 2)
        path = os.path.join(self.store, parts[1][:2], parts[1])
        if not os.path.isfile(path):
            raise NotFound()
        with open(path, 'r') as fh:
            return (http.OK,
                    [('Content-Type', 'application/zip')],
                    [fh.read()])

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

        # For 'python setup.py upload_docs' to work properly without
        # reporting a spurious error. It's the least worst way of checking
        # if the upload is happening via CLI or a form.
        if 'HTTP_REFERER' not in environ:
            bundle = here + name + '/'
            content = pystache.render(self.refresh, url=bundle)
            return (http.OK,
                    [('Content-Type', 'text/html; charset=utf-8'),
                     ('Location', bundle)],
                    [content.encode('utf-8')])

        return (http.SEE_OTHER,
                [('Content-Type', 'text/plain'), ('Location', here)],
                [here])

    def get_entries(self):
        """
        Get a list of documentation bundles.
        """
        pattern = os.path.join(self.store, '??/*.zip')
        for entry in sorted(glob.iglob(pattern)):
            stat = os.stat(entry)
            modified = datetime.datetime.fromtimestamp(stat.st_mtime)
            yield {
                # The first '4' refers to '/??/', the second to '.zip'
                'name': entry[len(self.store) + 4:-4],
                'modified': humanize.naturaltime(modified),
                'size': humanize.naturalsize(stat.st_size, binary=True),
            }


# pylint: disable-msg=W0613
def create_application(global_config=None, **local_conf):
    """
    Create a configured instance of the WSGI application.
    """
    return DocServer(**local_conf)


# pylint: disable-msg=W0102
def main(argv=sys.argv):
    """
    Run the WSGI application using :mod:`wsgiref`.
    """
    args = docopt.docopt(__doc__, argv[1:], version=__version__)

    if args['--print-template']:
        six.print_(DEFAULT_FRONTPAGE)
        return 0

    host = args['--host']
    port = int(args['--port'])
    store = os.path.realpath(os.path.expanduser(args['--store']))
    template = args['--template']

    if 0 > port > 65535:
        six.print_('Bad port: {0}'.format(port), file=sys.stderr)
        return 1

    try:
        app = create_application(None, store=store, template=template)
    except BadPath as exc:
        six.print_(exc.message, file=sys.stderr)
        return 1

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    from wsgiref.util import guess_scheme
    scheme = guess_scheme(os.environ)
    six.print_("Serving on {0}://{1}:{2}/".format(scheme, host, port),
               file=sys.stderr)

    from wsgiref.simple_server import make_server
    make_server(host, port, app).serve_forever()
    return 0


if __name__ == '__main__':
    sys.exit(main())
