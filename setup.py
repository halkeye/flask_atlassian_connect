import io
import re
from setuptools import setup

init_py = io.open('ac_flask/__init__.py').read()
metadata = dict(re.findall("__([a-z]+)__ = '([^']+)'", init_py))
metadata['doc'] = re.findall('"""(.+)"""', init_py)[0]

setup(
    name='AC_Flask',
    version=metadata['version'],
    description=metadata['doc'],
    author=metadata['author'],
    author_email=metadata['email'],
    url=metadata['url'],
    license=open('LICENSE.md').read(),
    packages=['ac_flask', 'tests'],
    platforms='any',
    install_requires=io.open('requirements/runtime.txt').readlines(),
    setup_requires=['pytest-runner'],
    tests_require=['mock', 'requests_mock', 'pytest'],
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
