.. include:: links.rst

.. _assimilate_api:

Python API
==========

*Assimilate* has a simple API that allows you to run *Borg* commands. Here is an 
example taken from `sparekeys <https://github.com/kalekundert/sparekeys>`_ that 
exports the keys from your *Borg* repository so then can be backed up 
separately:

.. code-block:: python

    from assimilate import Assimilate, AssimilateError
    from pathlib import Path

    destination = Path('key')

    try:
        with Assimilate('home') as assimilate:
            borg = assimilate.run_borg(
                cmd = 'key export',
                args = [destination]
            )
            if borg.stdout:
                print(borg.stdout.strip())
    except AssimilateError as e:
        e.report()

*Assimilate* takes the config name as an argument, if not given the default 
config is used.  You can also pass list of *Assimilate* options and the path to 
the configurations directory.

*Assimilate* provides the following useful methods and attributes:


**configs**

The list of configs associated with the requested config.  If a scalar config 
was requested, the list be a list with a single member, the requested config.  
If the requested config is a composite config, the list consists of all the 
member configs of the requested config.


**repository**

The path to the repository.


**version**

The *Assimilate* version number as a 3-tuple (major, minor, patch).


**run_borg(cmd, args, borg_opts, assimilate_opts)**

Runs a *Borg* command.

*cmd* is the desired *Borg* command (ex: 'create', 'prune', etc.).

*args* contains the command line arguments (such as the repository or 
archive). It may also contain any additional command line options not 
automatically provided.  It may be a list or a string. If it is a string, it 
is split at white space.

*borg_opts* are the command line options needed by *Borg*. If not given, it is 
created for you by *Assimilate* based upon your configuration settings.

Finally, *assimilate_opts* is a list that may contain any of the following 
options: 'verbose', 'narrate', 'dry-run', or 'no-log'.

This function runs the *Borg* command and returns a process object that 
allows you access to stdout via the *stdout* attribute.


**run_borg_raw(args)**

Runs a raw *Borg* command without interpretation except for replacing 
a ``@repo`` argument with the path to the repository.

*args* contains all command line options and arguments except the path to 
the executable.


**borg_options(cmd, assimilate_opts)**

This function returns the default *Borg* command line options, those that would 
be used in *run_borg* if *borg_opts* is not set. It can be used when 
constructing a custom *borg_opts*.


**value(name, default='')**

Returns the value of a scalar setting from an *Assimilate* configuration. If not 
set, *default* is returned.


**values(name, default=())**

Returns the value of a list setting from an *Assimilate* configuration. If not 
set, *default* is returned.


Of these entry points, only *configs* works with composite configurations.

You can examine the assimilate/command.py file for inspiration and examples on 
how to use the *Assimilate* API.


Example
-------

A command that queries one or more configs and prints the total size of its 
archives.  This example is a simplified version of the *Assimilate* accessory 
available from `Borg-Space <https://github.com/KenKundert/borg-space>`_.

.. code-block:: python

    #!/usr/bin/env python3
    """
    Borg Repository Size

    Reports on the current size of one or more Borg repositories managed by 
    *Assimilate*.

    Usage:
        borg-space [options] [<config>...]

    Options:
        -m <msg>, --message <msg>   template to use when building output message

    <msg> may contain {size}, which is replaced with the measured size, and 
    {config}, which is replaced by the config name.
    If no replacements are made, size is appended to the end of the message.
    """

    import arrow
    from docopt import docopt
    from assimilate import Assimilate
    from quantiphy import Quantity
    from inform import Error, display
    import json

    now = str(arrow.now())

    cmdline = docopt(__doc__)
    show_size = not cmdline['--quiet']
    record_size = cmdline['--record']
    message = cmdline['--message']

    try:
        requests = cmdline['<config>']
        if not requests:
            requests = ['']  # this gets the default config

        for request in requests:
            # expand composite configs
            with Assimilate(request, assimilate_opts=['no-log']) as assimilate:
                configs = assimilate.configs

            for config in configs:
                with Assimilate(config, assimilate_opts=['no-log']) as assimilate:

                    # get name of latest archive
                    borg = assimilate.run_borg(
                        cmd = 'list',
                        args = ['--json', assimilate.destination()]
                    )
                    response = json.loads(borg.stdout)
                    try:
                        archive = response['archives'][-1]['archive']
                    except IndexError:
                        raise Error('no archives available.', culprit=config)

                    # get size info for latest archive
                    borg = assimilate.run_borg(
                        cmd = 'info',
                        args = ['--json', assimilate.destination(archive)]
                    )
                    response = json.loads(borg.stdout)
                    size = response['cache']['stats']['unique_csize']

                    # report the size
                    size_in_bytes = Quantity(size, 'B')
                    if not message:
                        message = '{config}: {size}'
                    msg = message.format(config=config, size=size_in_bytes)
                    if msg == message:
                        msg = f'{message}: {size_in_bytes}'
                    display(msg)

    except Error as e:
        e.report()
