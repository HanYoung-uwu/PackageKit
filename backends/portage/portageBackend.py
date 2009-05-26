#!/usr/bin/python
#
# Copyright (C) 2009 Mounir Lamouri (volkmar) <mounir.lamouri@gmail.com>
#
# Licensed under the GNU General Public License Version 2
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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

# packagekit imports
from packagekit.backend import *
from packagekit.progress import *
from packagekit.package import PackagekitPackage

# portage imports
# TODO: why some python app are adding try / catch around this ?
import portage

# misc imports
import sys
import signal
import re
#from urlgrabber.progress import BaseMeter, format_number

# NOTES:
#
# Package IDs description:
# CAT/PN;PV;KEYWORD;[REPOSITORY|installed]
# Last field must be "installed" if installed. Otherwise it's the repo name
# TODO: KEYWORD ? (arch or ~arch) with update, it will work ?
#
# Naming convention:
# cpv: category package version, the standard representation of what packagekit
# 	names a package (an ebuild for portage)

# TODO:
# print only found package or every ebuilds ?

def sigquit(signum, frame):
	sys.exit(1)

def id_to_cpv(pkgid):
	'''
	Transform the package id (packagekit) to a cpv (portage)
	'''
	# TODO: raise error if ret[0] doesn't contain a '/'
	ret = split_package_id(pkgid)

	if len(ret) < 4:
		raise "id_to_cpv: package id not valid"

	return ret[0] + "-" + ret[1]

def cpv_to_id(cpv):
	'''
	Transform the cpv (portage) to a package id (packagekit)
	'''
	# TODO: how to get KEYWORDS ?
	package, version, rev = portage.pkgsplit(cpv)
	keywords, repo = portage.portdb.aux_get(cpv, ["KEYWORDS", "repository"])

	if rev != "r0":
		version = version + "-" + rev

	return get_package_id(package, version, "KEYWORD", repo)

class PackageKitPortageBackend(PackageKitBaseBackend, PackagekitPackage):

	def __init__(self, args, lock=True):
		signal.signal(signal.SIGQUIT, sigquit)
		PackageKitBaseBackend.__init__(self, args)

		self.portage_settings = portage.config()
		self.vardb = portage.db[portage.settings["ROOT"]]["vartree"].dbapi
		#self.portdb = portage.db[portage.settings["ROOT"]]["porttree"].dbapi

		if lock:
			self.doLock()

	def download_packages(self, directory, pkgids):
		# TODO: what is directory for ?
		# TODO: remove wget output
		# TODO: percentage
		self.status(STATUS_DOWNLOAD)
		self.allow_cancel(True)
		percentage = 0

		for pkgid in pkgids:
			cpv = id_to_cpv(pkgid)

			# is cpv valid
			if not portage.portdb.cpv_exists(cpv):
				self.message(MESSAGE_COULD_NOT_FIND_PACKAGE, "Could not find the package %s" % pkgid)
				continue

			# TODO: FEATURES=-fetch ?

			try:
				uris = portage.portdb.getFetchMap(cpv)

				if not portage.fetch(uris, self.portage_settings, fetchonly=1, try_mirrors=1):
					self.error(ERROR_INTERNAL_ERROR, _format_str(traceback.format_exc()))
			except Exception, e:
				self.error(ERROR_INTERNAL_ERROR, _format_str(traceback.format_exc()))

	def get_details(self, pkgids):
		self.status(STATUS_INFO)
		self.allow_cancel(True)
		self.percentage(None)

		for pkgid in pkgids:
			cpv = id_to_cpv(pkgid)

			# is cpv valid
			if not portage.portdb.cpv_exists(cpv):
				self.message(MESSAGE_COULD_NOT_FIND_PACKAGE, "Could not find the package %s" % pkgid)
				continue

			homepage, desc, license = portage.portdb.aux_get(cpv, ["HOMEPAGE", "DESCRIPTION", "LICENSE"])
			# get size
			ebuild = portage.portdb.findname(cpv)
			if ebuild:
				dir = os.path.dirname(ebuild)
				manifest = portage.manifest.Manifest(dir, portage.settings["DISTDIR"])
				uris = portage.portdb.getFetchMap(cpv)
				size = manifest.getDistfilesSize(uris)

			self.details(cpv_to_id(cpv), license, "GROUP?", desc, homepage, size)

	def search_name(self, filters, key):
		# TODO: manage filters
		# TODO: collections ?
		self.status(STATUS_QUERY)
		self.allow_cancel(True)
		self.percentage(None)

		searchre = re.compile(key, re.IGNORECASE)

		for cp in portage.portdb.cp_all():
			if searchre.search(cp):
				for cpv in portage.portdb.match(cp): #TODO: cp_list(cp) ?
					desc = portage.portdb.aux_get(cpv, ["DESCRIPTION"])
					if self.vardb.cpv_exists(cpv):
						info = INFO_INSTALLED
					else:
						info = INFO_AVAILABLE
					self.package(cpv_to_id(cpv), info, desc[0])

def main():
	backend = PackageKitPortageBackend("") #'', lock=True)
	backend.dispatcher(sys.argv[1:])

if __name__ == "__main__":
	main()
