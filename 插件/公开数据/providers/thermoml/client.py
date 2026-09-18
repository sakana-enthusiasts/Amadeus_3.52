from urllib.parse import urlparse


class ThermoMLClient:
    def __init__(self, http):
        self.http = http

    def document(self, url):
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "trc.nist.gov" or parsed.username or parsed.password:
            raise ValueError("ThermoML URL must refer to the official HTTPS archive")
        return self.http.get(url, url)
