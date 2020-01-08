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

"""Builder for RHEL."""

import os
import shutil

from mib import utils
from mib.builders import BuildError, VirtInstallBuilder

ISOLINUX_CFG = (
    "default text\n"
    "timeout 0\n"
    "\n"
    "label text\n"
    "  kernel vmlinuz\n"
    "  append initrd=initrd.img linux text console=ttyS0 inst.repo=cdrom "
    "inst.ks=cdrom:/ks.cfg inst.cmdline inst.headless\n")


class RHELBuilder(VirtInstallBuilder):
    """Builds the RHEL image for amd64. Uses virt-install
    to perform this installation process."""

    name = "rhel"
    arches = ["amd64"]
    os_type = "linux"
    os_variant = "rhel7.0"
    disk_size = 5
    nic_model = "virtio"

    def populate_parser(self, parser):
        """Add parser arguments."""
        parser.add_argument(
            '--rhel-iso', required=True,
            help="Path to RHEL installation ISO.")
        parser.add_argument(
            '--custom-kickstart', default=None,
            help="Path to a custom kickstart file used to customize the image")

    def validate_params(self, params):
        """Validates the command line parameters."""
        self.install_cdrom = params.rhel_iso
        if self.install_cdrom is None:
            raise BuildError(
                "RHEL requires the --rhel-iso option.")
        if not os.path.exists(self.install_cdrom):
            raise BuildError(
                "Invalid RHEL iso. File does not exist.")
        if (params.custom_kickstart is not None and
                not os.path.exists(params.custom_kickstart)):
            raise BuildError(
                "Custom kickstart file '%s' does not exist!" %
                params.custom_kickstart)

    def mount_iso(self, workdir, source):  # pylint: disable=no-self-use
        """Mounts iso in 'iso' directory under workdir."""
        iso_dir = os.path.join(workdir, 'iso')
        os.mkdir(iso_dir)
        utils.subp([
            'mount',
            source,
            iso_dir,
            ])
        return iso_dir

    def umount_iso(self, iso_dir):  # pylint: disable=no-self-use
        """Unmounts iso at path."""
        utils.subp(['umount', iso_dir])

    def copy_iso(self, workdir, iso_dir):  # pylint: disable=no-self-use
        """Copies the contents of the iso_dir, into output dir."""
        output = os.path.join(workdir, 'output')
        shutil.copytree(iso_dir, output)
        return output

    def write_ks(self, output_dir, custom_kickstart=None):
        """Writes the kickstarter config into the output_dir at 'ks.cfg'."""
        base_kickstart_file = self.get_contrib_path('rhel7-amd64.ks')
        output_file = os.path.join(output_dir, 'ks.cfg')
        if custom_kickstart is None:
            shutil.copyfile(base_kickstart_file, output_file)
        else:
            with open(output_file, 'w') as output:
                for ks_file_path in (base_kickstart_file, custom_kickstart):
                    output.write('#\n# From %s\n#\n\n' % ks_file_path)
                    with open(ks_file_path, 'r') as ks_file:
                        for line in ks_file:
                            output.write(line)

    def set_timeout_zero(self, output_dir):  # pylint: disable=no-self-use
        """Sets the isolinux.cfg timeout to zero."""
        isolinux_cfg = os.path.join(output_dir, 'isolinux', 'isolinux.cfg')
        with open(isolinux_cfg, 'w') as stream:
            stream.write(ISOLINUX_CFG + '\n')

    def create_iso(self, workdir, source):  # pylint: disable=no-self-use
        """Creates iso at output, containing files at source."""
        output = os.path.join(workdir, 'output.iso')
        utils.subp([
            'mkisofs',
            '-o', output,
            '-b', 'isolinux/isolinux.bin',
            '-c', 'isolinux/boot.cat',
            '-no-emul-boot',
            '-boot-load-size', '4',
            '-boot-info-table', '-R', '-J', '-v',
            '-T', source
            ])
        utils.subp(['chmod', '777', workdir])
        utils.subp(['chmod', '777', output])
        return output

    def modify_mount(self, mount_path):
        """Install the curtin directory into mount point."""
        path = self.get_contrib_path('curtin')
        if not os.path.exists(path):
            return
        opt_path = os.path.join(mount_path, 'curtin')
        shutil.copytree(path, opt_path)

    def build_image(self, params):
        self.validate_params(params)

        # Create work space
        with utils.tempdir() as workdir:
            # Copy out the contents of the ISO file.
            iso_dir = self.mount_iso(workdir, self.install_cdrom)
            try:
                output_dir = self.copy_iso(workdir, iso_dir)
            finally:
                self.umount_iso(iso_dir)
                shutil.rmtree(iso_dir)

            # Write the kickstarter config.
            self.write_ks(output_dir, params.custom_kickstart)

            # Update isolinux to not have a timeout.
            self.set_timeout_zero(output_dir)

            # Create the final ISO for installation.
            try:
                self.install_cdrom = self.create_iso(workdir, output_dir)
            finally:
                shutil.rmtree(output_dir)

            super(RHELBuilder, self).build_image(params)
