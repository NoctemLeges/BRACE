#!/bin/bash

OUTPUT_FILE="VersionInfo.txt"

# Clear file
> "$OUTPUT_FILE"

# -------- OpenVPN --------
OPENVPN_BIN="/usr/local/sbin/openvpn"

if [ -x "$OPENVPN_BIN" ]; then
    version=$("$OPENVPN_BIN" --version | head -n1 | awk '{print $2}')
    echo "openvpn:openvpn:$version" >> "$OUTPUT_FILE"
fi

# -------- OpenSSH --------
SSH_BIN="$(command -v ssh 2>/dev/null)"

if [ -n "$SSH_BIN" ]; then
    version=$("$SSH_BIN" -V 2>&1 | awk '{print $1}' | cut -d'_' -f2 | sed 's/,$//')
    echo "openbsd:openssh:$version" >> "$OUTPUT_FILE"
fi

# -------- NGINX --------
NGINX_BIN="/usr/local/nginx/sbin/nginx"

if [ -x "$NGINX_BIN" ]; then
    version=$("$NGINX_BIN" -v 2>&1 | cut -d'/' -f2)
    echo "f5:nginx:$version" >> "$OUTPUT_FILE"
fi

echo "Version info written to $OUTPUT_FILE"