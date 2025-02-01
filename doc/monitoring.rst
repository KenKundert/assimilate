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
        max entries: 20

By default *Assimilate* uses the following defaults for *NTLog*:

.. code-block:: nestedtext

    logging:
        keep for: 1w
        max entries: 20
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

Both the *due* and *info* commands report on the status of the active config.


.. _assimilate_overdue:

Overdue
-------

*Assimilate* provides the *overdue* command that can be used to determine which 
of your repositories are overdue for backup.  Unlike the :ref:`due command 
<due>`, it is not limited to reporting on the active config and can even report 
on remote configs via *ssh*.  As such, *overdue* is generally used to present 
a summary of all of your backups.

It uses the :ref:`overdue setting <overdue setting>` to specify the desired 
configs, which is a composite setting that consists of:

| *max_age* (how old a repository must be to constitute failure)
| *sentinel_root* (default directory for sentinel files)
| *message* (a template for the message to be printed for each repository)
| *repositories* (details and overrides for each repository)

For each repository, you can specify the following repository-specific settings:

| *config* (name of the *Assimilate* config for the repository)
| *sentinel_dir* (a path to the directory containing the sentinel file)
| *host* (the remote host for repositories of interest)
| *max_age* (how old a repository must be to constitute failure)
| *notify* (email address -- mail is sent to this person upon failure)
| *command* (command used on remote hosts to generate an overdue report)

There are three different types of repositories supported:

Local client configs:

    In this case you are running the *overdue* command on the machine that 
    contains the files being backed up.  You need to specify its *Assimilate 
    config*.  You would also specify the *sentinel_dir* if the config being 
    backed up is not one of your own, in which case you would specify the 
    directory that contains Assimilate's *config*.latest.nt file (typically 
    ~user/.local/share/assimilate).  The sentinel directory combined with the 
    config name specifies the sentinel file: 
    ``❬sentinel_dir❭/❬config❭.latest.nt``, which must be readable.
    If *sentinel_dir* is a relative directory, it is relative to 
    *sentinel_root*.

Local server repositories:
    In this case you are running the *overdue* command on the machine that is 
    the destination of the backups.  Here you must not specify the *config*.  
    Instead, specify the *sentinel_dir* as the destination directory for the 
    *Borg* repository.

    One limitation of this type is that *overdue* reports on the status of the 
    repository, not on any specific config that deposits to the repository.  So, 
    for example, if two machines are depositing archives to the same repository, 
    and the backups on one machine begins failing, it will likely not be noticed 
    because the second machine will continue refreshing the repository.

Remote repositories:
    In this case you are running the *overdue* command on a remote machine that 
    contains one or more *Borg* repositories.  Here you must specify the *host*, 
    which gives the name of the machine where a child overdue process will be 
    run.  The results from this run is then incorporated into the results from 
    the parent overdue process.  The overdue command must be configured to run 
    properly on this remote host.
    The name used for the *assimilate* command on the remote host can be 
    specified with *command*.  The default *command* is ``assimilate overdue``.  
    You may also specify *command* as ``emborg-overdue`` to use *Emborg* to 
    query the repositories.

Here is an example config that contains three local client repositories 
(*earch*) and one remote repository (*sol*).  This would be a typical settings 
file for a user that is both running backups from his or her personal machine 
while also monitoring the repositories on a backups server.

.. code-block:: nestedtext

    notify: admin@solsystem.com
    overdue:
        max age: 36h
        message: {description}: {updated} ago{locked: (currently active)}{overdue: — PAST DUE}
        repositories:
            earth (cache):
                config: cache
                max age: 15m
            earth (home):
                config: home
            earth (root):
                config: root
                sentinel dir: /root/.local/share/assimilate
            sol:
                host: sol

*repositories* is a dictionary (a collection of key-value pairs) whose keys 
contain a brief description of each repository and whose values are also 
dictionaries that give the details for each repository.  The description of 
a repository is an arbitrary string but should be very concise and must be 
unique.  It is included in the email that is sent when problems occur to 
identify the backup source.  It is a good idea for it to contain both the host 
name and the name of the config or the source directory being backed up.

The dictionary for each repository may contain the following fields:

*config*:
    The name of a local *Assimilate* config.  Used primarily for local client 
    repositories, in which case it specifies a normal *Assimilate* config.  It 
    also can be specified for remote repositories.

*sentinel_dir*:
    The path to the repository.  For local client configs this is the path to 
    the *Assimilate* data directory, typically 
    ``~user/.local/share/assimilate``.  It is not necessary to specify this path 
    for configs in your own account.  For local server repositories this is the 
    path to a *Borg* repository.

    If a relative path is given, it is combined with *sentinel_root* and the 
    combination specifies the absolute path to the repository.

*host*:
    The name of remote host for remote repositories.

*notify*:
    An email address, an email is sent to this address if there is an issue.
    If given it overrides the shared :ref:`notify`.

*max_age*:
    The maximum age.  If the backup is older it is considered over due.
    If given it overrides the shared *max_age*.  See the description of the 
    shared *max_age* (below) for details on how to specify the age.

*command*:
    The name used for the *assimilate* command on the remote host if it is not 
    *assimilate*.

In addition, there are some shared settings available:

*sentinel_root*:
    The directory used as the root when converting a relative path given in 
    *sentinel_dir* to an absolute path.  Must be an absolute path.  If given it 
    is combined with *sentinel_dir* from the repository specification to form 
    the path to the repository.

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

*locked_color*:
    The text color to use for repositories that are currently locked.  Choose 
    from:
    ``'black``, ``'red``, ``'green``, ``'yellow``, ``'blue``, ``'magenta``,
    ``'cyan``, ``'white``, or ``'none``.
    The default is ``'magenta``.

*overdue_color*:
    The text color to use for repositories that are currently locked.  Choose 
    from:
    ``'black``, ``'red``, ``'green``, ``'yellow``, ``'blue``, ``'magenta``,
    ``'cyan``, ``'white``, or ``'none``.
    The default is ``'red``.

*current_color*:
    The text color to use for repositories that are currently locked.  Choose 
    from:
    ``'black``, ``'red``, ``'green``, ``'yellow``, ``'blue``, ``'magenta``,
    ``'cyan``, ``'white``, or ``'none``.
    The default is ``'green``.


To run the program interactively, type:

.. code-block:: bash

    $ assimilate overdue

It is also common to run *assimilate overdue* on a fixed schedule from cron. To 
do so, run:

.. code-block:: bash

    $ crontab -e

and add something like the following:

.. code-block:: text

    34 5 * * * assimilate --quiet overdue --mail

or:

.. code-block:: text

    34 5 * * * assimilate --quiet overdue --notify

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

    notify: root@continuum.com
    notify from: dumper@continuum.com
    overdue:
        max age: 12h
        sentinel_root: /mnt/borg-backups/repositories
        colorscheme: dark
        message: {description}: {Age} ago{locked: (currently active)}{overdue: — PAST DUE}
        repositories:
            mercury (/):
                sentinel dir: mercury-root-root
            venus (/):
                sentinel dir: venus-root-root
            earth (/):
                sentinel dir: earth-root-root
            mars (/):
                sentinel dir: mars-root-root
            jupiter (/):
                sentinel dir: jupiter-root-root
            saturn (/):
                sentinel dir: saturn-root-root
            uranus (/):
                sentinel dir: uranus-root-root
            neptune (/):
                sentinel dir: neptune-root-root
            pluto (/):
                sentinel dir: pluto-root-root

The *overdue* command should be run daily, at which time `root@continuum.com` 
receives an email if there are any that are delinquent.

In this example the *overdue* command is expected to run from *cron* with any 
delinquent backups reported by email.  The *crontab* entry might look something 
like this::

    0 8 * * *  assimilate --quiet overdue --mail



.. _client_overdue:

Checking for Overdue Backups from the Client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The *overdue* command can also be used to report on the status of your 
repositories from the machine that is the source of your backups.  One generally 
does this if you are backing up multiple *Borg* repository using local 
*Assimilate* configs.  This can be used to monitor your backups when you do not 
control the server and so cannot run *overdue* there.  For example:

.. code-block:: nestedtext

    notifier: notify-send -u critical {prog_name} "{msg}"
    overdue:
        max age: 36h
        message: {description}: {updated} ago{locked: (currently active)}{overdue: — PAST DUE}
        repositories:
            earth (cache):
                config: cache
                max age: 15m
            earth (home):
                config: home
            earth (root):
                config: root
                sentinel_dir: /root/.local/share/assimilate

Notice that one config, *root*, is not owned by you and so the files used to 
monitor the backup are not contained in your data directory for *Assimilate*.  
In this case you must explicitly specify the path to the appropriate 
*Assimilate* data directory and assure that the `root.latest.nt` file is 
readable.

In this example the *overdue* command is expected to run from *cron* with any 
delinquent backups reported with an on-screen notification.  The *crontab* entry 
might look something like this::

    12 * * * *  assimilate --quiet overdue --notify


.. _remote_overdue:

Running the Overdue Command Remotely
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are managing both one or more servers that hold multiple *Borg* 
repositories, you might want to get a report on the status of those repositories 
from your local machine.  This is done by configuring a remote repository.  For 
example:

.. code-block:: nestedtext

    overdue:
        max age: 36h
        repositories:
            earth (home):
                config: home
            sol:
                host: sol
                command: emborg-overdue

In this example both a local client repository and a remote repository are 
configured.  In addition, since this command is only expected to run 
interactively, no email address is needed.  The *sol* host is still using 
*Emborg* and so the *command* field was specified.


.. _monitoring_services:

Monitoring Services
-------------------

Various monitoring services are available on the web.  You can configure 
*Assimilate* to notify them when back-up jobs have started and finished.  These 
services allow you to monitor many of your routine tasks and assure they have 
completed recently and successfully.

There are many such services available and they are not difficult to add.  There 
is built-in support for a few common services.  For others you can use the 
*custom* service.  It can handle most web-based services.  If the service you 
prefer is not currently available and cannot be supported as a custom service, 
feel free to request it on `Github 
<https://github.com/KenKundert/assimilate/issues>`_ or add it yourself and issue 
a pull request.

.. _custom monitoring service:

Custom
~~~~~~

You can configure *Assimilate* to send custom web-based messages to your 
monitoring service when backing up.  You can configure four different types of 
messages: *start*, *success*, *failure* and *finish*.  These messages are sent 
as follows:

start:
    When the backup begins.

success:
    When the backup completes, but only if there were no errors.

failure:
    When the backup completes, but only if there were errors.

finish:
    When the backup completes.

Generally you do not configure all of them as they are redundant.  Specifically, 
you would configure *success* and *failure* together, or you would configure 
*finish* in such a way as to indicate whether the backup succeeded.  For 
example, here is how one might configure HealthCheck.io using the custom 
service:

.. code-block:: nestedtext

    monitoring:
        custom:
            id: 51cb35d8-2975-110b-67a7-11b65d432027
            url: https://hc-ping.com/{id}
            start: {url}/start
            success: {url}/0
            failure:
                url: {url}/fail
                post:
                    > CONFIG: {config}
                    > EXIT STATUS: {status}
                    > ERROR: {error}
                    >
                    > STDOUT:
                    > {stdout}
                    >
                    > STDERR:
                    > {stderr}

In this example *start*, *success* and *failure* were configured. With each, you 
can simply specify a URL, or you can specify key-value pairs that control the 
message that is sent.  Furthermore, you can specify *id* and *url* up-front and 
simply refer to them in when configuring your message.  For example, *start* is 
specified as ``{url}/start``.  Here ``{url}`` is replaced by the value you 
specified earlier for *url*.  Similarly, *success* is specified only by its URL, 
``{url}/0``.  But, *fail* is given as a collection of key-value pairs.  Three 
keys are allowed: *url*, *params*, and *post*.  *url* is required, but the other 
two are optional.  *params* is a collection of key-value pairs.  These will be 
passed in the URL as parameters.  Specify *params* only if your service requires 
them.  *post* indicates that the *post* method is to be used, otherwise the 
*get* method is used.  The value of post may be a string, or a collection of 
key-value pairs.  You would specify both *params* and *post* to conform with the 
requirements of your service.

When constructing your messages you can insert placeholders that are replaced 
before sending the message.  The available placeholders are:

config:
    The name of the config being backed up.

status:
    The exit status of the *Borg* process performing the backup.

error:
    A short message that describes error that occurred during the backup if 
    appropriate.

stdout:
    The text sent to the standard output by the *Borg* process performing the 
    backup.

stderr:
    The text sent to the standard error output by the *Borg* process performing 
    the backup.

id:
    The value specified as *id*.

url:
    The value specified as *url*.

success:
    A Boolean `truth object <https://inform.readthedocs.io/en/stable/user.html#truth>`_
    that evaluates to *yes* if *Borg* returned with an exit status of 0 or 1, 
    which implies that the command completed as expected, though there might 
    have been issues with individual files or directories.  If *Borg* returns 
    with an exit status of 2 or greater, *success* evaluates to *no*.  However, 
    you can specify different values by specifying a format string.  For 
    example, the above example specifies both *success* and *failure*, but this 
    could be collapsed to using only *finish* by using *success* to modify the 
    URL used to communicate the completion message.  In this example, the URL is 
    specified as ``{url}/{success:0/fail}``.  Here ``{success:0/fail}`` 
    evaluates to ``0`` if *Borg* succeeds and ``fail`` otherwise.

.. code-block:: nestedtext

    monitoring:
        custom:
            id: 51cb35d8-2975-110b-67a7-11b65d432027
            url: https://hc-ping.com/{id}
            start: {url}/start
            finish:
                url: {url}/{success:0/fail}
                post:
                    > CONFIG: {config}
                    > EXIT STATUS: {status}
                    > ERROR: {error}
                    >
                    > STDOUT:
                    > {stdout}
                    >
                    > STDERR:
                    > {stderr}

.. _cronhub:

CronHub.io
~~~~~~~~~~

When you sign up with `cronhub.io <https://cronhub.io>`_ and configure the 
health check for your *Assimilate* configuration, you will be given a UUID (a 32 
digit hexadecimal number partitioned into 5 parts by dashes).  Add that to the 
following setting in your configuration file:

.. code-block:: nestedtext

    monitoring:
        cronhub.io:
            uuid: 51cb35d8-2975-110b-67a7-11b65d432027

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

.. code-block:: nestedtext

    monitoring:
        healthchecks.io:
            uuid: 51cb35d8-2975-110b-67a7-11b65d432027

If given, this setting should be specified on an individual configuration.  It 
causes a report to be sent to *HealthChecks* each time an archive is created.  
A successful report is given if *Borg* returns with an exit status of 0 or 1, 
which implies that the command completed as expected, though there might have 
been issues with individual files or directories.  If *Borg* returns with an 
exit status of 2 or greater, a failure is reported.

.. vim: set sw=4 sts=4 tw=80 fo=ntcqwa12rjo et spell nofoldenable :
