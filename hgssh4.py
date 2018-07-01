#!/usr/bin/env python3

"""
hgssh4.py - a wrapper for ssh access to mercurial repositories

This script is based on hg-ssh, hgssh2, and hgssh3.

Copyright 2018 ikdc@mit.edu

This software may be used and distributed according to the terms of the
GNU General Public License version 2 or any later version.

Usage:

Similarly to hgssh3, prefix

    command="hgssh4 username /path/to/acl_file"

to ssh keys in the authorized_keys file.

hgssh4 improves on hgssh3 by using file permissions to enforce
read-only access to repositories instead of using hooks.  To do this,
we require there exists a user with read-only access to the
repositories whom we can impersonate using sudo to run commands.  For
instance, if the user running hgssh4 is "hg" and the user without
permissions is "hgread", then the following line in the sudoers file
will have the effect of allowing hg to run any command as hgread.

    hg ALL=(hgread) NOPASSWD:ALL

Then for read-only access, instead of running

    hg -R <repo> serve --stdio

We run

    sudo --user=hgread -- hg -R <repo> serve --stdio

ACL file format is similar to hgssh3, except for the "readonly/sudo"
option for setting the name of the user to use for read-only
impersonation; and sections for repositories are prefixed by "repos.".

Example ACL:

[readonly]
sudo = hgread

# This repository would be accessible as ssh://hg@my.server/myrepo1
[repos.myrepo1]
location = relative/path/to/repo
user1 = write # Read/Write access
user2 = read  # Read-only access

[repos.myrepo2]
location = /absolute/path/to/repo
user1 = read
user4 = read
user3 = write
"""

import argparse
import configparser
import os
import shlex
import subprocess
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('user')
    parser.add_argument('conf')
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(args.conf)

    # Get the original SSH Command sent through. The repo should be the
    # item after the connect string
    orig_cmd = os.getenv('SSH_ORIGINAL_COMMAND', '?')

    cmdargv = shlex.split(orig_cmd)

    if not (cmdargv[:2] == ['hg', '-R'] and
            cmdargv[3:] == ['serve', '--stdio']):
        raise ValueError('Illegal command {}'.format(cmdargv))

    repo_name = cmdargv[2].replace(os.sep, '', 1)
    try:
        repo_conf = config['repos.{}'.format(repo_name)]
    except KeyError as e:
        raise ValueError('No such repository') from e
    try:
        repo_path = repo_conf['location']
    except KeyError as e:
        raise ValueError('Bad config: no location for repository') from e
    repo_path = os.path.abspath(os.path.expanduser(repo_path))

    try:
        access = repo_conf[args.user]
    except KeyError as e:
        raise ValueError('Access denied') from e

    if access not in ['read', 'write']:
        raise ValueError('Access denied')

    cmd = ['hg', '-R', repo_path, 'serve', '--stdio']
    if access == 'read':
        try:
            sudo_user = config['readonly']['sudo']
        except KeyError as e:
            raise ValueError('Bad config: no readonly sudo user') from e
        cmd = ['sudo', '--user={}'.format(sudo_user), '--'] + cmd

    subprocess.run(cmd,
                   stdin=sys.stdin,
                   stdout=sys.stdout,
                   stderr=sys.stderr)

if __name__ == '__main__':
    try:
        main()
    except BaseException as e:
        print(e, file=sys.stderr)
        sys.exit(1)
