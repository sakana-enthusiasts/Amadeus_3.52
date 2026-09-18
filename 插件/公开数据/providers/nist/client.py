from urllib.parse import urlencode


class WebBookClient:
    base = "https://webbook.nist.gov/cgi/cbook.cgi"

    def __init__(self, http):
        self.http = http

    def properties(self, record_id, individual_type=None):
        params = {"ID": record_id, "Units": "SI"}
        params.update({"Type": individual_type} if individual_type else {"Mask": "7"})
        return self.http.get(self.base + "?" + urlencode(params), record_id)
