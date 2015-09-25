
import asyncio
from asyncio.subprocess import PIPE
import re
import shlex


class ProcessError(Exception):
    def __init__(self, args, proc):
        self.args = args
        self.proc = proc

    def __str__(self):
        try:
            return self.proc.err
        except UnicodeDecodeError:
            return self.proc.err_bytes


def quoted_cmdline(*args):
    return ' '.join(shlex.quote(s) for s in args)


class ProcWrap:
    def __init__(self, *, status, stdout, stderr, strip):
        self.status = status
        self.out_bytes = stdout
        self.err_bytes = stderr
        self.strip = strip

    def _to_str(self, bytes_content):
        ret = bytes_content.decode('utf8')
        ret = re.sub('(\r\n|\r)', '\n', ret)
        if self.strip:
            ret = ret.strip()
        return ret

    @property
    def err(self):
        return self._to_str(self.err_bytes)

    @property
    def out(self):
        return self._to_str(self.out_bytes)

    @property
    def out_lines(self):
        return self.out.split('\n')


async def aiorun(*args,
                 log,
                 stdin_bytes=None,
                 stdin=None,
                 strip=True,
                 ignore_errors=False,
                 env=None,
                 cwd=None):

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        env=env,
        cwd=cwd)

    log.info('Running process', pid=proc.pid, command=quoted_cmdline(*args))

    if stdin_bytes is None and stdin is not None:
        stdin_bytes = stdin.encode('utf8')

    if stdin_bytes:
        stdout_head, stderr_head = await proc.communicate(stdin_bytes)
    else:
        stdout_head, stderr_head = b'', b''

    status = await proc.wait()
    stdout = stdout_head + (await proc.stdout.read())
    stderr = stderr_head + (await proc.stderr.read())

    ret = ProcWrap(
        status=status,
        stdout=stdout,
        stderr=stderr,
        strip=strip)

    try:
        log_out = ret.out
    except UnicodeDecodeError:
        log_out = 'Could not decode: ' + str(ret.out_bytes)

    try:
        log_err = ret.err
    except UnicodeDecodeError:
        log_err = 'Could not decode:' + str(ret.err_bytes)

    log.debug('Process exited', pid=proc.pid, status=ret.status, stdout=log_out, stderr=log_err)

    if not ignore_errors and status != 0:
        raise ProcessError(args, ret)
    else:
        return ret
