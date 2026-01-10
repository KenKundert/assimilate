.. include:: links.rst

.. _migrating:

Migrating
=========

.. _migrating_to_assimilate:

Migrating to Assimilate
-----------------------

*Assimilate* and *Emborg* are not compatible, meaning that the configuration 
files, the commands, the use model, and the API are derived from and similar to 
those in *Emborg*, but at the same time are someone different and so adaptation 
is required.


Configuration File Format
~~~~~~~~~~~~~~~~~~~~~~~~~

The basic form of the configuration files has changed from *Python* in *Emborg* 
to NestedText_ in *Assimilate*.  *NestedText* allows for a simpler and cleaner 
specification, but it is not a programming language like *Python*.  It only 
supports data and not executable code.  Configurations in *Emborg* generally 
take the form of simple assignment statements, where the target variable names 
are *Emborg* settings and the right-hand side of the assignment is a simple 
string or a list of strings.  For example:

.. code-block:: python

    repository = 'backups:/mnt/borg-backups/{host_name}-{user_name}-home'
    archive = '{config_name}-{{now}}'
    glob_archives = '{config_name}-*'
    encryption = 'repokey'
    passphrase = "bedroom stage infirmary lessen"

    patterns = [
        # directories to be backed up
        "R /etc",
        "R /root",
        "R /var",
        "R /usr/local",

        # directories/files to be excluded
        "- /var/cache",
        "- /var/lock",
        "- /var/run",
        "- /var/tmp",
        "- /root/.cache"
    ]

When converted to an *Assimilate* config, it would look like this:

.. code-block:: nestedtext

    repository: backups:/mnt/borg-backups/{host_name}-{user_name}-home
    archive: {config_name}-{{now}}
    match archives: sh:{config_name}-*
    encryption: repokey
    passphrase: bedroom stage infirmary lessen

    patterns:
        # directories to be backed up
        - R /etc
        - R /root
        - R /var
        - R /usr/local

        # directories/files to be excluded
        - /var/cache
        - /var/lock
        - /var/run
        - /var/tmp
        - /root/.cache

Here are a few things to notice about this specification:

1.  The assignment statements are replaced by key-value pairs.  The ``=`` of the 
    assignment statement is replaced by the ``:␣`` name-value separator (the 
    ␣ represents a space).

2.  The string values are not quoted and special characters are not escaped.  
    The values are taken verbatim, so if you include quote characters or back 
    slashes, they are included in the value literally.

3.  Boolean values in *Assimilate* are given as *'yes* or *'no*.  In general, 
    named choices are prefixed with a single quote character.  Named choices 
    involve choosing between a predefined set of choice, like Booleans.  Another 
    example is *check_after_create*, in which you choose between *'no*, *'yes*, 
    *'latest*, *'all* and *'all_in_repository*.

4.  In both *Python* and *NestedText*, ``#`` introduces a comment, though in 
    *NestedText* the ``#`` must be the first non-space character on the line.  
    So in *NestedText* you cannot append a comment to a line that contains a key 
    or value as you can in *Python*.

5.  Both *Python* and *NestedText* use indentation to denote hierarchy, but in 
    *Python* the indentation is largely ignored within an expression.  Thus when 
    giving a multi-line value in *Python* the indentation is arbitrary.  Not so 
    with *NestedText.  Here is how you would specify a multi-line string in 
    *NestedText*:

    .. code-block:: nestedtext

        patterns:
            > R /etc
            > R /root
            > R /var
            > R /usr/local

    In *Python* multiline strings are delimited by triple quotes (``"""`` or 
    ``'''``).  In *NestedText* each line is placed on its own line and is 
    introduced with a leading ``>␣`` (again, ␣ represents a space).  Also notice 
    that the lines are all identically indented relative to *patterns* to 
    indicate that they belong to *patterns*.

    Here is how the same value can be specified as a list of individual lines:

    .. code-block:: nestedtext

        patterns:
            - R /etc
            - R /root
            - R /var
            - R /usr/local

    In *Python* lists are delimited by a pair of brackets and the list items are 
    separated with commas.  In *NestedText* each list item is placed on its own 
    line and is introduced with a leading ``-␣`` (again, ␣ represents a space).  
    Also notice that the list items are all identically indented relative to 
    *patterns* to indicate that they belong to *patterns*.

    In these examples *patterns* is specified first as a multiline string and 
    then as a list of single line strings.  *patterns* is one of several 
    settings that may be specified either as a string or as a list.  If 
    specified as a string it is split at the line breaks to form a list.

    It is also possible to specify dictionaries (a collection of name-value 
    pairs) in *NestedText*:

    .. code-block:: nestedtext

        list formats:
            name: {path}
            short: {path}{Type}
            date: {mTime:ddd YYYY-MM-DD HH:mm:ss} {path}{Type}
            size: {size:8} {path}{Type}
            si: {Size:7.2b} {path}{Type}
            owner: {user:8} {path}{Type}
            group: {group:8} {path}{Type}
            long: {mode:10} {user:6} {group:6} {size:8} {mtime} {path}{extra}

    In *Python* dictionaries are delimited by a pair of braces, the dictionary 
    items are separated with commas, and the key is separated from the value 
    using a colon.  In *NestedText* each dictionary item is placed on its own 
    line that consists of a key, a colon, and the value.  Also notice that the 
    dictionary items are all identically indented relative to *patterns* to 
    indicate that they belong to *patterns*.

6. The setting name (the key in a key-value pair) can be given with or without 
   underscores.  So for example, ``default_mount_point`` can be specified as 
   ``default mount point``.

7. Some setting names have changed.  For example, notice that ``glob_archives`` 
   changed to ``match_archives``.


Settings
~~~~~~~~

In most case the names of settings in *Assimilate* are the same as those in 
*Emborg*.  Here are a few exceptions:

*prefix* and *glob_archives* have been replaced by *match_archives*, which can 
be either a list or string.  If you have ``prefix = "home-"`` or ``glob_archives 
= "home-*"``, then you should replace them with ``match_archives: sh:home-*`` 
(the ``sh:`` prefix indicates that the match pattern is a shell-like glob 
pattern).

The *configurations* setting has been replaced by *composite_configs*.  Unlike 
*configurations*, *composite_configs* should not include scalar configurations.  
So,

.. code-block:: python

   configurations = "home cache"

would be removed and:

.. code-block:: python

   configurations = "rsync cache home=rsync,cache"

becomes:

.. code-block:: nestedtext

   ccomposite configs:
       home: rsync cache


.. _migrating_to_borg_2:

Migrating to Borg 2
-------------------

Migrating a *Borg* version 1.* repository to *Borg 2* requires the use of the 
*Borg 2* *transfer* command.  *Assimilate* does not directly support the 
*transfer* command, but you can use the :ref:`borg <borg>` command to facilitate 
the transfer.  Be aware that the transfer can take a considerable amount of time 
and that it creates a copy of the old repository and so also can require 
considerable disk space.

Example
-------

Imagine converting a *Borg 1.4* repository located in 
``/mnt/borg-backups/home/hilvar`` to a new *Borg 2* repository to be located in 
``/mnt/borg2-backups/home/hilvar``

Before starting, it is useful to carefully read the documentation for the *Borg 
2* transfer_ command, paying special attention to the details about encryption.

**Step 1**:

    You should create a *Assimilate* configuration for you new repository.  
    Assume it is named *hilvar*, and assume that it is made the default 
    configuration and so ``--config hilvar`` need not be specified when running 
    *assimilate*

    At a minimum you should specify: *repository*, *archive*, and *encryption* 
    and related settings.  *archive* should be chosen to match the archives in 
    your *Borg 1* repository.

    You should choose *archive* or *match_archives* settings to match the 
    archive naming of your old repository.  In addition, you should choose 
    *working_dir* to maintain the same root paths.

**Step 2**:

    Now create the new *Borg 2* repository

    .. code-block:: bash

        assimilate repo-create

**Step 3**:

    Copy the old *Borg 1* repository and convert into the new *Borg 2* 
    repository we just created using *Assimilate*.

    .. code-block:: bash

        assimilate borg transfer \
            --repo=@repo \
            --other-repo=/mnt/borg-backups/home/hilvar \
            --from-borg1 \
            --compress=zstd,3 --recompress=always

    Specifying the ``--from-borg`` option is critical when converting a *Borg 1* 
    repository to *Borg 2*.

    Also demonstrated is how to change the compression for the repository.  This 
    is optional.

Finally you should run a few commands, such as :ref:`repo-list <repo-list>`, to 
confirm that things work as expected.
