Flask-AtlassianConnect
~~~~~~~~~~~~~~~~~~~~~~

.. module:: flask_atlassian_connect

Flask-AtlassianConnect helps to do all the heavy lifting for creating Atlassian Connect
based integrations using a `Flask`_ application

.. _Flask: http://flask.pocoo.org/

Installation
============

Install Flask-AtlassianConnect with ``pip`` command::

    $ pip install Flask-AtlassianConnect

or check out development version::

    $ git clone git://github.com/halkeye/flask_atlassian_connect.git

How to Use
==========

Flask-AtlassianConnect is pretty easy to use. You give it a flask application.
Tell it where to save/load installation info from, and the rest are simple decorators

Basic usage:

.. code-block:: python

    from flask import Flask
    from flask_atlassian_connect import AtlassianConnect

    app = Flask(__name__)
    ac = AtlassianConnect(app)

    @ac.webhook('jira:issue_created')
    def handle_jira_issue_created(client, event):
        pass

    if __name__ == '__main__':
        app.run()

When your app is all up and running, access /atlassian_connect/descriptor
to get to your atlassian connect descriptor file.

Configuration
=============

* APP_NAME = 
* ADDON_NAME = "Marketplace App Name"
* ADDON_KEY = "Marketplace Addon Key"
* ADDON_DESCRIPTION = "Description"
* ADDON_VENDOR_URL = 'https://saucelabs.com'
* ADDON_VENDOR_NAME = 'Sauce Labs'

Template Variables
==================

* atlassian_jwt_post_url - If used in your template form, it will automatically validate and pull client info again

Customizing
===========

Decorators
``````````


API
===

Configuration
`````````````

.. autoclass:: AtlassianConnect
   :members:

Fallback Client Model
`````````````````````

.. autoclass:: AtlassianConnectClient
   :members:

Licensing and Author
====================

This project is licensed under Apache2_. See LICENSE_ for the details.

I'm `Gavin Mogan`_. Feel free to open tickets if you need help. This was something that worked for me so I thought I'd share.

.. _Apache2: https://en.wikipedia.org/wiki/Apache_License
.. _LICENSE: https://github.com/halkeye/flask_atlassian_connect/blob/master/LICENSE.md
.. _Gavin Mogan: http://www.gavinmogan.com/

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

