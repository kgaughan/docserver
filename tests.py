import unittest

import docserver


class TestFramework(unittest.TestCase):

    def test_status_line(self):
        self.assertEqual(docserver.make_status_line(200), '200 OK')
        self.assertEqual(docserver.make_status_line(201), '201 Created')

    def test_require_method(self):
        docserver.require_method({'REQUEST_METHOD': 'POST'},
                                 ('HEAD', 'GET', 'POST'))
        self.assertRaises(docserver.MethodNotAllowed,
                          docserver.require_method,
                          {'REQUEST_METHOD': 'POST'},
                          allowed=('HEAD', 'GET'))
        try:
            docserver.require_method({'REQUEST_METHOD': 'baz'},
                                     allowed=('foo', 'bar'))
        except docserver.MethodNotAllowed as exc:
            self.assertEqual(exc.headers(), [('Allow', 'foo, bar')])

    def test_absolute(self):
        def test(expected, path_info, add_slash):
            self.assertEqual(expected,
                             docserver.absolute({'wsgi.url_scheme': 'http',
                                                 'HTTP_HOST': 'localhost:8080',
                                                 'PATH_INFO': path_info},
                                                add_slash=add_slash))
        test('http://localhost:8080/foo/bar/', '/foo/bar', add_slash=True)
        test('http://localhost:8080/foo/bar', '/foo/bar', add_slash=False)
        test('http://localhost:8080/foo/bar/', '/foo/bar/', add_slash=True)

    def test_check_if_modified(self):
        pass


class TestConfig(unittest.TestCase):

    def test_get_store(self):
        pass

    def test_get_template(self):
        pass
