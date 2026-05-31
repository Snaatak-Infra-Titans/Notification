# -*- coding: utf-8 -*-

__author__ = 'aitormf'

import sys, os
import yaml
from .properties import Properties


def findConfigFile(filename):
    '''
    Returns filePath or None if it couldn't find the file

    @param filename: Name of the file

    @type filename: String

    @return String with path or None

    '''
    paths = "."
    config_paths = os.getenv("YAML_CONFIG_PATHS")
    if config_paths:
        paths = paths+":"+config_paths

    for path in paths.split(":"):
        file_path = os.path.join(path, filename)
        if os.path.exists(file_path):
            return file_path

    return None


def load(filename):
    '''
    Returns the configuration as dict

    @param filename: Name of the file

    @type filename: String

    @return a dict with propierties reader from file

    '''
    filepath = findConfigFile(filename)
    prop= None
    if (filepath):
        print ('loading Config file %s' %(filepath))

        with open(filepath, 'r') as stream:
            cfg=yaml.load(stream, Loader=yaml.FullLoader)
            prop = Properties(cfg) 
    else:
        msg = "Config file '%s' could not being found" % (filename)
        raise ValueError(msg)

    return prop