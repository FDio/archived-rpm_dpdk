# Add option to build as static libraries (--without shared)
%bcond_without shared
# Add option to build without examples
%bcond_without examples
# Add option to build without tools
%bcond_without tools

# Dont edit Version: and Release: directly, only these:
%define ver %{?_ver}
%define rel 5
# Define when building git snapshots

%define srcver %{ver}%{?_snapver:.%{_snapver}}

Name: dpdk
Version: %{ver}
Release: %{?_snapver:0.%{_snapver}.}%{rel}%{?dist}
URL: http://dpdk.org
Source: http://dpdk.org/browse/dpdk/snapshot/dpdk-%{srcver}.tar.gz

# Only needed for creating snapshot tarballs, not used in build itself
Source100: dpdk-snapshot.sh

Patch2:0001-virtio-tx-with-can_push-when-VERSION_1-is-set.patch

Summary: Set of libraries and drivers for fast packet processing

#
# Note that, while this is dual licensed, all code that is included with this
# Pakcage are BSD licensed. The only files that aren't licensed via BSD is the
# kni kernel module which is dual LGPLv2/BSD, and thats not built for fedora.
#
License: BSD and LGPLv2 and GPLv2

#
# The DPDK is designed to optimize througput of network traffic using, among
# other techniques, carefully crafted x86 assembly instructions.  As such it
# currently (and likely never will) run on non-x86 platforms.
ExclusiveArch: x86_64 i686

# machine_arch maps between rpm and dpdk arch name, often same as _target_cpu
%define machine_arch %{_target_cpu}
# machine_tmpl is the config template machine name, often "native"
%define machine_tmpl native
# machine is the actual machine name used in the dpdk make system
%ifarch x86_64
%define machine default
%endif
%ifarch i686
%define machine atm
%endif

%define target %{machine_arch}-%{machine_tmpl}-linuxapp-gcc

%define sdkdir  %{_datadir}/%{name}
%define docdir  %{_docdir}/%{name}
%define incdir  %{_includedir}/%{name}
%define pmddir %{_libdir}/%{name}-pmds

BuildRequires: kernel-headers, libpcap-devel, zlib-devel, numactl-devel
BuildRequires: doxygen, python-sphinx, git

%description
The Data Plane Development Kit is a set of libraries and drivers for
fast packet processing in the user space.

%package devel
Summary: Data Plane Development Kit development files
Requires: %{name}%{?_isa} = %{version}-%{release}
%if ! %{with shared}
Provides: %{name}-static = %{version}-%{release}
%endif

%description devel
This package contains the headers and other files needed for developing
applications with the Data Plane Development Kit.

%package doc
Summary: Data Plane Development Kit API documentation
BuildArch: noarch

%description doc
API programming documentation for the Data Plane Development Kit.

%if %{with tools}
%package tools
Summary: Tools for setting up Data Plane Development Kit environment
Requires: kmod pciutils findutils iproute

%description tools
%{summary}
%endif

%if %{with examples}
%package examples
Summary: Data Plane Development Kit example applications
BuildRequires: libvirt-devel

%description examples
Example applications utilizing the Data Plane Development Kit, such
as L2 and L3 forwarding.
%endif

%prep
%setup -n %{name}-%{srcver}
%patch2 -p1 -z .virtio

%build
function setconf()
{
    cf=%{target}/.config
    if grep -q ^$1= $cf; then
        sed -i "s:^$1=.*$:$1=$2:g" $cf
    else
        echo $1=$2 >> $cf
    fi
}
# In case dpdk-devel is installed
unset RTE_SDK RTE_INCLUDE RTE_TARGET

# Avoid appending second -Wall to everything, it breaks hand-picked
# disablers like per-file -Wno-strict-aliasing. Strip expclit -march=
# from rpm optflags because they will just make builds fail, DPDK is
# really picky about these things.
export EXTRA_CFLAGS="`echo %{optflags} | sed -e 's:-Wall::g' -e 's:-march=[[:alnum:]]* ::g'` -Wformat -fPIC"

make V=1 O=%{target} T=%{target} %{?_smp_mflags} config

# DPDK defaults to optimizing for the builder host we need generic binaries
setconf CONFIG_RTE_MACHINE '"%{machine}"'
setconf CONFIG_RTE_SCHED_VECTOR n

# Enable automatic driver loading from this path
setconf CONFIG_RTE_EAL_PMD_PATH '"%{pmddir}"'

# Enable bnx2x, qede, pcap and vhost-numa, the added deps are ok for us
setconf CONFIG_RTE_LIBRTE_BNX2X_PMD y
setconf CONFIG_RTE_LIBRTE_QEDE_PMD y
setconf CONFIG_RTE_LIBRTE_PMD_PCAP y
setconf CONFIG_RTE_LIBRTE_VHOST_NUMA y

%if %{with shared}
setconf CONFIG_RTE_BUILD_SHARED_LIB y
%endif

# Disable kernel modules
setconf CONFIG_RTE_EAL_IGB_UIO n
setconf CONFIG_RTE_LIBRTE_KNI n
setconf CONFIG_RTE_KNI_KMOD n

# Disable experimental and ABI-breaking code
setconf CONFIG_RTE_NEXT_ABI n
setconf CONFIG_RTE_LIBRTE_POWER n

make V=1 O=%{target} %{?_smp_mflags}

# Creating PDF's has excessive build-requirements, html docs suffice fine
make V=1 O=%{target} %{?_smp_mflags} doc-api-html doc-guides-html

%if %{with examples}
make V=1 O=%{target}/examples T=%{target} %{?_smp_mflags} examples
%endif

%install
# In case dpdk-devel is installed
unset RTE_SDK RTE_INCLUDE RTE_TARGET

%make_install O=%{target} prefix=%{_usr} libdir=%{_libdir}

# Create a driver directory with symlinks to all pmds
mkdir -p %{buildroot}/%{pmddir}
%if %{with shared}
for f in %{buildroot}/%{_libdir}/*_pmd_*.so.*; do
    bn=$(basename ${f})
    ln -s ../${bn} %{buildroot}%{pmddir}/${bn}
done
%endif

%if ! %{with tools}
rm -rf %{buildroot}%{sdkdir}/tools
rm -rf %{buildroot}%{_sbindir}/dpdk-devbind
%endif
rm -f %{buildroot}%{sdkdir}/tools/setup.sh

%if %{with examples}
find %{target}/examples/ -name "*.map" | xargs rm -f
for f in %{target}/examples/*/%{target}/app/*; do
    bn=`basename ${f}`
    cp -p ${f} %{buildroot}%{_bindir}/${bn}
done
%else
rm -rf %{buildroot}%{sdkdir}/examples
%endif

# Setup RTE_SDK environment as expected by apps etc
mkdir -p %{buildroot}/%{_sysconfdir}/profile.d
cat << EOF > %{buildroot}/%{_sysconfdir}/profile.d/dpdk-sdk-%{_arch}.sh
if [ -z "\${RTE_SDK}" ]; then
    export RTE_SDK="%{sdkdir}"
    export RTE_TARGET="%{target}"
    export RTE_INCLUDE="%{incdir}"
fi
EOF

cat << EOF > %{buildroot}/%{_sysconfdir}/profile.d/dpdk-sdk-%{_arch}.csh
if ( ! \$RTE_SDK ) then
    setenv RTE_SDK "%{sdkdir}"
    setenv RTE_TARGET "%{target}"
    setenv RTE_INCLUDE "%{incdir}"
endif
EOF

# Fixup target machine mismatch
sed -i -e 's:-%{machine_tmpl}-:-%{machine}-:g' %{buildroot}/%{_sysconfdir}/profile.d/dpdk-sdk*

%files
# BSD
%doc README MAINTAINERS
%{_bindir}/testpmd
%{_bindir}/dpdk-procinfo
%dir %{pmddir}
%if %{with shared}
%{_libdir}/*.so.*
%{pmddir}/*.so.*
%endif

%files doc
#BSD
%{docdir}

%files devel
#BSD
%{incdir}/
%{sdkdir}/
%if %{with tools}
%exclude %{sdkdir}/tools/
%endif
%if %{with examples}
%exclude %{sdkdir}/examples/
%endif
%{_sysconfdir}/profile.d/dpdk-sdk-*.*
%if %{with shared}
%{_libdir}/*.so
%else
%{_libdir}/*.a
%endif

%if %{with examples}
%files examples
%exclude %{_bindir}/dpdk-procinfo
%{_bindir}/*
%doc %{sdkdir}/examples/
%endif

%if %{with tools}
%files tools
%{sdkdir}/tools/
%{_sbindir}/dpdk-devbind
%endif

%changelog
* Fri Jan 13 2017 Thomas F Herbert <therbert@tedhat.com> 16.11.0-6
- Applies virtio driver patch to 16.11

* Fri Dec 30 2016 Thomas F Herbert <therbert@tedhat.com> 16.11.0-5
- Builds 16.07 and 16.11

* Tue May 24 2016 Panu Matilainen <pmatilai@redhat.com> - 16.07-0.4560.git587d684d.4
- Create DT_NEEDED entries for internal library dependencies
- Fix missing zlib dependency on qede driver

* Tue May 24 2016 Panu Matilainen <pmatilai@redhat.com> - 16.07-0.4560.git587d684d.3
- Enable crypto library + null driver, it is no longer experimental in 16.04

* Fri May 20 2016 Panu Matilainen <pmatilai@redhat.com> - 16.07-0.4560.git587d684d.2
- Workaround #1337864

* Fri May 20 2016 Panu Matilainen <pmatilai@redhat.com> - 16.07-0.4560.git587d684d.1
- New snapshot

* Tue May 17 2016 Panu Matilainen <pmatilai@redhat.com> - 16.07-0.4518.git213af31e.1
- New snapshot

* Wed May 11 2016 Panu Matilainen <pmatilai@redhat.com> - 16.07-0.4499.gita5e20775.1
- New snapshot

* Tue May 10 2016 Panu Matilainen <pmatilai@redhat.com> - 16.07-0.4481.gitdb340cf2.2
- Fix build with gcc >= 6.0

* Tue May 10 2016 Panu Matilainen <pmatilai@redhat.com> - 16.07-0.4481.gitdb340cf2.1
- New snapshot

* Wed Apr 27 2016 Panu Matilainen <pmatilai@redhat.com> - 16.07-0.4433.gitd9ba0b2c.1
- New 16.07-based snapshot
- Drop the trailing zero from version for good
- Add missing DT_NEEDED on librte_vhost to vhost pmd

* Tue Apr 26 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-2
- Get rid of the fedora-specific patch, -Wformat in CFLAGS is a nicer solution
- Switch to %autosetup to reduce fiddling with eventual patches
- Buildrequire git for patch application
- Upstream patch to fix segfault on virtio tx

* Wed Apr 13 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-1
- Oops, bring back trailing zero, needed for rpm version compare...

* Tue Apr 12 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04-1
- Update to 16.04 final
- Drop extra zero from version

* Fri Apr 08 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.4398.gitc0f81e90.1
- New snapshot (16.04.0-rc4)

* Thu Apr 07 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.4370.gitb7d65109.1
- New snapshot
- Re-enable vhost numa support (fixed in rc1 already)

* Mon Apr 04 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.4339.gitf887a6f8.1
- New snapshot (16.04.0-rc3)

* Fri Apr 01 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.4316.git4410efd3.1
- New snapshot

* Thu Mar 31 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.4281.git5bcd7b5d.1
- New snapshot

* Tue Mar 29 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.4273.git6ac91f93.1
- New snapshot (16.04.0-rc2)

* Wed Mar 23 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.4194.git281948b4.1
- New snapshot

* Thu Mar 17 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3984.git6b5a857f.1
- New snapshot (16.04.0-rc1)

* Wed Mar 16 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3984.git6b5a857f.2
- Switch to ifarch-based solution for target/machine etc afterall

* Mon Mar 14 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3984.git6b5a857f.1
- New snapshot
- Drop upstreamed dtneeded patch

* Fri Mar 11 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3934.git94b0ad8e.2
- vhost numa code causes crashes, disable until upstream fixes

* Fri Mar 11 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3934.git94b0ad8e.1
- New snapshot
- Generalize target/machine/etc macros to enable i686 builds too

* Thu Mar 10 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3914.git4c387fcd.2
- Drop no longer needed -fno-strict-aliasing

* Thu Mar 10 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3914.git4c387fcd.1
- New snapshot

* Mon Mar 07 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3875.git8f6f2434.1
- New snapshot

* Thu Mar 03 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3860.gitf4730aa6.1
- New snapshot
- Drop ip_pipeline buildopts patch, should be fixed upstream for some time now
- Drop no longer needed -Wno-error

* Wed Mar 02 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3853.git948fd64b.1
- New snapshot
- Adapt to upstream accepting the linker script approach, yay

* Tue Mar 01 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3850.git9ec201f5.1
- New snapshot

* Mon Feb 29 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3843.gita3af38a1.1
- New snapshot

* Thu Feb 18 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3809.git9fd72e3c.1
- New snapshot
- Temporarily disable strict aliasing to appease gcc 6
- Enable parallel build again

* Mon Feb 15 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3790.git5fa83b53.2
- Disable unmaintained librte_power as per upstream recommendation

* Fri Feb 12 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3790.git5fa83b53.1
- New snapshot

* Thu Feb 11 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3783.git50810f09.2
- Temporarily disable -Werror due to many new warnings from gcc 6

* Thu Feb 11 2016 Panu Matilainen <pmatilai@redhat.com> - 16.04.0-0.3783.git50810f09.1
- New snapshot, with new upstream versioning scheme

* Fri Jan 29 2016 Panu Matilainen <pmatilai@redhat.com> - 2.3.0-0.3759.gitdd34ff1f.1
- New snapshot

* Thu Jan 28 2016 Panu Matilainen <pmatilai@redhat.com> - 2.3.0-0.3757.git2593612d.1
- New snapshot

* Wed Jan 27 2016 Panu Matilainen <pmatilai@redhat.com> - 2.3.0-0.3746.gitc7985de0.1
- New snapshot
- Use a different quoting method to avoid messing up vim syntax highlighting
- A string is expected as CONFIG_RTE_MACHINE value, quote it too

* Tue Jan 19 2016 Panu Matilainen <pmatilai@redhat.com> - 2.3.0-0.3742.gitff82e08a.2
- Enable librte_vhost NUMA-awareness

* Mon Jan 18 2016 Panu Matilainen <pmatilai@redhat.com> - 2.3.0-0.3742.gitff82e08a.1
- New snapshot

* Wed Jan 13 2016 Panu Matilainen <pmatilai@redhat.com> - 2.3.0-0.3725.git3b60ce8c.3
- Fix extra junk being generated in profile.d
- Never include setup.sh

* Thu Jan 07 2016 Panu Matilainen <pmatilai@redhat.com> - 2.3.0-0.3725.git3b60ce8c.2
- Make option matching stricter in spec setconf

* Fri Dec 18 2015 Panu Matilainen <pmatilai@redhat.com> - 2.3.0-0.3725.git3b60ce8c.1
- New 2.3-pre snapshot

* Wed Dec 16 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-1
- Update to DPDK 2.2.0 final

* Tue Dec 15 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3711.git728c9e54-1
- New snapshot

* Mon Dec 14 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3688.gitbc31261c-2
- Fixup target machine mismatch in profile.d environment
- Fixup installed dpdk-devel affecting "make install" result
- Add README and MAINTAINERS docs

* Mon Dec 14 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3688.gitbc31261c-1
- New snapshot (2.2.0-rc4)

* Fri Dec 11 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3637.gitb700090c-4
- Fix relpath.sh bug causing broken symlinks

* Fri Dec 11 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3637.gitb700090c-3
- Adopt new upstream standard installation layout

* Fri Dec 11 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3637.gitb700090c-2
- Define + use a local macro for include dir location
- Group our directory macros together
- Fix static (ie --without shared) build

* Fri Dec 11 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3637.gitb700090c-1
- New snapshot

* Thu Dec 10 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3624.git1befe9ca-1
- New snapshot
- More complete dtneeded patch which should fixes build on rawhide

* Tue Dec 08 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3614.git2616f497-1
- New snapshot (2.2.0-rc3)

* Mon Dec 07 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3593.git3f3d6010-1
- New snapshot with fixed ip_pipeline

* Mon Dec 07 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3592.git13318bbb-1
- New snapshot
- ip_pipeline example is broken, disable temporarily
- upstream introduced new complications wrt our warning flags, adjust patches...

* Mon Nov 30 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3504.git538020aa
- New snapshot

* Thu Nov 26 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3496.git84fb2e67.1
- New snapshot (2.2.0-rc2)
- Disable experimental cryptodev library

* Wed Nov 25 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3463.git61383240.1
- New snapshot
- Disable CONFIG_RTE_SCHED_VECTOR, it conflicts with CONFIG_RTE_MACHINE default

* Tue Nov 24 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3424.git4522eca1.1
- New snapshot

* Fri Nov 20 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3399.gite64833f2.1
- New snapshot

* Thu Nov 19 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3394.git4c02e453.1
- New snapshot

* Wed Nov 18 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3371.git2d123257.3
- Make driver links to the actual pmd dso's, not their -devel symlinks

* Wed Nov 18 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3371.git2d123257.2
- Make plugin loading filesystem agnostic, sigh
- Fix missing symbol export

* Mon Nov 16 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3371.git2d123257.1
- New snapshot

* Fri Nov 13 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3329.git695ae278.1
- New snapshot
- Move the unversioned pmd symlinks from libdir -devel
- Establish a driver directory for automatic driver loading

* Wed Nov 04 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3321.gitc4d404d7.1
- New snapshot (2.2.0-rc1)

* Wed Nov 04 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3306.git4b90a3ff.1
- New snapshot
- Drop librte_kni afterall, makes no sense without the kernel module
- Drop main package dependency from -tools, its not strictly needed

* Mon Nov 02 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3216.gitab3257e1.1
- New snapshot

* Fri Oct 30 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3141.git92e689ce.1
- New snapshot
- Fix vhost-user segfault with multiqueue

* Wed Oct 28 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3111.git4c8db5f0.1
- New snapshot

* Tue Oct 27 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3076.git19d4d7ef.1
- New snapshot

* Mon Oct 26 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3064.gitfaefe229.1
- New snapshot

* Wed Oct 21 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.3049.gitce8e1218.1
- New snapshot
- Enable bnx2x pmd, which buildrequires zlib-devel

* Tue Sep 29 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.2955.git9702b2b5.3
- Oops, rename our linker script to match current upstream

* Mon Sep 28 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.2955.git9702b2b5
- New snapshot
- Make lib and include available both ways in the SDK paths

* Mon Sep 21 2015 Panu Matilainen <pmatilai@redhat.com> - 2.2.0-0.2947.gitc36a82f0
- New snapshot

* Tue Aug 18 2015 Panu Matilainen <pmatilai@redhat.com> - 2.1.0-1
- Update to dpdk 2.1.0 final

* Wed Aug 12 2015 Panu Matilainen <pmatilai@redhat.com> - 2.1.0-0.2898.gitf1e779ec
- New snapshot
- Disable ABI_NEXT
- Rebase patches as necessary
- Fix build of ip_pipeline example
- Drop no longer needed -Wno-error=array-bounds
- Enable librte_kni build but disable the kernel module

* Tue Jun 23 2015 Panu Matilainen <pmatilai@redhat.com> - 2.1.0-0.2429.gitc6a0fb5f
- New snapshot

* Mon Jun 22 2015 Panu Matilainen <pmatilai@redhat.com> - 2.1.0-0.2395.git1c2bbcdf
- New snapshot

* Wed Jun 17 2015 Panu Matilainen <pmatilai@redhat.com> - 2.1.0-0.2367.git790aa264
- New snapshot

* Mon Jun 15 2015 Panu Matilainen <pmatilai@redhat.com> - 2.1.0-0.2320.gitc76ee0d0
- Update to pre-2.1.0 snapshot

* Wed Jun 03 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-9
- Really enable example apps on the copr repos

* Wed Jun 03 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-8
- Re-enable example apps on the copr repos

* Tue May 19 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-7
- Drop pointless build conditional, the linker script is here to stay
- Drop vhost-cuse build conditional, vhost-user is here to stay
- Cleanup comments a bit
- Enable parallel build again
- Dont build examples by default

* Thu Apr 30 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-6
- Fix potential hang and thread issues with VFIO eventfd

* Fri Apr 24 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-5
- Fix a potential hang due to missed interrupt in vhost library

* Tue Apr 21 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-4
- Drop unused pre-2.0 era patches
- Handle vhost-user/cuse selection automatically based on the copr repo name

* Fri Apr 17 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-3
- Dont depend on fuse when built for vhost-user support
- Drop version from testpmd binary, we wont be parallel-installing that

* Thu Apr 09 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-2
- Remove the broken kmod stuff
- Add a new dkms-based eventfd_link subpackage if vhost-cuse is enabled

* Tue Apr 07 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-1
- Update to 2.0 final (http://dpdk.org/doc/guides-2.0/rel_notes/index.html)

* Thu Apr 02 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.2086.git263333bb.2
- Switch (back) to vhost-user, thus disabling vhost-cuse support
- Build requires fuse-devel for now even when fuse is unused

* Mon Mar 30 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.2049.git2f95a470.1
- New snapshot
- Add spec option for enabling vhost-user instead of vhost-cuse
- Build requires fuse-devel only with vhost-cuse
- Add virtual provide for vhost user/cuse tracking

* Fri Mar 27 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.2038.git91a8743e.3
- Disable vhost-user for now to get vhost-cuse support, argh.

* Fri Mar 27 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.2038.git91a8743e.2
- Add a bunch of missing dependencies to -tools

* Thu Mar 26 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.2038.git91a8743e.1
- Another day, another snapshot
- Disable IVSHMEM support for now

* Fri Mar 20 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.2022.gitfe4810a0.2
- Dont fail build for array bounds warnings for now, gcc 5 is emitting a bunch

* Fri Mar 20 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.2022.gitfe4810a0.1
- Another day, another snapshot
- Avoid building pdf docs

* Tue Mar 03 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.1916.gita001589e.2
- Add missing dependency to tools -subpackage

* Tue Mar 03 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.1916.gita001589e.1
- New snapshot
- Work around #1198009

* Mon Mar 02 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.1911.gitffc468ff.2
- Optionally package tools too, some binding script is needed for many setups

* Mon Mar 02 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.1911.gitffc468ff.1
- New snapshot
- Disable kernel module build by default
- Add patch to fix missing defines/includes for external applications

* Fri Feb 27 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.1906.git00c68563.1
- New snapshot
- Remove bogus devname module alias from eventfd-link module
- Whack evenfd-link to honor RTE_KERNELDIR too

* Thu Feb 26 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.1903.gitb67578cc.3
- Add spec option to build kernel modules too
- Build eventfd-link module too if kernel modules enabled

* Thu Feb 26 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.1903.gitb67578cc.2
- Move config changes from spec after "make config" to simplify things
- Move config changes from dpdk-config patch to the spec

* Thu Feb 19 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.1717.gitd3aa5274.2
- Fix warnings tripping up build with gcc 5, remove -Wno-error

* Wed Feb 18 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.1698.gitc07691ae.1
- Move the unversioned .so links for plugins into main package
- New snapshot

* Wed Feb 18 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.1695.gitc2ce3924.3
- Fix missing symbol export for rte_eal_iopl_init()
- Only mention libs once in the linker script

* Wed Feb 18 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.1695.gitc2ce3924.2
- Fix gcc version logic to work with 5.0 too

* Wed Feb 18 2015 Panu Matilainen <pmatilai@redhat.com> - 2.0.0-0.1695.gitc2ce3924.1
- Add spec magic to easily switch between stable and snapshot versions
- Add tarball snapshot script for reference
- Update to pre-2.0 git snapshot

* Thu Feb 12 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-15
- Disable -Werror, this is not useful behavior for released versions

* Wed Feb 11 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-14
- Fix typo causing librte_vhost missing DT_NEEDED on fuse

* Wed Feb 11 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-13
- Fix vhost library linkage
- Add spec option to build example applications, enable by default

* Fri Feb 06 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-12
- Enable librte_acl build
- Enable librte_ivshmem build

* Thu Feb 05 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-11
- Drop the private libdir, not needed with versioned libs

* Thu Feb 05 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-10
- Drop symbol versioning patches, always do library version for shared
- Add comment on the combined library thing

* Wed Feb 04 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-9
- Add missing symbol version to librte_cmdline

* Tue Feb 03 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-8
- Set soname of the shared libraries
- Fixup typo in ld path config file name

* Tue Feb 03 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-7
- Add library versioning patches as another build option, enable by default

* Tue Feb 03 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-6
- Add our libraries to ld path & run ldconfig when using shared libs

* Fri Jan 30 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-5
- Add DT_NEEDED for external dependencies (pcap, fuse, dl, pthread)
- Enable combined library creation, needed for OVS
- Enable shared library creation, needed for sanity

* Thu Jan 29 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-4
- Include scripts directory in the "sdk" too

* Thu Jan 29 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-3
- Fix -Wformat clash preventing i40e driver build, enable it
- Fix -Wall clash preventing enic driver build, enable it

* Thu Jan 29 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-2
- Enable librte_vhost, which buildrequires fuse-devel
- Enable physical NIC drivers that build (e1000, ixgbe) for VFIO use

* Thu Jan 29 2015 Panu Matilainen <pmatilai@redhat.com> - 1.8.0-1
- Update to 1.8.0

* Wed Jan 28 2015 Panu Matilainen <pmatilai@redhat.com> - 1.7.0-8
- Always build with -fPIC

* Wed Jan 28 2015 Panu Matilainen <pmatilai@redhat.com> - 1.7.0-7
- Policy compliance: move static libraries to -devel, provide dpdk-static
- Add a spec option to build as shared libraries

* Wed Jan 28 2015 Panu Matilainen <pmatilai@redhat.com> - 1.7.0-6
- Avoid variable expansion in the spec here-documents during build
- Drop now unnecessary debug flags patch
- Add a spec option to build a combined library

* Tue Jan 27 2015 Panu Matilainen <pmatilai@redhat.com> - 1.7.0-5
- Avoid unnecessary use of %%global, lazy expansion is normally better
- Drop unused destdir macro while at it
- Arrange for RTE_SDK environment + directory layout expected by DPDK apps
- Drop config from main package, it shouldn't be needed at runtime

* Tue Jan 27 2015 Panu Matilainen <pmatilai@redhat.com> - 1.7.0-4
- Copy the headers instead of broken symlinks into -devel package
- Force sane mode on the headers
- Avoid unnecessary %%exclude by not copying unpackaged content to buildroot
- Clean up summaries and descriptions
- Drop unnecessary kernel-devel BR, we are not building kernel modules

* Sat Aug 16 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.7.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Thu Jul 17 2014 - John W. Linville <linville@redhat.com> - 1.7.0-2
- Use EXTRA_CFLAGS to include standard Fedora compiler flags in build
- Set CONFIG_RTE_MACHINE=default to build for least-common-denominator machines
- Turn-off build of librte_acl, since it does not build on default machines
- Turn-off build of physical device PMDs that require kernel support
- Clean-up the install rules to match current packaging
- Correct changelog versions 1.0.7 -> 1.7.0
- Remove ix86 from ExclusiveArch -- it does not build with above changes

* Thu Jul 10 2014 - Neil Horman <nhorman@tuxdriver.com> - 1.7.0-1.0
- Update source to official 1.7.0 release

* Thu Jul 03 2014 - Neil Horman <nhorman@tuxdriver.com>
- Fixing up release numbering

* Tue Jul 01 2014 - Neil Horman <nhorman@tuxdriver.com> - 1.7.0-0.9.1.20140603git5ebbb1728
- Fixed some build errors (empty debuginfo, bad 32 bit build)

* Wed Jun 11 2014 - Neil Horman <nhorman@tuxdriver.com> - 1.7.0-0.9.20140603git5ebbb1728
- Fix another build dependency

* Mon Jun 09 2014 - Neil Horman <nhorman@tuxdriver.com> - 1.7.0-0.8.20140603git5ebbb1728
- Fixed doc arch versioning issue

* Mon Jun 09 2014 - Neil Horman <nhorman@tuxdriver.com> - 1.7.0-0.7.20140603git5ebbb1728
- Added verbose output to build

* Tue May 13 2014 - Neil Horman <nhorman@tuxdriver.com> - 1.7.0-0.6.20140603git5ebbb1728
- Initial Build
