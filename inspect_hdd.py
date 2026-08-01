import requests
from requests.auth import HTTPDigestAuth
from config import DVR

apis = [
    '/ISAPI/ContentMgmt/Storage',
    '/ISAPI/ContentMgmt/Storage/hdd',
    '/ISAPI/ContentMgmt/Storage/hdds',
    '/ISAPI/ContentMgmt/Storage/disks',
    '/ISAPI/ContentMgmt/Storage/volume',
]

for api in apis:
    try:
        url = f"http://{DVR['ip']}{api}"
        r = requests.get(url, auth=HTTPDigestAuth(DVR['username'], DVR['password']), timeout=5)
        print('===', api, '===')
        print('status:', r.status_code)
        print(r.text[:5000])
        print()
    except Exception as e:
        print('ERR', api, e)
