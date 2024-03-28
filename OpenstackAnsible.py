#!/usr/bin/python3
# Script to generate a config for openstack-ansible from MaaS inventory
# Import modules needed for this to work
# If this errors use "pip" to install the needed modules (in requirements.txt)
import datetime
import ipaddress

import yaml

import AnsibleMaaS
from AnsibleMaaS import client, get_tags, get_machines

# include rack_controllers as hosts, used as True to deploy openstack-ansible also on these hosts
AnsibleMaaS.include_rack_controllers = True
# not excluding powered off hosts as this script only generates an
# openstack_user_config.yml file which can be used later
AnsibleMaaS.exclude_powered_off_machines = False

# filename to use for generated config
user_config_filename = 'openstack_user_config.yml.generated'

# the management network is used for connecting through SSH to hosts and for connecting to deployed containers
management_network_name = 'management'
# the tunnel network is used for project VXLAN networks
tunnel_network_name = 'tunnel'
# the storage network is used for storage services such as cinder and swift
storage_network_name = 'storage'


def get_cidr_networks_config(cidr_networks, subnets):
    for name, cidr in cidr_networks.items():
        space = client.spaces.get(name)
        for space_vlan in space.vlans:
            for subnet in subnets:
                if space_vlan.id == subnet.vlan.id:
                    cidr_networks[name] = ipaddress.ip_network(subnet.cidr)
    cidr_networks_config = [{name: str(cidr)} for name, cidr in cidr_networks.items()]
    return cidr_networks_config


def get_used_ips_config(discoveries):
    one_week = datetime.timedelta(weeks=1)
    now = datetime.datetime.now()
    last_week = (now - one_week).date()
    used_ips_config = list(set([discovery.ip for discovery in discoveries if discovery.last_seen.date() > last_week]))
    return used_ips_config


def get_global_overrides_config():
    global_overrides_config = {
        'internal_lb_vip_address': None,
        'external_lb_vip_address': None,
        'management_bridge': 'br-mgmt',
        'provider_networks': [
            {
                'network': {
                    'group_binds': [
                        'all_containers',
                        'hosts',
                    ],
                    'type': 'raw',
                    'container_bridge': 'br-mgmt',
                    'container_interface': 'eth1',
                    'container_type': 'veth',
                    'ip_from_q': management_network_name,
                    'is_management_address': True,
                },
            },
            {
                'network': {
                    'group_binds': [
                        'glance_api',
                        'cinder_api',
                        'cinder_volume',
                        'nova_compute',
                        'ceph-mon',
                        'ceph-osd',
                    ],
                    'type': 'raw',
                    'container_bridge': 'br-storage',
                    'container_interface': 'eth2',
                    'container_type': 'veth',
                    'container_mtu': '9000',
                    'ip_from_q': storage_network_name,
                }
            },
            {
                'network': {
                    'group_binds': [
                        'neutron_linuxbridge_agent',
                    ],
                    'type': 'vxlan',
                    'container_bridge': 'br-vxlan',
                    'container_type': 'veth',
                    'container_interface': 'eth10',
                    'ip_from_q': tunnel_network_name,
                    'range': '1:1000',
                    'net_name': 'vxlan',
                }
            },
            {
                'network': {
                    'group_binds': [
                        'neutron_linuxbridge_agent',
                    ],
                    'type': 'vlan',
                    'container_bridge': 'br-vlan',
                    'container_type': 'veth',
                    'container_interface': 'eth11',
                    'range': '101:200,301:400',
                    'net_name': 'vlan',
                }
            },
            {
                'network': {
                    'group_binds': [
                        'neutron_linuxbridge_agent',
                    ],
                    'type': 'flat',
                    'container_bridge': 'br-vlan',
                    'container_type': 'veth',
                    'container_interface': 'eth12',
                    'host_bind_override': 'eth12',
                    'net_name': 'flat',
                }
            }
        ],
    }
    return global_overrides_config


def get_groups_config(cidr_networks, machines, tags):
    groups = {}
    for tag in tags:
        group_name = f"{tag}_hosts"
        groups[group_name] = {}
        for hostname in machines[tag]:
            machine = machines['maas']['children'][hostname]
            management_ip = None
            if len(machine['ip_addresses']) > 0:
                for ip_address in machine['ip_addresses']:
                    ip_address_obj = ipaddress.ip_address(ip_address)
                    management_network = cidr_networks[management_network_name]
                    if management_network is not None and ip_address_obj in management_network:
                        management_ip = ip_address
            groups[group_name][hostname] = {
                'ip': management_ip,
                'host_vars': {
                    'ansible_user': machine['ansible_user'],
                },
            }
    return groups


def main():
    machines = get_machines()
    tags = get_tags()
    machines.update(tags)
    subnets = client.subnets.list()
    discoveries = client.discoveries.list()
    cidr_networks = {
        management_network_name: None,
        tunnel_network_name: None,
        storage_network_name: None,
    }

    cidr_networks_config = get_cidr_networks_config(cidr_networks=cidr_networks, subnets=subnets)
    used_ips_config = get_used_ips_config(discoveries=discoveries)
    global_overrides_config = get_global_overrides_config()
    groups = get_groups_config(cidr_networks=cidr_networks, machines=machines, tags=tags)
    user_config: dict = {
        'cidr_networks': cidr_networks_config,
        'global_overrides': global_overrides_config,
        'used_ips': used_ips_config,
        **groups
    }
    with open(user_config_filename, 'w') as user_config_file:
        yaml.safe_dump(user_config, user_config_file)


if __name__ == '__main__':
    main()
