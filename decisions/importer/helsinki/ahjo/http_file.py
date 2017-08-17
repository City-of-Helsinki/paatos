import os
import urllib


class HttpFetchedFile(object):
    """
    File-like object for reading a remote file over HTTP.

    Supports seeking.
    """
    def __init__(self, url):
        self.url = url
        self.pos = 0
        self._length = None

    def read(self, size=None):
        start = self.tell()
        end = start + size - 1 if size is not None else ''
        range_str = 'bytes={}-{}'.format(start, end)
        req = urllib.request.Request(self.url)
        req.headers['Range'] = range_str
        with urllib.request.urlopen(req) as fp:
            if fp.getcode() != 206:  # Partial Content
                raise IOError("Server does not support HTTP Range feature")
            data = fp.read()
            cr = fp.getheader('Content-Range')
            if cr:
                self._length = int(cr.split('/', 1)[1])
        self.pos += len(data)
        return data

    def tell(self):
        return self.pos

    def seek(self, pos, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            self.pos = pos
        elif whence == os.SEEK_CUR:
            self.pos += pos
        elif whence == os.SEEK_END:
            self.pos = self.length + pos
        return self.pos

    @property
    def length(self):
        if self._length is None:
            self.read(1)  # Sets self._length as side effect
        return self._length
