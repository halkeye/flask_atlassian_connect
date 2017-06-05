"""
Flask-DBConfig
--------------

Configure your Flask application from a local SQLite database, and never have
to ship with a config file again!

Links
`````

* `documentation <http://packages.python.org/Flask-DBConfig>`_

"""

from setuptools import setup, find_packages

setup(
    name='Flask-AC',
    version='0.0.1',
    url='https://github.com/saucelabs/flask-ac/',
    license='Apache License, Version 2.0',
    author='Sauce Labs',
    author_email='opensource@saucelabs.com',
    description='Configure Flask applications from a local DB',
    long_description=__doc__,
    packages=find_packages(),
    platforms='any',
    install_requires=[
        'Flask',
        'requests'
    ],
    test_requires=[
        'requests_mock',
        'mock'
    ],
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
