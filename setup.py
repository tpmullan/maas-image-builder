#!/usr/bin/env python3
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

"""Distribute/Setuptools installer for MAAS Image Builder."""

from glob import glob
from os.path import (
    dirname,
    join,
    isfile,
    )

from setuptools import (
    find_packages,
    setup,
    )

# The source tree's location in the filesystem.
SOURCE_DIR = dirname(__file__)


def read(filename):
    """Return the whitespace-stripped content of `filename`."""
    path = join(SOURCE_DIR, filename)
    with open(path, "rb") as fin:
        return fin.read().strip()


__version__ = "1.0.2"

setup(
    name="maas-image-builder",
    version=__version__,
    url="https://launchpad.net/maas-image-builder",
    license="Proprietary",
    description="MAAS Image Builder",
    long_description="",

    author="Blake Rouse",
    author_email="blake.rouse@canonical.com",

    packages=find_packages(
        where='src',
        exclude=[
            "*.testing",
            "*.tests",
            ],
        ),
    package_dir={'': 'src'},
    include_package_data=True,

    entry_points={
        'console_scripts': [
            'maas-image-builder = mib.core:execute',
        ],
        'mib.builder': [
            'centos = mib.builders.centos:CentOSBuilder',
            'rhel = mib.builders.rhel:RHELBuilder',
            'windows = mib.builders.windows:WindowsOSBuilder',
        ],
    },

    data_files=[
        ('/usr/bin',
            ['scripts/maas-image-builder']),
        ('/usr/lib/maas-image-builder/contrib/centos/centos6',
            [f for f in glob('contrib/centos/centos6/*') if isfile(f)]),
        ('/usr/lib/maas-image-builder/contrib/centos/centos6/curtin',
            [f for f in glob('contrib/centos/centos6/curtin/*') if isfile(f)]),
        ('/usr/lib/maas-image-builder/contrib/centos/centos7',
            [f for f in glob('contrib/centos/centos7/*') if isfile(f)]),
        ('/usr/lib/maas-image-builder/contrib/centos/centos7/curtin',
            [f for f in glob('contrib/centos/centos7/curtin/*') if isfile(f)]),
        ('/usr/lib/maas-image-builder/contrib/rhel',
            [f for f in glob('contrib/rhel/*') if isfile(f)]),
        ('/usr/lib/maas-image-builder/contrib/rhel/curtin',
            [f for f in glob('contrib/rhel/curtin/*') if isfile(f)]),
        ('/usr/lib/maas-image-builder/contrib/windows',
            [f for f in glob('contrib/windows/*') if isfile(f)]),
        ('/usr/lib/maas-image-builder/contrib/windows/curtin',
            [f for f in glob('contrib/windows/curtin/*') if isfile(f)]),
        ('/usr/lib/maas-image-builder/contrib/windows/scripts',
            [f for f in glob('contrib/windows/scripts/*') if isfile(f)]),
    ],

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        "Intended Audience :: System Administrators",
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
)
