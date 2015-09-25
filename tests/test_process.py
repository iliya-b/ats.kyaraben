
import asynctest
import locale
import logging
import tempfile
import unittest

from ats.kyaraben.process import aiorun, ProcessError, quoted_cmdline

log = logging.getLogger(__name__)


class TestQuotedCmdline(unittest.TestCase):
    def test_simple(self):
        q = quoted_cmdline('echo', 'foo')
        self.assertEqual(q, 'echo foo')

    def test_spaces(self):
        q = quoted_cmdline('echo', 'foo bar')
        self.assertEqual(q, "echo 'foo bar'")

    def test_quotes(self):
        q = quoted_cmdline('echo', "mo' quotes, mo' problems")
        self.assertEqual(q, 'echo \'mo\'"\'"\' quotes, mo\'"\'"\' problems\'')

    def test_quotes_list(self):
        # could have a better message
        with self.assertRaises(TypeError):
            quoted_cmdline(['echo', 'foo'])


class TestAiorun(asynctest.TestCase):

    async def test_dummy_command(self):
        await aiorun('/bin/true', log=log)

    async def test_status_ok(self):
        r = await aiorun('/bin/true', log=log)
        self.assertEqual(r.status, 0)

    async def test_status_error(self):
        with self.assertRaises(ProcessError):
            await aiorun('/bin/false', log=log)

    async def test_status_error_message(self):
        with self.assertRaisesRegexp(ProcessError, "^/bin/cat: /: Is a directory$"):
            await aiorun('/bin/cat', '/', log=log)

    async def test_status_error_ignored(self):
        r = await aiorun('/bin/false', ignore_errors=True, log=log)
        self.assertEqual(r.status, 1)

    async def test_empty_output(self):
        r = await aiorun('/bin/echo', log=log)
        self.assertEqual(r.out, '')
        self.assertEqual(r.err, '')

    async def test_empty_output_bytes(self):
        r = await aiorun('/bin/echo', log=log)
        self.assertEqual(r.out_bytes, b'\n')
        self.assertEqual(r.err_bytes, b'')

    async def test_empty_output_nostrip(self):
        r = await aiorun('/bin/echo', strip=False, log=log)
        self.assertEqual(r.out, '\n')
        self.assertEqual(r.err, '')
        self.assertEqual(r.out_bytes, b'\n')
        self.assertEqual(r.err_bytes, b'')

    async def test_stdout(self):
        r = await aiorun('/bin/echo', log=log)
        self.assertEqual(r.out, '')
        r = await aiorun('/bin/echo', 'foo', log=log)
        self.assertEqual(r.out, 'foo')

    async def test_stdout_bytes(self):
        r = await aiorun('/bin/echo', log=log)
        self.assertEqual(r.out_bytes, b'\n')
        r = await aiorun('/bin/echo', 'foo', log=log)
        self.assertEqual(r.out_bytes, b'foo\n')

    async def test_arg_quote(self):
        r = await aiorun('/bin/echo', '"greengrocers apostrophe\'s"', log=log)
        self.assertEqual(r.out, '"greengrocers apostrophe\'s"')

    async def test_stderr(self):
        r = await aiorun('/bin/echo', log=log)
        self.assertEqual(r.err, '')

        r = await aiorun('/bin/cat', '/', ignore_errors=True, log=log)
        self.assertEqual(r.out, '')
        self.assertEqual(r.err, '/bin/cat: /: Is a directory')

    async def test_unicode_stdout(self):
        r = await aiorun('/bin/echo', '\u0420\u043e\u0441\u0441\u0438\u044f', log=log)
        self.assertEqual(r.out, 'Россия')

    async def test_unicode_stderr(self):
        r = await aiorun('/bin/cat', '/\u0420\u043e\u0441\u0441\u0438\u044f', ignore_errors=True, log=log)
        self.assertEqual(r.out, '')
        self.assertEqual(r.err, '/bin/cat: /Россия: No such file or directory')

    async def test_nostrip_stdout(self):
        r = await aiorun('/bin/echo', 'foo', strip=False, log=log)
        self.assertEqual(r.out, 'foo\n')
        self.assertEqual(r.out_bytes, b'foo\n')

    async def test_nostrip_stderr(self):
        r = await aiorun('/bin/cat', '/', strip=False, ignore_errors=True, log=log)
        self.assertEqual(r.err, '/bin/cat: /: Is a directory\n')

    async def test_locale_environment(self):
        french = 'fr_FR.UTF-8'

        # can we run the test?
        try:
            lc_time = locale.getlocale(locale.LC_TIME)
            locale.setlocale(locale.LC_TIME, french)
            locale.setlocale(locale.LC_TIME, lc_time)
        except locale.Error:
            self.skipTest('localized output test skipped: unsupported locale %s' % french)
            return

        r = await aiorun('/bin/cat', '/', strip=True, env={'LC_ALL': french}, ignore_errors=True, log=log)
        self.assertEqual(r.err, '/bin/cat: /: est un dossier')

        # Override everything with boring ascii english

        r = await aiorun('/bin/cat', '/', strip=True, env={'LC_ALL': 'C'}, ignore_errors=True, log=log)
        self.assertEqual(r.err, '/bin/cat: /: Is a directory')

        r = await aiorun('/bin/date', '-d', '01/01/01', '+%B', env={'LC_TIME': french}, log=log)
        self.assertEqual(r.out, 'janvier')

    async def test_stdout_lines(self):
        with tempfile.NamedTemporaryFile(delete=True) as fout:
            fout.write(b'One Two Three Four\nIf I had ever been here before\nI would probably know just what to do\n')
            fout.flush()
            r = await aiorun('/bin/cat', fout.name, log=log)
            self.assertEqual(r.out_lines, [
                'One Two Three Four',
                'If I had ever been here before',
                'I would probably know just what to do'
            ])

    async def test_change_workdir(self):
        r = await aiorun('realpath', '.', cwd='/', log=log)
        self.assertEqual(r.out, '/')

    async def test_universal_newlines(self):
        r = await aiorun('echo', '-e', 'a\\rb', log=log)
        self.assertEqual(r.out_lines, ['a', 'b'])
        r = await aiorun('echo', '-e', 'a\\r\\nb', log=log)
        self.assertEqual(r.out_lines, ['a', 'b'])
        r = await aiorun('echo', '-e', 'a\\n\\rb', log=log)
        self.assertEqual(r.out_lines, ['a', '', 'b'])
        r = await aiorun('echo', '-e', 'a\\nb', log=log)
        self.assertEqual(r.out_lines, ['a', 'b'])

    async def test_stdin(self):
        r = await aiorun('cat', stdin_bytes=b'some data', log=log)
        self.assertEqual(r.out, 'some data')
