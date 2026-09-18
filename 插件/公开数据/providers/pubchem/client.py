from urllib.parse import quote

from .mapping import REST_PROPERTIES


class PUGRestClient:
    base = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

    def __init__(self, http):
        self.http = http

    def resolve(self, namespace, query):
        return self.http.get(f"{self.base}/compound/{namespace}/{quote(str(query), safe='')}/cids/JSON")

    def properties(self, cid):
        return self.http.get(f"{self.base}/compound/cid/{cid}/property/{','.join(REST_PROPERTIES)}/JSON", cid)


class PUGViewClient:
    base = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"

    def __init__(self, http):
        self.http = http

    def index(self, cid):
        return self.http.get(f"{self.base}/index/compound/{cid}/JSON", cid)

    def heading(self, cid, heading):
        return self.http.get(f"{self.base}/data/compound/{cid}/JSON?heading={quote(heading, safe='')}", cid)
