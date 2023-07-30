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
            try:
                response = func(self, *args, **kwargs)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error: {e}")
                self.logger.error(f"URL: {self.uri_base}{args[0]}")
                return None
            except Exception as ex:
                self.logger.error(f"Unexpected error: {ex}")
                self.logger.error(f"URL: {self.uri_base}{args[0]}")
                return None

        return wrapper

    @_request
    def get(self, uri_endpoint):
        return requests.get(
            f"{self.uri_base}{uri_endpoint.lstrip('/')}",
            headers=self.headers,
            verify=False,
            auth=self.cred,
            timeout=60,
        )

    @_request
    def put(self, uri_endpoint, data):
        return requests.put(
            f"{self.uri_base}{uri_endpoint}",
            json=data,
            verify=False,
            auth=self.cred,
            timeout=60,
        )

    @_request
    def post(self, uri_endpoint, data):
        return requests.post(
            f"{self.uri_base}{uri_endpoint}",
            json=data,
            verify=False,
            auth=self.cred,
            timeout=60,
        )

    @_request
    def patch(self, uri_endpoint, data):
        return requests.patch(
            f"{self.uri_base}{uri_endpoint}",
            json=data,
            verify=False,
            auth=self.cred,
            timeout=60,
        )


class DellApi(GicaRedfish):
    def __init__(self, user, password, base_uri):
        self.logger = logging.getLogger("dell_redfish")
        GicaRedfish.__init__(self, user, password, base_uri)
        self.user = user
        self.password = password

    def get_embedded(self):
        response = self.get("Chassis/System.Embedded.1")
        pass

    def get_i_drac(self):
        response = self.get("Chassis/{iDRAC uri}")
        pass

    def get_nvms(self):
        response = self.get(env["nvm_index"])
        result = [member["nvm_slot"] for member in response["Members"]]
        return result
        # DO THE THING WITH response#

    def get_boot_order(self):
        response_data = self.get(
            "Systems/System.Embedded.1/BootOptions?$expand=*($levels=1)"
        )

        if response_data is not None:
            boot_options = response_data.get("Members")

            if boot_options and isinstance(boot_options, list):
                print("Boot Order (Enabled options):")
                for boot_option in boot_options:
                    if boot_option.get("BootOptionEnabled", False):
                        display_name = boot_option.get("DisplayName", "")
                        boot_option_id = boot_option.get("Id", "")
                        print(f"  DisplayName: {display_name}")
                        print(f"  Boot Option Id: {boot_option_id}")
                        print("----------------------")
                return
            else:
                self.logger.error("Error: 'Members' key not found in the JSON data.")
        else:
            self.logger.error("Error: Failed to retrieve data from the endpoint.")

        print("No enabled boot options found or there was an error.")

    def get_bios_attributes(self):
        response = self.get("Systems/System.Embedded.1/Bios")
        if response is not None and "Attributes" in response:
            return response["Attributes"]
        else:
            self.logger.error("Error: Failed to retrieve BIOS attributes.")
            return None

    def get_dell_idrac_attributes(self):
        response = self.get(
            "Managers/iDRAC.Embedded.1/Oem/Dell/DellAttributes/System.Embedded.1"
        )
        if response is not None and "Attributes" in response:
            return response["Attributes"]
        else:
            self.logger.error("Error: Failed to retrieve Dell iDRAC attributes.")
            return None

    def get_raid_ids(self):
        response = self.get("Systems/System.Embedded.1/Storage")
        raid_ids = []

        if response is not None:
            for member in response.get("Members", []):
                if "RAID" in member.get("@odata.id", ""):
                    raid_id = member["@odata.id"].split("/")[
                        -1
                    ]  # Extract the RAID ID from the URL
                    raid_ids.append(raid_id)

            self.logger.info(f"RAID IDs: {raid_ids}")
            print(f"RAID IDs: {raid_ids}")  # Print to console
        else:
            self.logger.error("Error: Failed to retrieve RAID IDs.")

        return raid_ids

    def create_raid_volume(self, raid_id, data):
        response = self.post(
            f"Systems/System.Embedded.1/Storage/{raid_id}/Volumes/", data=data
        )
        return response

    def delete_raid_volume(self, raid_id, volume_id):
        response = self.delete(
            f"Systems/System.Embedded.1/Storage/{raid_id}/Volumes/{volume_id}"
        )
        return response

    def get_disk_info(self):
        response = self.get("Systems/System.Embedded.1/Storage/Drives")
        if response is not None:
            return response["Members"]

    def get_firmware_versions(self):
        response = self.get("UpdateService/FirmwareInventory")

        firmware_versions = []

        if response is not None:
            for member in response.get("Members", []):
                firmware_detail = self.get(
                    member.get("@odata.id", "").replace("/redfish/v1", "")
                )
                if firmware_detail is not None:
                    firmware_versions.append(
                        {
                            "Name": firmware_detail.get("Name", ""),
                            "Version": firmware_detail.get("Version", ""),
                            "Updateable": firmware_detail.get("Updateable", ""),
                            "Id": firmware_detail.get("Id", ""),
                        }
                    )

            self.logger.info(f"Firmware versions: {firmware_versions}")
            print(f"Firmware versions: {firmware_versions}")  # Print to console
        else:
            self.logger.error("Error: Failed to retrieve firmware versions.")

        return firmware_versions

    def get_memory(self):
        response = self.get("Systems/System.Embedded.1/Memory")
        total_memory = 0

        if response is not None:
            for memory_module in response.get("Members", []):
                memory_detail = self.get(
                    memory_module.get("@odata.id", "").replace("/redfish/v1", "")
                )
                if memory_detail is not None:
                    total_memory += memory_detail.get("CapacityMiB", 0)

            total_memory_gib = total_memory / 1024  # Convert to GiB
            self.logger.info(f"Total Memory: {total_memory_gib} GB")
            print(f"Total Memory: {total_memory_gib} GB")  # Print to console
        else:
            self.logger.error("Error: Failed to retrieve memory details.")

        return total_memory_gib

    def get_something(self):
        pass

    def set_job(self):
        pass


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
   
