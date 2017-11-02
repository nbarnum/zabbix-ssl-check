# Zabbix SSL Check

Scripts, Zabbix userparameters, and Zabbix templates for monitoring SSL certificate expiration from [Zabbix](https://www.zabbix.com/).

The included python script uses `openssl` to discover SSL certificates on a host and add Zabbix items to monitor certificate expiry.

Templates were built against Zabbix 3.0.

## Check types

Two Zabbix templates are included in `templates/` for two different approaches:

### `externalscripts`

Zabbix server or Zabbix proxy runs the checks via pollers.

#### Installation

1. Install `scripts/ssl_cert.py` to the `externalscripts` directory

    ```
    $ cp scripts/ssl_cert.py /usr/lib/zabbix/externalscripts/
    ```

    `ExternalScripts` is a configuration option in `zabbix_server.conf` and `zabbix_proxy.conf`, so check there first to see where your directory is. On a default install on Ubuntu via repos.zabbix.com I found my `zabbix_server.conf` was configured to `ExternalScripts=/usr/lib/zabbix/externalscripts`.

2. Import template `templates/template_ssl_cert_externalscripts.xml` in the Zabbix server UI.

    This will create `Template SSL Cert - externalscripts` in the `Templates` group of the Zabbix server.

3. Create a hostname representing the host you want to monitor SSL certs for. For example `github.com`.

    By default the template passes the `{HOST.NAME}` macro into the script. This will be the target of the SSL certificate discovery and monitoring.

### `agent`

Zabbix agent runs the checks.

_NOTE: Zabbix agent can run checks against `localhost` and/or remote hosts_

#### Installation

1. Install `scripts/ssl_cert.py` to the `/etc/zabbix/scripts/` directory on the host where the Zabbix agent is running.

2. Install `zabbix_agentd.d/userparameter_ssl_cert.conf` to the userparameters directory on the host where the Zabbix agent is running.

    Default is `/etc/zabbix/zabbix_agentd.d/`.

3. Restart `zabbix-agent` service to load the new UserParameter.

4. Import template `templates/template_ssl_cert_agent.xml` in the Zabbix server UI.

    This will create `Template SSL Cert - agent` in the `Templates` group of the Zabbix server.

5. Apply the template to monitor SSL certificates.

    The agent will run the script, but by default it will still target the `{HOST.NAME}` macro. If you wanted apply the template many hosts and have them monitor SSL certificates on `localhost`, the `Run SSL certificate checks` item in the template can be updated to look like this:

    ```
    ssl_cert.run_checks[localhost,443,10]
    ```


## Limitations

- In cases where one IP/server serves many hostnames (i.e. using nginx for SSL termination of multiple hostnames), only the default SSL Certificate will be returned. The script `ssl_cert.py` can target by servername if the `Run SSL certificate checks` in the `externalscripts` version is updated:

    ```
    ssl_cert.py["--hostname","{HOST.NAME}","--port","443","--timeout","10","--servername"]
    ```

    This still requires individually adding each host in Zabbix, however.

## Vagrant

A `Vagrantfile` has been included that will create a Zabbix 3.0 server VM and provide an example configuration of these monitoring templates.

1. Install [VirtualBox](https://www.virtualbox.org/wiki/Downloads)

2. Install [Vagrant](https://www.vagrantup.com/)

3. Change directory to `test/` and bring the Vagrant VM up

    ```
    $ cd test/
    $ vagrant up
    ```

4. Browse to http://localhost:8080/zabbix

    ```
    User: Admin
    Pass: zabbix
    ```

    Two hosts will be created: `github.com` (example of externalscripts template) and `google.com` (example of agent template). SSL certificates will be discovered and added as items on these hosts.
