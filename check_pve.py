#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# vim: expandtab ts=4 sw=4:
#
# Nagios Check plugin for Proxmox server using Poxmox's VE API:
# https://pve.proxmox.com/wiki/Proxmox_VE_API
#
# require Python 3.4+, simplejson, requests modules.
# * On RHEL/Centos:
#   yum install python34 python34-simplejson python34-requests
# * On Debian:
#   apt-get install python3-requests python3-simplejson
#
# 2018-10-12 - Eric Belhomme <rico.github@ricozome.net>
#
# licenced under GPL2 terms.

import sys, argparse, re
import json, requests

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)



class IncludeExclude:
    def __init__(self):
        self.isregex = False
        self._linc = None
        self._lexc = None
        self._rinc = None
        self._rexc = None

    def setup(self, isregex, include, exclude):
        self.isregex = isregex
        if include:
            if self.isregex:
                self._rinc = re.compile(include)
                self._linc = None
            else:
                self._linc = include.split(',')
                self._rinc = None
        if exclude:
            if self.isregex:
                self._rexc = re.compile(exclude)
                self._lexc = None
            else:
                self._lexc = exclude.split(',')
                self._rexc = None

    def test(self, name):
        if self.isregex:
            if self._rinc is not None:
                if not self._rinc.match(name):
                    return False
            if self._rexc is not None:
                if self._rexc.match(name):
                    return False
        else:
            if self._linc is not None:
                if name not in self._linc:
                    return False
            if self._lexc is not None:
                if name in self._lexc:
                    return False
        return True


session = requests.Session()
session.verify = False
incexc = IncludeExclude()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', '--hostname', type=str, help='Poxmox VE server hostname or IP address', required=True)
    parser.add_argument('-U', '--username', type=str, help='username', required=True)
    parser.add_argument('-P', '--password', type=str, help='user password', required=True)
    parser.add_argument('-r', '--realm', type=str, help='Authentication Realm', default='pam', choices=['pam'])
    parser.add_argument('-p', '--port', type=int, nargs='?', help='HTTPS API port', default=8006)

    parser.add_argument('-m', '--mode', type=str, help='Check mode', choices=['node','kvm','lxc','storage','test'], required=True)

    parser.add_argument('-u', '--url', type=str, help='URL')

    parser.add_argument('-E', '--exclude', type=str, help='comma-separated or regexp back-list (cf. --isregexp)', required=False)
    parser.add_argument('-I', '--include', type=str, help='comma-separated or regexp white-list (cf. --isregexp)', required=False)
    parser.add_argument('-R', '--isregexp', help='Whether to treat name, blacklist and whitelist as regexp', action='store_true')

    parser.add_argument('-W', '--warning', help='Warning', required=False)
    parser.add_argument('-C', '--critical', help='Critical', required=False)


    args = parser.parse_args()



    if not re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})|([\w\.-]+[a-zA-Z]+)$', args.hostname):
        print('invalid hostname !')
        exit(1)





    res = session.post('https://' + args.hostname + ':' + str(args.port) +
                       '/api2/json/access/ticket',
                       data={'username': args.username + '@' + args.realm,
                             'password': args.password
                            }
                       ).json()['data']
    if res is None:
        print('Unable to log on', res)
        exit(1)
    session.headers.update({'Accept': 'application/json', 'Content-type': 'application/json'})
    session.cookies.update({'PVEAuthCookie': res['ticket'],
                            'CSRFPreventionToken': res['CSRFPreventionToken']})

    incexc.setup(args.isregexp, args.include, args.exclude)

    argsmode = {
        'node': mode_node,
        'kvm': mode_kvm,
        'lxc': mode_lxc,
        'storage': mode_storage,
        'test': mode_test
    }
    mode = argsmode.get(args.mode)
    mode(args)



def mode_node(args):
    r = session.get('https://' + args.hostname + ':' + str(args.port) + '/api2/json/cluster/status')

    if r.status_code == 200:
        j = json.loads(r.content.decode())
        print(j['data'][0]['name'])
    else:
        print('erruer ?')

def mode_kvm(args):
    nodes = _get_nodes(args)
    for node in nodes:
        r = session.get('https://' + args.hostname + ':' + str(args.port) + '/api2/json/nodes/' + node + '/qemu')
        if r.status_code == 200:
            kvm = json.loads(r.content.decode())['data']
            for item in kvm:
                if incexc.test(item.get('name')):
                    print( item['name'], item['status'])


def mode_lxc(args):
    pass
def mode_storage():
    pass

def mode_test(args):
    if not args.url:
        print('url not defined')
        exit(1)
    r = session.get('https://' + args.hostname + ':' + str(args.port) + '/api2/json/' + args.url)
    if r.status_code == 200:
        j = json.loads(r.content.decode())
        print(j)
    else:
        print('erruer ?')

    return







def _get_nodes(args):
    r = session.get('https://' + args.hostname + ':' + str(args.port) + '/api2/json/cluster/status')
    if r.status_code == 200:
        j = json.loads(r.content.decode())
        return [ item.get('name') for item in j['data'] if item.get('type') == 'node' ]
    return None






if __name__ == '__main__':
    main()
