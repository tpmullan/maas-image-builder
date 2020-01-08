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

"""Utilities for networking."""

import os
import random

from mib import utils

TAP_PREFIX = "vmtap"
TAP_SEARCH_PATH = '/sys/class/net'


class NetworkError(Exception):
    """Exception raise when error occurs creating or destroy network."""


def get_avaliable_tap_name():
    """Gets the next available tap name."""
    tapnum = 0
    tappath = os.path.join(
        TAP_SEARCH_PATH, '%s%d' % (TAP_PREFIX, tapnum))
    while os.path.exists(tappath):
        tapnum += 1
        tappath = os.path.join(
            TAP_SEARCH_PATH, '%s%d' % (TAP_PREFIX, tapnum))
    return '%s%d' % (TAP_PREFIX, tapnum)


def get_random_qemu_mac():
    """Returns a random mac address with QEMU prefix."""
    mac = [
        0x52, 0x54, 0x00,
        random.randint(0x00, 0x7f),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
        ]
    return ':'.join(map(lambda x: "%02x" % x, mac))


def create_tap(bridge):
    """Creates the tap device on bridge."""
    tap_name = get_avaliable_tap_name()
    owner = utils.get_sudo_user()

    # Create the tap device
    try:
        utils.subp([
            'ip', 'tuntap',
            'add', 'mode', 'tap',
            'user', owner,
            tap_name,
            ])
    except utils.ProcessExecutionError:
        raise NetworkError(
            'Failed to create tap %s for %s.' % (tap_name, owner))

    # Bring the tap device up
    try:
        utils.subp([
            'ip', 'link',
            'set', tap_name, 'up',
            ])
    except utils.ProcessExecutionError:
        delete_tap(tap_name)
        raise NetworkError('Failed to bring up %s.' % tap_name)

    # Add the tap device to the bridge
    try:
        utils.subp([
            'ip', 'link',
            'set', tap_name,
            'master', bridge,
            ])
    except utils.ProcessExecutionError:
        delete_tap(tap_name)
        raise NetworkError('Failed to add tap %s to %s.' % (tap_name, bridge))
    return tap_name


def delete_tap(tap_name):
    """Deletes the tap device."""
    try:
        utils.subp([
            'ip', 'tuntap',
            'del', 'mode', 'tap',
            tap_name,
            ])
    except utils.ProcessExecutionError:
        raise NetworkError('Failed to delete tap %s.' % tap_name)
