# Architecture of *ADB Wifi*

ADB has always had the capability to communicate with a device over TCP. However
the process involved is convoluted and results in an insecure channel.
The steps are as follows.

1. Connect device via USB cable.
2. Accept host's public key in the device UI dialog (pairing).
3. Request adbd to open a TCP server socket
```
$ adb tcpip 5555
```
4. Retrieve device's Wi-Fi IP address
```
IP=`adb shell ip route | awk '{print $9}'`
```
5. Finally, connect over TCP
```
$ adb connect $IP:5555
```

After all these steps, adb server is communicating
with adbd over TCP unencrypted.
This means all traffic can be eavesdropped and open to MITM attacks.

## The two problems *ADB Wifi* solves

*ADB Wifi* allows a user to pair a device and a host in a single step, without
requiring prior USB connection.

Moreover, *ADB Wifi* uses TLS which allows for secure authentication and
a secure connection after authentication.

## How *ADB Wifi* works

*ADB Wifi* revolves around four capabilities.

- Pair without the user having to click "Allow debugging".
- Encrypt ADB traffic.
- Advertise services over the network.
- Auto-connect to paired devices.

### Pairing

A host and a device are considered *paired* if the host's public key
is in the device's `/data/misc/adb/adb_keys` or `/adb_keys` files (keystore). After pairing, the
host can be trusted by the device because the host
can use its private key to answer the challenges from the device (and the device can verify
answer using keys from the keystore until a matching public key is found).

To pair, *ADB Wifi* uses a Pairing Server running on the device.
The Pairing Server communicates using RSA 2048-bit encryption (in a x509 certificate).
Trust is bootstrapped using a shared secret, seeded either by a six-digit number (pairing code)
or a 10-digit number (QR code pairing).

### Encrypted traffic

After pairing, and if the user has enabled "Wireless debugging", adbd listens on
a TCP server socket (port picked at random). This is not the same as the legacy `tcpip` socket. The
legacy socket greets all communication attempts with an A_AUTH packet whereas
this socket opens communication with A_STLS which means all traffic will be
TLS encrypted (and [authentication](../../protocol.txt) is different as well).

All this traffic is handled by the TLSServer which is forwarded to adbd's fdevent.
When users toggle "Wireless Debugging", they start and stop the TLSServer.

### Network Advertising (mDNS)

All of the elements previously mentioned advertise their presence on the network
via mDNS. Three service types are used.

- `_adb._tcp`: This is the legacy TCP service started via `adb tcpip <PORT>`.
- `_adb-tls-pairing._tcp`: The service advertised when the device pairing server is active.
- `_adb-tls-connect._tcp`: The service advertised when the device TLSServer is active.

Note that all services' instances are published by the device (adb server is merely a consumer
of mDNS packets). Both `_adb._tcp` and `_adb-tls-connect._tcp` are published directly
by adbd while `_adb-tls-pairing._tcp` is published via NsdServiceInfo.

#### mDNS Service Instance names

An instance name prefix is usually `adb-` followed by the value of the property `ro.serialno` plus a random suffix added
by the mdns backend.

The Pairing Server is special. Its service instance name changes whether it is intended
to be used with a pairing code or a QR code.

- Pairing code: `adb-`<`prop(persist.adb.wifi.guid)`>
- QR code: `studio-`< RANDOM-10> (e.g: `studio-58m*7E2fq4`)

### Auto-connect

When the host starts, it also starts mDNS service discovery for all three service types.
Any service instance of type `_adb-tls-connect` being published by the device results in a connection attempt
by the host (if the device's GUID is known to the host from pairing). If the device was previously paired,
TLS authentication will automatically succeed and the device is made available to the host.

There is one exception. When the pairing client finishes on the host, it also attempts to connect to the device
it just paired with. This is because `_adb-tls-connect` was already published before pairing even began, which
means the host cannot rely on the mDNS `_adb-tls-connect` "Create" event being published.

### Device components communication

On the device, three components must communicate. There is adbd, Framework (AdbDebuggingManager)
and the mDNS daemon.

The Pairing Server and the TLS server are part of the adbd apex API.
These two libraries are linked into system_server (AdbDebuggingManager).
The rest of the communication works via system properties.

- `persist.adb.tls_server.enable`: Set when the Developer Settings UI checkbox "Use wireless debugging" is changed.
adbd listens for these changes and manages the TLSServer lifecycle accordingly.
-  `service.adb.tls.port`: Set by adbd. Retrieved by Framework so it can publish `_adb-tls-connect`.
- `ctl.start`: Set to `mdnsd` by adbd to make sure the mDNS daemon is up and running.
- `persist.adb.wifi.guid`: Where the device GUID (used to build service instance name) comes from. Both adbd
and Framework retrieve this property to build  `_adb-tls-connect` and `_adb-tls-pairing` service instance
names.

# CLI tools

*ADB Wifi* can be set up and monitored with the command line.

### mdns check
`$ adb mdns check` tells the user the name of adb's mDNS stack and its version.

```
$ adb mdns check
mdns daemon version [Openscreen discovery 0.0.0]
```

### mdns services
`$ adb mdns services` lists all supported mdns services' instances discovered and still active,
followed by their service type and their resolved IPv4 address/port.
```
$ adb mdns services
List of discovered mdns services
adb-14141FDF600081         _adb._tcp	          192.168.86.38:5555
adb-14141FDF600081-QXjCrW  _adb-tls-pairing._tcp  192.168.86.38:33861
adb-14141FDF600081-TnSdi9  _adb-tls-connect._tcp  192.168.86.38:33015
studio-g@<xeYnap/          _adb-tls-pairing._tcp  192.168.86.39:55861
```

Note: At the moment, IPv6 addresses are resolved but not output by the command.

### pair

If a user starts a Pairing Server on the device (via
`Settings > System > Developer options > Wireless debugging > Pair device with pairing code`), they
are presented with both a pairing code and the IPv4:port of the Wi-fi interface. In this case
the vector to exchange the TLS secret is the user who reads it on the device then types the pairing code on the host.

![](adb_wifi_assets/pairing_dialog.png)

With the Pairing Server active, *ADB Wifi* is entirely configurable from the command-line, as follows.

```
$ adb pair 192.168.86.38:43811
Enter pairing code: 515109
$ adb connect 192.168.86.34:44643
$ adb devices
List of devices attached
adb-43081FDAS000VS-QXjCrW._adb-tls-connect._tcp	device
```

# Android Studio

## Pair with code
Android Studio automates pairing with a pairing code thanks to its GUI.
The advantage compared to the CLI method
is that it relies on mDNS to detect devices with an active Pairing Server.
To this effect, Studio polls adb server for service instances of type `_adb-tls-pairing`.

## Pair with QR code
Studio also introduces a QR code system which is just an easy way to share
the pairing code between the host and the device.

When a user clicks on "Pair device Using Wi-Fi", they are shown a QR code.

![](adb_wifi_assets/qrcode.png)

In the example code above Studio generated a QR code containing the string `WIFI:T:ADB;S:studio-g@<xeYnap/;P:(Aq+v9>Cx>!/;;`.
The QR code piggyback on [WPA3 Specification](https://www.wi-fi.org/system/files/WPA3%20Specification%20v3.2.pdf#page=25)
which specifies the format as follows.

```
“WIFI:” [type “;”] [trdisable “;”] ssid “;” [hidden “;”] [id “;”] [password “;”] [publickey “;”] “;”
```

Tokens are `;` separated. The QR Code contains three tokens

1. Type (marked by `T:` prefix) indicates this is an `ADB` special string.

1. The `ssid` field (marked by `S:` prefix) is repurposed to request a specific service instance name for `_adb-tls-pairing._tcp`.
The device has a special Camera QR code handler which when it sees
type `T:ADB` starts a Pairing Server with the requested instance name. Note that the part after `studio-` is randomized.
This is done so Studio can tell which phone just scanned the QR code (here the instance name requested is `studio-g@<xeYnap/`).

3. The password (marked by `P:` prefix) to use with the Pairing Server (here: `(Aq+v9>Cx>!/`).
This is the second shared secret vector we mentioned earlier. Here the code is generated
by Studio and read by the device's camera.
