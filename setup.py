import os

from setuptools import setup

mydir = os.path.dirname(__file__)
if mydir:
    os.chdir(mydir)

setup(name = 'termcolors',
      version = '0.1',
      description = 'RGB queries on xterm-like terminals',
      packages = ['termcolors'],
      package_dir = {'termcolors' : 'termcolors'},
      entry_points = {'console_scripts': [
          'termcolors-demo = termcolors.demo:main'
      ]})
