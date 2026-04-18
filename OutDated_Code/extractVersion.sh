#! /bin/bash

#Setup steps
#sudo apt install nmap

GATEWAY_IP=$(ip route | grep default | awk '{print $3}')
WEBSERVER_IP="192.168.29.113"
MACHINE_IP=$(hostname -I | awk '{print $1}')

#DHCP Server Check
#Only tested for isc-dhcp-server
#This check only works if this script is ran on the router or the dhcp server.
if [ -f "VersionInfo.txt" ]; then
	rm VersionInfo.txt
fi
touch VersionInfo.txt

if [ "$(systemctl list-unit-files | grep dhcp-server | wc -l)" -gt 0 ]; then
	VERSION="$(dhcpd --version 2>&1)"
	echo "dhcpd: $VERSION" >> VersionInfo.txt
else
	echo "dhcpd NOT FOUND"
fi

#DNS Version Check
if [ "$(sudo nmap -sV -sU -p 53 $GATEWAY_IP | grep 53/udp | tr -s ' ' | cut -d ' ' -f4,5)" ]; then
	echo "DNS Server: $(sudo nmap -sV -sU -p 53 $GATEWAY_IP | grep 53/udp | tr -s ' ' | cut -d ' ' -f4,5)" >> VersionInfo.txt
else
	echo "DNS Server NOT FOUND"
fi

#Web Server Version Check
if [ "$(nmap -sV -Pn -p 80 $MACHINE_IP | grep 80/tcp | tr -s ' ' | cut -d ' ' -f4,5,6)" ]; then
	echo "Web Server: $(nmap -sV -Pn -p 80 $MACHINE_IP | grep 80/tcp | tr -s ' ' | cut -d ' ' -f4,5,6)" >> VersionInfo.txt
else
	echo "Web Server NOT FOUND"
fi

#OpenVPN Version Check
if [ "$(systemctl list-unit-files | grep openvpn | wc -l)" -gt 0 ]; then
	VERSION="$(openvpn --version | head -n 1 | tr -s ' ' | cut -d ' ' -f2)"
	echo "openvpn: $VERSION" >> VersionInfo.txt
else
	echo "NOT AN openvpn CLIENT"
fi

#MySQL Version Check
if [ "$(systemctl list-unit-files | grep mysql | wc -l)" -gt 0 ]; then
	VERSION="$(mysql --version | awk '{print $3}')"
	echo "mysql: $VERSION" >> VersionInfo.txt
else
	echo "NOT A mysql SERVER"
fi

#SSH Version Check
if [ "$(systemctl list-unit-files | grep ssh | wc -l)" -gt 0 ]; then
	VERSION="$(ssh -V 2>&1 | awk '{print $1,$2}' | tr -d ',')"
	echo "ssh: $VERSION" >> VersionInfo.txt
else
	echo "NOT AN ssh SERVER"
fi

#SSH Version Check with nmap (Not Reliable)
echo "SSH (nmap): $(nmap -sV -Pn -p 22 $MACHINE_IP | grep 22/tcp | tr -s ' ' | cut -d ' ' -f4,5,6,7)"

#Postfix SMTP Version Check
if [ "$(systemctl list-unit-files | grep postfix | wc -l)" -gt 0 ]; then
	VERSION="$(postconf -d | grep mail_version | head -n 1 | awk '{print $3}')"
	echo "postfix: $VERSION" >> VersionInfo.txt
else
	echo "NOT AN postfix SERVER"
fi

#SMTP (Postfix) Version Check with nmap (Not Reliable)
echo "SMTP (nmap): $(nmap -sV -Pn -p 25 $MACHINE_IP | grep 25/tcp | tr -s ' ' | cut -d ' ' -f4,5,6,7)"
