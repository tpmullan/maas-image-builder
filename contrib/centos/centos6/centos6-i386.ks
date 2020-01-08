#version=DEVEL
# Firewall configuration
firewall --enabled --service=ssh
repo --name="repo0" --baseurl=http://mirror.centos.org/centos/6/os/i386/
repo --name="repo1" --baseurl=http://mirror.centos.org/centos/6/updates/i386/
repo --name="repo2" --baseurl=http://dl.fedoraproject.org/pub/epel/6/i386/
# Root password
rootpw --iscrypted --lock $1$2e74e5$wMj25e4rEb4rJxqm7BAnk0
# System authorization information
auth --useshadow --enablemd5
# System keyboard
keyboard us
# System language
lang en_US.UTF-8
# SELinux configuration
selinux --enforcing
# Installation logging level
logging --level=info
# Reboot after installation
reboot
# System services
services --disabled="avahi-daemon,iscsi,iscsid,firstboot,kdump" --enabled="network,sshd,rsyslog,tuned"
# System timezone
timezone --isUtc America/New_York
# Network information
network  --bootproto=dhcp --device=eth0 --onboot=on
# System bootloader configuration
bootloader --append="console=ttyS0,115200n8 console=tty0" --location=mbr --driveorder="sda" --timeout=1
# Clear the Master Boot Record
zerombr
# Partition clearing information
clearpart --all
# Disk partitioning information
part / --fstype="ext4" --size=3072

%post

# make sure firstboot doesn't start
echo "RUN_FIRSTBOOT=NO" > /etc/sysconfig/firstboot

cat <<EOL >> /etc/rc.local
if [ ! -d /root/.ssh ] ; then
    mkdir -p /root/.ssh
    chmod 0700 /root/.ssh
    restorecon /root/.ssh
fi
EOL

cat <<EOL >> /etc/ssh/sshd_config
UseDNS no
PermitRootLogin without-password
EOL

# bz705572
ln -s /boot/grub/grub.conf /etc/grub.conf

# bz688608
sed -i 's|\(^PasswordAuthentication \)yes|\1no|' /etc/ssh/sshd_config

# allow sudo powers to cloud-user
echo -e 'cloud-user\tALL=(ALL)\tNOPASSWD: ALL' >> /etc/sudoers

#bz912801
# prevent udev rules from remapping nics
touch /etc/udev/rules.d/75-persistent-net-generator.rules

#setup getty on ttyS0
echo "ttyS0" >> /etc/securetty
cat <<EOF > /etc/init/ttyS0.conf
start on stopped rc RUNLEVEL=[2345]
stop on starting runlevel [016]
respawn
instance /dev/ttyS0
exec /sbin/agetty /dev/ttyS0 115200 vt100-nav
EOF

# lock root password
passwd -d root
passwd -l root

# clean up installation logs"
yum clean all
rm -rf /var/log/yum.log
rm -rf /var/lib/yum/*
rm -rf /root/install.log
rm -rf /root/install.log.syslog
rm -rf /root/anaconda-ks.cfg
rm -rf /var/log/anaconda*
%end

%packages --nobase
acpid
attr
audit
authconfig
basesystem
bash
cloud-init
coreutils
cpio
cronie
device-mapper
dhclient
dracut
e2fsprogs
efibootmgr
filesystem
glibc
grub
heat-cfntools
initscripts
iproute
iptables
iptables-ipv6
iputils
kbd
kernel
kpartx
ncurses
net-tools
nfs-utils
openssh-clients
openssh-server
parted
passwd
policycoreutils
procps
python-oauth
rootfiles
rpm
rsync
rsyslog
selinux-policy
selinux-policy-targeted
sendmail
setup
shadow-utils
sudo
syslinux
tar
tuned
util-linux-ng
vim-minimal
yum
yum-metadata-parser
-NetworkManager
-b43-openfwwf
-biosdevname
-fprintd
-fprintd-pam
-gtk2
-libfprint
-mcelog
-plymouth
-redhat-support-tool
-system-config-*
-wireless-tools

%end
