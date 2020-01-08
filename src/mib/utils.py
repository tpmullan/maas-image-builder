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

"""Utilities."""

import os
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from shutil import rmtree


def get_contrib_dir():
    """Return path to the contrib directory."""
    pieces = os.path.abspath(sys.argv[0]).split('.tox', 1)
    if len(pieces) > 1:
        # Running in development, path to contrib is next to .tox.
        return os.path.join(pieces[0], 'contrib')
    return "/usr/lib/maas-image-builder/contrib"


def get_contrib_path(name, path):
    """Return the full path of the file in the contrib directory."""
    return os.path.join(get_contrib_dir(), name, path)


def get_sudo_user():
    """Gets the name of the user, that launched sudo."""
    if 'SUDO_USER' not in os.environ:
        return 'root'
    return os.environ['SUDO_USER']


def subp(args, data=None, rcs=None, env=None, capture=False, shell=False):
    """Executes a subprocess.

    :param args: command arguments
    :param data: data to send to stdin
    :param rcs: allowed exit codes
    :param env: spawning environment
    :param capture: capture output
    :param shell: execute in shell
    :returns: (out, err) when capture=True
    :raises ProcessExecutionError: error executing process
    """
    if rcs is None:
        rcs = [0]
    try:
        if not capture:
            stdout = None
            stderr = None
        else:
            stdout = subprocess.PIPE
            stderr = subprocess.PIPE
        stdin = subprocess.PIPE
        process = subprocess.Popen(
            args, stdout=stdout, stderr=stderr, stdin=stdin,
            env=env, shell=shell)
        (out, err) = process.communicate(data)
        if isinstance(out, bytes):
            out = out.decode()
        if isinstance(err, bytes):
            err = err.decode()
    except OSError as exc:
        raise ProcessExecutionError(cmd=args, reason=exc)
    return_code = process.returncode
    if return_code not in rcs:
        raise ProcessExecutionError(
            stdout=out, stderr=err, exit_code=return_code, cmd=args)
    if not out and capture:
        out = ''
    if not err and capture:
        err = ''
    return (out, err)


class ProcessExecutionError(IOError):
    """Exception for subprocess."""

    MESSAGE_TMPL = ('%(description)s\n'
                    'Command: %(cmd)s\n'
                    'Exit code: %(exit_code)s\n'
                    'Reason: %(reason)s\n'
                    'Stdout: %(stdout)r\n'
                    'Stderr: %(stderr)r')

    def __init__(self, stdout=None, stderr=None,
                 exit_code=None, cmd=None,
                 description=None, reason=None):
        if not cmd:
            self.cmd = '-'
        else:
            self.cmd = cmd

        if not description:
            self.description = 'Unexpected error while running command.'
        else:
            self.description = description

        if not isinstance(exit_code, int):
            self.exit_code = '-'
        else:
            self.exit_code = exit_code

        if not stderr:
            self.stderr = ''
        else:
            self.stderr = stderr

        if not stdout:
            self.stdout = ''
        else:
            self.stdout = stdout

        if reason:
            self.reason = reason
        else:
            self.reason = '-'

        message = self.MESSAGE_TMPL % {
            'description': self.description,
            'cmd': self.cmd,
            'exit_code': self.exit_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'reason': self.reason,
        }
        IOError.__init__(self, message)


@contextmanager
def tempdir(
        suffix=b'', prefix=b'img-builder-',
        location=b'/var/lib/libvirt/images'):
    """Context manager: temporary directory.

    Creates a temporary directory (yielding its path, as `unicode`), and
    cleans it up again when exiting the context.

    The directory will be readable, writable, and searchable only to the
    system user who creates it.
    """
    path = tempfile.mkdtemp(suffix, prefix, location)
    if isinstance(path, bytes):
        path = path.decode(sys.getfilesystemencoding())
    assert isinstance(path, str)
    try:
        yield path
    finally:
        rmtree(path, ignore_errors=True)


def kpartx_add(src):
    """Adds partition mappings for src into kpartx."""
    subp(['kpartx', '-s', '-a', src])


def kpartx_list(src):
    """Lists the partition mappins for src in kpartx."""
    out, _ = subp(['kpartx', '-l', src], capture=True)
    return [
        '/dev/mapper/%s' % line.split()[0]
        for line in out.splitlines()
        ]


def kpartx_del(src):
    """Removes partition mappings for src from kpartx.

    Handles failure and will retry up to 10 seconds.
    """
    for i in range(10):
        try:
            subp(['kpartx', '-d', src])
        except ProcessExecutionError:
            if i == 9:
                raise
            else:
                time.sleep(1)
        else:
            break


def mount_loop(src, target, idx=0):
    """Mounts the source using loopback onto the target."""
    kpartx_add(src)
    devs = kpartx_list(src)
    subp(['mount', '-o', 'loop', devs[idx], target])


def umount_loop(src, target):
    """Un-mounts the source using loopback."""
    subp(['umount', target])
    kpartx_del(src)


def fs_sync():
    """Synchronize cached writes to persistent storage."""
    subp(['sync'])


def create_tarball(output, path):
    """Creates a tarball from path and places into output."""
    subp(['tar', 'zcpf', output, '-C', path, '.'])
