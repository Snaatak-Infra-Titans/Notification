# -*- coding: utf-8 -*-

__author__ = 'aitormf'

import yaml

class Properties:
	def __init__(self, cfg):
		self._config = cfg

	def getNode(self):
		return self._config

	def getProperty(self, name):

		names = name.split(".")

		return self._searchNode(self._config, names)

	def getPropertyWithDefault(self, name, dataDefault):

		try:
			return self.getProperty(name)
		
		except KeyError:
			return dataDefault


	def _searchNode(self, node, lst):
		name = lst.pop(0)

		nod = node[name]

		if (len(lst) > 0):
			return (self._searchNode(nod, lst))
		else:
			return nod

	def __str__(self):
		return yaml.dump(self._config)

