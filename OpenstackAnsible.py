#!/usr/bin/python3
# Script to generate a config for openstack-ansible from MaaS inventory
import datetime

import yaml

import AnsibleMaaS
from AnsibleMaaS import client, get_tags, get_machines

AnsibleMaaS.include_rack_controllers = True


def main():
    machines = get_machines()
    tags = get_tags()
    machines.update(tags)
    subnets = client.subnets.list()
    cidr_networks = {
        'management': None,
        'tunnel': None,
        'storage': None
    }
    for name, cidr in cidr_networks.items():
        space = client.spaces.get(name)
        for space_vlan in space.vlans:
            for subnet in subnets:
                if space_vlan.id == subnet.vlan.id:
                    cidr_networks[name] = subnet.cidr

    discoveries = client.discoveries.list()
    one_week = datetime.timedelta(weeks=1)
    now = datetime.datetime.now()
    last_week = (now - one_week).date()
    used_ips = set([discovery.ip for discovery in discoveries if discovery.last_seen.date() > last_week])
    used_ips_config = list(used_ips)
    groups = {}
    for tag in tags:
        group_name = f"{tag}_hosts"
        groups[group_name] = {}
        for hostname in machines[tag]:
            machine = machines['maas']['children'][hostname]
            ip_address = None
            # TODO: take the IP of management subnet
            if len(machine['ip_addresses']) > 0:
                ip_address = machine['ip_addresses'][0]
            groups[group_name][hostname] = {
                'ip': ip_address,
                'host_vars': {
                    'ansible_user': machine['ansible_user'],
                },
            }

    user_config: dict = {
        'cidr_networks': cidr_networks,
        'global_overrides': {
            'internal_lb_vip_address': '',
            'external_lb_vip_address': '',
            'management_bridge': 'br-mgmt',
            'provider_networks': [],
        },
        'used_ips': used_ips_config,
        **groups
    }
    print(yaml.safe_dump(user_config))


if __name__ == '__main__':
    main()
