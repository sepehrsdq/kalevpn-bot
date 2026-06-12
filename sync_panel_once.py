import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from app.services.sync import sync_services_with_panel

ok, msg = sync_services_with_panel()
print(ok, msg)
