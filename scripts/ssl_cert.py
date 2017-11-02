#!/usr/bin/env python
import argparse
import datetime
import json
import re
import socket
import subprocess
from threading import Timer


def run_cmd(cmd, timeout_sec):
    '''
    Run shell command with a timeout and return stdout and stderr.
    https://stackoverflow.com/a/10012262
    '''
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    kill_proc = lambda p: p.kill()
    timer = Timer(timeout_sec, kill_proc, [proc])
    stdout = ""
    stderr = ""
    try:
        timer.start()
        stdout, stderr = proc.communicate()
    finally:
        timer.cancel()

    return stdout.decode('utf-8'), stderr


def extract_ssl_field(regex, subject):
    '''
    Extract field from subject of ssl certificate.
    Return empty string if no matches or field is missing from subject.
    '''
    r = re.findall(regex, subject)
    if len(r) > 0:
        return r[0]
    else:
        return ""


parser = argparse.ArgumentParser(description='Retrieve SSL certificate expiry for Zabbix checks')
parser.add_argument(
    'hostname',
    metavar='HOSTNAME',
    help='Retrieve SSL certificates from this hostname'
)
parser.add_argument(
    '--port',
    default='443',
    help='The port to target in openssl (Default: 443)'
)
parser.add_argument(
    '--dryrun',
    action='store_true',
    help='Dryrun does not attempt to send metrics to Zabbix (Default: false)'
)
parser.add_argument(
    '--timeout',
    type=int,
    default=15,
    help='Time in seconds before sending a timeout to openssl (Default: 15)'
)
parser.add_argument(
    '--zabbix-config',
    default='/etc/zabbix/zabbix_agentd.conf',
    help='Path to the Zabbix agent configuration file. Passed to the zabbix_sender command. (Default: /etc/zabbix/zabbix_agentd.conf)'
)
parser.add_argument(
    '--zabbix-sender',
    default='zabbix_sender',
    help='Path to the zabbix_sender binary. (Default: zabbix_sender)'
)
parser.add_argument(
    '--servername',
    action='store_true',
    help='Whether to target the servername in the openssl command or not. Useful for cases such as nginx where multiple multiple hostnames are served by 1 IP address and must be individually targeted. (Default: false)'
)
args = parser.parse_args()

# Retrive SSL certificates from hostname
openssl_cmd = 'echo | openssl s_client -connect {0}:{1} -showcerts'.format(args.hostname, args.port)
# if servername targeting is enabled, add to cmd
if args.servername:
    openssl_cmd += ' -servername {0}'.format(args.hostname)

stdout, stderr = run_cmd(openssl_cmd, args.timeout)

# Find all x509 certificates and extract them
x509_certs = re.findall('(-----BEGIN CERTIFICATE-----\n.*?-----END CERTIFICATE-----\n)', stdout, re.DOTALL)

zabbix_discovery = {"data": []}
metrics = []

# iterate over discovered certificates
for cert in x509_certs:
    # run the cert through openssl to get subject
    stdout, stderr = run_cmd('echo "{0}" | openssl x509 -noout -subject -dates'.format(cert), 10)

    # extract fields from subject
    country = extract_ssl_field('/C=(.*?)/', stdout)
    common_name = extract_ssl_field('/CN=(.*?)\n', stdout)
    locality = extract_ssl_field('/L=(.*?)/', stdout)
    organization = extract_ssl_field('/O=(.*?)/', stdout)
    department = extract_ssl_field('/OU=(.*?)/', stdout)
    state = extract_ssl_field('/ST=(.*?)/', stdout)

    # date_before = extract_ssl_field('\nnotBefore=(.*?)\n', stdout)
    date_after = extract_ssl_field('\nnotAfter=(.*?)\n', stdout)

    # format of the date in cert subject
    strptime_string = "%b %d %H:%M:%S %Y %Z"

    # convert notAfter timestamp to datetime
    datetime_after = datetime.datetime.strptime(date_after, strptime_string)

    # calculate number of days till expiry: notAfter - today
    days_to_expiry = (datetime_after - datetime.datetime.now()).days

    if common_name != "":
        # append this cert to zabbix discovery
        zabbix_discovery["data"].append({
            "{#SSL_C}": country,
            "{#SSL_CN}": common_name,
            "{#SSL_L}": locality,
            "{#SSL_O}": organization,
            "{#SSL_OU}": department,
            "{#SSL_ST}": state
        })

        metrics.append(['ssl_cert.days_remaining["{0}"]'.format(common_name), days_to_expiry])
        metrics.append(['ssl_cert.notafter["{0}"]'.format(common_name), datetime_after.strftime("%s")])

metrics.append(['ssl_cert.discovery', json.dumps(zabbix_discovery).replace('"', '\\"')])

# print metrics if it's a dryrun, otherwise send metrics into zabbix
for metric in metrics:
    cmd = '{0} -c {1} -s {2} -k "{3}" -o "{4}"'.format(args.zabbix_sender, args.zabbix_config, args.hostname, metric[0].replace('"', '\\"'), metric[1])

    print(cmd)

    if not args.dryrun:
        stdout, stderr = run_cmd(cmd, 1)
        print(stdout)
