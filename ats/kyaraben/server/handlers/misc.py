
import tempfile


def dump_stream(tempdir, stream):
    bufsize = 1024 * 1024 * 1
    with tempfile.NamedTemporaryFile(mode='wb', dir=tempdir, delete=False) as fout:
        while True:
            b = stream.read(bufsize)
            if not b:
                break
            fout.write(b)
        fout.flush()
        return fout.name
