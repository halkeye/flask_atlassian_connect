"""
Flask-AtlassianConnect
----------------------

This is a simple module to make creating atlassian connect based
plugins easier

See https://halkeye.github.io/flask_atlassian_connect/ for docs
"""
import io
import re

from setuptools import find_packages, setup

init_py = io.open('flask_atlassian_connect/__init__.py').read()
metadata = dict(re.findall("__([a-z]+)__ = '([^']+)'", init_py))

setup(
    name='Flask-AtlassianConnect',
    version=metadata['version'],
    description="Atlassian Connect Helper",
    long_description=__doc__,
    author=metadata['author'],
    author_email=metadata['email'],
    url=metadata['url'],
    license=open('LICENSE.md').read(),
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=io.open('requirements/runtime.txt').readlines(),
    setup_requires=['pytest-runner'],
    tests_require=filter(lambda x: not x.startswith('-'), io.open(
        'requirements/dev.txt').readlines()),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
