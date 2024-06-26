#!/usr/bin/env python3
# MaaS to Ansible Inventory Script
# Import modules needed for this to work
# If this errors use "pip" to install the needed modules (in requirements.txt)
import getpass
import ipaddress
import json
import os

import maas.client
from dotenv import load_dotenv
from maas.client.enum import PowerState
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
group_by_tags = True  # True will create a host group for each tag
group_by_az = False  # True will create a host group for each availability zone
group_by_pool = False  # True will create a host group for each resource pool
include_bare_metal = True  # True will include KVM hosts in the inventory
include_host_details = True  # True will include all known attributes from MaaS or limit to hostname

include_rack_controllers = False  # True will include rack_controllers in the inventory
exclude_powered_off_machines = True  # True will exclude machines without PowerState.ON

# name of space to get ip of machines for ansible
ansible_management_space_name = 'management'

# ansible_user to be used for differing OSs
# none_user when machine is not deployed
none_user = None
ubuntu_user = "ubuntu"  # Default ansible user
centos7_user = "centos"
centos8_user = "cloud-user"
windows_user = "cloud-admin"

load_dotenv()

# Grab MAAS environment variables from the environment 
api_key = os.getenv('MAAS_API_KEY')
maas_url = os.getenv('MAAS_URL')
# Test if environment variables were present
if api_key is None:
    raise OSError("MAAS_API_KEY environment variable is not set. Please set the MAAS_API_KEY environment variable!")
if maas_url is None:
    raise OSError("MAAS_URL environment variable is not set. Please set the MAAS_URL environment variable!")
# Connect to the MaaS API
client = maas.client.connect(maas_url, apikey=api_key)

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
def get_machines(meta: dict):
    machines = [
        machine for machine in client.machines.list()
        if not exclude_powered_off_machines or (machine.power_state == PowerState.ON and exclude_powered_off_machines)
    ]
    rack_controllers = []
    current_user = None
    # get rack_controllers if we want to include them
    if include_rack_controllers:
        rack_controllers = client.rack_controllers.list()
        # we use the current user for rack controllers as they are probably not deployed by maas
        current_user = getpass.getuser()

    # get management network from specific space
    space = client.spaces.get(ansible_management_space_name)
    subnets = client.subnets.list()
    management_network = None
    for space_vlan in space.vlans:
        for subnet in subnets:
            if space_vlan.id == subnet.vlan.id:
                management_network = ipaddress.ip_network(subnet.cidr)
    maas_machines = {}
    for machine in machines:
        ostype = str(machine.osystem)
        oskernel = str(machine.distro_series)
        htags = list(machine.tags)
        interfaces = list(machine.interfaces)
        block_devices = list(machine.block_devices)
        tags = [tag.name for tag in htags]

        ansible_user = none_user
        # Determine the ansible_user to assign by OS
        if machine.osystem == "ubuntu":
            ansible_user = ubuntu_user
        if machine.osystem == "centos" and machine.distro_series == "8":
            ansible_user = centos8_user
        if machine.osystem == "centos" and machine.distro_series == "7":
            ansible_user = centos7_user

        ansible_ip = [ip for ip in machine.ip_addresses if ipaddress.ip_address(ip) in management_network][0]

        if include_host_details:
            this_os = ostype + "-" + oskernel
            # Build a dictionary of network interfaces for each machine instance
            ifs = [
                {
                    interface.name: {
                        "type": interface.type.name,
                        "enabled": interface.enabled,
                        "id": interface.id,
                        "mac_address": interface.mac_address,
                        "params": interface.params,
                        "mtu": interface.effective_mtu,
                    }
                }
                for interface in interfaces
            ]
            # Build a dictionary of block devices (disks) for each machine instance
            disks = [
                {
                    block_device.name: {
                        "type": block_device.type.name,
                        "model": block_device.model,
                        "used_for": block_device.used_for,
                        "size": block_device.size,
                        "used": block_device.used_size,
                        "block_size": block_device.block_size,
                        "id": block_device.id,
                        "id_path": block_device.id_path,
                    }
                }
                for block_device in block_devices
            ]
            # Build the root dictionary for each machine instance
            # with nested dictionaries for interfaces and disks/block devices
            host = {
                "ansible_host": ansible_ip,
                "ansible_user": ansible_user,
                "hostname": machine.hostname,
                "status": machine.status.name,
                "netboot": machine.netboot,
                "architecture": machine.architecture,
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
                "ansible_host": ansible_ip,
                "ansible_user": ansible_user,
                "hostname": machine.hostname
            }
        # Add each machine dictionary into a root dictionary as elements
        if not include_bare_metal:
            if machine.power_type == "virsh" or machine.power_type == "lxd":
                meta.update({host["hostname"]: host})
                maas_machines.update({host["hostname"]: host})
        else:
            meta.update({host["hostname"]: host})
            maas_machines.update({host["hostname"]: host})

    # do not need to test include_rack_controllers as rack_controllers list is empty
    # if include_rack_controllers=False
    for rack_controller in rack_controllers:
        ostype = str(rack_controller.osystem)
        oskernel = str(rack_controller.distro_series)
        htags = list(rack_controller.tags)
        interfaces = list(rack_controller.interfaces)
        tags = [tag.name for tag in htags]

        ansible_ip = [ip for ip in rack_controller.ip_addresses if ipaddress.ip_address(ip) in management_network][0]

        if include_host_details:
            this_os = ostype + "-" + oskernel
            # Build a dictionary of network interfaces for each rack_controller instance
            ifs = [
                {
                    interface.name: {
                        "type": interface.type.name,
                        "enabled": interface.enabled,
                        "id": interface.id,
                        "mac_address": interface.mac_address,
                        "params": interface.params,
                        "mtu": interface.effective_mtu,
                    }
                }
                for interface in interfaces
            ]
            # Build the root dictionary for each rack_controller instance
            # with nested dictionaries for interfaces
            host = {
                "ansible_host": ansible_ip,
                "ansible_user": current_user,
                "hostname": rack_controller.hostname,
                "architecture": rack_controller.architecture,
                "os": rack_controller.osystem,
                "distro_series": rack_controller.distro_series,
                "fqdn": rack_controller.fqdn,
                "cpus": rack_controller.cpus,
                "memory": rack_controller.memory,
                "interfaces": ifs,  # This is a dictionary
                "ip_addresses": rack_controller.ip_addresses,  # This is a list
                "system_id": rack_controller.system_id,
                "operating_system": this_os,
                "node_type": rack_controller.node_type,
                "zone": rack_controller.zone.name,
                "tags": tags
            }
        else:
            host = {
                "ansible_host": ansible_ip,
                "ansible_user": current_user,
                "hostname": rack_controller.hostname
            }
        meta.update({host["hostname"]: host})
        maas_machines.update({host["hostname"]: host})
    maas_data = {"children": maas_machines}
    maas_inventory = {"maas": maas_data}
    return maas_inventory


#
def get_tags():
    maas_tag_groups = {}
    tags = client.tags.list()
    maas_tags = [tag.name for tag in tags]
    maas_machines = [
        machine for machine in client.machines.list()
        if not exclude_powered_off_machines or (machine.power_state == PowerState.ON and exclude_powered_off_machines)
    ]
    rack_controllers = []
    if include_rack_controllers:
        rack_controllers = client.rack_controllers.list()
    for tag in maas_tags:
        maas_tag_groups.update({tag: []})
        for machine in maas_machines:
            htag = repr(machine.tags)
            status = htag.find(tag)
            if status != -1:
                if not include_bare_metal:
                    if machine.power_type == "virsh" or machine.power_type == "lxd":
                        maas_tag_groups[tag].append(machine.hostname)
                else:
                    maas_tag_groups[tag].append(machine.hostname)
        # do not need to test include_rack_controllers as rack_controllers list is empty
        # if include_rack_controllers=False
        for rack_controller in rack_controllers:
            htag = repr(rack_controller.tags)
            status = htag.find(tag)
            if status != -1:
                maas_tag_groups[tag].append(rack_controller.hostname)
    return maas_tag_groups


def get_zones():
    maas_zone_group = {}
    zones = client.zones.list()
    maas_zones = [zone.name for zone in zones]
    maas_machines = [
        machine for machine in client.machines.list()
        if not exclude_powered_off_machines or (machine.power_state == PowerState.ON and exclude_powered_off_machines)
    ]
    rack_controllers = []
    if include_rack_controllers:
        rack_controllers = client.rack_controllers.list()
    for zone in maas_zones:
        maas_zone_group.update({zone: []})
        for machine in maas_machines:
            if machine.zone.name == zone:
                if not include_bare_metal:
                    if machine.power_type == "virsh" or machine.power_type == "lxd":
                        maas_zone_group[zone].append(machine.hostname)
                else:
                    maas_zone_group[zone].append(machine.hostname)
        # do not need to test include_rack_controllers as rack_controllers list is empty
        # if include_rack_controllers=False
        for rack_controller in rack_controllers:
            if rack_controller.zone.name == zone:
                maas_zone_group[zone].append(rack_controller.hostname)
    return maas_zone_group


def get_pools():
    maas_pool_group = {}
    pools = client.resource_pools.list()
    maas_pools = [pool.name for pool in pools]
    maas_machines = [
        machine for machine in client.machines.list()
        if not exclude_powered_off_machines or (machine.power_state == PowerState.ON and exclude_powered_off_machines)
    ]
    rack_controllers = []
    if include_rack_controllers:
        rack_controllers = client.rack_controllers.list()
    for pool in maas_pools:
        maas_pool_group.update({pool: []})
        for machine in maas_machines:
            if machine.pool.name == pool:
                if not include_bare_metal:
                    if machine.power_type == "virsh" or machine.power_type == "lxd":
                        maas_pool_group[pool].append(machine.hostname)
                else:
                    maas_pool_group[pool].append(machine.hostname)
        # do not need to test include_rack_controllers as rack_controllers list is empty
        for rack_controller in rack_controllers:
            if rack_controller.pool.name == pool:
                maas_pool_group[pool].append(rack_controller.hostname)
    return maas_pool_group


def get_inventory():
    meta = {
        "_meta": {
            "hostvars": {}
        }
    }
    machines = get_machines(meta)
    if group_by_tags:
        tags = get_tags()
        machines.update(tags)
    if group_by_az:
        zones = get_zones()
        machines.update(zones)
    if group_by_pool:
        pools = get_pools()
        machines.update(pools)
    machines.update(meta)
    return machines


def main():
    inventory = get_inventory()
    print(json.dumps(inventory, indent=4))


if __name__ == '__main__':
    main()
