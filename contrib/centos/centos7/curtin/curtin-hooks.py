#!/usr/bin/env python

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

import os
import re
import sys
import shutil

sys.path.append('/curtin')
from curtin import (
    block,
    net,
    util,
    )

"""
CentOS/RHEL 7

Currently Support:

- Legacy boot
- UEFI boot
- DHCP of BOOTIF

Not Supported:

- Multiple network configration
- IPv6
"""

FSTAB_PREPEND = """\
#
# /etc/fstab
# Created by MAAS fast-path installer.
#
# Accessible filesystems, by reference, are maintained under '/dev/disk'
# See man pages fstab(5), findfs(8), mount(8) and/or blkid(8) for more info
#
"""

FSTAB_UEFI = """\
LABEL=uefi-boot /boot/efi vfat defaults 0 0
"""

GRUB_PREPEND = """\
# Set by MAAS fast-path installer.
GRUB_TIMEOUT=0
GRUB_TERMINAL_OUTPUT=console
GRUB_DISABLE_OS_PROBER=true
"""


def get_block_devices(target):
    """Returns list of block devices for the given target."""
    devs = block.get_devices_for_mp(target)
    blockdevs = set()
    for maybepart in devs:
        (blockdev, part) = block.get_blockdev_for_partition(maybepart)
        blockdevs.add(blockdev)
    return list(blockdevs)


def get_root_info(target):
    """Returns the root partitions information."""
    rootpath = block.get_devices_for_mp(target)[0]
    rootdev = os.path.basename(rootpath)
    blocks = block._lsblock()
    return blocks[rootdev]


def read_file(path):
    """Returns content of a file."""
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def write_fstab(target, curtin_fstab):
    """Writes the new fstab, using the fstab provided
    from curtin."""
    fstab_path = os.path.join(target, 'etc', 'fstab')
    fstab_data = read_file(curtin_fstab)
    with open(fstab_path, 'w') as stream:
        stream.write(FSTAB_PREPEND)
        stream.write(fstab_data)
        if util.is_uefi_bootable():
            stream.write(FSTAB_UEFI)


def strip_kernel_params(params, strip_params=[]):
    """Removes un-needed kernel parameters."""
    new_params = []
    for param in params:
        remove = False
        for strip in strip_params:
             if param.startswith(strip):
                 remove = True
                 break
        if remove is False:
            new_params.append(param)
    return new_params


def get_extra_kernel_parameters():
    """Extracts the extra kernel commands from /proc/cmdline
    that should be placed onto the host.

    Any command following the '--' entry should be placed
    onto the host.
    """
    cmdline = read_file('/proc/cmdline')
    cmdline = cmdline.split()
    if '--' not in cmdline:
        return []
    idx = cmdline.index('--') + 1
    if idx >= len(cmdline) + 1:
        return []
    return strip_kernel_params(
        cmdline[idx:],
        strip_params=['initrd=', 'BOOT_IMAGE=', 'BOOTIF='])


def update_grub_default(target, extra=[]):
    """Updates /etc/default/grub with the correct options."""
    grub_default_path = os.path.join(target, 'etc', 'default', 'grub')
    kernel_cmdline = ' '.join(extra)
    with open(grub_default_path, 'a') as stream:
        stream.write(GRUB_PREPEND)
        stream.write('GRUB_CMDLINE_LINUX=\"%s\"\n' % kernel_cmdline)


def grub2_install(target, root):
    """Installs grub2 to the root."""
    with util.RunInChroot(target) as in_chroot:
        in_chroot(['grub2-install', '--recheck', root])


def grub2_mkconfig(target):
    """Writes the new grub2 config."""
    with util.RunInChroot(target) as in_chroot:
        in_chroot(['grub2-mkconfig', '-o', '/boot/grub2/grub.cfg'])


def get_efibootmgr_value(output, key):
    """Parses the `output` from 'efibootmgr' to return value for `key`."""
    for line in output.splitlines():
        split = line.split(':')
        if len(split) == 2:
            curr_key = split[0].strip()
            value = split[1].strip()
            if curr_key == key:
                return value


def get_file_efi_loaders(output):
    """Parses the `output` from 'efibootmgr' to return all loaders that exist
    in '\EFI' path."""
    return re.findall(
        r"^Boot(?P<hex>[0-9a-fA-F]{4})\*?\s*\S+\s+.*File\(\\EFI.*$",
        output, re.MULTILINE)


def grub2_install_efi(target):
    """Configure for EFI.

    First capture the currently booted loader (normally a network device),
    then perform grub installation (adds a new bootloader and adjusts the
    boot order), finally re-adjust the boot order so that the currently booted
    loader is set to boot first in the new order.
    """
    with util.RunInChroot(target) as in_chroot:
        stdout, _ = in_chroot(['efibootmgr', '-v'], capture=True)
        currently_booted = get_efibootmgr_value(stdout, 'BootCurrent')
        loaders = get_file_efi_loaders(stdout)
        if currently_booted in loaders:
            loaders.remove(currently_booted)
        for loader in loaders:
            in_chroot(['efibootmgr', '-B', '-b', loader], capture=True)
        in_chroot([
            'grub2-install', '--target=x86_64-efi',
            '--efi-directory', '/boot/efi',
            '--recheck'])
        stdout, _ = in_chroot(['efibootmgr'], capture=True)
        currently_booted = get_efibootmgr_value(stdout, 'BootCurrent')
        boot_order = get_efibootmgr_value(stdout, 'BootOrder').split(',')
        if currently_booted in boot_order:
            boot_order.remove(currently_booted)
        boot_order = [currently_booted] + boot_order
        new_boot_order = ','.join(boot_order)
        in_chroot(['efibootmgr', '-o', new_boot_order])


def set_autorelabel(target):
    """Creates file /.autorelabel.

    This is used by SELinux to relabel all of the
    files on the filesystem to have the correct
    security context. Without this SSH login will
    fail.
    """
    path = os.path.join(target, '.autorelabel')
    open(path, 'a').close()


def get_boot_mac():
    """Return the mac address of the booting interface."""
    cmdline = read_file('/proc/cmdline')
    cmdline = cmdline.split()
    try:
        bootif = [
            option
            for option in cmdline
            if option.startswith('BOOTIF')
            ][0]
    except IndexError:
        return None
    _, mac = bootif.split('=')
    mac = mac.split('-')[1:]
    return ':'.join(mac)


def get_interface_names():
    """Return a dictionary mapping mac addresses to interface names."""
    sys_path = "/sys/class/net"
    ifaces = {}
    for iname in os.listdir(sys_path):
        mac = read_file(os.path.join(sys_path, iname, "address"))
        mac = mac.strip().lower()
        ifaces[mac] = iname
    return ifaces


def get_ipv4_config(iface, data):
    """Returns the contents of the interface file for ipv4."""
    config = [
        'TYPE="Ethernet"',
        'NM_CONTROLLED="no"',
        'USERCTL="yes"',
        ]
    if 'hwaddress' in data:
        config.append('HWADDR="%s"' % data['hwaddress'])
    # Fallback to using device name
    else:
        config.append('DEVICE="%"' % iface)
    if data['auto']:
        config.append('ONBOOT="yes"')
    else:
        config.append('ONBOOT="no"')

    method = data['method']
    if method == 'dhcp':
        config.append('BOOTPROTO="dhcp"')
        config.append('PEERDNS="yes"')
        config.append('PERSISTENT_DHCLIENT="1"')
        if 'hostname' in data:
            config.append('DHCP_HOSTNAME="%s"' % data['hostname'])
    elif method == 'static':
        config.append('BOOTPROTO="none"')
        config.append('IPADDR="%s"' % data['address'])
        config.append('NETMASK="%s"' % data['netmask'])
        if 'broadcast' in data:
            config.append('BROADCAST="%s"' % data['broadcast'])
        if 'gateway' in data:
            config.append('GATEWAY="%s"' % data['gateway'])
    elif method == 'manual':
        config.append('BOOTPROTO="none"')
    return '\n'.join(config)


def write_interface_config(target, iface, data):
    """Writes config for interface."""
    family = data['family']
    if family != "inet":
        # Only supporting ipv4 currently
        print(
            "WARN: unsupported family %s, "
            "failed to configure interface: %s" (family, iface))
        return
    config = get_ipv4_config(iface, data)
    path = os.path.join(
        target, 'etc', 'sysconfig', 'network-scripts', 'ifcfg-%s' % iface)
    with open(path, 'w') as stream:
        stream.write(config + '\n')


def write_network_config(target, mac):
    """Write network configuration for the given MAC address."""
    inames = get_interface_names()
    iname = inames[mac.lower()]
    write_interface_config(
        target, iname, {
            'family': 'inet',
            'hwaddress': mac.upper(),
            'auto': True,
            'method': 'dhcp'
        })


def main():
    state = util.load_command_environment()
    target = state['target']
    if target is None:
        print("Target was not provided in the environment.")
        sys.exit(1)
    fstab = state['fstab']
    if fstab is None:
        print("/etc/fstab output was not provided in the environment.")
        sys.exit(1)
    bootmac = get_boot_mac()
    if bootmac is None:
        print("Unable to determine boot interface.")
        sys.exit(1)
    devices = get_block_devices(target)
    if not devices:
        print("Unable to find block device for: %s" % target)
        sys.exit(1)

    write_fstab(target, fstab)

    update_grub_default(
        target, extra=get_extra_kernel_parameters())
    grub2_mkconfig(target)
    if util.is_uefi_bootable():
        grub2_install_efi(target)
    else:
        for dev in devices:
            grub2_install(target, dev)

    set_autorelabel(target)
    write_network_config(target, bootmac)


if __name__ == "__main__":
    main()
