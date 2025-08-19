# ADB(1) MAN PAGE

# VERSION

1.0.41

# NAME

**adb**
&nbsp;&nbsp;&nbsp;&nbsp;CLI Client for ADB (Android Debug Bridge) Server.

# SYNOPSIS

**adb** [*GLOBAL_OPTIONS*] command [*COMMAND_OPTIONS*]

# DESCRIPTION

Connects to the ADB Server via its smart socket interface. Allows sending requests, receives responses and manages lifecycle of the adb server.

Tasks are performed via commands. Some commands are fulfilled directly by the server while others are "forwarded over to the adbd(ADB daemon) running on the device.

# GLOBAL OPTIONS:

**-a**
&nbsp;&nbsp;&nbsp;&nbsp;Listen on all network interfaces, not just localhost.

**-d**
&nbsp;&nbsp;&nbsp;&nbsp;Use USB device (error if multiple devices connected).

**-e**
&nbsp;&nbsp;&nbsp;&nbsp;Use TCP/IP device (error if multiple TCP/IP devices available).

**-s** **SERIAL**
&nbsp;&nbsp;&nbsp;&nbsp;Use device with given **SERIAL** (overrides $ANDROID_SERIAL).

**-t** **ID**
&nbsp;&nbsp;&nbsp;&nbsp;Use device with given transport **ID**.

**-H**
&nbsp;&nbsp;&nbsp;&nbsp;Name of adb server host [default=localhost].

**-P** **PORT*
&nbsp;&nbsp;&nbsp;&nbsp;Smart socket **PORT** of adb server [default=5037].

**-L** **SOCKET**
&nbsp;&nbsp;&nbsp;&nbsp;Listen on given socket for adb server [default=tcp:localhost:5037].

**\-\-one-device** **SERIAL**|**USB**
&nbsp;&nbsp;&nbsp;&nbsp;Server will only connect to one USB device, specified by a **SERIAL** number or **USB** device address (only with 'start-server' or 'server nodaemon').

**\-\-exit-on-write-error**
&nbsp;&nbsp;&nbsp;&nbsp;Exit if stdout is closed.


# GENERAL COMMANDS:

devices [**-l**]
&nbsp;&nbsp;&nbsp;&nbsp;List connected devices.

**-l**
&nbsp;&nbsp;&nbsp;&nbsp;Use long output.

help
&nbsp;&nbsp;&nbsp;&nbsp;Show this help message.

version
&nbsp;&nbsp;&nbsp;&nbsp;Show version number.

# NETWORKING

connect **HOST**[:**PORT**]
&nbsp;&nbsp;&nbsp;&nbsp;Connect to a device via TCP/IP [default **PORT**=5555].

disconnect [**HOST**[:**PORT**]]
&nbsp;&nbsp;&nbsp;&nbsp;Disconnect from given TCP/IP device [default **PORT**=5555], or all.

pair **HOST**[:**PORT**] [**PAIRING_CODE**]
&nbsp;&nbsp;&nbsp;&nbsp;Pair with a device for secure TCP/IP communication.

forward **\-\-list** | [**--no-rebind**] **LOCAL_REMOTE** | **\-\-remove** **LOCAL** | **\-\-remove-all**

**\-\-list**
&nbsp;&nbsp;&nbsp;&nbsp;List all forward socket connections.

[**--no-rebind**] **LOCAL_REMOTE**
&nbsp;&nbsp;&nbsp;&nbsp;Forward socket connection using one of the followings.

&nbsp;&nbsp;&nbsp;&nbsp;**tcp**:**PORT** (local may be "tcp:0" to pick any open port.
&nbsp;&nbsp;&nbsp;&nbsp;**localreserved**:**UNIX_DOMAIN_SOCKET_NAME**.
&nbsp;&nbsp;&nbsp;&nbsp;**localfilesystem**:**UNIX_DOMAIN_SOCKET_NAME**.
&nbsp;&nbsp;&nbsp;&nbsp;**jdwp**:**PROCESS PID** (remote only).
&nbsp;&nbsp;&nbsp;&nbsp;**vsock**:**CID**:**PORT** (remote only).
&nbsp;&nbsp;&nbsp;&nbsp;**acceptfd**:**FD** (listen only).
&nbsp;&nbsp;&nbsp;&nbsp;**dev**:**DEVICE_NAME**.
&nbsp;&nbsp;&nbsp;&nbsp;**dev-raw**:**DEVICE_NAME**. (open device in raw mode)**.

**\-\-remove** **LOCAL**
&nbsp;&nbsp;&nbsp;&nbsp;Remove specific forward socket connection.

**\-\-remove-all**
&nbsp;&nbsp;&nbsp;&nbsp;Remove all forward socket connections.

reverse **\-\-list** | [**\-\-no-rebind**] **REMOTE** **LOCAL** | **\-\-remove** **REMOTE** | **\-\-remove-all**

**\-\-list**
&nbsp;&nbsp;&nbsp;&nbsp;List all reverse socket connections from device.

[**\-\-no-rebind**] **REMOTE** **LOCAL**
&nbsp;&nbsp;&nbsp;&nbsp;Reverse socket connection using one of the following.

&nbsp;&nbsp;&nbsp;&nbsp;tcp:**PORT** (**REMOTE** may be "tcp:0" to pick any open port).
&nbsp;&nbsp;&nbsp;&nbsp;localabstract:**UNIX_DOMAIN_SOCKET_NAME**.
&nbsp;&nbsp;&nbsp;&nbsp;localreserved:**UNIX_DOMAIN_SOCKET_NAME**.
&nbsp;&nbsp;&nbsp;&nbsp;localfilesystem:**UNIX_DOMAIN_SOCKET_NAME**.

**\-\-remove** **REMOTE**
&nbsp;&nbsp;&nbsp;&nbsp;Remove specific reverse socket connection.

**\-\-remove-all**
&nbsp;&nbsp;&nbsp;&nbsp;Remove all reverse socket connections from device.

mdns **check** | **services**
&nbsp;&nbsp;&nbsp;&nbsp;Perform mDNS subcommands.

**check**
&nbsp;&nbsp;&nbsp;&nbsp;Check if mdns discovery is available.

**services**
&nbsp;&nbsp;&nbsp;&nbsp;List all discovered services.


# FILE TRANSFER:

push [**--sync**] [**-z** **ALGORITHM**] [**-Z**] **LOCAL**... **REMOTE**
&nbsp;&nbsp;&nbsp;&nbsp;Copy local files/directories to device.

**--sync**
&nbsp;&nbsp;&nbsp;&nbsp;Only push files that are newer on the host than the device.

**-n**
&nbsp;&nbsp;&nbsp;&nbsp;Dry run, push files to device without storing to the filesystem.

**-z**
&nbsp;&nbsp;&nbsp;&nbsp;enable compression with a specified algorithm (any/none/brotli/lz4/zstd).

**-Z**
&nbsp;&nbsp;&nbsp;&nbsp;Disable compression.

pull [**-a**] [**-z** **ALGORITHM**] [**-Z**] **REMOTE**... **LOCAL**
&nbsp;&nbsp;&nbsp;&nbsp;Copy files/dirs from device

**-a**
&nbsp;&nbsp;&nbsp;&nbsp;preserve file timestamp and mode.

**-z**
&nbsp;&nbsp;&nbsp;&nbsp;enable compression with a specified algorithm (**any**/**none**/**brotli**/**lz4**/**zstd**)

**-Z**
&nbsp;&nbsp;&nbsp;&nbsp;disable compression

sync [**-l**] [**-z** **ALGORITHM**] [**-Z**] [**all**|**data**|**odm**|**oem**|**product**|**system**|**system_ext**|**vendor**]
&nbsp;&nbsp;&nbsp;&nbsp;Sync a local build from $ANDROID_PRODUCT_OUT to the device (default all)

**-n**
&nbsp;&nbsp;&nbsp;&nbsp;Dry run. Push files to device without storing to the filesystem.

**-l**
&nbsp;&nbsp;&nbsp;&nbsp;List files that would be copied, but don't copy them.

**-z**
Enable compression with a specified algorithm (**any**/**none**/**brotli**/**lz4**/**zstd**)

**-Z**
Disable compression.

# SHELL:

shell [**-e** **ESCAPE**] [**-n**] [**-Tt**] [**-x**] [**COMMAND**...]
&nbsp;&nbsp;&nbsp;&nbsp;Run remote shell command (interactive shell if no command given).

**-e**
&nbsp;&nbsp;&nbsp;&nbsp;Choose escape character, or "**none**"; default '**~**'.

**-n**
&nbsp;&nbsp;&nbsp;&nbsp;Don't read from stdin.

**-T**:
&nbsp;&nbsp;&nbsp;&nbsp;Disable pty allocation.

**-t**:
&nbsp;&nbsp;&nbsp;&nbsp;Allocate a pty if on a tty (-tt: force pty allocation).

**-x**
&nbsp;&nbsp;&nbsp;&nbsp;Disable remote exit codes and stdout/stderr separation.

emu **COMMAND**
&nbsp;&nbsp;&nbsp;&nbsp;Run emulator console **COMMAND**

# APP INSTALLATION
(see also `adb shell cmd package help`):

install [**-lrtsdg**] [**--instant**] **PACKAGE**
&nbsp;&nbsp;&nbsp;&nbsp;Push a single package to the device and install it

install-multiple [**-lrtsdpg**] [**--instant**] **PACKAGE**...
&nbsp;&nbsp;&nbsp;&nbsp;Push multiple APKs to the device for a single package and install them

install-multi-package [**-lrtsdpg**] [**--instant**] **PACKAGE**...
&nbsp;&nbsp;&nbsp;&nbsp;Push one or more packages to the device and install them atomically

**-r**:
&nbsp;&nbsp;&nbsp;&nbsp;Replace existing application.

**-t**
&nbsp;&nbsp;&nbsp;&nbsp;Allow test packages.

**-d**
&nbsp;&nbsp;&nbsp;&nbsp;Allow version code downgrade (debuggable packages only).

**-p**
&nbsp;&nbsp;&nbsp;&nbsp;Partial application install (install-multiple only).

**-g**
&nbsp;&nbsp;&nbsp;&nbsp;Grant all runtime permissions.

**\-\-abi** **ABI**
&nbsp;&nbsp;&nbsp;&nbsp;Override platform's default ABI.

**\-\-instant**
&nbsp;&nbsp;&nbsp;&nbsp;Cause the app to be installed as an ephemeral install app.

**\-\-no-streaming**
&nbsp;&nbsp;&nbsp;&nbsp;Always push APK to device and invoke Package Manager as separate steps.

**\-\-streaming**
&nbsp;&nbsp;&nbsp;&nbsp;Force streaming APK directly into Package Manager.

**\-\-fastdeploy**
&nbsp;&nbsp;&nbsp;&nbsp;Use fast deploy.

**-no-fastdeploy**
&nbsp;&nbsp;&nbsp;&nbsp;Prevent use of fast deploy.

**-force-agent**
&nbsp;&nbsp;&nbsp;&nbsp;Force update of deployment agent when using fast deploy.

**-date-check-agent**
&nbsp;&nbsp;&nbsp;&nbsp;Update deployment agent when local version is newer and using fast deploy.

**\-\-version-check-agent**
&nbsp;&nbsp;&nbsp;&nbsp;Update deployment agent when local version has different version code and using fast deploy.

**\-\-local-agent**
&nbsp;&nbsp;&nbsp;&nbsp;Locate agent files from local source build (instead of SDK location). See also `adb shell pm help` for more options.

uninstall [**-k**] **APPLICATION_ID**
&nbsp;&nbsp;&nbsp;&nbsp;Remove this **APPLICATION_ID** from the device.

**-k**
&nbsp;&nbsp;&nbsp;&nbsp;Keep the data and cache directories.

# DEBUGGING:

bugreport [**PATH**]
&nbsp;&nbsp;&nbsp;&nbsp;Write bugreport to given PATH [default=bugreport.zip]; if **PATH** is a directory, the bug report is saved in that directory. devices that don't support zipped bug reports output to stdout.

jdwp
&nbsp;&nbsp;&nbsp;&nbsp;List pids of processes hosting a JDWP transport.

logcat
&nbsp;&nbsp;&nbsp;&nbsp;Show device log (logcat --help for more).

server-status Display server configuration (USB backend, mDNS backend, log location, binary path. See [adb_host.proto](../../proto/adb_host.proto) (AdbServerStatus) for details.

# SECURITY:

disable-verity
&nbsp;&nbsp;&nbsp;&nbsp;Disable dm-verity checking on userdebug builds.

enable-verity
&nbsp;&nbsp;&nbsp;&nbsp;Re-enable dm-verity checking on userdebug builds.

keygen **FILE**
&nbsp;&nbsp;&nbsp;&nbsp;Generate adb public/private key; private key stored in **FILE**.

# SCRIPTING:

wait-for [-**TRANSPORT**] -**STATE**...
&nbsp;&nbsp;&nbsp;&nbsp; Wait for device to be in a given state.

&nbsp;&nbsp;&nbsp;&nbsp;**STATE**: device, recovery, rescue, sideload, bootloader, or disconnect.
&nbsp;&nbsp;&nbsp;&nbsp;**TRANSPORT**: **usb**, **local**, or **any** [default=**any**].

get-state
&nbsp;&nbsp;&nbsp;&nbsp;Print offline | bootloader | device.

get-serialno
&nbsp;&nbsp;&nbsp;&nbsp;Print **SERIAL_NUMBER**.

get-devpath
&nbsp;&nbsp;&nbsp;&nbsp;Print  **DEVICE_PATH**.

remount [**-R**]
&nbsp;&nbsp;&nbsp;&nbsp;Remount partitions read-write.

**-R**
&nbsp;&nbsp;&nbsp;&nbsp;Automatically reboot the device.

reboot [**bootloader**|**recovery**|**sideload**|**sideload-auto-reboot**]
&nbsp;&nbsp;&nbsp;&nbsp;Reboot the device; defaults to booting system image but supports **bootloader** and **recovery** too.

**sideload**
&nbsp;&nbsp;&nbsp;&nbsp;Reboots into recovery and automatically starts sideload mode.

**sideload-auto-reboot**
&nbsp;&nbsp;&nbsp;&nbsp;Same as **sideload** but reboots after sideloading.


sideload **OTAPACKAGE**
&nbsp;&nbsp;&nbsp;&nbsp;Sideload the given full OTA package **OTAPACKAGE**.

root
&nbsp;&nbsp;&nbsp;&nbsp;Restart adbd with root permissions.

unroot
&nbsp;&nbsp;&nbsp;&nbsp;Restart adbd without root permissions.

usb
&nbsp;&nbsp;&nbsp;&nbsp;Restart adbd listening on USB.

tcpip **PORT**
&nbsp;&nbsp;&nbsp;&nbsp;Restart adbd listening on TCP on **PORT**.

# INTERNAL DEBUGGING:

start-server
&nbsp;&nbsp;&nbsp;&nbsp;Ensure that there is a server running.

kill-server
&nbsp;&nbsp;&nbsp;&nbsp;Kill the server if it is running.

reconnect
&nbsp;&nbsp;&nbsp;&nbsp;Close connection from host side to force reconnect.

reconnect device
&nbsp;&nbsp;&nbsp;&nbsp;Close connection from device side to force reconnect.

reconnect offline
&nbsp;&nbsp;&nbsp;&nbsp;Reset offline/unauthorized devices to force reconnect.

# USB:

Only valid when running with libusb backend.

attach **SERIAL**
&nbsp;&nbsp;&nbsp;&nbsp;Attach a detached USB device identified by its **SERIAL** number.

detach **SERIAL**
&nbsp;&nbsp;&nbsp;&nbsp;Detach from a USB device identified by its **SERIAL** to allow use by other processes.


# Features:

host-features  
&nbsp;&nbsp;&nbsp;&nbsp;list features supported by adb server.

features  
&nbsp;&nbsp;&nbsp;&nbsp;list features supported by both adb server and device.

# ENVIRONMENT VARIABLES

$ADB_TRACE
&nbsp;&nbsp;&nbsp;&nbsp;Comma (or space) separated list of debug info to log: all,adb,sockets,packets,rwx,usb,sync,sysdeps,transport,jdwp,services,auth,fdevent,shell,incremental, mdns.

$ADB_VENDOR_KEYS
&nbsp;&nbsp;&nbsp;&nbsp;Colon-separated list of keys (files or directories).

$ANDROID_SERIAL
&nbsp;&nbsp;&nbsp;&nbsp;Serial number to connect to (see -s).

$ANDROID_LOG_TAGS
&nbsp;&nbsp;&nbsp;&nbsp;Tags to be used by logcat (see logcat --help).

$ADB_LOCAL_TRANSPORT_MAX_PORT
&nbsp;&nbsp;&nbsp;&nbsp;Max emulator scan port (default 5585, 16 emulators).

$ADB_MDNS_AUTO_CONNECT
&nbsp;&nbsp;&nbsp;&nbsp;Comma-separated list of mdns services to allow auto-connect (default adb-tls-connect).

$ADB_MDNS_OPENSCREEN
&nbsp;&nbsp;&nbsp;&nbsp;The default mDNS-SD backend is Bonjour (mdnsResponder). For machines where Bonjour is not installed, adb can spawn its own, embedded, mDNS-SD back end, openscreen. If set to "1", this env variable forces mDNS backend to openscreen.

$ADB_LIBUSB
&nbsp;&nbsp;&nbsp;&nbsp;ADB has its own USB backend implementation but can also employ libusb. use `adb devices -l` (`usb:` prefix is omitted for libusb)  or `adb host-features` (look for `libusb` in the output list) to identify which is in use. To override the default for your OS, set ADB_LIBUSB to "1" to enable libusb, or "0" to enable the ADB backend implementation.

# BUGS

See Issue Tracker: [here](https://issuetracker.google.com/issues/new?component=192795&template=1310483).

# AUTHORS

See [OWNERS](../../OWNERS) file in ADB AOSP repo.
