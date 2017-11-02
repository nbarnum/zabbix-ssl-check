import glob
import sys
from pyzabbix import ZabbixAPI, ZabbixAPIException

'''
This script imports the Zabbix templates, creates a host group "SSL Certs",
then creates a couple of example hosts to apply the templates. It drops the
interval down to 60 sec (instead of default 3600 sec) so that SSL certs
will be discovered more quickly when bringing up a test env.
'''

# list of hosts to create and which type of checks to use for SSL monitoring
hosts_to_create = [
    {
        "hostname": "github.com",
        "checktype": "externalscripts"
    },
    {
        "hostname": "google.com",
        "checktype": "agent"
    }
]

# Zabbix API configuration import rules
rules = {
    'applications': {
        'createMissing': 'true',
        'updateExisting': 'true'
    },
    'discoveryRules': {
        'createMissing': 'true',
        'updateExisting': 'true'
    },
    'items': {
        'createMissing': 'true',
        'updateExisting': 'true'
    },
    'templates': {
        'createMissing': 'true',
        'updateExisting': 'true'
    },
    'triggers': {
        'createMissing': 'true',
        'updateExisting': 'true'
    },
}

# connect to Zabbix API with default creds
zapi = ZabbixAPI('http://localhost/zabbix')
zapi.login("Admin", "zabbix")

# gather list of all templates
path = '/etc/zabbix/templates/*.xml'
files = glob.glob(path)

# import Zabbix templates
for file in files:
    with open(file, 'r') as f:
        template = f.read()
        try:
            zapi.confimport('xml', template, rules)
        except ZabbixAPIException as e:
            print(e)

# create a new hostgroup "SSL Certs" and store in a format friendly to host.create
hostgroups = [{"groupid": g} for g in zapi.hostgroup.create(name="SSL Certs")['groupids']]

# create example hosts
for host in hosts_to_create:

    # retrieve the templateid for "Template SSL Cert - <checktype>"
    templates = [{"templateid": t['templateid']} for t in zapi.template.get(filter={"host": ["Template SSL Cert - " + host['checktype']]})]

    # query itemid for item that runs script
    itemid = zapi.item.get(templateids=templates[0]['templateid'], search={"key_": "ssl_cert"})[0]['itemid']
    # update the delay (interval) for item on the template to 60s
    # his allows for faster check times over the default 3600 sec in the templates
    zapi.item.update(itemid=itemid, delay=60)

    # create host in "SSL Certs" group with the correct template for the checktype
    zapi.host.create(
        host=host['hostname'],
        interfaces=[{"dns": host['hostname'], "ip": "127.0.0.1", "main": 1, "port": "10050", "type": 1, "useip": 1}],
        groups=hostgroups,
        templates=templates
    )
