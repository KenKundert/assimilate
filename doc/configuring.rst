.. include:: links.rst

.. _configuring_assimilate:

Configuring
===========

Typically the settings files go in the default location for configuration files 
on your system.  On Linux systems, that location is `~/.config/assimilate`.
Other systems use more awkward locations, so *Assimilate* allows you to specify
the configuration directory using the `XDG_CONFIG_HOME` environment variable.
If `XDG_CONFIG_HOME` is set to `/home/$HOME/.config`, then the *Assimilate* 
configuration directory will be `/home/$HOME/.config/assimilate`, as on Linux 
systems.

You need a shared settings file and then a settings file for each backup 
configuration you need.  Except for :ref:`composite_configs` and 
:ref:`default_configuration` any setting may be placed in either the shared file 
or the configuration specific file.  If a setting is found in both files, the 
version in the configuration specific file dominates.

Settings file are NestedText_ files.  The name of the shared settings file is 
`shared.conf.nt`.  The name of the settings file for a scalar configuration is 
`<config_name>.conf.nt` where *<config_name>* is the desired name of the 
configuration file (composite configurations will be declared inside the shared 
settings file).

You can get a complete list of available configuration settings by running:

.. code-block:: bash

    $ assimilate settings --available


NestedText
----------

*Assimilate* settings are specified in NestedText_ files.  The basic structure 
of the files is a collection of name-value pairs where the name is followed by 
a colon.  The value may be a simple string, a multiline string, a list, or 
a dictionary.  Here is an example of each:

.. code-block:: nestedtext

    simple string: This is a simple string, it continues to the end of the line.
    multiline string:
        > This is a multi-line string.
        > It may contain newlines.
    list:
        - First item in list.
        - Second item in list.
    dictionary:
        key1: value1
        key2: value2

There are a few things to notice.

1. The structures can be nested.  The top level is a dictionary, and the example 
   shows that it itself may contain other dictionaries.  Similarly both list and 
   dictionary values may be lists or dictionaries.

2. The hierarchy is imposed through indentation.

3. The leaf values are always strings.

4. No quoting or escaping of special characters are used.  Each character is 
   taken literally.

5. The keys are case insensitive and are converted internally to snake case.  
   Thus, the key may be `Tempus Fugit` or `tempus-fugit`, but either of those is 
   converted to *tempus_fugit*.

6. A choice from an *Assimilate*-specified set of possible choices is always 
   given with a leading single quote.  For example, Booleans are given as either 
   ``'yes`` or ``'no``.  The case of the name is unimportant, so Booleans may 
   also be given as ``'YES`` or ``'No``.


.. _shared_settings:

Shared Settings
---------------

Shared settings go in *~/.config/assimilate/shared.conf.nt*.  This is 
a NestedText_ file that contains values shared by all of your configurations.  
It might look like the following:

.. code-block:: nestedtext

    # shared settings

    default config: home
    notifier: notify-send -u normal {prog_name} "{msg}"

    # encryption
    encryption: keyfile-blake2-chacha20-poly1305
    passphrase: watershed valuation gibbet washday

    # composite commands
    prune_after_create: 'yes
    check_after_create: 'latest
    compact_after_delete: 'yes

    # excludes
    exclude if present: .nobackup
    exclude caches: 'yes

    # personalize assimilate
    command aliases:
        create: backup
        repo-list:
            - archives
            - a
            - recent --last=20
        list:
            - l
            - ln -N
            - ls -S
            - ld -D
        overdue: od
        umount: unmount

    logging:
        keep for: 1w
        max entries: 20


.. _individual_configurations:

Configurations
--------------

Each backup configuration must have a settings file in ~/.config/assimilate. The 
name of the file is the name of the backup configuration with a `.conf.nt` 
suffix.  It might look like the following:

.. code-block:: nestedtext

    # home configuration
    repository: borgbase:borg_backups/{host_name}-{user_name}-{config_name}
    archive: {config_name}-{{now}}

    patterns:
        # directories to be backed up
        - R ~

        # patterns are applied in order
        # get rid of some always uninteresting files early so they do not get
        # pulled back in by inclusions later
        - - **/*~
        - - **/__pycache__
        - - **/.*.sw[ponml]

        # specific directories/files to be excluded
        - - ~/.cache

    # prune settings
    keep within: 2d
    keep daily: 7
    keep weekly: 4
    keep monthly: 6


.. _placeholders:

Placeholders
------------

String valued settings may incorporate other string valued settings. Use braces 
to interpolate another setting.  In addition, you may interpolate the 
configuration name (*config_name*), the host name (*host_name*), the user name 
(*user_name*), Assimilate's program name (*prog_name*), your home directory 
(*home_dir*), the configuration directory (*config_dir*) or the log directory 
(*log_dir*).  An example of this is shown in both the *repository* and *archive* 
settings given above.  Doubling up the braces acts to escape them.  In this way 
you gain access to *Borg* placeholders. *archive* shows an example of that.  
Interpolation is not performed on any setting whose name is given in 
:ref:`do_not_expand`.

If desired, you can create your own placeholders.  Simply add a named value to 
an appropriate configuration file.  *Assimilate* will not recognize it and so 
will ignore it, but the value is available to be used as a placeholder.


.. _paths:

Paths
-----

When *Borg* places files into a repository, it always uses relative paths.  
However, you may specify them either using relative paths or absolute paths.

*Borg* backs up the recursion roots. These are directories that you specify to 
:ref:`src_dirs` or using the ``R`` key in :ref:`patterns` or 
:ref:`patterns_from`.  Within a recursion root you can specify particular paths 
to exclude and within those you can specify particular files to include. This is 
done using :ref:`excludes` and :ref:`exclude_from` and using the path keys 
(``+``, ``-``, ``!``) in :ref:`patterns` and :ref:`patterns_from`.  When you use 
a relative path to specify a recursion root then you should also use relative 
paths for its include and exclude paths. Similarly, if you use an absolute path 
for the recursion root then you should also use absolute paths for its include 
and exclude paths. *Borg* is okay with you having some recursion roots specified 
with relative paths and some with absolute paths, but this confuses *Assimilate* 
when it comes time to extract or restore files from your repository. With 
*Assimilate*, all of your recursive roots must either be specified using
relative paths or they must all be specified with absolute paths.

If you specify absolute paths, *Borg* converts them to relative paths as it 
inserts them into the repository by stripping off the leading ``/`` from the 
path.  If you specify relative paths, it inserts them as is.  When using *Borg* 
directly, the relative paths would be relative to the directory where *borg 
create* is invoked. For this reason, *borg create* must always be invoked from 
the same directory when using relative paths. To make this work, *Assimilate* 
internally changes to :ref:`working_dir` before running *borg create*.  Thus, if 
you choose to use relative paths, you should also specify :ref:`working_dir`, 
which should be specified with an absolute path.  For example:

.. code-block:: nestedtext

    working_dir: ~
    src_dirs: .
    excludes:
        - .cache
        - *~

If you do not specify :ref:`working_dir`, it defaults to ``/``.

Other than paths to include files, all relative paths specified in your 
configuration are relative to :ref:`working_dir`.  This can be confusing, so it 
is recommended that all paths in your configuration, other than those being 
passed directly to *Borg* should be given using absolute paths.  This includes 
settings such as :ref:`default_mount_point`, :ref:`must_exist`, 
:ref:`patterns_from`, and :ref:`exclude_from`.

Paths specified directly to *Assimilate* are processed and any leading tildes 
(``~``) are expanded to the appropriate user's home directory. However, paths 
specified in :ref:`exclude_from` and :ref:`patterns_from` files are processed 
directly by *Borg*, which does not expand tildes to a user's home directory.


.. _includes:

Includes
--------

You can also place settings in files that can be included into the configuration 
files.  This allows you to define settings once, and include them into multiple 
but not all configurations.  These name of these files should end in ``.nt`` 
rather than ``.conf.nt``.  These files can be included into a configuration file 
using the syntax:

.. code-block:: nestedtext

    include: <path>

where *<path>* is the path to the include file.  A configuration file may have 
at most one *include* statement and that statement can include one file.

If you specify a relative path for an include file, it it relative to the file 
that includes it.


.. _composite_configurations:

Composite Configurations
------------------------

It is possible to define composite configurations that allow you to run several 
configurations at once.  This might be useful if you want to backup to more than 
one repository for redundancy.  Or perhaps you have files that benefit from 
different prune schedules.

As an example, consider having three configurations that you would like to run 
all at once. You can specify these configurations as follows:

.. code-block:: nestedtext

    composite configs:
        all: home lamp data

In this case *home*, *lamp*, and *data* are simple configurations and *all* is 
a composite configuration.  *home*, *lamp*, and *data* would have configuration 
files whereas *all* would not.  The *composite configs* setting must be 
specified in the shared settings file.

You can run a specific configuration with:

.. code-block:: bash

    $ assimilate -c home extract ~/bin

You can run all three configurations with:

.. code-block:: bash

    $ assimilate -c all create

Only certain commands support composite configurations, and if a command does 
support composite configurations it may either apply each subconfig in sequence, 
or only the first subconfig.

=========== ===============================
Command     Response to Composite Config
=========== ===============================
borg        error
break-lock  error
check       run on each subconfig
compare     run only on first subconfig
configs     does not use any configurations
create      run on each subconfig
delete      error
diff        error
due         run on each subconfig
extract     run only on first subconfig
help        does not use any configurations
info        run on each subconfig
list        run only on first subconfig
log         run on each subconfig
mount       run only on first subconfig
prune       run on each subconfig
repo-create run on each subconfig
repo-list   run only on first subconfig
repo-space  run on each subconfig
restore     run only on first subconfig
settings    run only on first subconfig
umount      run only on first subconfig
version     does not use any configurations
=========== ===============================


.. _repositories_archives_configs:

Repositories, Archives, and Configurations
------------------------------------------

*Borg* repositories can contain archives from multiple sources.  For example you 
can have multiple machines backing up to a single repository, or multiple users, 
or single user may have multiple configurations that use the same repository.  
Doing so allows for de-duplication across all sources.  For example, consider 
a team of programmers, each with their own computers but working to develop the 
same large program.  Each will have their own copies of the source code and the 
large data files used as testcases.  However if they are all backing up to the 
same repository only a single copy of each unmodified file will be saved.  This 
can result in a significant reduction in the disk space needed to hold the 
repository.

The archives contributed from all the various sources can be distinguished from 
their names.  Each source should use a different name for its archive.  In 
*Assimilate* the archive name is given by :ref:`archive`.  You can use the 
*host_name*, *user_name* and *config_name* place holders to distinguish the 
sources.  For example, the default value for the *archive* setting is:

.. code-block:: nestedtext

    archive: {host_name}-{user_name}-{config_name}-{{now}}

This generates relatively long names, but they completely distinguish the 
different sources, regardless of whether the are from different machines, users, 
or configurations.

The addition of `{{now}}` to the archive name is optional.  Adding it makes the 
name of each archive unique, which allows you to use the name directly when 
specifying an archive to the various *Assimilate* commands that take one.  If 
instead you were to use:

.. code-block:: nestedtext

    archive: {host_name}-{user_name}-{config_name}

Then the name of each archive from a particular source would be the same.  In 
that case you would not be able to directly use the name to identify a archive 
to a command.  Instead, you would use its archive ID.

Specifying the *archive* setting indicates how new archives are to be named, but 
they do not indicate how a particular source should recognize its own archives.  
This is done using the :ref:`match_archives` setting.  If you include `{{now}}` 
or `{{utcnow}}` in your archive names, you will need to specify *match_archives* 
as a pattern.  For example, you can specify it using a glob pattern by adding 
the `sh:` prefix:

.. code-block:: nestedtext

    match_archives: sh:{host_name}-{user_name}-{config_name}-*

You can give multiple values for *match_archives*, and if you do all must match.  
For example:

.. code-block:: nestedtext

    match_archives:
        - id:{host_name}-{user_name}-{config_name}
        - user:squamish
        - host:continuum

This is described more fully on `borg match patterns 
<https://borgbackup.readthedocs.io/en/master/usage/help.html#borg-help-match-archives>`_.


.. _patterns_intro:

Patterns
--------

Patterns are an alternate way of specifying which files are backed up, and which 
are not.  Patterns can be specified in conjunction with, or instead of, 
:ref:`src_dirs` and :ref:`excludes`.  One powerful feature of patterns is that 
they allow you to specify that a directory or file should be backed up even if 
it is contained within a directory that is being excluded.  The patterns are 
processed in the order given, so in this example the pattern that matches the 
file to be included should be given before the pattern that matches the 
containing directory that is to be excluded.

An example that uses :ref:`patterns` in lieu of :ref:`src_dirs` and 
:ref:`excludes` is:

.. code-block:: nestedtext

    patterns:
        - R /
        - + /home/susan
        - - /home
        - - /dev
        - - /opt
        - - /proc
        - - /run
        - - /sys
        - - /tmp
        - - /var

The *NestedText* list item indicators (the first dash on the line) can be 
visually confusing when holding a *Borg* exclude specification (second dash on 
most lines).  You might find less confusing to use a multiline string rather 
than a list to hold the patters.  In that case the multiline string is converted 
to a list by splitting on newlines:

.. code-block:: nestedtext

    patterns:
        > R /
        > + /usr/local
        > - /usr
        > - /dev
        > - /proc
        > - /run
        > - /tmp

In this example, ``R`` specifies a root, which would otherwise be specified by 
:ref:`src_dirs`.  ``+`` specifies path that should be included in the backups 
and ``-`` specifies a path that should be excluded.  With this example, 
/usr/local is included while all other files and directories in /usr are not.
The subdirectory to include must be specified before the directory that contains 
it is excluded.  This is a relatively simple example, additional features are 
described in BorgPatterns_.


.. _retention:

Archive Retention
-----------------

You use the retention limits (the *keep_X* settings) to specify how long to keep 
archives after they have been created.  A good description of the use of these 
settings can be found on the `Borg Prune Command 
<https://borgbackup.readthedocs.io/en/stable/usage/prune.html>`_ page.

Generally you want to thin the archives out more and more as they age.  When 
choosing your retention limits you need to consider the nature of the files you 
are archiving.  Specifically you need to consider how often the files change, 
whether you would want to recover prior versions of the files you keep and if so 
how many prior versions are of interest, and how long precious files may be 
missing or damaged before you notice that they need to be restored.

If files are changing all the time, long high retention limits result in high 
storage requirements.  If you want to make sure you retain the latest version of 
a file but you do not need prior versions, then you can reduce your retention 
limits to reduce your storage requirements.  For example, consider a directory 
of log files.  Log files generally change all the time, but they also tend to be 
cumulative, meaning that the latest file contains the information contained in 
prior versions of the same file, so keeping those prior versions is of low 
value.  In this situation using “*keep_last N*” where *N* is small is a good 
approach.

Now consider a directory of files that should be kept forever, such as family 
photos or legal documents.  The loss of these files due to disk corruption or 
accidental deletion might not be noticed for years.  In this case you would want 
to specify “*keep_yearly N*” where *N* is large.  These files never change, so 
the de-duplication feature of *Borg* avoids growth in storage requirements 
despite high retention limits.

You cannot specify retention limits on a per file or per directory basis within 
a single configuration.  Instead, if you feel it is necessary, you would create 
individual configurations for files with different retention needs.  For 
example, as a system administrator you might want to create separate 
configurations for operating system files, which tend to need low retention 
limits, and users home directories, which benefit from longer retention limits.

Remember that your retention limits are not enforced until you run the 
:ref:`prune command <prune>` and the space is not reclaimed until you run the 
:ref:`compact command <compact>`.  You can automate pruning and compaction using 
the :ref:`prune_after_create` and :ref:`compact_after_delete` settings.


.. _confirming_configuration:

Confirming Your Configuration
-----------------------------

Once you have specified your configuration you should carefully check it to make 
sure you are backing up the files you need and not backing up the files you 
don't need.  It is important to do this in the beginning, otherwise you might 
find your self with a bloated repository that does not contain the files you 
require.

There are a number of ways that *Assimilate* can help you check your work.

1. You can run ``assimilate settings`` to see the values used by *Assimilate* for
   all settings.

2. You can use *Borg*'s ``--dry-run`` option to perform a practice run and see 
   what will happen.  For example:

   .. code-block:: bash

       $ assimilate --dry-run create --list

   will show you all of the files that are to be backed up and which of those 
   files have changed since the last time you created an archive.

3. After running *Assimilate* you can run ``assimilate log`` to see what
   *Assimilate* did in detail and what it asked *Borg* to do.  The log contains
   the full *Borg* command invocation and *Borg*'s response.

4. Once you have created your repository and created your first archive, you can 
   use the ``--sort-by-size`` option of the :ref:`list command <list>` to find 
   the largest files that were copied into the repository.  If they are not 
   needed, you can add them to your exclude list, delete the archive, and then 
   recreate the archive, this time without the large unnecessary files.

4. You can run the :ref:`mount` command and then navigate around an archive to 
   assure it has all the files you need and none of files you do not.  On Linux 
   you can run on ``du -hs *`` to see the cumulative to total of the space used 
   by the subdirectories.


.. _assimilate_settings:

Assimilate Settings
-------------------

These settings control the behavior of *Assimilate*.


.. _archive:

archive
~~~~~~~

*archive* is a template that specifies the name of each archive.  A typical 
value might be:

.. code-block:: nestedtext

    archive: {config_name}-{{now}}

*Assimilate* examines the string for names within a single brace-pair and replaces 
them with the value specified by the name. Names within double-brace pairs are 
interpreted by *Borg*.

More than one backup configuration can share the same repository.  This allows 
*Borg*’s de-duplication feature to work across all configurations, resulting in 
less total space needed for the combined set of all your archives.  In this case 
you must also set the :ref:`match_archives <match_archives>` setting so that 
each backup configuration can recognize its own archives.  It is used by the 
:ref:`check`, :ref:`delete`, :ref:`info`, :ref:`list`, :ref:`mount`, and 
:ref:`prune` commands to filter out archives not associated with the desired 
backup configuration.

If the *archive* setting includes *{{now}}* or *{{utcnow}}* then the archive 
names will be unique, which means that they can directly be specified to those 
commands that operate on a single archive.  Otherwise you would use the archive 
ID to specify the desired archive.

You can customize *now* and *utcnow* using `strftime 
<https://docs.python.org/3/library/datetime.html#datetime.date.strftime>`_ 
formatting codes.  For example, you can reduce the length of the timestamp using:

.. code-block:: nestedtext

    archive: {host_name}-{{now:%Y%m%d}}

However, you should be aware that by including only the date in the archive name 
rather than the full timestamp, you are limiting yourself to creating one 
archive per day.  A second archive created on the same day simply writes over 
the previous archive.


.. _avendesora_account:

avendesora_account
~~~~~~~~~~~~~~~~~~

An alternative to :ref:`passphrase`. The name of the
`Avendesora <https://avendesora.readthedocs.io>`_ account used to hold the 
passphrase for the encryption key.  Using *Avendesora* keeps your passphrase out 
of your settings file, but requires that GPG agent be available and loaded with 
your private key.  This is normal when running interactively.  When running 
batch, say from *cron*, you can use the Linux *keychain* command to retain your 
GPG credentials for you.

The value may consists of two components separated by a space.  The first is the
Avendesora account name, and the second is the name of the field that contains
the passcode.  The second is optional.


.. _borg_executable:

borg_executable
~~~~~~~~~~~~~~~

The path to the *Borg* executable or the name of the *Borg* executable. By 
default it is simply ``borg``.


.. _check_after_create:

check_after_create
~~~~~~~~~~~~~~~~~~

Whether the archive or repository should be checked after an archive is created.  
May be one of the following: ``'yes``, ``'no``, ``'latest``, ``'all``, or 
``'all_in_repository``. If ``'no``, no checking is performed. If ``'latest``, 
only the archive just created is checked.  If ``'yes`` or ``'all``, all archives 
associated with the current configuration are checked.  Finally, if 
``'all_in_repository``, all the archives contained in the repository are 
checked, including those associated with other archives.  In all cases checks 
are performed on the repository and the archive or archives selected, but in 
none of the cases is data integrity verification performed.  To check the 
integrity of the data you must explicitly run the :ref:`check command <check>`.  
Regardless, the checking can be quite slow if ``'all`` or ``'all_in_repository`` 
are used.


.. _colorscheme:

colorscheme
~~~~~~~~~~~

A few commands colorize the text to convey extra information. You can optimize 
the tints of those colors to make them more visible and attractive.  
*colorscheme* should be set to ``'none``, ``'light``, or ``'dark``.  With 
``'none`` the text is not colored.  In general it is best to use the ``'light`` 
colorscheme on dark backgrounds and the ``'dark`` colorscheme on light 
backgrounds.


command aliases
~~~~~~~~~~~~~~~

This collection of settings allows you to choose the names and options you use 
for the various commands available in *Assimilate*.  It takes the following 
form:

.. code-block:: nestedtext

    command aliases:
        create: backup
        repo-list:
            - archives
            - a
            - recent --last=20
        list:
            - l
            - ln -N
            - ls -S
            - ld -D
        overdue: od
        umount: unmount

The *command_aliases* setting takes a collection of key-value pairs, where the 
key is the name of the *Assimilate* command you wish to personalize.  The value 
is a list of aliases for that command. Each list item includes the desired name 
and desired command line options.  If there is only one item in the list, it can 
be given on the same line as the key.  So for example:

.. code-block:: nestedtext

    command aliases:
        create: backup

This simply adds an alternative name for the *create* command.  You might do 
this to allow yourself to use a name that is more comfortable for you, as with 
*backup* or *archives*, or to make a command you use often easier to type, as 
with *l* or *od*.

You can customize the behavior of the command when invoked with an alias by 
adding command line arguments.  For example:

.. code-block:: nestedtext

    command aliases:
        list:
            - l
            - ln -N
            - ls -S
            - ld -D

Besides creating a simple alias for the *list* command, this also creates three 
new versions: *ln* sorts the listed files by name, *ls* sorts them by size, and 
*ld* sorts them by date.


.. _compact_after_delete:

compact_after_delete
~~~~~~~~~~~~~~~~~~~~

If ``'yes``, the :ref:`compact command <compact>` is run after deleting an 
archive or pruning a repository.

If you set this to yes, your cannot use the :ref:`undelete command <undelete>`.


.. _composite_configs:

composite_configs
~~~~~~~~~~~~~~~~~

The dictionary  of composite configurations.  The composite configurations are 
given in key-value pairs where the key is name of the composite configuration 
and the value is the list of simple configs included in the composite config.  
For example:

.. code-block:: nestedtext

    composite configs:
        rsync:
            - home
            - media

Alternately this can written more compactly using:

.. code-block:: nestedtext

    composite configs:
        rsync: home media

In the this case the value of *rsync* is converted to a list by splitting the 
string on whitespace.


.. _create_retries:

create_retries
~~~~~~~~~~~~~~

If given and greater than 1 *Assimilate* will retry a *Borg* *create* command if 
there is a failure.


.. _create_retry_sleep:

create_retry_sleep
~~~~~~~~~~~~~~~~~~

The time, in seconds, to pause before retrying a "Borg* *create* command if 
*create_retries* is 2 or greater.


.. _cronhub_url:

cronhub_url
~~~~~~~~~~~

This setting specifies the URL to use for `cronhub.io <https://cronhub.io>`_.
Normally it is not needed.  If not specified ``https://cronhub.io`` is used.  
You only need to specify the URL in special cases.


.. _cronhub_uuid:

cronhub_uuid
~~~~~~~~~~~~

If this setting is provided, *Assimilate* notifies `cronhub.io 
<https://cronhub.io>`_ when the archive is being created and whether the 
creation was successful.  The value of the setting should be a UUID (a 32 digit 
hexadecimal number that contains 4 dashes).  If given, this setting should be 
specified on an individual configuration.  For example:

.. code-block:: nestedtext

    cronhub_uuid: 51cb35d8-2975-110b-67a7-11b65d432027


.. _default_configuration:

default_configuration
~~~~~~~~~~~~~~~~~~~~~

The name of the configuration to use if one is not specified on the command 
line.


.. _default_mount_point:

default_mount_point
~~~~~~~~~~~~~~~~~~~

The path to a directory that should be used if one is not specified on the 
:ref:`mount command <mount>` or :ref:`umount command <umount>` commands.  When 
set the mount point directory becomes optional on these commands. You should 
choose a directory that itself is not subject to being backed up to avoid 
creating a loop. For example, you might consider something in /tmp:

.. code-block:: nestedtext

    default_mount_point: /tmp/assimilate


.. _do_not_expand:

do_not_expand
~~~~~~~~~~~~~

All settings that are specified as strings or lists of strings may contain 
placeholders that are expanded before use. The placeholder is replaced by the 
value it names.  For example, in:

.. code-block:: nestedtext

    archive: {host_name}-{{now}}

*host_name* is a placeholder that is replaced by the host name of your computer 
before it is used (*now* is escaped using double braces and so does not act as 
a placeholder for *Assimilate*).

*do_not_expand* is a list of names for settings that should not undergo 
placeholder replacement.  The value may be specified as a list of strings or 
just as a string. If specified as a string, it is split on white space to form 
the list.

.. _encoding:

encoding
~~~~~~~~

The encoding used when communicating with Borg. The default is utf-8, which is 
generally suitable for Linux systems.


.. _encryption:

encryption
~~~~~~~~~~

The encryption mode used by first creating the repository.  The available 
encryption modes are documented in the `repo-create 
<https://borgbackup.readthedocs.io/en/master/usage/repo-create.html>`_ 
documentation.
Common values are ``none`` if the repository resides on a trusted machine or 
``repokey-blake2-chacha20-poly1305`` or ``keyfile-blake2-chacha20-poly1305`` if 
the repository lives on an untrusted machine.  There are many other choices, so 
it is worth read the *Borg* documentation before choosing.  One thing that is 
important to understand are the roles of the encryption key and the pass phrase.  
When you specify encryption *Borg* creates a log random encryption key and uses 
that key to encrypt the repository.  Before saving the encryption key, *Borg* 
encrypts it using the pass phrase.  Thus, anyone that does not know the pass 
phrase can not open the encryption key and so cannot decrypt the repository.  
Borg stores the encryption key locally, and if you add the ``repokey`` prefix on 
the encryption model it also copies it into the repository.  If instead the you 
add the ``keyfile`` prefix, the encryption key is not copied to the repository.

There are important trade-offs between these two modes that it is important to 
understand.  If you use the ``repokey`` prefix you must choose a secure (long, 
random) pass phrase and keep it secure.  If someone with access to the machine 
that holds your repository were to find or guess you pass phrase they could 
access your files.  This is not possible if ``keyfile`` is used because the 
encryption key is not copied to the repository, but there is another, perhaps 
more serious, risk.  If the disk that holds your source files becomes unreadable 
and you have not manually copied the key file to secure backup location, your 
files become unrecoverable.  If you choose to use a ``keyfile`` encryption mode 
you must remember to export your key file and save it to a safe place that is 
not on the same disk you are backing up.  Use the following command to export 
your key file:

.. code-block:: bash

    $ assimilate borg key export @repo key.borg

The more ``key.borg`` to a safe location.

Once encrypted, a passphrase is needed to access the repository.  There are 
a variety of ways to provide it.  *Borg* itself uses the *BORG_PASSPHRASE*, 
*BORG_PASSPHRASE_FD*, and *BORG_COMMAND* environment variables if set.  
*BORG_PASSPHRASE* contains the passphrase, or *BORG_PASSPHRASE_FD* is a file 
descriptor that provides the passphrase, or *BORG_COMMAND* contains a command 
that generates the passphrase.  If none of those are set, *Assimilate* looks to 
its own settings.  If either :ref:`passphrase` or :ref:`passcommand` are set, 
they are used.  If neither are set, *Assimilate* uses :ref:`avendesora_account` 
if set.  Otherwise no passphrase is available and the command fails if the 
repository is encrypted.


.. _excludes:

excludes
~~~~~~~~

A list of files or directories to exclude from the backups.  Typical value might 
be:

.. code-block:: nestedtext

    excludes:
        - ~/tmp
        - ~/.local
        - ~/.cache
        - ~/.mozilla
        - ~/.thunderbird
        - ~/.config/google-chrome*
        - ~/.config/libreoffice
        - ~/**/__pycache__
        - ~/**/*.pyc
        - ~/**/.*.swp
        - ~/**/.*.swo

The value can either be specified as a list of strings or as a multi-line string 
with one exclude per line.

*Assimilate* supports the same exclude patterns that `Borg 
<https://borgbackup.readthedocs.io/en/stable/usage/help.html>`_ itself supports. 

When specifying paths to excludes, the paths may be relative or absolute. When 
relative, they are taken to be relative to :ref:`working_dir`.


.. _exclude_from:

exclude_from
~~~~~~~~~~~~

An alternative to :ref:`excludes`.  You can list your excludes in one or more 
files, one per line, and then specify the file or files using the *exclude_from* 
setting:

.. code-block:: nestedtext

    exclude_from: {config_dir}/excludes

The value of *exclude_from* may either be a multi-line string, one file per 
line, or a list of strings. The string or strings would be the paths to the file 
or files that contain the list of files or directories to exclude. If given as 
relative paths, they are relative to :ref:`working_dir`.  These files are 
processed directly by *Borg*, which does not allow ``~`` to represent users' 
home directories, unlike the patterns specified using :ref:`patterns`.


.. _get_repo_size:

get_repo_size
~~~~~~~~~~~~~

A Boolean that when ``'yes`` causes the repository size to be saved to the 
*latest.nt* file.  The repository size is produced by the :ref:`compact command 
<compact>` and requires the use of the ``--stats`` option, which can be very 
slow for some type of repositories (sftp and cloud storage).

Must be enabled when using :ref:`borg space`.


.. _healthchecks_url:

healthchecks_url
~~~~~~~~~~~~~~~~

This setting specifies the URL to use for `healthchecks.io 
<https://healthchecks.io>`_.  Normally it is not needed.  If not specified 
``https://.hc-ping.com`` is used.  You only need to specify the URL in special 
cases.


.. _healthchecks_uuid:

healthchecks_uuid
~~~~~~~~~~~~~~~~~

If this setting is provided, *Assimilate* notifies `healthchecks.io 
<https://healthchecks.io>`_ when the archive is being created and whether the 
creation was successful.  The value of the setting should be a UUID (a 32 digit 
hexadecimal number that contains 4 dashes).  If given, this setting should be 
specified on an individual configuration.  For example:

.. code-block:: nestedtext

    healthchecks_uuid: 51cb35d8-2975-110b-67a7-11b65d432027


.. _include:

include
~~~~~~~

A path to a NestedText_ file that contains settings more settings.
These settings simply replace the include statement.  If the path is relative, 
it is relative to the file that includes it.

The file being included should have a '.nt' suffix, but not a '.conf.nt' suffix.  


.. _manage_diffs_cmd:

manage_diffs_cmd
~~~~~~~~~~~~~~~~

Command to use to perform interactive file and directory comparisons using the 
``--interactive`` option to the :ref:`compare command <compare>`.  The command 
may be specified in the form of a string or a list of strings.  If a string, it 
may contain the literal text ``{archive_path}`` and ``{local_path}``, which are 
replaced by the two files or directories to be compared.  If not, then the paths 
are simply appended to the end of the command as specified.  Suitable commands 
for use in this setting include `Vim <https://www.vim.org>`_ with the `DirDiff 
<https://www.vim.org/scripts/script.php?script_id=102>`_  plugin, `Meld 
<https://meldmerge.org>`_, and presumably others such as *DiffMerge*, *Kompare*, 
*Diffuse*, *KDiff3*, etc.  If you are a *Vim* user, another alternative is 
`vdiff <https://github.com/KenKundert/vdiff>`_, which provides a more 
streamlined interface to *Vim/DirDiff*.  Here are examples on how to configure 
*Vim*, *Meld* and *VDiff*:

.. code-block:: nestedtext

    manage_diffs_cmd: meld
    manage_diffs_cmd:
        - meld
        - -a
    manage_diffs_cmd: gvim -f -c 'DirDiff {archive_path} {local_path}'
    manage_diffs_cmd: vdiff -g

The :ref:`compare command <compare>` mounts the remote archive, runs the 
specified command and then immediately un-mounts the archive.  As such, it is 
important that the command run in the foreground.  By default, *gvim* runs in 
the background.  You can tell this because if runs directly in a shell, the 
shell immediately accepts new commands even though *gvim* is still active.  To 
avoid this, the ``-f`` option is added to the *gvim* command line to indicate it 
should run in the foreground.  Without this, you will see an error from 
*fusermount* indicating ‘Device or resource busy’.  If you get this message, you 
will have to close the editor and manually un-mount the archive.


.. _list_default_format:

list_default_format
~~~~~~~~~~~~~~~~~~~

A string that specifies the name of the default format.  The name must be a key 
in :ref:`list_formats`.  If not specified, ``short`` is used.


.. _list_formats:

list_formats
~~~~~~~~~~~~

A dictionary that defines how the output of the :ref:`list command <list>` is to 
be formatted.  The default value for *list_formats* is:

.. code-block:: nestedtext

        list_formats:
            name: {path}
            short: {path}{Type}
            date: {mtime} {path}{Type}
            size: {size:8} {path}{Type}
            si: {Size:6.2} {path}{Type}
            owner: {user:8} {path}{Type}
            group: {group:8} {path}{Type}
            long: {mode:10} {user:6} {group:6} {size:8} {mtime} {path}{extra}

        list_default_format: short

Notice that 8 formats are defined:

    :name: used when ``--name-only`` is specified.
    :short: used by when ``--short`` is specified and when sorting by name.
    :date: used by default when sorting by date.
    :size: size in bytes (fixed format).
    :si: size in bytes (SI format), used by default when sorting by size.
    :owner: used by default when sorting by owner.
    :group: used by default when sorting by group.
    :long: used when ``--long`` is specified.

Your *list_formats* need not define all or even any of these formats.
The above example shows the formats that are predefined in *Assimilate*. You do not 
need to specify them again.  Anything you specify will override the predefined 
versions, and you can add additional formats.

The formats may contain the fields supported by the `Borg list command 
<https://borgbackup.readthedocs.io/en/stable/usage/list.html#borg-list>`_.  In 
addition, Assimilate provides some variants:

*MTime*, *CTime*, *ATime*:
   The *Borg* *mtime*, *ctime*, and *atime* fields are simple strings, these 
   variants are `Arrow objects 
   <https://arrow.readthedocs.io/en/latest/#supported-tokens>`_ that support 
   formatting options.  For example:

   .. code-block:: nestedtext

        date: {MTime:ddd YYYY-MM-DD HH:mm:ss} {path}{Type}

*Size*, *CSize*, *DSize*, *DCSize*:
   The *Borg* *size*, *csize*, *dsize* and *dctime* fields are simple integers, 
   these variants are `QuantiPhy objects 
   <https://quantiphy.readthedocs.io/en/stable/user.html#string-formatting>`_ 
   that support formatting options.  For example:

   .. code-block:: nestedtext

        size: {Size:5.2r} {path}{Type}
        size: {Size:7.2b} {path}{Type}

*Type*:
   Displays ``/`` for directories, ``@`` for symbolic links, and ``|`` for named 
   pipes.

*healthy*:
   A Boolean `truth object 
   <https://inform.readthedocs.io/en/stable/user.html#truth>`_ that indicates 
   whether there are problems with the underlying files.  By default it outputs 
   ``healthy`` or ``broken``, but you control the output as follows:

   .. code-block:: nestedtext

        short: {path}{Type} {healthy:✓/✗}

   The string to output if ``healthy`` is true goes before the slash and the 
   string that indicates a problem goes after the slash.

*QuantiPhy* objects (sizes) allow you to format the size using SI scale factors 
(K, Ki, M, Mi, etc.). *Arrow* objects (times) allow you to format the date and 
time in a wide variety of ways.  Boolean objects (*healthy*) allows you to 
specify true/false values.  Any use of *QuantiPhy* or *Arrow* can slow long 
listings considerably.

The fields support `Python format strings 
<https://docs.python.org/3/library/string.html#formatstrings>`_, which allows 
you to specify how they are to be formatted.  Anything outside a field is copied 
literally.


.. _logging:

logging
~~~~~~~

Specifies settings for the composite logging, such as how long to accumulate log 
files and how events should be labeled.  For more detail, see :ref:`log_files`.

Be aware the composite logfile generation occurs on most commands can be slow if 
a large number of log entries are kept.  It is recommended that you specify 
a reasonable value for *max_entries*.


.. _monitoring setting:

monitoring
~~~~~~~~~~

*monitoring* is a dictionary setting that configures status reporting to 
monitoring services.  Detailed information about this setting can be found in 
:ref:`monitoring <monitoring_services>`.


.. _must_exist:

must_exist
~~~~~~~~~~

Specifies paths to files that must exist before :ref:`create command <create>` 
can be run.  This is used to assure that relevant file systems are mounted 
before making backups of their files.

May be specified as a list of strings or as a multi-line string with one path 
per line.


.. _needs_ssh_agent:

needs_ssh_agent
~~~~~~~~~~~~~~~

A Boolean. If true, *Assimilate* will issue an error message and refuse to run if an 
SSH agent is not available.  Specify ``'yes`` for true and ``'no`` for false.


.. _notifier:

notifier
~~~~~~~~

A string that specifies the command used to interactively notify the user of an 
issue. A typical value is:

.. code-block:: nestedtext

    notifier: notify-send -u critical {prog_name} "{msg}"

Any of the following names may be embedded in braces and included in the string.  
They will be replaced by their value:

 |  *msg*: The message for the user.
 |  *hostname*: The host name of the system that *Assimilate* is running on.
 |  *user_name*: The user name of the person that started *Assimilate*
 |  *prog_name*: The name of the *Assimilate* program.

The notifier is only used if the standard output from *Assimilate* does not go 
directly to a terminal window (a TTY).

Use of *notifier* requires that you have a notification daemon installed (ex: 
`Dunst <https://wiki.archlinux.org/title/Dunst>`_).  The notification daemon 
provides the *notify-send* command.  If you do not have the *notify-send* 
command, do not set *notifier*.

The *notify* and *notifier* settings operate independently.  You may specify 
none, one, or both.  Generally, one uses just one: *notifier* if you primarily 
use *Assimilate* interactively and *notify* if used from cron or anacron.


.. _notify:

notify
~~~~~~

A string that contains one or more email addresses separated with spaces.  If 
specified, an email will be sent to each of the addresses to notify them of any 
problems that occurred while running *Assimilate*.

The email is only sent if the command is not running from a TTY.

Use of *notify* requires that you have a mail daemon installed (ex: PostFix_ 
configured as a null client).  The mail daemon provides the *mailx* command.  If 
you do not have the *mailx* command, do not set *notify*.

The *notify* and *notifier* settings operate independently.  You may specify 
none, one, or both.  Generally, one uses just one: *notifier* if you primarily 
use *Assimilate* interactively and *notify* if used from cron or anacron.


.. _overdue setting:

overdue
~~~~~~~

*overdue* is a dictionary setting that contains the information needed by the 
:ref:`overdue command <overdue>`.  Detailed information about this setting can 
be found in :ref:`monitoring <assimilate_overdue>`.


.. _passcommand:

passcommand
~~~~~~~~~~~

A string that specifies a command to be run by *BORG* to determine the pass 
phrase for the encryption key. The standard output of this command is used as 
the pass phrase.  This string is passed to *Borg*, which executes the command.

Here is an example of a passcommand that you can use if your GPG agent is 
available when *Assimilate* is run. This works if you are running it interactively, 
or in a cron script if you are using `keychain 
<https://www.funtoo.org/Keychain>`_ to provide you access to your GPG agent:

.. code-block:: nestedtext

    passcommand: gpg -qd /home/user/.store-auth.gpg

This is used as an alternative to :ref:`passphrase` when it is desirable to keep 
the passphrase out of your configuration file.


.. _passphrase:

passphrase
~~~~~~~~~~

A string that specifies the pass phrase for the encryption key.  This string is 
passed to *Borg*.  When specifying a pass phrase you should be careful to assure 
that the configuration file that contains is only readable by the user and 
nobody else.


.. _prune_after_create:

prune_after_create
~~~~~~~~~~~~~~~~~~

A Boolean. If true the :ref:`prune command <prune>` is run after creating an 
archive.  Specify ``'yes`` for true and ``'no`` for false.


.. _report_diffs_cmd:

report_diffs_cmd
~~~~~~~~~~~~~~~~

Command used to perform file and directory comparisons using the :ref:`compare 
command <compare>`.  The command may be specified in the form of a string or 
a list of strings.  If a string, it may contain the literal text 
``{archive_path}`` and ``{local_path}``, which are replaced by the two files or 
directories to be compared.  If not, then the paths are simply appended to the 
end of the command as specified.  Suitable commands for use in this setting 
include ``diff -r`` the and ``colordiff -r``.  Here are examples of two 
different but equivalent ways of configuring *diff*:

.. code-block:: nestedtext

    report_diffs_cmd: diff -r
    report_diffs_cmd: diff -r {archive_path} {local_path}

You may prefer to use *colordiff*, which is like *diff* but in color:

.. code-block:: nestedtext

    report_diffs_cmd: colordiff -r


.. _repository:

repository
~~~~~~~~~~

The destination for the backups. A typical value might be:

.. code-block:: nestedtext

    repository: archives:/mnt/backups/{host_name}-{user_name}-{config_name}

where in this example 'archives' is the hostname and /mnt/backups is the 
absolute path to the directory that is to contain your Borg repositories, 
and {host_name}-{user_name}-{config_name} is the directory to contain this 
repository.  For a local repository you would use something like this:

.. code-block:: nestedtext

    repository: /mnt/backups/{host_name}-{user_name}-{config_name}

These examples assume that */mnt/backups* contains many independent 
repositories, and that each repository contains the files associated with 
a single backup configuration.  Borg allows you to make a repository the target 
of more than one backup configuration, and in this way you can further benefit 
from its ability to de-duplicate files.  In this case you might want to use 
a less granular name for your repository.  For example, a particular user could 
use a single repository for all their configurations on all their hosts using:

.. code-block:: nestedtext

    repository: /mnt/backups/{user_name}

When more than one configuration shares a repository you should specify the 
:ref:`match_archives` setting so that each configuration can recognize its own 
archives.

A local repository should be specified with an absolute path, and that path 
should not contain a colon (``:``) to avoid confusing the algorithm that 
determines whether the repository is local or remote.


.. _run_after_backup:
.. _run_after_last_backup:

run_after_backup, run_after_last_backup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Specifies commands that are to be run after the :ref:`create <create>` command 
successfully completes.  These commands often recreate useful files that were 
deleted by the :ref:`run_before_backup <run_before_backup>` commands.

May be specified as a list of strings or as a multi-line string with one command 
per line (lines that begin with ``#`` are ignored).  If given as a string, 
a shell is used to run the command or commands.  If given as a list of strings, 
a shell is not used, meaning that shell path and variable expansions, 
redirections and pipelines are not available.

The commands specified in *run_after_backup* are run each time an archive is 
created whereas commands specified in *run_after_last_backup* are run only if 
the configuration is run individually or if it is the last run in a composite 
configuration.  For example, imagine a composite configuration *home* that 
consists of two children, *local* and *remote*, and imagine that both are 
configured to run the command *restore* after they are run.  If 
*run_after_backup* is used to specify *restore*, then running ``assimilate -c home 
create`` results in *restore* being run twice, after both the *local* and 
*remote* archives are created.  However, if *run_after_last_backup* is used, 
*restore* is only run once, after the *remote* archive is created.  Generally, 
one specifies identical commands to *run_after_last_backup* for each 
configuration in a composite configuration with the intent that the commands 
will be run only once regardless whether the configurations are run individually 
or as a group.

For example, the following runs :ref:`borg space` after each back-up to record 
the size history of your repository:

.. code-block:: nestedtext

    run_after_backup: borg-space -r -m "Repository is now {{size:.2}}." {config_name}

You can also specify a list as the value if you have multiple commands to run.


.. _run_before_backup:
.. _run_before_first_backup:

run_before_backup, run_before_first_backup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Specifies commands that are to be run before the :ref:`create <create>` command 
starts the backup. These commands often delete large files that can be easily 
recreated from those files that are backed up.

May be specified as a list of strings or as a multi-line string with one command 
per line (lines that begin with ``#`` are ignored).  If given as a string, 
a shell is used to run the command or commands.  If given as a list of strings, 
a shell is not used, meaning that shell path and variable expansions, 
redirections and pipelines are not available.

The commands specified in *run_before_backup* are run each time an archive is 
created whereas commands specified in *run_before_first_backup* are run only if 
the configuration is run individually or if it is the first run in a composite 
configuration.  For example, imagine a composite configuration *home* that 
consists of two children, *local* and *remote*, and imagine that both are 
configured to run the command *clean* before they are run.  If 
*run_before_backup* is used to specify *clean*, then running ``assimilate -c home 
create`` results in *clean* being run twice, before both the *local* and 
*remote* archives are created.  However, if *run_before_first_backup* is used, 
*clean* is only run once, before the *local* archive is created.  Generally, one 
specifies identical commands to *run_before_first_backup* for each configuration 
in a composite configuration with the intent that the commands will be run only 
once regardless whether the configurations are run individually or as a group.


.. _run_before_borg:
.. _run_after_borg:

run_before_borg, run_after_borg
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Specifies commands that are to be run before the first *Borg* command is run or 
after the last one is run.  These can be used, for example, to mount and then 
unmount a remote repository, if such a thing is needed.

May be specified as a list of strings or as a multi-line string with one command 
per line (lines that begin with ``#`` are ignored).  If given as a string, 
a shell is used to run the command or commands.  If given as a list of strings, 
a shell is not used, meaning that shell path and variable expansions, 
redirections and pipelines are not available.


.. _show_progress:

show_progress
~~~~~~~~~~~~~

Show progress when running *Borg*'s *create* and *compact* commands.
You also get this by adding the ``--progress`` command line option to the 
command, but if this option is set to ``'yes`` then this command always shows 
the progress.


.. _show_stats:

show_stats
~~~~~~~~~~

Show statistics when running *Borg*'s *create* and *compact* commands.
You can always get this by adding the ``--stats`` command line option to the 
appropriate commands, but if this option is set to ``'yes`` then these commands 
always show the statistics.  If the statistics are not requested, they will be 
recorded in the log file rather than being displayed.

Statistics are incompatible with the --dry-run option and so are suppressed on 
trial runs.


.. _src_dirs:

src_dirs
~~~~~~~~

A list of strings, each of which specifies a directory to be backed up.  May be 
specified as a list of strings or as a multi-line string with one source 
directory per line.

When specifying the paths to the source directories, the paths may be relative 
or absolute.  When relative, they are taken to be relative to 
:ref:`working_dir`.


.. _ssh_command:

ssh_command
~~~~~~~~~~~

A string that contains the command to be used for SSH. The default is ``ssh``.  
This can be used to specify SSH options.


.. _verbose:

verbose
~~~~~~~

A Boolean. If ``'yes`` *Borg* is run in verbose mode and the output from *Borg* 
is output by *Assimilate*.


.. _working_dir:

working_dir
~~~~~~~~~~~~

All relative paths specified in the configuration files (other than those 
specified to :ref:`include`) are relative to *working_dir*.

*Assimilate* changes to the working directory before running the *Borg* *create* 
command, meaning that relative paths specified as roots, excludes, or patterns 
(:ref:`src_dirs`, :ref:`excludes`, :ref:`patterns`, :ref:`exclude_from` or 
:ref:`patterns_from`) are taken to be relative to the working directory.  If you 
use absolute paths for your roots, excludes, and pattern, then the working 
directory must be set to ``/``.

To avoid confusion, it is recommended that all other paths in your configuration 
be specified using absolute paths (ex: :ref:`default_mount_point`,
:ref:`must_exist`, :ref:`patterns_from`, and :ref:`exclude_from`).

If specified, *working_dir* must be specified using an absolute path.
If not specified, *working_dir* defaults to ``/``.


Borg Settings
-------------

These settings control the behavior of *Borg*. Detailed descriptions can be 
found in the `Borg documentation 
<https://borgbackup.readthedocs.io/en/stable/usage/general.html>`_.

.. _append_only:

append_only
~~~~~~~~~~~

Create an append-only mode repository.


.. _chunker_params:

chunker_params
~~~~~~~~~~~~~~

Parameters used by the chunker command.
More information is available from `chunker_params Borg documentation
<https://borgbackup.readthedocs.io/en/stable/usage/notes.html#chunker-params>`_.


.. _compression:

compression
~~~~~~~~~~~

The name of the desired compression algorithm.


.. _exclude_caches:

exclude_caches
~~~~~~~~~~~~~~

Exclude directories that contain a CACHEDIR.TAG file
Specify ``'yes`` or ``'no``.


.. _exclude_if_present:

exclude_if_present
~~~~~~~~~~~~~~~~~~

Exclude directories that are tagged by containing a filesystem object with the 
given NAME.  For example if *exclude_if_present* is set to ``.nobackup`` then 
a directory that contains a file named ``.nobackup`` will be excluded from the 
back ups.


.. _lock_wait:

lock_wait
~~~~~~~~~

Maximum time to wait for a repository or cache lock to be released [seconds].  
The default is 1.


.. _keep_within:

keep_within
~~~~~~~~~~~

Keep all archives created within this time interval.  Specify as a number and 
a unit, where the available units are "y", "m", "w", "d", "H", "M", and "S"
and they represent years, months, weeks, days, hours, minutes, and seconds.

For example:


.. code-block:: nestedtext

    keep_within: 1d

Be aware that *keep_within* is passed to *Borg* and so uses the *Borg* time 
interval conventions, and that those conventions differ from the *Assimilate* 
conventions.  *Borg* uses lower case letters for the longer intervals whereas 
*Assimilate* uses upper case letters.


.. _keep_last:

keep_last
~~~~~~~~~

Number of the most recent archives to keep.


.. _keep_minutely:

keep_minutely
~~~~~~~~~~~~~

Number of minutely archives to keep.


.. _keep_hourly:

keep_hourly
~~~~~~~~~~~

Number of hourly archives to keep.


.. _keep_daily:

keep_daily
~~~~~~~~~~

Number of daily archives to keep.


.. _keep_weekly:

keep_weekly
~~~~~~~~~~~

Number of weekly archives to keep.


.. _keep_monthly:

keep_monthly
~~~~~~~~~~~~

Number of monthly archives to keep.


.. _keep_yearly:

keep_yearly
~~~~~~~~~~~

Number of yearly archives to keep.


.. _match_archives:

match_archives
~~~~~~~~~~~~~~

A collection of one or more patterns that must match before a command will 
operate on an archive.  For example:

.. code-block:: nestedtext

    match_archives:
        - id:{host_name}-{user_name}-{config_name}
        - user:squamish
        - host:continuum

The available patterns are described at `borg match patterns 
<https://borgbackup.readthedocs.io/en/master/usage/help.html#borg-help-match-archives>`_.

May be specified as a list of single-line strings or a multiline string that is 
split on newlines.

If not specified, it is constructed from :ref:`archive` by replacing ``{{now}}`` 
or ``{{utcnow}}`` with ``*`` and adding ``sh:`` as a prefix.


.. _one_file_system:

one_file_system
~~~~~~~~~~~~~~~

Stay in the same file system and do not store mount points of other file 
systems.
Specify ``'yes`` or ``'no``.


.. _patterns:

patterns
~~~~~~~~

A list of files or directories to exclude from the backups.  The value can 
either be specified as a list of strings or as a multi-line string with one 
pattern per line.

Typical value might be:

.. code-block:: nestedtext

    patterns:
    patterns:
        - R /
        - + /usr/local
        - - /usr
        - - /dev
        - - /proc
        - - /run
        - - /tmp

or equivalently:

.. code-block:: nestedtext

    patterns:
        > R /
        > + /usr/local
        > - /usr
        > - /dev
        > - /proc
        > - /run
        > - /tmp

Patterns allow you to specify what to back up and what not to in a manner that 
is more flexible than :ref:`src_dirs` and :ref:`excludes` allows, and can fully 
replace them.

For example, notice that /usr/local is included while excluding the directory 
that contains it (/usr).  Be sure to include sub directories before excluding 
the directories that contain them.

*Assimilate* supports the same patterns that `Borg 
<https://borgbackup.readthedocs.io/en/stable/usage/help.html>`_ itself supports. 

When specifying paths in patterns, the paths may be relative or absolute. When 
relative, they are taken to be relative to :ref:`working_dir`.


.. _patterns_from:

patterns_from
~~~~~~~~~~~~~

An alternative to :ref:`patterns`.  You can list your patterns in one or more 
files, one per line, and then specify the file or files using the *exclude_from* 
setting.

.. code-block:: nestedtext

    patterns_from: {config_dir}/patterns

The value of *patterns_from* may either be a multi-line string, one file per 
line, or a list of strings. The string or strings would be the paths to the file 
or files that contain the patterns. If given as relative paths, they are 
relative to :ref:`working_dir`.  These files are processed directly by *Borg*, 
which does not allow ``~`` to represent users' home directories, unlike the 
patterns specified using :ref:`patterns`.


.. _remote_path:

remote_path
~~~~~~~~~~~

Name of *Borg* executable on remote platform.


.. _sparse:

sparse
~~~~~~~~~

Detect sparse holes in input (supported only by fixed chunker).


.. _threshold:

threshold
~~~~~~~~~

Sets minimum threshold for saved space when compacting a repository with the 
:ref:`compact command <compact>`.  Value is given in percent.


.. _umask:

umask
~~~~~

Set umask. This is passed to *Borg*. It uses it when creating files, either 
local or remote. The default is 0o077.


.. _upload_buffer:

upload_buffer
~~~~~~~~~~~~~

Set network upload buffer size in MiB.  By default no buffer is used.


.. _upload_ratelimit:

upload_ratelimit
~~~~~~~~~~~~~~~~

Set upload rate limit in KiB/s when writing to a remote network (default: 
0=unlimited).


Read Only Settings
------------------

These settings are set by *Assimilate* itself.  They are useful as place-holders 
in other settings.

.. _cmd_name:

cmd_name
~~~~~~~~

The name of the *Assimilate* command currently being run.


.. _config_dir:

config_dir
~~~~~~~~~~~

Absolute path to *Assimilate*'s configuration directory.


.. _config_name:

config_name
~~~~~~~~~~~

Name of active configuration.


.. _home_dir:

home_dir
~~~~~~~~

Absolute path to user's home directory.


.. _log_dir:

log_dir
~~~~~~~

Absolute path to the *Assimilate*'s logging directory.


Environment Variables
---------------------

The following environment variables affect *Assimilate*.

XDG_CONFIG_HOME
~~~~~~~~~~~~~~~

Specifies the directory that contains configuration directories.  When set, 
*Assimilate*'s configuration directory will be ``$XDG_CONFIG_HOME/assimilate``.  
If not set, the location of the configuration directories is system specific.  
On Linux systems it is ``~/.config``.


XDG_DATA_HOME
~~~~~~~~~~~~~

Specifies the directory that contains data directories.  When set, *Assimilate*s 
data directory will be ``$XDG_DATA_HOME/assimilate``.  If not set, the location 
of the configuration directories is system specific.  On Linux systems it is 
``~/.local/share``.  The *Assimilate* data directory is where *Assimilate* 
places its log files.


PAGER
~~~~~

The command used for paging through text one screenful at a time.  This is used 
when displaying help messages.  The default is *less*.


PATH
~~~~

Specifies the search path used by your shell to find executables.  When 
*Assimilate* runs commands on your behalf, such as *borg*, this affects which 
version of programs are run.
