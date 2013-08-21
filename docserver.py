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

from six.moves import http_client as http


def make_status_line(code):
    """
    Create a HTTP status line.
    """
    return '{0} {1}'.format(code, http.responses[code])


class DocServer(object):

    def __init__(self):
        super(DocServer, self).__init__()

    def __call__(self, environ, start_response):
        start_response(make_status_line(http.OK),
                       [('Content-Type', 'text/plain')])
        return ['Hello, world!']
