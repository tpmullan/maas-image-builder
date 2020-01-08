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

"""Builder for Windows."""

import os
import re
import shutil
import tempfile

from tempita import Template

from mib import net, utils
from mib.builders import Builder, BuildError

EDITIONS = {
    'win2008r2': "Windows Server 2008 R2 SERVERSTANDARD",
    'win2008hvr2': "Windows Server 2008 R2 SERVERHYPERCORE",
    'win2012': "Windows Server 2012 SERVERSTANDARD",
    'win2012hv': "Hyper-V Server 2012 SERVERHYPERCORE",
    'win2012r2': "Windows Server 2012 R2 SERVERSTANDARD",
    'win2012hvr2': "Hyper-V Server 2012 R2 SERVERHYPERCORE",
    'win2016': "Windows Server 2016 SERVERSTANDARD",
    'win2016hv': "Hyper-V Server 2016 SERVERHYPERCORE",
    }


class WindowsOSBuilder(Builder):
    """Builds the Windows image using kvm-spice."""

    name = "windows"
    arches = ["i386", "amd64"]

    def populate_parser(self, parser):
        """Add parser options."""
        parser.add_argument(
            '--windows-iso',
            help="Path to Windows installation ISO.")
        parser.add_argument(
            '--windows-edition',
            help="Windows edition to install from the ISO.")
        parser.add_argument(
            '--windows-license-key',
            help="Windows license key to embed into generated image.")
        parser.add_argument(
            '--windows-updates', action='store_true',
            help=(
                "Install all Windows updates into generated image. "
                "(Requires access to microsoft.com)"))
        parser.add_argument(
            '--windows-drivers',
            help=(
                "Folder containing drivers to be injected into the Windows "
                "installation before the image is generated."))
        parser.add_argument(
            '--windows-language',
            default='en-US',
            help="Windows installation language. Default: en-US")
        parser.add_argument(
            '--cloudbase-init',
            help=(
                "Path to the cloudbase-init installer to use. By default it "
                "will be pulled from cloudbase.it"))

    def validate_params(self, params):
        """Validates the command line parameters."""
        iso = params.windows_iso
        if iso is None:
            raise BuildError(
                "Windows requires the --windows-iso option.")
        if not os.path.exists(iso):
            raise BuildError(
                "Failed to access Windows ISO at: %s" % iso)
        edition = params.windows_edition
        if edition is None or edition == '':
            raise BuildError(
                "Windows requires the --windows-edition option.")
        if edition not in EDITIONS.keys():
            raise BuildError(
                "Invalid Windows edition, should be one of %s." % (
                    EDITIONS.keys()))
        license_key = params.windows_license_key
        if license_key is not None and license_key != '':
            if not self.validate_license_key(license_key):
                raise BuildError(
                    "Invalid Windows license key.")
        drivers = params.windows_drivers
        if drivers is not None and not os.path.isdir(drivers):
            raise BuildError(
                "Invalid driver path: %s" % drivers)

    def validate_license_key(self, license_key):  # pylint: disable=no-self-use
        """Validates that license key is in the correct format. It does not
        validate, if that license key will work with the selected edition of
        Windows."""
        regex = re.compile('^([A-Za-z0-9]{5}-){4}[A-Za-z0-9]{5}$')
        return regex.match(license_key)

    def load_unattended_template(self):
        """Loads the unattended template that is used for installation."""
        path = self.get_contrib_path('Autounattend.xml')
        with open(path, "rb") as stream:
            return Template(stream.read().decode('utf-8'))

    def write_unattended(self, output_path, arch, edition, language,
                         license_key=None, enable_updates=False):
        """Outputs the effective unattended.xml file that will be used by
        Windows during the installation."""
        template = self.load_unattended_template()
        image_name = EDITIONS[edition]
        # Windows doesn't accept i386, instead that maps to x86.
        if arch == 'i386':
            arch = 'x86'
        output = template.substitute(
            arch=arch, image_name=image_name, language=language,
            license_key=license_key, enable_updates=enable_updates)
        with open(output_path, 'w') as stream:
            for line in output.splitlines():
                stream.write("%s\r\n" % line)

    def create_floppy_disk(self, output_path):  # pylint: disable=no-self-use
        """Creates an empty floppy disk, formatted with vfat."""
        utils.subp([
            'dd', 'if=/dev/zero',
            'of=%s' % output_path,
            'bs=1024', 'count=1440',
            ])
        utils.subp([
            'mkfs.vfat',
            output_path
            ])

    def prepare_floppy_disk(self, workdir, arch, edition, language,
                            license_key=None, enable_updates=False):
        """Prepares the working directory with Autounattend.vfd."""
        # Create the disk
        vfd_path = os.path.join(workdir, 'Autounattend.vfd')
        self.create_floppy_disk(vfd_path)

        # Mount the disk
        mount_path = os.path.join(workdir, 'vfd_mount')
        os.mkdir(mount_path)
        utils.subp([
            'mount',
            '-t', 'vfat',
            '-o', 'loop',
            vfd_path, mount_path,
            ])

        # Place the generated Autounattend.xml file
        xml_path = os.path.join(mount_path, 'Autounattend.xml')
        try:
            self.write_unattended(
                xml_path, arch, edition, language,
                license_key=license_key, enable_updates=enable_updates)
        finally:
            utils.subp(['umount', mount_path])
            os.rmdir(mount_path)
        return vfd_path

    def download_cloudbase_init(  # pylint: disable=no-self-use
            self, workdir, arch, cloudbase_init=None):
        """Downloads cloudbase init."""
        output_path = os.path.join(workdir, 'cloudbase_init.msi')
        if arch == 'amd64':
            msi_file = "CloudbaseInitSetup_x64.msi"
        elif arch == 'i386':
            msi_file = "CloudbaseInitSetup_x86.msi"
        download_path = "http://www.cloudbase.it/downloads/" + msi_file

        # --cloudbase-init passed in, don't download.
        if cloudbase_init:
            shutil.copyfile(cloudbase_init, output_path)
            return output_path

        # Remove me, testing only
        tmp_path = os.path.join('/tmp', msi_file)
        if os.path.exists(tmp_path):
            shutil.copyfile(tmp_path, output_path)
            return output_path

        utils.subp([
            'wget',
            '-O', output_path,
            download_path
            ])
        return output_path

    def download_ps_windows_update(  # pylint: disable=no-self-use
            self, workdir):
        """Downloads the PSWindowsUpdate package."""
        output_path = os.path.join(workdir, 'pswindowsupdate.zip')
        download_path = (
            "http://gallery.technet.microsoft.com/scriptcenter/"
            "2d191bcd-3308-4edd-9de2-88dff796b0bc/file/41459/43/"
            "PSWindowsUpdate.zip")
        utils.subp([
            'wget',
            '-O', output_path,
            download_path
            ])
        return output_path

    def unzip_archive(self, src, dest):  # pylint: disable=no-self-use
        """Un-zips an archive into destination."""
        utils.subp([
            'unzip', '-q',
            src,
            '-d', dest,
            ])

    def create_iso(self, output, source):  # pylint: disable=no-self-use
        """Creates iso at output, containing files at source."""
        utils.subp([
            'genisoimage',
            '-o', output,
            '-V', 'SCRIPTS',
            '-J', source
            ])

    def build_install_iso(self, workdir, arch, with_updates=False,
                          drivers_path=None, cloudbase_init=None):
        """Builds the iso that is mounted to Windows, to complete the
        installation process."""
        install_path = os.path.join(workdir, 'install')
        os.mkdir(install_path)

        # Download cloudbase-init into install/cloudbase
        cloudbase_dir = os.path.join(install_path, 'cloudbase')
        os.mkdir(cloudbase_dir)
        self.download_cloudbase_init(
            cloudbase_dir, arch, cloudbase_init=cloudbase_init)

        # Copy contrib scripts into install/scripts
        contrib_path = self.get_contrib_path('scripts')
        scripts_path = os.path.join(install_path, 'scripts')
        shutil.copytree(contrib_path, scripts_path)

        # Copy the drivers if provided
        if drivers_path is not None:
            shutil.copytree(
                drivers_path,
                os.path.join(install_path, 'infs'))

        # Place PSWindowsUpdate modules if using with_updates
        if with_updates:
            zip_path = self.download_ps_windows_update(workdir)
            self.unzip_archive(zip_path, install_path)

        # Create the iso
        output_iso = os.path.join(workdir, 'install.iso')
        self.create_iso(output_iso, install_path)
        shutil.rmtree(install_path)
        return output_iso

    def create_disk_image(  # pylint: disable=no-self-use
            self, output_path, size):
        """Creates the disk image that Windows will install to."""
        utils.subp([
            'qemu-img', 'create',
            '-f', 'raw',
            output_path, size
            ])

    def spawn_vm(  # pylint: disable=no-self-use
            self, ram, vcpus, cdrom, floppy, install_iso, disk,
            tap=None):
        """Spawns the qemu vm for Windows to install."""
        args = [
            'kvm-spice',
            '-m', '%s' % ram, '-smp', vcpus,
            '-cdrom', cdrom,
            '-drive', 'file=%s,index=0,format=raw,if=ide,media=disk' % disk,
            '-drive', 'file=%s,index=1,format=raw,if=floppy' % floppy,
            '-drive', 'file=%s,index=3,format=raw,if=ide,media=cdrom' % install_iso,
            ]
        if tap is not None:
            mac = net.get_random_qemu_mac()
            args.extend([
                '-device', 'rtl8139,netdev=net00,mac=%s' % mac,
                '-netdev',
                'type=tap,id=net00,script=no,downscript=no,ifname=%s' % tap,
                ])
        args.extend([
            '-boot', 'd', '-vga', 'std',
            '-k', 'en-us',
            # Debug *Remove*
            '-vnc', 'localhost:1',
            ])
        utils.subp(args)

    def mount_partition(  # pylint: disable=no-self-use
            self, workdir, disk_path, partition):
        """Mounts the parition from the disk."""
        mount_path = os.path.join(workdir, 'disk_mount')
        os.mkdir(mount_path)
        utils.mount_loop(disk_path, mount_path, partition)
        return mount_path

    def umount_partition(  # pylint: disable=no-self-use
            self, disk_path, target, partition):
        """Un-mounts the target, marks ntfs as clean, and removes loopback."""
        utils.subp(['umount', target])
        devs = utils.kpartx_list(disk_path)
        utils.subp(['ntfsfix', '-d', devs[partition]])
        utils.fs_sync()
        utils.kpartx_del(disk_path)
        os.rmdir(target)

    def convert_to_unix(self, file_path):  # pylint: disable=no-self-use
        """Converts file to unix to easily view."""
        try:
            utils.subp(['dos2unix', file_path])
        except utils.ProcessExecutionError:
            pass

    def check_success(self, mount_path, save_error_path):
        """Checks for success.touch and for error_log.txt."""
        error_log_path = os.path.join(mount_path, 'error_log.txt')
        if os.path.exists(error_log_path):
            shutil.copy(error_log_path, save_error_path)
            self.convert_to_unix(save_error_path)
            raise BuildError((
                'Windows installation failed, '
                'output placed %s.') % save_error_path)
        success_path = os.path.join(mount_path, 'success.tch')
        if not os.path.exists(success_path):
            raise BuildError(
                'Windows installation failed with an unknown reason.')
        os.unlink(success_path)

    def install_curtin(self, mount_path):
        """Installs the curtin scripts folder into the root."""
        src_path = self.get_contrib_path('curtin')
        curtin_path = os.path.join(mount_path, 'curtin')
        shutil.copytree(src_path, curtin_path)

    def remove_serial_log(self, target):  # pylint: disable=no-self-use
        """Removes serial log output from the configuration files for
        cloudbase-init."""
        cloudbase_init_cfg = os.path.join(
            target,
            "Program Files",
            "Cloudbase Solutions",
            "Cloudbase-Init",
            "conf",
            "cloudbase-init.conf")
        cloudbase_init_unattended_cfg = os.path.join(
            target,
            "Program Files",
            "Cloudbase Solutions",
            "Cloudbase-Init",
            "conf",
            "cloudbase-init-unattend.conf")

        configs = [cloudbase_init_cfg, cloudbase_init_unattended_cfg]
        for config in configs:
            with open(config, 'r') as stream:
                data = stream.read()
                data = data.replace(
                    'logging_serial_port_settings=COM1,115200,N,8\r\n', '')
            with open(config, 'w') as stream:
                stream.write(data)

    def qemu_convert(  # pylint: disable=no-self-use
            self, disk_path, output_path):
        """Converts the disk path to output path."""
        utils.subp([
            'qemu-img', 'convert',
            '-O', 'raw',
            disk_path, output_path,
            ])

    def create_tarball(  # pylint: disable=no-self-use
            self, disk_path, output_path):
        """Creates tarball of the disk."""
        disk_dir = os.path.dirname(os.path.abspath(disk_path))
        disk_filename = os.path.basename(disk_path)
        utils.subp([
            'tar', 'Szcf',
            output_path,
            '-C', disk_dir,
            disk_filename,
            ])

    def build_image(self, params):
        self.validate_params(params)

        # Create work space
        with utils.tempdir() as workdir:

            # Build the install.iso
            install_iso = self.build_install_iso(
                workdir, params.arch,
                with_updates=params.windows_updates,
                drivers_path=params.windows_drivers,
                cloudbase_init=params.cloudbase_init)

            # Create the floppy with the Autounattend.xml
            floppy_path = self.prepare_floppy_disk(
                workdir, params.arch,
                params.windows_edition, params.windows_language,
                license_key=params.windows_license_key,
                enable_updates=params.windows_updates)

            # Create the disk image
            disk_path = os.path.join(workdir, 'output.img')
            self.create_disk_image(disk_path, '16G')

            # Create tap device, if installing Windows updates
            # as the VM needs access to microsoft.com
            tap_name = None
            if params.windows_updates:
                tap_name = net.create_tap(params.interface)

            try:
                # Start the Windows installation
                self.spawn_vm(
                    params.ram, params.vcpus, params.windows_iso,
                    floppy_path, install_iso,
                    disk_path, tap=tap_name)
            finally:
                # Destroy the tap
                if tap_name is not None:
                    net.delete_tap(tap_name)

            # Installation has finished, mount the disk
            mount_path = self.mount_partition(workdir, disk_path, 1)

            try:
                # Check that installation went as expected
                error_filename = 'windows-%s-%s-error.log' % (
                    params.windows_edition, params.arch)
                save_error_path = os.path.join(
                    tempfile.mkdtemp(prefix="mib-windows"), error_filename)
                self.check_success(mount_path, save_error_path)

                # Install the curtin scripts into the root
                self.install_curtin(mount_path)

                # Remove serial output from cloudbase-init.conf
                self.remove_serial_log(mount_path)

            finally:
                # Unmount and clean
                self.umount_partition(disk_path, mount_path, 1)

            # Convert to raw, to save on some sparse space
            clean_disk_path = os.path.join(workdir, 'clean-output.img')
            self.qemu_convert(disk_path, clean_disk_path)
            os.unlink(disk_path)

            # Create the tarball of raw image
            tarball_path = os.path.join(workdir, 'output.ddtgz')
            self.create_tarball(clean_disk_path, tarball_path)

            # Move to output
            shutil.move(tarball_path, params.output)
