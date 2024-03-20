#!/usr/bin/python3
# MaaS to Ansible Inventory Script
# Import modules needed for this to work
# If this errors use "pip" to install the needed modules (in requirements.txt)
import os
import maas.client
import json
from packaging import version

# Stuff needed to integrate as an Ansible plugin
# from ansible.plugins.inventory import BaseInventoryPlugin, Constructable, Cacheable
# class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
#     NAME = 'AnsibleMaaS'
#
#     def verify_file(self, path):
#         ''' return true/false if this is possibly a valid file for this plugin to consume '''
#         valid = False
#         if super(InventoryModule, self).verify_file(path):
#             if path.endswith(('AnsibleMaaS.yaml', 'AnsibleMaaS.yml')):
#                 valid = True
#         return valid
#
#     def parse(self, inventory, loader, path, cache=True):
#         self.loader = loader
#         self.inventory = inventory
#         self.templar = Templar(loader=loader)


# CONFIGURATION
# Set the below variables to True or False
sort_by_tags = True  # True will create a host group for each tag
group_by_az = True  # True will create a host group for each availability zone
group_by_pool = True  # True will create a host group for each resource pool
include_bare_metal = True  # True will include KVM hosts in the inventory
include_host_details = True  # Include all known attributes from MaaS or limit to hostname

# ansible_user to be used for differing OSs
# none_user when machine is not deployed
none_user = None
ubuntu_user = "ubuntu"  # Default ansible user
centos7_user = "centos"
centos8_user = "cloud-user"
windows_user = "cloud-admin"

# Grab MAAS environment variables from the environment 
api_key = os.getenv('MAAS_API_KEY')
maas_url = os.getenv('MAAS_URL')
# Test if environment variables were present
if api_key is None:
    raise OSError("MAAS_API_KEY environment variable is not set. Please set the MAAS_API_KEY environment variable!")
if maas_url is None:
    raise OSError("MAAS_URL environment variable is not set. Please set the MAAS_URL environment variable!")
# Connect to the MaaS API
client = maas.client.connect(
    maas_url, apikey=api_key)

# Test MaaS version. Tested against 2.9.1 and newer. Earlier releases have functional gaps.
reqver = "2.9.1"  # Minimum required version of MaaS
ver = client.version.get()
ver = str(ver.version)
if version.parse(ver) < version.parse(reqver):
    print("MaaS must be version ", reqver, " or newer")
    print("Current MaaS version is:", ver, "\n")
    quit()


# Define function to pull machine instance info from the API and reformat data
# to be more JSON and Ansible friendly
def getmachines():
    machines = client.machines.list()
    maas_machines = {}
    maas_group = {}
    for machine in machines:
        tags = {}
        ifs = {}
        disks = {}
        maas_group.update({machine.fqdn: "Null"})
        ostype = str(machine.osystem)
        oskernel = str(machine.distro_series)
        htags = list(machine.tags)
        interfaces = list(machine.interfaces)
        block_devices = list(machine.block_devices)

        ansible_user = none_user
        # Determine the ansible_user to assign by OS
        if machine.osystem == "ubuntu":
            ansible_user = ubuntu_user
        if machine.osystem == "centos" and machine.distro_series == "8":
            ansible_user = centos8_user
        if machine.osystem == "centos" and machine.distro_series == "7":
            ansible_user = centos7_user

        # Build a list of tags for each machine instance
        if include_host_details:
            for htag in htags:
                tags.update({htag.name: "null"})
            this_os = ostype + "-" + oskernel
            # Build a dictionary of network interfaces for each machine instance
            for interface in interfaces:
                ifs.update({interface.name: {
                    "type": interface.type.name,
                    "enabled": interface.enabled,
                    "id": interface.id,
                    "mac_address": interface.mac_address,
                    "params": interface.params,
                    "mtu": interface.effective_mtu,
                }
                })
            # Build a dictionary of block devices (disks) for each machine instance
            for block_device in block_devices:
                disks.update({block_device.name: {
                    "type": block_device.type.name,
                    "model": block_device.model,
                    "used_for": block_device.used_for,
                    "size": block_device.size,
                    "used": block_device.used_size,
                    "block_size": block_device.block_size,
                    "id": block_device.id,
                    "id_path": block_device.id_path,
                }
                })
            # Build the root dictionary for each machine instance
            # with nested dictionaries for interfaces and disks/block devices
            host = {
                "ansible_host": machine.fqdn,
                "ansible_user": ansible_user,
                "hostname": machine.hostname,
                "status": machine.status.name,
                "netboot": machine.netboot,
                "archictecture": machine.architecture,
                "os": machine.osystem,
                "distro_series": machine.distro_series,
                "fqdn": machine.fqdn,
                "cpus": machine.cpus,
                "memory": machine.memory,
                "interfaces": ifs,  # This is a dictionary
                "ip_addresses": machine.ip_addresses,  # This is a list
                "system_id": machine.system_id,
                "operating_system": this_os,
                "node_type": machine.node_type,
                "pool": machine.pool.name,
                "zone": machine.zone.name,
                "block_devices": disks,  # This is a dictionary
                "tags": tags
            }
        else:
            host = {
                "ansible_host": machine.fqdn,
                "ansible_user": ansible_user,
                "hostname": machine.hostname
            }
        # Add each machine dictionary into a root dictionary as elements
        if not include_bare_metal:
            if machine.power_type == "virsh" or machine.power_type == "lxd":
                maas_machines.update({host["hostname"]: host})
        else:
            maas_machines.update({host["hostname"]: host})
    maas_data = {"children": maas_machines}
    maas = {"maas": maas_data}
    return maas


#
def gettags():
    maas_tags = []
    maas_tag_groups = {}
    tags = client.tags.list()
    for tag in tags:
        maas_tags.append(tag.name)
    maas_machines = client.machines.list()
    for tag in maas_tags:
        maas_tag_groups.update({tag: []})
        for machine in maas_machines:
            htag = repr(machine.tags)
            status = htag.find(tag)
            if not include_bare_metal:
                if machine.power_type == "virsh" or machine.power_type == "lxd":
                    if status != -1:
                        maas_tag_groups[tag].append(machine.hostname)
            if include_bare_metal:
                if status != -1:
                    maas_tag_groups[tag].append(machine.hostname)
    return maas_tag_groups


#
#
def getzones():
    maas_zones = []
    maas_zone_group = {}
    zones = client.zones.list()
    for zone in zones:
        maas_zones.append(zone.name)
    maas_machines = client.machines.list()
    for zone in maas_zones:
        maas_zone_group.update({zone: []})
        for machine in maas_machines:
            if machine.zone.name == zone:
                if not include_bare_metal:
                    if machine.power_type == "virsh" or machine.power_type == "lxd":
                        maas_zone_group[zone].append(machine.hostname)
                if include_bare_metal:
                    maas_zone_group[zone].append(machine.hostname)
    return maas_zone_group


def getpools():
    maas_pools = []
    maas_pool_group = {}
    pools = client.resource_pools.list()
    for pool in pools:
        maas_pools.append(pool.name)
    maas_machines = client.machines.list()
    for pool in maas_pools:
        maas_pool_group.update({pool: []})
        for machine in maas_machines:
            if machine.pool.name == pool:
                if not include_bare_metal:
                    if machine.power_type == "virsh" or machine.power_type == "lxd":
                        maas_pool_group[pool].append(machine.hostname)
                if include_bare_metal:
                    maas_pool_group[pool].append(machine.hostname)
    return maas_pool_group


def main():
    # Do stuff
    machines = getmachines()
    meta = {
        "_meta": {
            "hostvars": {}
        }}
    if sort_by_tags:
        tags = gettags()
        machines.update(tags)
    if group_by_az:
        zones = getzones()
        machines.update(zones)
    if group_by_pool:
        pools = getpools()
        machines.update(pools)
    machines.update(meta)
    print(json.dumps(machines, indent=4))


if __name__ == '__main__':
    main()
