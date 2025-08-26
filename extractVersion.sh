#! /bin/bash

#Setup steps
#sudo apt install nmap

GATEWAY_IP=$(ip route | grep default | awk '{print $3}')
WEBSERVER_IP="192.168.29.113"
MACHINE_IP=$(hostname -I | awk '{print $1}')

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
echo "Web Server: $(nmap -sV -Pn -p 80 $MACHINE_IP | grep 80/tcp | tr -s ' ' | cut -d ' ' -f4,5,6)"

#OpenVPN Version Check
if [ "$(systemctl list-unit-files | grep openvpn | wc -l)" -gt 0 ]; then
	VERSION="$(openvpn --version | head -n 1 | tr -s ' ' | cut -d ' ' -f2)"
	echo "OPENVPN: $VERSION"
else
	echo "NOT AN OPENVPN CLIENT"
fi

#MySQL Version Check
if [ "$(systemctl list-unit-files | grep mysql | wc -l)" -gt 0 ]; then
	VERSION="$(mysql --version | awk '{print $3}')"
	echo "MySQL: $VERSION"
else
	echo "NOT A MYSQL SERVER"
fi

#SSH Version Check
if [ "$(systemctl list-unit-files | grep ssh | wc -l)" -gt 0 ]; then
	VERSION="$(ssh -V 2>&1 | awk '{print $1,$2}' | tr -d ',')"
	echo "SSH: $VERSION"
else
	echo "NOT AN SSH SERVER"
fi

#SSH Version Check with nmap (Not Reliable)
echo "SSH (nmap): $(nmap -sV -Pn -p 22 $MACHINE_IP | grep 22/tcp | tr -s ' ' | cut -d ' ' -f4,5,6,7)"

#Postfix SMTP Version Check
if [ "$(systemctl list-unit-files | grep postfix | wc -l)" -gt 0 ]; then
	VERSION="$(postconf -d | grep mail_version | head -n 1 | awk '{print $3}')"
	echo "SMTP (Postfix): $VERSION"
else
	echo "NOT AN SMTP SERVER"
fi

#SMTP (Postfix) Version Check with nmap (Not Reliable)
echo "SMTP (nmap): $(nmap -sV -Pn -p 25 $MACHINE_IP | grep 25/tcp | tr -s ' ' | cut -d ' ' -f4,5,6,7)"
