# MaaSOpenstackAnsible

This repo is composed of 2 python scripts :

- AnsibleMaaS.py originated (but modified) from the original/forked repo : https://github.com/billyFelton/AnsibleMaaS
- OpenstackAnsible.py originated from this repo

## AnsibleMaaS.py

Ansible dynamic inventory script written in python to pull inventory from Canonical MaaS.  
Originally part of a larger integration effort with MaaS the inventory component was spun off on its own.  
This inventory script uses libmaas.

Existing integrations with MaaS only provided a list of hosts and required complicated playbooks to implement any
form of automation. The plugins were slow sometimes taking more than 5 minutes to pull a handful of host instances.

We needed to be able to sort inventory based off MaaS specific attributes and associations. Resource pools, availability
zones and simple tagging being the most relevant.

We also needed to be able to sever dependencies on ansible plugins / libraries.

Simple inventory that creates instance json records with MaaS attributes

**Inventory Output Example:**

```
{
    "ansible_host": "vault.halo.lan",
    "ansible_user": "ubuntu",
    "archictecture": "amd64/generic",
    "block_devices": {
        "sda": {
            "block_size": 512,
            "id": 64,
            "id_path": "/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_lxd_root",
            "model": "QEMU HARDDISK",
            "size": 10000007168,
            "type": "PHYSICAL",
            "used": 9996075008,
            "used_for": "GPT partitioned with 2 partitions"
        }
    },
    "cpus": 4,
    "distro_series": "focal",
    "fqdn": "vault.halo.lan",
    "hostname": "vault",
    "interfaces": {
        "br-enp2s0": {
            "enabled": true,
            "id": 104,
            "mac_address": "ec:d6:8a:17:1d:74",
            "mtu": 1500,
            "params": {
                "bridge_fd": 15,
                "bridge_stp": false,
                "bridge_type": "standard"
            },
            "type": "BRIDGE"
        },
        "enp2s0": {
            "enabled": true,
            "id": 103,
            "mac_address": "ec:d6:8a:17:1d:74",
            "mtu": 1500,
            "params": "",
            "type": "PHYSICAL"
        },
        "eth0": {
            "enabled": true,
            "id": 484,
            "mac_address": "00:16:3e:4d:87:21",
            "mtu": 1500,
            "params": "",
            "type": "PHYSICAL"
        },
        "lxdbr0": {
            "enabled": true,
            "id": 105,
            "mac_address": "00:16:3e:a6:a1:4b",
            "mtu": 1500,
            "params": "",
            "type": "BRIDGE"
        },
        "tap66c2cb36": {
            "enabled": true,
            "id": 419,
            "mac_address": "56:14:72:cc:17:ad",
            "mtu": 1500,
            "params": "",
            "type": "PHYSICAL"
        },
        "tapc44828f4": {
            "enabled": true,
            "id": 120,
            "mac_address": "06:6d:bb:45:f2:4c",
            "mtu": 1500,
            "params": "",
            "type": "PHYSICAL"
        },
        "tapd2cdd085": {
            "enabled": true,
            "id": 485,
            "mac_address": "ea:44:c1:4d:6d:54",
            "mtu": 1500,
            "params": "",
            "type": "PHYSICAL"
        },
        "wlp1s0": {
            "enabled": true,
            "id": 106,
            "mac_address": "08:ed:b9:c2:93:2b",
            "mtu": 1500,
            "params": "",
            "type": "PHYSICAL"
        }
    },
    "ip_addresses": [
        "10.1.1.31"
    ],
    "memory": 4096,
    "netboot": false,
    "node_type": 0,
    "operating_system": "ubuntu-focal",
    "os": "ubuntu",
    "pool": "virtual",
    "status": "DEPLOYED",
    "system_id": "gfx7qd",
    "tags": {
        "pod-console-logging": "null",
        "tag_AppType_vault": "null",
        "virtual": "null"
    },
    "zone": "halo"
}
```

## OpenstackAnsible.py

This script try to generate an openstack_user_config.yml file with what it can read from Canonical MaaS.

```yaml
ceph-mds_hosts: { }
ceph-mon_hosts: { }
ceph-nfs_hosts: { }
ceph-osd_hosts: { }
cidr_networks:
  management: 172.20.90.0/24
  storage: null
  tunnel: null
compute-infra_hosts:
  compute1:
    host_vars:
      ansible_user: null
    ip: null
compute_hosts:
  compute1:
    host_vars:
      ansible_user: null
    ip: null
dashboard_hosts: { }
global_overrides:
  external_lb_vip_address: ''
  internal_lb_vip_address: ''
  management_bridge: br-mgmt
  provider_networks: [ ]
haproxy_hosts: { }
identity_hosts: { }
image_hosts: { }
manila-data_hosts: { }
manila-infra_hosts: { }
metering-alarm_hosts: { }
metering-compute_hosts: { }
metering-infra_hosts: { }
metric_hosts: { }
network_hosts:
  mesocloud:
    host_vars:
      ansible_user: null
    ip: 172.20.90.10
orchestration_hosts:
  mesocloud:
    host_vars:
      ansible_user: null
    ip: 172.20.90.10
repo-infra_hosts: { }
shared-infra_hosts: { }
storage-infra_hosts: { }
storage_hosts: { }
used_ips:
  - 172.20.91.10
  - 172.20.90.10
  - 172.20.90.1
  - 172.20.90.254
```

## Prerequisites:

### Common

1. A deployed instance of Canonical's MaaS v2.7 or better.
2. Ansible v2.9 or newer installed and configured on a server/vm that has network access to the MaaS APIs.
3. Python3 installed on the Ansible server(Control/Tower)/vm.
4. Network access to the MaaS API URL and an API Key.

### OpenstackAnsible.py specific

1. All tags used by openstack-ansible need to be added (manually at the moment) in MaaS instance
2. Every network needed for openstack-ansible must be in 1 `space` for 1 network in openstack_user_config.yml
3. Every machine/host you want included in openstack_user_config.yml file must be tagged
4.

## Dependencies:

Python libs:

- ansible
- python-libmaas
- yaml # for OpenstackAnsible
- json
- packaging
- os

## To Install:

1. Clone this git repo.
2. Install the dependencies.
   ```shell
   cd MaaSOpenstackAnsible
   sudo pip install -r requirements.txt
   ```
3. Copy the AnsibleMaaS.py file to the directory where you manage your ansible dynamic inventory.  
   Normally: `/etc/ansible/inventory`  
   Read this if you need help: https://docs.ansible.com/ansible/latest/user_guide/intro_dynamic_inventory.html
4. Set environment variables!!
   ```shell
   export MAAS_API_KEY=APIKEY-TO-ACCESS-MAAS-API # API KEY obtained from your MaaS's user preferences
   export MAAS_URL=http://(IP or FQDN):5240/MAAS/api/2.0 # FQDN and URL of your MaaS Region API.
   ```

## Edit AnsibleMaaS.py to set options:

sort_by_tags = True # True will create a host group for each tag  
group_by_az = True # True will create a host group for each availability zone  
group_by_pool = True # True will create a host group for each resource pool  
include_bare_metal = True # True will include KVM hosts in the inventory  
include_host_details = True # Will include all known facts from MaaS into the inventory  
include_rack_controllers = True # Will include rack controllers hosts in the inventory

### ansible_user to be used for differing OSs:

ubuntu_user = "ubuntu"        
centos7_user = "centos"  
centos8_user = "cloud-user"  
windows_user = "cloud-admin"

Once everything is set up simply execute an ansible module against the inventory.

```shell
ansible -m ping all
```

and / or

```shell
ansible-inventory --list
```

## Connectivity and access issues.

MaaS deploys private keys on bare metal and vm instances. Whichever user is running ansible must have public keys
associated with ssh on each instance ansible will need to access.
If you are unfamiliar with ansible, ansible-inventory or ssh, take the time to read the docs.  
Having a strategy on inventory and ssh is a good idea. Rotating keys, using secrets management are generally a good
idea.

- Getting started with Ansible - https://docs.ansible.com/ansible/latest/getting_started/index.html
- Ansible Connection Methods - https://docs.ansible.com/ansible/latest/user_guide/connection_details.html
- Halo - https://www.halo.inc/ansible-integration-with-maas/
- OpenstackAnsible - https://docs.openstack.org/openstack-ansible/latest/