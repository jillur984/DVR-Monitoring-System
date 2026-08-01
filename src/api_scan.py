import requests
from requests.auth import HTTPDigestAuth

IP = "10.64.2.253"
USER = "admin"
PASS = "test@125"

apis = [
    "/ISAPI/ContentMgmt/Storage",
    "/ISAPI/ContentMgmt/Storage/hdd",
    "/ISAPI/ContentMgmt/Storage/hdds",
    "/ISAPI/ContentMgmt/Storage/disks",
    "/ISAPI/ContentMgmt/Storage/volume",
    "/ISAPI/System/deviceInfo",
    "/ISAPI/System/Video/inputs/channels",
    "/ISAPI/ContentMgmt/record/status",
]

for api in apis:

    try:

        r = requests.get(
            f"http://{IP}{api}",
            auth=HTTPDigestAuth(USER, PASS),
            timeout=5
        )

        print("=" * 60)
        print(api)
        print("Status:", r.status_code)

        if r.status_code == 200:
            print(r.text[:1000])

    except Exception as e:
        print(api, e)