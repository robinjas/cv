import sys
import json
import yaml
import logging
import requests
from functools import wraps
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(filename="redfish.log", level=logging.DEBUG)

class GicaRedfish:
    def __init__(self, user, password, uri_base):
        self.logger = logging.getLogger("redfish_base")
        self.uri_base = uri_base
        self.cred = (user, password)
        self.headers = {"content-type": "application/json"}

    def _request(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            url = f"{self.uri_base}{args[0]}"
            try:
                response = func(self, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error: {e}")
                self.logger.error(f"URL: {url}")
                return None
            except Exception as ex:
                self.logger.error(f"Unexpected error: {ex}")
                self.logger.error(f"URL: {url}")
                return None

        return wrapper

    @_request
    def get(self, uri_endpoint, **kwargs):
        return requests.get(uri_endpoint, headers=self.headers, verify=False, auth=self.cred, timeout=60, **kwargs)

    @_request
    def put(self, uri_endpoint, data, **kwargs):
        return requests.put(uri_endpoint, json=data, verify=False, auth=self.cred, timeout=60, **kwargs)

    @_request
    def post(self, uri_endpoint, data, **kwargs):
        return requests.post(uri_endpoint, json=data, verify=False, auth=self.cred, timeout=60, **kwargs)

    @_request
    def patch(self, uri_endpoint, data, **kwargs):
        return requests.patch(uri_endpoint, json=data, verify=False, auth=self.cred, timeout=60, **kwargs)

class HpeApi(GicaRedfish):
    def __init__(self, user, password, base_uri):
        self.logger = logging.getLogger("hpe_redfish")
        GicaRedfish.__init__(self, user, password, base_uri)
        self.user = user
        self.password = password

    def get_firmware_inventory(self):
        response = self.get("UpdateService/FirmwareInventory")
        return response if response else {}

    def get_system_status(self):
        response = self.get("Systems/1")
        return response.get('Status') if response else {}

    def get_thermal_details(self):
        response = self.get("Chassis/1/Thermal")
        return response if response else {}

    def get_power_details(self):
        response = self.get("Chassis/1/Power")
        return response if response else {}

    def get_processor_info(self):
        response = self.get("Systems/1/Processors")
        return response.get('Members', []) if response else []

    def get_memory(self):
        response = self.get("Systems/1/Memory")
        total_memory = 0
        if response:
            members = response.get("Members", [])
            for memory_module in members:
                memory_detail = memory_module.get("@odata.id", "")
                if memory_detail:
                    memory_info = self.get(memory_detail.replace("/redfish/v1", ""))
                    if memory_info:
                        total_memory += memory_info.get("CapacityMiB", 0)
        return total_memory/1024 

    def get_network_interfaces(self):
        response = self.get("Systems/1/EthernetInterfaces")
        return response.get('Members', []) if response else []

if __name__ == "__main__":
    api = HpeApi("mhsadmin", "letsr0ll", "https://192.168.95.88/redfish/v1/")
    print("Total Memory:", api.get_memory(), "GB")