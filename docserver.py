#!/usr/bin/env python3
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

import argparse
import datetime
import glob
from http import client as http
import logging
import mimetypes
import os
import os.path
import re
import sys
import zipfile

import humanize
import pystache
from werkzeug.exceptions import BadRequest, NotFound
from werkzeug.routing import Map, Rule
from werkzeug.serving import run_simple
from werkzeug.utils import redirect
from werkzeug.wrappers import Request, Response


__version__ = "0.2.1"


logger = logging.getLogger("docserver")


DEFAULT_STORE = "~/docstore"


DEFAULT_FRONTPAGE = """\
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
"""


class BadPath(Exception):
    """
    Bad path.
    """


def scrub_name(name):
    """
    Clean up a documentation distribution's name.
    """
    return "-".join(re.findall("[a-z0-9]+", name.lower()))


def get_store(store):
    """
    Get the path of the directory to use for the bundle store.
    """
    if store is None:
        store = os.getenv("DOCSERVER_STORE", DEFAULT_STORE)
    store = os.path.realpath(os.path.expanduser(store)).rstrip("/")
    if not os.path.isdir(store):
        raise BadPath('"{0}" not found.'.format(store))
    return store


def get_template(template):
    """
    Read the template to use to render the frontpage.
    """
    if template is None:
        template = os.getenv("DOCSERVER_TEMPLATE")
    if template is None:
        return DEFAULT_FRONTPAGE
    with open(os.path.realpath(template), "r") as fp:
        return fp.read()


def render(template, **kwargs):
    return Response(
        pystache.render(template, **kwargs), mimetype="text/html; charset=utf-8"
    )


class DocServer:
    """
    A documentation server.
    """

    url_map = Map(
        [
            Rule("/", endpoint="index", methods=["GET", "POST"]),
            Rule("/<bundle>.zip", endpoint="download", methods=["GET"]),
            Rule("/<bundle>/", endpoint="page", methods=["GET"]),
            Rule("/<bundle>/<path:page>", endpoint="page", methods=["GET"]),
        ]
    )

    def __init__(self, store=None, template=None):
        super().__init__()
        self.store = get_store(store)
        self.frontpage = pystache.parse(get_template(template))

    def __call__(self, environ, start_response):
        """
        Request convert the WSGI request to a more convenient format.
        """
        request = Request(environ)
        response = self.url_map.bind_to_environ(request.environ).dispatch(
            lambda ep, values: getattr(self, "on_" + ep)(request, **values),
            catch_http_exceptions=True,
        )
        return response(environ, start_response)

    def on_index(self, request):
        """
        List documentation bundles.
        """
        if request.method == "GET":
            return render(
                self.frontpage, entries=list(self.get_entries()), version=__version__
            )

        # Process an upload instead.
        if request.form.get(":action") != "doc_upload":
            raise BadRequest(":action must be 'doc_upload'")

        content = request.files.get("content")
        if content is None:
            raise BadRequest("No content submitted")

        name = request.form.get("name", "").strip()
        if name == "":
            name = content.filename
            if name.endswith(".zip"):
                name = name[:-4]
        name = scrub_name(name)
        if len(name) < 2:
            raise BadRequest("Name must be at least two characters long.")

        # HACK: Force the SpooledTemporaryFile to be written to disc. This is
        # needed otherwise we get the error "'SpooledTemporaryFile' object has
        # no attribute 'seekable'"
        content.stream.seekable = lambda: True

        try:
            archive = zipfile.ZipFile(content.stream)
            if archive.testzip() is not None:
                raise BadRequest("Bad Zip file")
        except zipfile.BadZipfile:
            raise BadRequest("Bad Zip file")

        # Reset to the start, or we'll end up with a truncated file.
        content.stream.seek(0, 0)

        catalogue = os.path.join(self.store, name[:2])
        if not os.path.isdir(catalogue):
            os.makedirs(catalogue)
        content.save(os.path.join(catalogue, name + ".zip"))

        return redirect(request.base_url, code=http.SEE_OTHER)

    def on_download(self, request, bundle):
        path = os.path.join(self.store, bundle[:2], bundle + ".zip")
        if not os.path.isfile(path):
            raise NotFound()
        with open(path, "rb") as fh:
            return Response(fh.read(), mimetype="application/zip")

    def on_page(self, request, bundle, page="index.html"):
        """
        Display a file from a documentation bundle.
        """
        bundle_path = os.path.join(self.store, bundle[:2], bundle + ".zip")
        if not os.path.isfile(bundle_path):
            raise NotFound()

        mimetype, _ = mimetypes.guess_type(page)
        if mimetype is None:
            mimetype = "application/octet-stream"

        with zipfile.ZipFile(bundle_path, "r") as archive:
            try:
                info = archive.getinfo(page)
            except KeyError:
                raise NotFound()
            content = archive.read(info)

        return Response(content, mimetype=mimetype)

    def get_entries(self):
        """
        Get a list of documentation bundles.
        """
        pattern = os.path.join(self.store, "??/*.zip")
        for entry in sorted(glob.iglob(pattern)):
            stat = os.stat(entry)
            modified = datetime.datetime.fromtimestamp(stat.st_mtime)
            yield {
                # The first '4' refers to '/??/', the second to '.zip'
                "name": entry[len(self.store) + 4 : -4],
                "modified": humanize.naturaltime(modified),
                "size": humanize.naturalsize(stat.st_size, binary=True),
            }


# pylint: disable-msg=W0102
def main(argv=sys.argv):
    """
    Run the WSGI application using :mod:`wsgiref`.
    """
    parser = argparse.ArgumentParser(description="A PyPI-style documentation server.")
    parser.add_argument(
        "--host", help="hostname or address to bind server to", default="localhost"
    )
    parser.add_argument("--port", help="port to run server on", type=int, default=8080)
    parser.add_argument(
        "--store", help="path to bundle store directory", default="~/docstore"
    )
    parser.add_argument("--template", help="path to frontpage template", type=str)
    parser.add_argument("--print-template", action="store_true")
    args = parser.parse_args()

    if args.print_template:
        print(DEFAULT_FRONTPAGE)
        return 0

    store = os.path.realpath(os.path.expanduser(args.store))

    if 0 > args.port > 65535:
        print("Bad port:", args.port, file=sys.stderr)
        return 1

    try:
        app = DocServer(store=store, template=args.template)
    except BadPath as exc:
        print(exc, file=sys.stderr)
        return 1

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    run_simple(args.host, args.port, app)


if __name__ == "__main__":
    sys.exit(main())
