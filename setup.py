from setuptools import setup
try:
    #import pypandoc
    #print "Formats: %s" % (repr(pypandoc.get_pandoc_formats()))
    long_description = '' # pypandoc.convert('README.md', 'rst')
except ImportError:
    long_description = ''


setup(
    name='AC_Flask',
    version='0.0.1',
    url='https://github.com/halkeye/ac-flask/',
    license='Apache License, Version 2.0',
    author='Gavin Mogan',
    author_email='opensource@gavinmogan.com',
    description='Helper addon for Atlassian Connect',
    long_description=long_description,
    packages=['ac_flask', 'tests'],
    platforms='any',
    install_requires=[
        'Flask',
        'requests',
        'PyJWT',
        'atlassian_jwt'
    ],
    setup_requires=['pytest-runner', 'mock', 'requests_mock'],
    tests_require=['pytest'],
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
