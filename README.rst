Assimilate — Front-End to Borg Backup
=====================================

*Assimilate your files to the Borg Collective*


|downloads| |build status| |coverage| |rtd status| |pypi version| |python version|

:Author: Ken Kundert
:Version: 0.0b8
:Released: 2025-04-25

*Assimilate* is a simple command line utility to orchestrate backups. It is 
designed to make common tasks simple and efficient.  With *Assimilate*, you 
specify all the details about your backups once in advance, and then use 
a simple command line interface for your day-to-day activities.

*Assimilate* is a front-end to Borg_, a powerful and fast de-duplicating backup 
program.  Use of *Assimilate* does not preclude the use of *Borg* directly on 
the same repository.  The philosophy of *Assimilate* is to provide commands that 
you would use often and in an interactive manner with the expectation that you 
would use Borg directly for the remaining commands.

*Assimilate* is intended for use with Borg_ 2.0 or newer, which is currently not 
available in a stable release and is not recommended for general use.  If you 
are using a earlier version of *Borg* you should consider using Emborg_.  
*Emborg* is the immediate predecessor of *Assimilate*, but *Assimilate* is not 
backward compatible with *Emborg*.


Getting Help
------------

You can find the documentation here: Assimilate_.

The *help* command provides information on how to use Assimlates's various
features.  To get a listing of the topics available, use::

    assimilate help

Then, for information on a specific topic use::

    assimilate help <topic>

It is worth browsing all of the available topics at least once to get a sense of
all that *Assimilate* can do.


.. _borg: https://borgbackup.readthedocs.io
.. _emborg: https://emborg.readthedocs.io
.. _assimilate: https://assimilate.readthedocs.io

.. |downloads| image:: https://pepy.tech/badge/assimilate/month
    :target: https://pepy.tech/project/assimilate

..  |build status| image:: https://github.com/KenKundert/assimilate/actions/workflows/build.yaml/badge.svg
    :target: https://github.com/KenKundert/assimilate/actions/workflows/build.yaml

.. |coverage| image:: https://coveralls.io/repos/github/KenKundert/assimilate/badge.svg?branch=master
    :target: https://coveralls.io/github/KenKundert/assimilate?branch=master

.. |rtd status| image:: https://img.shields.io/readthedocs/assimilate.svg
    :target: https://assimilate.readthedocs.io/en/latest/?badge=latest

.. |pypi version| image:: https://img.shields.io/pypi/v/assimilate.svg
    :target: https://pypi.python.org/pypi/assimilate

.. |python version| image:: https://img.shields.io/pypi/pyversions/assimilate.svg
    :target: https://pypi.python.org/pypi/assimilate/

