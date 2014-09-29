#############################################################################
#
# Copyright (C) 2014 Impex-Sat Gmbh & Co.KG
# Written by Sandro Cavazzoni <sandro@skanetwork.com>
# All Rights Reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#############################################################################

from Components.config import config

from GBIpboxLocale import _

from enigma import eEPGCache, eDVBDB

from xml.dom import minidom
import urllib
import urllib2
import re
import os

def getValueFromNode(event, key):
	tmp = event.getElementsByTagName(key)[0].firstChild
	if (tmp):
		return str(tmp.nodeValue)
	
	return ""

class GBIpboxDownloader:
	def __init__(self, session):
		self.session = session
		
	def download(self):
		baseurl = "http://"
		if config.ipboxclient.auth.value:
			baseurl += config.ipboxclient.username.value
			baseurl += ":"
			baseurl += config.ipboxclient.password.value
			baseurl += "@"
			
		baseurl += config.ipboxclient.host.value
		baseurl += ":"
		
		streamingurl = baseurl

		baseurl += str(config.ipboxclient.port.value)
		streamingurl += str(config.ipboxclient.streamport.value)
		
		for stype in [ "tv", "radio" ]:
			bouquets = self.downloadBouquets(baseurl, stype)
			self.saveBouquets(bouquets, streamingurl, '/etc/enigma2/bouquets.' + stype)
		self.downloadEPG(baseurl)
		
	def getEPGLocation(self, baseurl):
		httprequest = urllib2.urlopen(baseurl + '/web/settings')
		xmldoc = minidom.parseString(httprequest.read())
		settings = xmldoc.getElementsByTagName('e2setting') 
		for setting in settings:
			if getValueFromNode(setting, 'e2settingname') == 'config.misc.epgcache_filename':
				return getValueFromNode(setting, 'e2settingvalue')
			
		return None
		
	def downloadBouquets(self, baseurl, stype):
		bouquets = []
		httprequest = urllib2.urlopen(baseurl + '/web/bouquets?stype=' + stype)
		xmldoc = minidom.parseString(httprequest.read())
		services = xmldoc.getElementsByTagName('e2service') 
		for service in services:
			bouquet = {}
			bouquet['reference'] = service.getElementsByTagName('e2servicereference')[0].firstChild.nodeValue
			bouquet['name'] = service.getElementsByTagName('e2servicename')[0].firstChild.nodeValue
			bouquet['services'] = [];

			httprequest = urllib2.urlopen(baseurl + '/web/getservices?' + urllib.urlencode({'sRef': bouquet['reference']}))
			xmldoc2 = minidom.parseString(httprequest.read())
			services2 = xmldoc2.getElementsByTagName('e2service') 
			for service2 in services2:
				bouquet['services'].append({
					'reference': service2.getElementsByTagName('e2servicereference')[0].firstChild.nodeValue,
					'name': service2.getElementsByTagName('e2servicename')[0].firstChild.nodeValue
				})

			bouquets.append(bouquet)

		return bouquets

	def saveBouquets(self, bouquets, baseurl, destinationfile):
		bouquetsfile = open(destinationfile, "w")
		bouquetsfile.write("#NAME Bouquets (TV)" + "\n")
		for bouquet in bouquets:
			pattern = r'"([A-Za-z0-9_\./\\-]*)"'
			m = re.search(pattern, bouquet['reference'])
			if not m:
				continue
			
			filename = m.group().strip("\"")
			bouquetsfile.write("#SERVICE " + bouquet['reference'] + "\n")
			outfile = open("/etc/enigma2/" + filename, "w")
			outfile.write("#NAME " + bouquet['name'] + "\n")
			for service in bouquet['services']:
				tmp = service['reference'].split(':')
				isDVB = False
				isStreaming = False
				url = ""
			
				if len(tmp) > 1 and tmp[0] == '1' and tmp[1] == '0':
					if len(tmp) > 10 and tmp[10].startswith('http%3a//'):
						isStreaming = True
					else:
						isDVB = True
						url = baseurl + ":8001/" + service['reference']
				
				if isDVB:
					outfile.write("#SERVICE " + service['reference'] + urllib.quote(url) + ":" + service['name'] + "\n")
				elif isStreaming:
					outfile.write("#SERVICE " + service['reference'] + "\n")
				else:
					outfile.write("#SERVICE " + service['reference'] + "\n")
					outfile.write("#DESCRIPTION " + service['name'] + "\n")
			outfile.close()
		bouquetsfile.close()
		db = eDVBDB.getInstance()
		db.reloadServicelist()
		db.reloadBouquets()

	def downloadEPG(self, baseurl):
		filename = self.getEPGLocation(baseurl)
		if not filename:
			return
			
		httprequest = urllib2.urlopen(baseurl + '/file?action=download&file=' + urllib.quote(filename))
		data = httprequest.read()
		if not data:
			return

		try:
			epgfile = open(config.misc.epgcache_filename.value, "w")
		except Exception:
			return
			
		epgfile.write(data)
		epgfile.close()
		epgcache = eEPGCache.getInstance()
		epgcache.load()
		
