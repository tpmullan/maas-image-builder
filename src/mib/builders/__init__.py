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

"""Built-in builders."""

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty,
    )
import os
import shutil

from mib import (
    utils,
    virt,
    )


class BuildError(Exception):
    """Error class for any build error."""


class Builder:
    """Base class for all builders."""

    __metaclass__ = ABCMeta

    @abstractproperty
    def name(self):
        """Name of the builder."""

    @abstractproperty
    def arches(self):
        """List of support architectures."""

    @abstractmethod
    def build_image(self, params):
        """Builds the image with the given parameters."""

    def populate_parser(self, parser):
        """Add parser options for this builder."""

    def get_contrib_path(self, path):
        """Returns the full path to file in contrib directory for this
        builder."""
        return utils.get_contrib_path(self.name, path)


class VirtInstallBuilder(Builder):
    """Builder that uses virt-install."""

    nic_model = None
    extra_arguments = None
    initrd_inject = None
    install_location = None
    install_cdrom = None

    @abstractproperty
    def os_type(self):
        """OS type for virt-install."""

    @abstractproperty
    def os_variant(self):
        """OS variant for virt-install."""

    @abstractproperty
    def disk_size(self):
        """Size of disk to create for virt-install to use."""

    def full_name(self, params):
        """Return the name of the first part of the generated image."""
        return '%s-%s' % (self.name, params.arch)

    def modify_mount(self, mount_path):
        """Allows modification of the files before the final image
        is generated."""

    def build_image(self, params):
        """Builds the image with virt-install."""
        # Check for valid location
        if self.install_location is None and self.install_cdrom is None:
            raise BuildError(
                "Missing install_location or install_cdrom for virt-install.")

        # Naming
        full_name = self.full_name(params)

        # Create work space
        with utils.tempdir() as workdir:
            # virt-install fails to access the directory
            # unless the following permissions are used
            utils.subp(['chmod', '777', workdir])

            # Create the disk, and set the permissions
            # that will allow virt-install to access it
            disk_path = os.path.join(workdir, 'disk.img')
            virt.create_disk(disk_path, self.disk_size, disk_format='raw')
            utils.subp(['chmod', '777', disk_path])
            disk_str = "path=%s,format=raw" % disk_path

            # Start the installation
            vm_name = 'img-build-%s' % full_name
            network_str = 'bridge=%s' % params.interface
            if self.nic_model is not None:
                network_str = '%s,model=%s' % (
                    network_str, self.nic_model)
            if self.install_location:
                virt.install_location(
                    vm_name,
                    params.ram,
                    params.arch,
                    params.vcpus,
                    self.os_type,
                    self.os_variant,
                    disk_str,
                    network_str,
                    self.install_location,
                    initrd_inject=self.initrd_inject,
                    extra_args=self.extra_arguments)
            else:
                virt.install_cdrom(
                    vm_name,
                    params.ram,
                    params.arch,
                    params.vcpus,
                    self.os_type,
                    self.os_variant,
                    disk_str,
                    network_str,
                    self.install_cdrom)

            # Remove the finished installation from virsh
            virt.undefine(vm_name)

            # Mount the disk image
            mount_path = os.path.join(workdir, "mount")
            os.mkdir(mount_path)
            try:
                utils.mount_loop(disk_path, mount_path)

                # Allow the osystem module to install any needed files
                # into the filesystem
                self.modify_mount(mount_path)

                # Create the tarball
                output_path = os.path.join(workdir, "output.tar.gz")
                utils.create_tarball(output_path, mount_path)
            finally:
                utils.umount_loop(disk_path, mount_path)

            # Place in output
            shutil.move(output_path, params.output)
