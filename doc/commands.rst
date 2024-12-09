.. include:: links.rst

.. _commands:

========
Commands
========

You invoke *Assimilate* from your shell by entering a line of the form:

.. code-block:: bash

    $ assimilate [global-options] <command> [command-options]

Details about the options and commands can be accessed with:

.. code-block:: bash

    $ assimilate help

or:

.. code-block:: bash

    $ assimilate help <command>

The available commands are:

    :borg:        :ref:`run a raw borg command <borg>`
    :break-lock:  :ref:`breaks the repository and cache locks <break-lock>`
    :check:       :ref:`checks the repository and its archives <check>`
    :compact:     :ref:`compact segment files in the repository <compact>`
    :compare:     :ref:`compare local files with those in an archive <compare>`
    :configs:     :ref:`list available backup configurations <configs>`
    :create:      :ref:`create an archive of the current files <create>`
    :delete:      :ref:`delete an archive currently contained in the repository <delete>`
    :diff:        :ref:`show the differences between two archives <diff>`
    :due:         :ref:`days since last backup <due>`
    :extract:     :ref:`recover file or files from archive <extract>`
    :help:        :ref:`give information about commands or other topics <assimilate_help>`
    :info:        :ref:`print information about a backup <info>`
    :list:        :ref:`list the files contained in an archive <list>`
    :log:         :ref:`print logfile for the last assimilate run <log>`
    :mount:       :ref:`mount a repository or archive <mount>`
    :overdue:     :ref:`show status of known repositories <overdue>`
    :prune:       :ref:`prune the repository of excess archives <prune>`
    :repo-create: :ref:`create the repository <repo-create>`
    :repo-list:   :ref:`list the archives currently contained in the repository <repo-list>`
    :repo-space:  :ref:`manage the amount of space kept in reserve <repo-space>`
    :restore:     :ref:`recover file or files from archive in place <restore>`
    :settings:    :ref:`show settings of chosen configuration <settings>`
    :umount:      :ref:`un-mount a previously mounted repository or archive <umount>`
    :version:     :ref:`display assimilate version <version>`

These commands are described in more detail below.  Not everything is described 
here. Run ``assimilate help <cmd>`` for the details.


.. _exit status:

Exit Status
===========

*Assimilate* returns with an exit status of 0 if it completes without issue.  It 
returns with an exit status of 1 if was able to terminate normally but some 
exceptional condition was encountered along the way.  For example, if the 
:ref:`compare <compare>` or :ref:`diff <diff>` detects a difference or if 
:ref:`due <due>` command detects the backups are overdue, a 1 is returned.  In 
addition, 1 is returned if *Borg* detects an error but is able to complete 
anyway. However, if *Assimilate* or *Borg* suffers errors and cannot complete, 
2 is returned.


Command Aliases
===============

You can change the names of commands or define new versions of commands with 
different default behavior.  To do so you would specify the desired mappings in 
the :ref:`shared configuration file <shared_settings>`.  Here is an example:

.. code-block:: nestedtext

    # command aliases
    command aliases:
        create: backup
        break-lock: breaklock
        repo-list:
            - archives
            - recent --last 20
        list: files
        umount: unmount

*command aliases* is a collection of key-value pairs.  The key proceed the colon 
(:) and the value follows it.  The first two given are simple aliases.  The 
first defines *backup* as an alias for *create* and the second defines 
*breaklock* as an alias for *break-lock*.  *repo-list* gets two aliases, the 
first is a simple alias *archives*.  The second, *recent*,  modifies *repo-list* 
so that it only lists the five most recent archives.


Command Line Options
====================

Through out this documentation full command line option names are used.  
However, in most cases shorter versions of the names are available and can be 
used.

For example, if you run `assimilate help compare` you would see that the 
available arguments are::

    -a, --archive <archive>     name of the archive to compare against
    -A, --after <date_or_age>   use first archive newer than given
    -B, --before <date_or_age>  use first archive older than given
    -i, --interactive           perform an interactive comparison

The first three arguments take a value, the last does not.

Imagine that you want to specify *--after* with *<date_or_age>* being `1w`.  You 
could do so in any of the following ways::

    --after 1w
    --after=1w
    -A 1w
    -A1w

You can specify *--interactive* using either of::

    --interactive
    -a


.. _selecting_an_archive:

Selecting an Archive
====================

Many commands operate on a single existing archive, and you can select which 
archive that is.  If you do not, you generally operate on the one most recently 
created.  Otherwise there are a variety of methods you can use to select the one 
you want.

The first approach is to specify the archive by ID, by name or by index.  You 
find the ID, name and index name using the :ref:`repo-list command <repo-list>`.  
For example:

.. code-block:: bash

    $ assimilate repo-list
    6  aid:6b07a29c  home-2024-12-03T10:16:25   2024-12-03 10:16 AM (4 days ago)
    5  aid:df69bd51  home-2024-12-03T22:48:04   2024-12-03 10:48 PM (4 days ago)
    4  aid:84b548d8  home-2024-12-04T11:12:59   2024-12-04 11:59 AM (3 days ago)
    3  aid:ba78ead6  home-2024-12-04T13:50:55   2024-12-04 1:50 PM (3 days ago)
    2  aid:e31a180f  home-2024-12-05T07:41:46   2024-12-05 7:41 AM (2 days ago)
    1  aid:f8b21edc  home-2024-12-06T12:03:20   2024-12-06 12:03 PM (a day ago)
    0  aid:f80b1d86  home-2024-12-07T06:50:30   2024-12-07 6:50 AM (3 hours ago)

The archives are described using four columns, the first is the index, the 
second is the ID, the third is the name, and the fourth is the date the archive 
was created.  The index is only shown by the *repo-list* command no command line 
arguments are given that restrict or expand the list of archives shown, so the 
first column may be missing.

In this example the names are all unique, so you can use name to identify the 
desired archive.  Otherwise you would have to use the index or ID.

Here is an example of specifying an ID to the *list* command.  The ID is 
actually the string of 8 hex characters.  The *aid:* prefix is used to indicate 
your are specifying an archive ID.

.. code-block:: bash

    $ assimilate list --archive aid:6b07a29c

And here is an example of selecting the same archive, but this time using its 
name:

.. code-block:: bash

    $ assimilate list --archive home-2024-12-03T10:16:25

Finally, here is an example of selecting the same archive, but this time using 
its index.  All archives associated with the chosen configuration have indices 
assigned in order starting from the youngest, which is 0.

.. code-block:: bash

    $ assimilate list --archive 6

You can also specify the archive by date and time or by age.  To do so you use 
the *--before* or *--after* command line options.  With *--before* the oldest 
archive that is younger than specified date and time is used.  With *--after* 
the youngest archive that is older than specified date and time is used.

Here are examples where the archive is selected by date or date and time.
If the time is not given, it is taken to be midnight.

.. code-block:: bash

    $ assimilate restore --before 2021-04-01 resume.doc
    $ assimilate restore --after 2021-04-01T18:30 resume.doc

Alternately you can select the archive using its age:

    $ assimilate restore --before 3d  resume.doc
    $ assimilate restore --after 1w  resume.doc

In this case 3d means 3 days. You can use s, m, h, d, w, M, and y to
represent seconds, minutes, hours, days, weeks, months, and years.

For conformation, the ID and name of the archive selected is displayed if it is 
chosen by date, age, or index.


.. _assimilate_commands:

Commands
========

You run a command in *Assimilate* by specifying the name of the command or its 
alias after any global options.  For example, to run the *list* command, you 
might use::

    $ assimilate --config=rsync list

The following global options are supported::

    -c <cfgname>, --config <cfgname>  Specifies the configuration to use.
    -d, --dry-run                     Run Borg in dry run mode.
    -h, --help                        Output basic usage information.
    -m, --mute                        Suppress all output.
    -n, --narrate                     Send Assimilate and Borg narration to stderr.
    -q, --quiet                       Suppress optional output.
    -r, --relocated                   Acknowledge that repository was relocated.
    -v, --verbose                     Make Borg more verbose.
    --no-log                          Do not create log file.

.. _borg:

Borg
----

Runs raw *Borg* commands. Before running the passphrase or passcommand is set.  
Also, if ``@repo`` is found on the command line, it is replaced by the path to 
the repository.

.. code-block:: bash

    $ assimilate borg key export @repo key.borg
    $ assimilate borg repo-list @repo

*Assimilate* runs the *Borg* command from :ref:`working_dir` if it is specified 
and ``/`` if not.


.. _break-lock:

Break Lock
----------

This command breaks the repository and cache locks. Use carefully and only if no 
*Borg* process (on any machine) is trying to access the cache or the repository.

.. code-block:: bash

    $ assimilate break-lock


.. _check:

Check
-----

Check the integrity of the repository and its archives.  The most recently 
created archive is checked if one is not specified unless ``--all`` is given, in 
which case all archives are checked.

The ``--repair`` option attempts to repair any damage found.  Be aware that the 
--repair option is considered a dangerous operation that might result in the 
complete loss of corrupt archives.  It is recommended that you create a backup 
copy of your repository and check your hardware for the source of the corruption 
before using this option.


.. _compact:

Compact
-------

This command frees repository space by compacting segments.

Use this regularly to avoid running out of space, however you do not need to it 
after each *Borg* command. It is especially useful after deleting archives, 
because only compaction really frees repository space.

If you set :ref:`compact_after_delete` *Assimilate* automatically runs this 
command after every use of the :ref:`delete <delete>` and :ref:`prune <prune>` 
commands.


.. _compare:

Compare
-------

Reports and allows you to manage the differences between your local files and 
those in an archive.  The base command simply reports the differences:

.. code-block:: bash

    $ assimilate compare

The ``--interactive`` option allows you to manage those differences.  
Specifically, it will open an interactive file comparison tool that allows you 
to compare the contents of your files and copy differences from the files in the 
archive to your local files:

.. code-block:: bash

    $ assimilate compare --interactive

You can select which archive you wish to compare against using the *--archive*, 
*--before* or *--after* command line arguments.  *--archive* is used to select 
the archive by ID, name, or index.  *--before* and *--after* select the archive 
by date, date and time, or age.  This is explained in 
:ref:`selecting_an_archive`.  If you do not specify an archive, the one most 
recently created is used.

Here are examples of the ways you can specify which archive to compare against:

.. code-block:: bash

    $ assimilate compare --archive continuum-2025-04-01T12:19:58 backups
    $ assimilate compare --archive aid:6b07a29c
    $ assimilate compare --archive 4
    $ assimilate compare --before 2021-04-01 backups
    $ assimilate compare --before 2021-04-01T18:30 backups
    $ assimilate compare --after 2021-04-01 backups
    $ assimilate compare --after 2021-04-01T18:30 backups
    $ assimilate compare --before 1w
    $ assimilate compare --after 1w

You can specify a path to a file or directory to compare, if you do not you will 
compare the files and directories of the current working directory.

.. code-block:: bash

    $ assimilate compare tests
    $ assimilate compare ~/bin

This command uses external tools to view and manage the differences.  Before it 
can be used it must be configured to use these tools, which is done with the
:ref:`manage_diffs_cmd` and :ref:`report_diffs_cmd` settings.  In addition, the 
:ref:`default_mount_point` must be configured.  The :ref:`manage_diffs_cmd` is 
used if the ``--interactive`` (or ``-i``) option is given, and 
:ref:`report_diffs_cmd` otherwise.  However, if only one is given it is used in 
both cases.  So, if you find that you only want to use the interactive tool to 
view and manage your differences, you can simply not specify 
:ref:`report_diffs_cmd`, which would eliminate the need to specify the ``-i`` 
option.

The command operates by mounting the desired archive, performing the comparison, 
and then un-mounting the directory. Problems sometimes occur that can result in 
the archive remaining mounted.  In this case you will need to resolve any issues 
that are preventing the unmounting, and then explicitly run the :ref:`umount 
command <umount>` before you can use this *Borg* repository again.

This command differs from the :ref:`diff command <diff>` in that it compares 
local files to those in an archive where as :ref:`diff <diff>` compares the 
files contained in two archives.


.. _configs:

Configs
-------

List the available backup configurations urations using:

.. code-block:: bash

    $ assimilate configs

To run a command on a specific configuration, add --config=<cfg> or -c cfg 
before the command. For example:

.. code-block:: bash

    $ assimilate -c home create


.. _create:

Create
------

This creates an archive in an existing repository. An archive is a snapshot of 
your files as they currently exist.  Borg is a de-duplicating backup program, so 
only the changes from the already existing archives are saved.

.. code-block:: bash

    $ assimilate create

Before creating your first archive, you must use the :ref:`repo-create 
<repo-create>` command to create your repository.

This is the default command, so you can create an archive with simply:

.. code-block:: bash

    $ assimilate

If the backup seems to be taking a long time for no obvious reason, run the 
backup in verbose mode:

.. code-block:: bash

    $ assimilate -v create

This can help you understand what is happening.


.. _delete:

Delete
------

Delete one or more archives currently contained in the repository:

.. code-block:: bash

    $ assimilate delete continuum-2025-12-05T19:23:09

If no archive is specified, the latest is deleted.

The disk space associated with deleted archives is not reclaimed until
the :ref:`compact <compact>` command is run.  You can specify that a compaction 
is performed as part of the deletion by setting :ref:`compact_after_delete`.  If 
set, the ``--fast`` flag causes the compaction to be skipped.  If not set, the 
``--fast`` flag has no effect.

Specifying ``--repo`` results in the entire repository being deleted.
Unlike with *borg* itself, no warning is issued and no additional conformation 
is required.


.. _diff:

Diff
----

Shows the differences between two archives:

.. code-block:: bash

    $ assimilate diff continuum-2025-12-05T19:23:09 continuum-2025-12-04T17:41:28

You can constrain the output listing to only those files in a particular 
directory by adding that path to the end of the command:

.. code-block:: bash

    $ assimilate diff continuum-2025-12-05T19:23:09 continuum-2025-12-04T17:41:28 .

This command differs from the :ref:`compare command <compare>` in that it only 
reports a list of files that differ between two archives, whereas :ref:`compare 
<compare>` shows how local files differ from those in an archive and can show 
you the contents of those files and allow you interactively copy changes from 
the archive to your local files.


.. _due:

Due
---

When run with no options it indicates when the last backup, squeeze and check 
operations were performed.  A backup operation is the running of the 
:ref:`create <create>` command.  A squeeze operation is the running of both the 
:ref:`prune <prune>` and :ref:`compact <compact>` commands.  The time to the 
latest squeeze operation is the time to the older of the most recent *prune* or 
*compact* commands.  For example:

.. code-block:: bash

    $ assimilate due
    home backup completed 11 hours ago.
    home compact never run.
    home check completed 11 hours ago.

Adding the --backup-days option, --squeeze-days, or --check-days  results in the 
message only being printed if the backup, squeeze, or check has not been 
performed within the specified number of days.  If more than one are specified 
and violated, only the backup violation is reported as it is considered the most 
urgent.

Adding the --email option results in the message being sent to the specified 
address rather than printed.  This allows you to run the :ref:`due <due>` 
command from a cron script in order to send your self reminders to do a backup 
if one has not occurred for a while.

.. code-block:: bash

    $ assimilate --no-log due --backup-days 1 --backup-days 7 --check-days 7 --email me@mydomain.com

You can specify a specific message to be printed with --message. In this case, 
the following replacements are available:

    {action}:
        Replaced with the type of operation reported on.  It is either *backup*, 
        *squeeze* or *check*.
    {config}:
        Replaced with the name of the configuration being reported on.
    {cmd}:
        Replaced with the name of the command being reported on.  It can be 
        *create*, *prune*, *compact* or *check*.  It will be *create* if 
        reporting on a backup operation, and either *prune* or *compact* if 
        reporting on a squeeze operation, depending on which is older, and 
        *check* if reporting on a check operation.
    {days}:
        Replaced by the number of days since the last backup or squeeze.
        You can add floating-point format codes to specify the resolution used.  
        For example: {days:.1f}.
    {elapsed}:
        Replaced with a humanized description of how long it has been since the 
        last backup.

So ``--message '{elapsed} since last {action} of {config}.'`` might produce 
something like this:

.. code-block:: text

    12 hours since last backup of home.

With composite configurations the message is printed for each component config 
unless --oldest is specified, in which case only the oldest is displayed.


.. _extract:

Extract
-------

You extract a file or directory from an archive using:

.. code-block:: bash

    $ assimilate extract home/shaunte/bin

Use :ref:`list` to determine what path you should specify to identify the 
desired file or directory.  You can specify more than one path. Usually, they 
will be paths that are relative to ``/``, thus the paths should look like 
absolute paths with the leading slash removed.  The paths may point to 
directories, in which case the entire directory is extracted.  It may also be 
a glob pattern, in which case it should be quoted to protect it from the shell.

You can select which archive you wish to extract from using the *--archive*, 
*--before* or *--after* command line arguments.  *--archive* is used to select 
the archive by ID, name, or index.  *--before* and *--after* select the archive 
by date, date and time, or age.  This is explained in 
:ref:`selecting_an_archive`.  If you do not specify an archive, the one most 
recently created is used.

Here are examples of the ways you can specify which archive to extract from:

.. code-block:: bash

    $ assimilate extract --archive continuum-2025-04-01T12:19:58 backups home/shaunte/bin
    $ assimilate extract --archive aid:6b07a29c home/shaunte/bin
    $ assimilate extract --archive 4 home/shaunte/bin
    $ assimilate extract --before 2021-04-01 backups home/shaunte/bin
    $ assimilate extract --before 2021-04-01T18:30 backups home/shaunte/bin
    $ assimilate extract --after 2021-04-01 backups home/shaunte/bin
    $ assimilate extract --after 2021-04-01T18:30 backups home/shaunte/bin
    $ assimilate extract --before 1w home/shaunte/bin
    $ assimilate extract --after 1w home/shaunte/bin

The extracted files are placed in the current working directory with
the original hierarchy. Thus, the above commands create the directory:

.. code-block:: text

    ./home/shaunte/bin

See the :ref:`restore <restore>` command as an alternative to *extract*.  It 
replaces the existing files rather than simply copying them into the current 
directory.


.. _assimilate_help:

Help
----

Show available commands and help topics with:

.. code-block:: bash

    $ assimilate help

You can ask for help on a specific command or topic with:

.. code-block:: bash

    $ assimilate help <topic>

For example:

.. code-block:: bash

    $ assimilate help extract


.. _info:

Info
----

This command prints out the locations of important files and directories.

.. code-block:: bash

    $ assimilate info

You can also get information about a particular archive.

.. code-block:: bash

    $ assimilate info home-2022-11-03T23:07:25


.. _log:

Log
---

Show the log from the previous run.

.. code-block:: bash

    $ assimilate log

Most commands save a log file, but some do not.
Specifically,
:ref:`configs <configs>`,
:ref:`due <due>`,
:ref:`help <assimilate_help>`,
:ref:`log <log>`,
:ref:`settings <settings>` and
:ref:`version <version>` do not.
Additionally, no command will save a log file if the ``--no-log`` command line 
option is specified.  If you need to debug a command that does not normally 
generate a log file and would like the extra detail that is normally included in 
the log, specify the ``--narrate`` command line option.


.. _list:

List
--------

Once a backup has been performed, you can list the files available in your 
archive using:

.. code-block:: bash

    $ assimilate list

You can specify a path.  If so, the files listed are those contained within that 
path.  For example:

.. code-block:: bash

    $ assimilate list .
    $ assimilate list -R .

The first command lists the files in the archive that were originally contained 
in the current working directory.  The second lists the files that were in 
specified directory and any sub directories.

You can select which archive you wish to list using the *--archive*, *--before* 
or *--after* command line arguments.  *--archive* is used to select the archive 
by ID, name, or index.  *--before* and *--after* select the archive by date, 
date and time, or age.  This is explained in :ref:`selecting_an_archive`.  If 
you do not specify an archive, the one most recently created is used.

Here are examples of the ways you can specify which archive to list:

.. code-block:: bash

    $ assimilate list --archive continuum-2025-04-01T12:19:58 backups
    $ assimilate list --archive aid:6b07a29c
    $ assimilate list --archive 4
    $ assimilate list --before 2021-04-01 backups
    $ assimilate list --before 2021-04-01T18:30 backups
    $ assimilate list --after 2021-04-01 backups
    $ assimilate list --after 2021-04-01T18:30 backups
    $ assimilate list --before 1w
    $ assimilate list --after 1w

The *list* command provides a variety of sorting and formatting options. The 
formatting options are under the control of the :ref:`list_formats` setting.  
For example:

.. code-block:: bash

    $ assimilate list

This outputs the files in the order and with the format produced by Borg.
If a line is green if the corresponding file is healthy, and if red it is broken 
(see `Borg list command
<https://borgbackup.readthedocs.io/en/stable/usage/list.html#description>`_ for 
more information on broken files).

.. code-block:: bash

    $ assimilate list -l
    $ assimilate list -n

These use the Borg order but change the amount of information shown.  With 
``-l`` the *long* format is used, which by default contains the size, the date, 
and the path. With ``-n`` the *name* is used, which by default contains 
only the path.

Finally:

.. code-block:: bash

    $ assimilate list -S
    $ assimilate list -D

The first sorts the files by size. It uses the *size* format, which by default 
contains only the size and the path.  The second sorts the files by modification 
date. It uses the *date* format, which by default contains the day, date, time 
and the path.  More choices are available; run ``assimilate help manifest`` for 
the details.


.. _mount:

Mount
-----

Once a backup has been performed, you can mount it and then look around as you 
would a normal read-only filesystem.

::

    $ assimilate mount backups

In this example, *backups* acts as a mount point. If it exists, it must be 
a directory. If it does not exist, it is created.

If you do not specify a mount point, the value of :ref:`default_mount_point` 
setting is used if set.

You can select which archive you wish to mount using the *--archive*, *--before* 
or *--after* command line arguments.  *--archive* is used to select the archive 
by ID, name, or index.  *--before* and *--after* select the archive by date, 
date and time, or age.  This is explained in :ref:`selecting_an_archive`.  If 
you do not specify an archive, the one most recently created is used.

Here are examples of the ways you can specify which archive to mount:

.. code-block:: bash

    $ assimilate mount --archive continuum-2025-04-01T12:19:58 backups
    $ assimilate mount --archive aid:6b07a29c
    $ assimilate mount --archive 4
    $ assimilate mount --before 2021-04-01 backups
    $ assimilate mount --before 2021-04-01T18:30 backups
    $ assimilate mount --after 2021-04-01 backups
    $ assimilate mount --after 2021-04-01T18:30 backups
    $ assimilate mount --before 1w
    $ assimilate mount --after 1w

You can mount all the available archives:

.. code-block:: bash

    $ assimilate mount --all backups

You will need to un-mount the repository or archive when you are done with it.  
To do so, use the :ref:`umount <umount>` command.


.. _overdue:

Overdue
-------

When configured this command shows you when your archives were last backed up.  
You can include remote configurations, so this command can be used to monitor 
configurations where neither the source files nor the destination repository are 
local.

This command and its configuration are describe in :ref:`monitoring <assimilate_overdue>`.


.. _prune:

Prune
-----

Prune the repository of excess archives.  You can use the :ref:`keep_within`, 
:ref:`keep_last`, :ref:`keep_minutely`, :ref:`keep_hourly`, :ref:`keep_daily`, 
:ref:`keep_weekly`, :ref:`keep_monthly`, and :ref:`keep_yearly` settings to 
control which archives should be kept. At least one of these settings must be 
specified to use :ref:`prune <prune>`:

.. code-block:: bash

    $ assimilate prune

The *prune* command unlinks archives that are no longer needed as determined by 
the prune rules.  However, the disk space is not reclaimed until the 
:ref:`compact <compact>` command is run.  You can specify that a compaction is 
performed as part of the prune by setting :ref:`compact_after_delete`.  If set, 
the ``--fast`` flag causes the compaction to be skipped.  If not set, the 
``--fast`` flag has no effect.


.. _repo-create:

Repo Create
-----------

Initializes a Borg repository. This must be done before you create your first 
archive.

.. code-block:: bash

    $ assimilate repo-create


.. _repo-list:

Repo List
---------

List available archives in the repository.

.. code-block:: bash

    $ assimilate repo-list


.. _repo-space:

Repo Space
----------

This command manages reserved space in a repository.

Borg can not work in disk-full conditions (cannot lock a repo and thus cannot 
run prune, delete, or compact operations to free disk space).  To avoid running 
into situations like this, you can put some objects into a repository that take 
up some disk space. If you ever run into a disk-full situation, you can free 
that space to allow *Borg* to run prune, delete, and compact operations.  After 
that, don’t forget to reserve space again, in case you run into a similar 
situation in the future.

Reserve space with:

.. code-block:: bash

    $ assimilate repo-space --reserve 1GiB

You can specify the desired amount of space using SI or binary scale factors and 
may include the units (ex. 1GB, 100MiB).  The actual amount of space reserved 
will be a multiple of 64 MiB.

Free space with:

.. code-block:: bash

    $ assimilate repo-space --free


.. _restore:

Restore
-------

This command is very similar to the :ref:`extract <extract>` command except that 
it is meant to be run in place. Thus, the paths given are converted to absolute 
paths and then the borg :ref:`extract <extract>` command is run from the root 
directory (/) so that the existing files are replaced by the extracted files.

For example, the following commands restore your .bashrc file:

.. code-block:: bash

    $ cd ~
    $ assimilate restore .bashrc

*Assimilate* runs the *restore* command from :ref:`working_dir` if it is 
specified and the current directory if not.

You can select which archive you wish to restore from using the *--archive*, 
*--before* or *--after* command line arguments.  *--archive* is used to select 
the archive by ID, name, or index.  *--before* and *--after* select the archive 
by date, date and time, or age.  This is explained in 
:ref:`selecting_an_archive`.  If you do not specify an archive, the one most 
recently created is used.

Here are examples of the ways you can specify which archive to restore from:

.. code-block:: bash

    $ assimilate restore --archive continuum-2025-04-01T12:19:58 backups
    $ assimilate restore --archive aid:6b07a29c
    $ assimilate restore --archive 4
    $ assimilate restore --before 2021-04-01 backups
    $ assimilate restore --before 2021-04-01T18:30 backups
    $ assimilate restore --after 2021-04-01 backups
    $ assimilate restore --after 2021-04-01T18:30 backups
    $ assimilate restore --before 1w
    $ assimilate restore --after 1w

This command is very similar to the :ref:`extract <extract>` command except that 
it is meant to replace files in place.  It also takes similar options.


.. _settings:

Settings
--------

This command displays all the settings that affect a backup configuration.

.. code-block:: bash

    $ assimilate settings

Add ``--available`` option to list out all available settings and their 
descriptions rather than the settings actually specified and their values.


.. _umount:

Umount
------

Un-mount a previously mounted repository or archive:

.. code-block:: bash

    $ assimilate umount backups
    $ rmdir backups

where *backups* is the existing mount point.

If you do not specify a mount point, the value of *default_mount_point* setting 
is used if set.


.. _version:

Version
-------

Prints the *Assimilate* version.

.. code-block:: bash

    $ assimilate version
