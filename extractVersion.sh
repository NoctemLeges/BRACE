#! /bin/bash

#Setup steps
#sudo apt install nmap

GATEWAY_IP=$(ip route | grep default | awk '{print $3}')
WEBSERVER_IP="192.168.29.113"

#DHCP Server Check
#Only tested for isc-dhcp-server
#This check only works if this script is ran on the router or the dhcp server.
if [ "$(systemctl list-unit-files | grep dhcp-server | wc -l)" -gt 0 ]; then
	VERSION="$(dhcpd --version 2>&1)"
	echo "DHCP Server: $VERSION"
else
	echo "DHCP SERVER NOT FOUND"
fi

#DNS Version Check
echo "DNS Server: $(sudo nmap -sV -sU -p 53 $GATEWAY_IP | grep 53/udp | tr -s ' ' | cut -d ' ' -f4,5)"

#Web Server Version Check
echo "Web Server: $(nmap -sV -Pn -p 80 $WEBSERVER_IP | grep 80/tcp | tr -s ' ' | cut -d ' ' -f4,5,6)"

if [ "$(systemctl list-unit-files | grep openvpn | wc -l)" -gt 0 ]; then
	VERSION="$(openvpn --version | head -n 1 | tr -s ' ' | cut -d ' ' -f2)"
	echo "OPENVPN: $VERSION"
else
	echo "NOT AN OPENVPN CLIENT"
fi
