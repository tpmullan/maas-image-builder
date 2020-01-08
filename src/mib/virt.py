# vi: ts=4 expandtab
# Upstream Author:
#
#     Canonical Ltd.
#
# Copyright:
#
#     (c) 2014-2017 Canonical Ltd.
#
# Licence:
#
# If you have an executed agreement with a Canonical group company which
# includes a licence to this software, your use of this software is governed
# by that agreement.  Otherwise, the following applies:
#
# Canonical Ltd. hereby grants to you a world-wide, non-exclusive,
# non-transferable, revocable, perpetual (unless revoked) licence, to (i) use
# this software in connection with Canonical's MAAS software to install Windows
# in non-production environments and (ii) to make a reasonable number of copies
# of this software for backup and installation purposes.  You may not: use,
# copy, modify, disassemble, decompile, reverse engineer, or distribute the
# software except as expressly permitted in this licence; permit access to the
# software to any third party other than those acting on your behalf; or use
# this software in connection with a production environment.
#
# CANONICAL LTD. MAKES THIS SOFTWARE AVAILABLE "AS-IS".  CANONICAL  LTD. MAKES
# NO REPRESENTATIONS OR WARRANTIES OF ANY KIND, WHETHER ORAL OR WRITTEN,
# WHETHER EXPRESS, IMPLIED, OR ARISING BY STATUTE, CUSTOM, COURSE OF DEALING
# OR TRADE USAGE, WITH RESPECT TO THIS SOFTWARE.  CANONICAL LTD. SPECIFICALLY
# DISCLAIMS ANY AND ALL IMPLIED WARRANTIES OR CONDITIONS OF TITLE, SATISFACTORY
# QUALITY, MERCHANTABILITY, SATISFACTORINESS, FITNESS FOR A PARTICULAR PURPOSE
# AND NON-INFRINGEMENT.
#
# IN NO EVENT UNLESS REQUIRED BY APPLICABLE LAW OR AGREED TO IN WRITING WILL
# CANONICAL LTD. OR ANY OF ITS AFFILIATES, BE LIABLE TO YOU FOR DAMAGES,
# INCLUDING ANY GENERAL, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES ARISING
# OUT OF THE USE OR INABILITY TO USE THIS SOFTWARE (INCLUDING BUT NOT LIMITED
# TO LOSS OF DATA OR DATA BEING RENDERED INACCURATE OR LOSSES SUSTAINED BY YOU
# OR THIRD PARTIES OR A FAILURE OF THE PROGRAM TO OPERATE WITH ANY OTHER
# PROGRAMS), EVEN IF SUCH HOLDER OR OTHER PARTY HAS BEEN ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGES.

"""Utilities for virt."""

import subprocess

from mib import utils

# QEMU Architecture Mapping
ARCH_MAP = {
    'amd64': 'x86_64'
    }


def create_disk(path, size, disk_format='qcow2'):
    """Creates disk using qemu-img."""
    args = [
        'qemu-img', 'create',
        '-f', disk_format,
        path,
        '%sG' % size,
        ]
    utils.subp(args)


def install_location(name, ram, arch, vcpus, os_type, os_variant,
                     disk, network, location, initrd_inject=None,
                     extra_args=None, reboot=False, graphics=False,
                     force=True):
    """Spawns virt-install."""
    if arch in ARCH_MAP:
        arch = ARCH_MAP[arch]
    args = [
        'virt-install',
        '--name', name,
        '--ram', '%s' % ram,
        '--arch', arch,
        '--vcpus', vcpus,
        '--os-type', os_type,
        '--os-variant', os_variant,
        '--disk', disk,
        '--network', network,
        '--location', location,
        ]
    if initrd_inject is not None:
        args.append('--initrd-inject=%s' % initrd_inject)
    if extra_args is not None:
        args.append("--extra-args=%s" % extra_args)
    if not reboot:
        args.append('--noreboot')
    if not graphics:
        args.append('--nographics')
    if force:
        args.append('--force')
    subprocess.check_call(args)


def install_cdrom(
        name, ram, arch, vcpus, os_type, os_variant,
        disk, network, cdrom, reboot=False, graphics=False,
        force=True):
    """Spawns virt-install."""
    if arch in ARCH_MAP:
        arch = ARCH_MAP[arch]
    args = [
        'virt-install',
        '--name', name,
        '--ram', '%s' % ram,
        '--arch', arch,
        '--vcpus', vcpus,
        '--os-type', os_type,
        '--os-variant', os_variant,
        '--disk', disk,
        '--network', network,
        '--cdrom', cdrom,
        ]
    if not reboot:
        args.append('--noreboot')
    if not graphics:
        args.append('--nographics')
    if force:
        args.append('--force')
    subprocess.check_call(args)


def undefine(name):
    """Undefines the virtual machine from virsh without deleting
    the storage volume.
    """
    utils.subp(['virsh', 'undefine', name])
