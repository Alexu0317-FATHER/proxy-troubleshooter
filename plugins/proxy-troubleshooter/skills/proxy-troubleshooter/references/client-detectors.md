# Client Detectors

Detect client families from evidence, not from user guesses.

Useful signals:

- Running process names: clash, mihomo, clash-verge, verge, flclash, v2rayn, nekoray, sing-box, xray, shadowsocks, hiddify.
- Listening loopback ports: mixed HTTP/SOCKS ports, controller ports, and DNS ports.
- Known config directory names under user app data.
- Config file fingerprints rather than raw config contents.
- TUN or virtual adapter names containing wintun, tun, clash, mihomo, wireguard, sing, or similar.

Do not scan broad home directories when known app-data paths or process evidence are enough.

Current Windows detector scope:

- `Clash for Windows`
- `.config/clash`
- `.config/mihomo`
- `mihomo`
- `clash-verge`
- `clash-verge-rev`
- `io.github.clash-verge-rev.clash-verge-rev`
- `FlClash`
- `Mihomo Party`
- `v2rayN`
- `nekoray`

For known directories, inspect only common config filenames or immediate profile YAML files. Emit path, existence, file hash, selected safe fields, rule count, and catch-all lines. Do not emit rule bodies or subscription data.
