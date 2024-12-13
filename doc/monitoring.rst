.. include:: links.rst

.. _monitoring:

Monitoring
==========

.. _log_files:

Log Files
---------

When there are problems, the log file can help you understand what is going 
wrong.  *Assimilate* creates log files for most commands (the commands that do 
not create logfiles are *configs*, *due*, *help*, *log*, *settings*, and 
*version*).  Two log files are created for each configuration employed: the 
individual and the composite log file.

The most recent individual logfile is accessible with the *log* command::

    assimilate log

These files reside in the data directory for *Assimilate*, which is 
`$XDG_DATA_HOME/assimilate`.  If the environment variable `XDG_DATA_HOME` is not 
set, the location of the data directory is operating system specific.  On Linux 
you will find it in `~/.local/.share/assimilate`.

The log files are named after the configuration.  For example, if the *home* 
configuration is run, the files *home.log* and *home.log.nt* will be found.  
*home.log* is the individual log file and *home.log.nt* is the composite log 
file.  The composite log file is a NestedText_ file that contains the contents 
of all of the most recent individual log files as separate entries.

The composite log is created using NTLog_.  You can configure the *NTLog* 
logging using the :ref:`logging` in the shared configuration file.
The contents of *logging is a dictionary (key-value pairs) where each line give 
the name and value of an *NTLog* command line argument.  For example:

.. code-block:: nestedtext

    logging:
        keep for: 1d

By default *Assimilate* uses the following defaults for *NTLog*:

.. code-block:: nestedtext

    logging:
        keep for: 1w
        day header: D MMMM YYYY  {{{{{{1
        entry header: h:mm A  {{{{{{2
        description: {cmd_name}
        editor: vim

If you use Vim, you can figure it to fold the composite log file with ``:set 
foldmethod=marker``.  You can then open a fold using ``zo`` and close it with 
``zc``.

Due and Info
------------

The :ref:`due <due>` and :ref:`info <info>` commands allow you to interactively 
check on the current status of your backups.  Besides the :ref:`create <create>` 
command, it is good hygiene to run the :ref:`prune <prune>`, :ref:`compact 
<compact>` and :ref:`check <check>` on a regular basis.  Either the :ref:`due 
<due>` or :ref:`info <info>` command can be used to determine when each were 
last run.


.. _assimilate_overdue:

Overdue
-------

*Assimilate* provides the *overdue* command that can be used to determine which 
of your repositories are overdue for backup.  This is useful if you are 
supporting many repositories as it can use ssh to query remote backups.  It 
reads its own settings file, typically `overdue.conf`, contained in the 
:ref:`Assimilate configuration directory <configuring_assimilate>`,  that is 
also a NestedText_ file and may contain the following settings:

| *to_email* (email address -- mail is sent to this person upon failure)
| *from_email* (email address -- mail is sent from this person upon failure)
| *max_age* (how old a repository must be to constitute failure)
| *root* (default directory for repositories)
| *message* (a template for the message to be printed for each repository)
| *repositories* (details and overrides for each repository)

For each repository, you can specify the following repository-specific settings:

| *config* (name of the *Assimilate* config for the repository)
| *repo* (a path to the repository)
| *host* (the remote host for repositories of interest)

You can also override or modify many of the non-repository-specific settings.

There are three different types of repositories supported:

Local client repositories:

    In this case you are running the *overdue* command on the machine that is 
    the source of the backups.  You need to specify its *Assimilate config*.  
    You would also specify the *repo* if the config being backed up is not one 
    of your own, in which case you would specify the directory that contains 
    Assimilate's *config*.latest.nt file (typically 
    ~user/.local/share/assimilate).

Local server repositories:
    In this case you are running the *overdue* command on the machine that is 
    the destination of the backups.  Here you must not specify the *config*.  
    Instead, specify the *repo* as the destination directory for the 
    repository.

Remote repositories:
    In this case you are running the *overdue* command on a machine that is the 
    neither the source nor the destination of the backups.  Here you must 
    specify the *host*, which gives the name of the machine where a child 
    overdue process will be run.  The results from this run is then incorporated 
    into the results from the parent overdue process.  The overdue command must 
    be configured to run properly on this remote host.  Normally, the 
    *overdue.conf.nt* configuration is used for the remote overdue process, but 
    you can use *config* to specify a different config.  The name used for the 
    *assimilate* command on the remote host can be specified with *command*.

Here is an example config that contains three local client repositories 
(*earch*) and one remote repository (*sol*).  This would be a typical settings 
file for a user that is both running backups from his or her personal machine 
while also monitoring the repositories on a backups server.

.. code-block:: nestedtext

    to email: root@continuum.com
    from email: dumper@continuum.com
    max age: 36h
    colorscheme: dark
    message: {description}: {updated} ago{locked: (currently active)}{overdue: — PAST DUE}
    repositories:
        earth (cache):
            config: cache
            max age: 15m
        earth (home):
            config: home
        earth (root):
            config: root
            repo: /root/.local/share/assimilate
        sol:
            host: sol

*repositories* is a dictionary (a collection of key-value pairs) whose keys 
contain a brief description of each repository and whose values are also 
dictionaries that give the details for each repository.  The description of 
a repository is an arbitrary string but should be very concise and must be 
unique.  It is included in the email that is sent when problems occur to 
identify the backup source.  It is a good idea for it to contain both the host 
name and the source directory being backed up.

The dictionary for each repository may contain the following fields:

*config*:
    The name of a local *Assimilate* config.  Used primarily for local client 
    repositories, in which case it specifies a normal *Assimilate* config.  It 
    also can be specified for remote repositories, in which case it specifies 
    the name of an *Assimilate overdue* config.

*repo*:
    The path to the repository.  For local client repositories this is the path 
    to the *Assimilate* data directory, typically 
    ``~user/.local/share/assimilate``.  It is not necessary to specify this path 
    for configs in your own account.  For local server repositories this is the 
    path to the *Borg* repository.

    If a relative path is given, it is combined with *root* and the combination 
    specifies the absolute path to the repository.

*host*:
    The name of remote host for remote repositories.

*to_email*:
    An email address, an email is sent to this address if there is an issue.
    If given it overrides the shared *to_email*.

*max_age*:
    The maximum age.  If the backup is older it is considered over due.
    If given it overrides the shared *max_age*.  See the description of the 
    shared *max_age* (below) for details on how to specify the age.

*command*:
    The name used for the *assimilate* command on the remote host if it is not 
    *assimilate*.

In addition, there are some shared settings available:

*from_email*:
    Email address of the account running the checks.  This will be the sender 
    address on any email sent as a result of an over due back-up.

*to_email*:
    The default email address of the account monitoring the checks.  This will 
    be the recipient address on any email sent as a result of an over due 
    back-up.  Can be overridden in the individual repositories.

*root*:
    The directory used as the root when converting relative paths given in 
    *repositories* to absolute paths.  Must be an absolute path.  If given it is 
    combined with *repo* from the repository specification to form the path to 
    the repository.

*max_age*:
    The default maximum age.  It is used if a maximum age is not given for 
    a particular repository.

    The age can be specified using a number and a unit, where the unit may be:

    | **seconds**: *s* *sec* *second* *seconds*
    | **minutes**: *m* *min* *minute* *minutes*
    | **hours**: *h* *hr* *hour* *hours*
    | **days**: *d* *day* *days*
    | **weeks**: *w* *week* *weeks*
    | **months**: *M* *month* *months*
    | **years**: *y* *year* *years*

    Examples::

       max age: 15m
       max age: 36h
       max age: 36 hours
       max age: 36

    Hours are assumed if no units are given.

*colorscheme*:
    The color scheme of your terminal.  If your terminal uses a dark background, 
    specify *dark*.  May be *dark*, *light*, or *none*.  If *none*, the output 
    is not colored.

*message*:
    A template that specifies a one-line summary for each host.  The string may 
    contain keys within braces that are replaced upon output.  The following 
    keys are supported:

    | *description*: replaced by the description or the repository, a string.
    | *max_age*: replaced by the max_age field from the config file, a quantity.
    | *mtime*: replaced by modification time, a datetime object.
    | *age*: replaced by the number of hours since last update, a quantity.
    | *updated*: replaced by time since last update, a string (a humanized version of *age*).
    | *overdue*: is the back-up overdue, a boolean.
    | *locked*: is the back-up currently active, a boolean.

    The message is a Python formatted string, and so the various fields can include
    formatting directives.  For example:

    - strings than include field width and justification, ex. {host:>20}
    - quantities can include QuantiPhy_ formats, ex. {age:0.1phours}
    - datetimes can include Arrow_ formats, ex: {mtime:DD MMM YY @ H:mm A}
    - booleans can include Inform_ true/false strings: {overdue:PAST DUE!/current}

.. _QuantiPhy: https://quantiphy.readthedocs.io/en/stable/api.html#quantiphy.Quantity.format
.. _Arrow: https://arrow.readthedocs.io/en/latest/guide.html#supported-tokens
.. _Inform: https://inform.readthedocs.io/en/stable/api.html#inform.truth
.. _NestedText: https://nestedtext.org

To run the program interactively, type:

.. code-block:: bash

    $ assimilate overdue

It is also common to run *assimilate overdue* on a fixed schedule from cron. To 
do so, run:

.. code-block:: bash

    $ crontab -e

and add something like the following:

.. code-block:: text

    34 5 * * * assimilate overdue --quiet --mail

or:

.. code-block:: text

    34 5 * * * assimilate overdue --quiet --notify

to your crontab.

The first example runs *overdue* at 5:34 AM every day.  The use of the 
``--mail`` option causes *overdue* to send mail to the maintainer when backups 
are found to be overdue.

.. note::

    By default Linux machines are not configured to send email.  If you are 
    using the ``--mail`` option to *overdue* be sure that to check that it is 
    working.  You can do so by sending mail to your self using the *mail* or 
    *mailx* command.  If you do not receive your test message you will need to 
    set up email forwarding on your machine.  You can do so by installing and 
    configuring `PostFix as a null client
    <http://www.postfix.org/STANDARD_CONFIGURATION_README.html#null_client>`_.

The second example uses ``--notify``, which sends a notification if a back-up is 
overdue and there is not access to the tty (your terminal).

Alternately you can run *overdue* from cron.daily (described in the :ref:`root 
example <root example>`).


.. _server_overdue:

Checking for Overdue Backups from the Destination Host
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have a machine configured to be the host for your *Borg* repositories it 
is a good idea to configure a *cron* to run *overdue* and report any issues by 
mail.  Here is a typical config for such a scenario.  In this case all 
repositories are local server repositories that need not be created or managed 
by *Assimilate*.

.. code-block:: nestedtext

    to email: root@continuum.com
    from email: dumper@continuum.com
    max age: 12h
    repo root: /mnt/borg-backups/repositories
    colorscheme: dark
    message: {description}: {Age} ago{locked: (currently active)}{overdue: — PAST DUE}
    repositories:
        mercury (/):
            repo: mercury-root-root
        venus (/):
            repo: venus-root-root
        earth (/):
            repo: earth-root-root
        mars (/):
            repo: mars-root-root
        jupiter (/):
            repo: jupiter-root-root
        saturn (/):
            repo: saturn-root-root
        uranus (/):
            repo: uranus-root-root
        neptune (/):
            repo: neptune-root-root
        pluto (/):
            repo: pluto-root-root

The *overdue* command should be run daily, at which time `root@continuum.com` 
receives an email if there are any that are delinquent.


.. _client_overdue:

Checking for Overdue Backups from the Client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The *overdue* command can also be used to report on the status of your 
repositories from the machine that is the source of your backups.  One generally 
does this if you are backing up multiple *Borg* repository using local 
*Assimilate* configs.  This can be used to monitor your backups when you do not 
control the server and so cannot run *overdue* there.  For example:

.. code-block:: nestedtext

    to email: root@continuum.com
    from email: dumper@continuum.com
    max age: 36h
    colorscheme: dark
    message: {description}: {updated} ago{locked: (currently active)}{overdue: — PAST DUE}
    repositories:
        earth (cache):
            config: cache
            max age: 15m
        earth (home):
            config: home
        earth (root):
            config: root
            repo: /root/.local/share/assimilate

Notice that one repository, *root*, is not owned by you and so the files used to 
monitor the backup are not contained in your data directory for *Assimilate*.  
In this case you must explicitly specify the path to the appropriate 
*Assimilate* data directory and assure that the `root.latest.nt` file is 
readable.


.. _remote_overdue:

Running the Overdue Command Remotely
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are managing both one or more servers that hold multiple *Borg* 
repositories, you might want to get a report on the status of those repositories 
from your local machine.  This is done by configuring a remote repository.  For 
example:

.. code-block:: nestedtext

    max age: 36h
    repositories:
        earth (home):
            config: home
        sol:
            host: sol

In this example both a local client repository and a remote repository are 
configured.  In addition, since this command is only expected to run 
interactively, no email address are specified.


.. _monitoring_services:

Monitoring Services
-------------------

Various monitoring services are available on the web.  You can configure 
*Assimilate* to notify them when back-up jobs have started and finished.  These 
services allow you to monitor many of your routine tasks and assure they have 
completed recently and successfully.

There are many such services available and they are not difficult to add.  If 
the service you prefer is not currently available, feel free to request it on 
`Github <https://github.com/KenKundert/assimilate/issues>`_ or add it yourself 
and issue a pull request.

.. _cronhub:

CronHub.io
~~~~~~~~~~

When you sign up with `cronhub.io <https://cronhub.io>`_ and configure the 
health check for your *Assimilate* configuration, you will be given a UUID (a 32 
digit hexadecimal number partitioned into 5 parts by dashes).  Add that to the 
following setting in your configuration file:

.. code-block:: python

    cronhub_uuid = '51cb35d8-2975-110b-67a7-11b65d432027'

If given, this setting should be specified on an individual configuration.  It 
causes a report to be sent to *CronHub* each time an archive is created.  
A successful report is given if *Borg* returns with an exit status of 0 or 1, 
which implies that the command completed as expected, though there might have 
been issues with individual files or directories.  If *Borg* returns with an 
exit status of 2 or greater, a failure is reported.


.. _healthchecks:

HealthChecks.io
~~~~~~~~~~~~~~~

When you sign up with `healthchecks.io <https://healthchecks.io>`_ and configure 
the health check for your *Assimilate* configuration, you will be given a UUID 
(a 32 digit hexadecimal number partitioned into 5 parts by dashes).  Add that to 
the following setting in your configuration file:

.. code-block:: python

    healthchecks_uuid = '51cb35d8-2975-110b-67a7-11b65d432027'

If given, this setting should be specified on an individual configuration.  It 
causes a report to be sent to *HealthChecks* each time an archive is created.  
A successful report is given if *Borg* returns with an exit status of 0 or 1, 
which implies that the command completed as expected, though there might have 
been issues with individual files or directories.  If *Borg* returns with an 
exit status of 2 or greater, a failure is reported.

.. vim: set sw=4 sts=4 tw=80 fo=ntcqwa12rjo et spell nofoldenable :
