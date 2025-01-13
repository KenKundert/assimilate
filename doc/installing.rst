.. include:: links.rst

.. _installing_assimilate:

Getting Started
===============

Installing
----------

Many Linux distributions include *Borg* in their package managers. In Fedora it 
is referred to as *borgbackup*. In this case you would install *borg* by running 
the following:

.. code-block:: bash

    $ sudo dnf install borgbackup

Alternately, you can download a precompiled version from `Borg Github Releases 
<https://github.com/borgbackup/borg/releases/>`_, which allows you to install 
Borg as an unprivileged user.  You can do so with following commands (they may 
need to be adjusted to get the latest version):

.. code-block:: bash

    $ cd ~/bin
    $ wget https://github.com/borgbackup/borg/releases/download/2.0.0b14/borg-linux-glibc236.tgz
    $ wget https://github.com/borgbackup/borg/releases/download/2.0.0b14/borg-linux-glibc236.tgz.asc
    $ gpg --recv-keys 6D5BEF9ADD2075805747B70F9F88FB52FAF7B393
    $ gpg --verify borg-linux64.asc
    $ rm borg-linux64.asc
    $ chmod 755 borg-linux64

Finally, you can install it using `pip 
<https://pip.pypa.io/en/stable/installing>`_:

.. code-block:: bash

    $ pip install borgbackup==2.0.0b14

Download and install *Assimilate* as follows (requires Python3.6 or better):

.. code-block:: bash

    $ pip install assimilate

Or, if you want the development version, use:

.. code-block:: bash

    $ git clone https://github.com/KenKundert/assimilate.git
    $ pip install ./assimilate

You may also need to install and configure either a notification daemon or 
a mail daemon.  This allows errors to be reported when you are not running 
*Assimilate* in a terminal.  More information can be found by reading about the 
:ref:`notifier` and :ref:`notify` *Assimilate* settings.

Finally, if you want *Assimilate* to send you email if something goes wrong, you 
will need local mail support.  Specifically, if you do not have the *mailx* 
command, you will need to install a mail server such as PostFix_ and configure 
it as a null client.


Configuring Assimilate to Backup A Home Directory
-------------------------------------------------

The basic idea behind *Assimilate* is that you place all information relevant to 
your backups in two configuration files, which allows you to use *Assimilate* to 
perform tasks without re-specifying that information.  Assimilate allows you to have 
any number of setups, which you might want if you wanted to backup to multiple 
repositories for redundancy or if you want to use different rules for different 
sets of files. Regardless, you use a separate configuration for each set up, 
plus there is a common configuration file shared by all setups. You are free to 
place most settings in either file, whichever is most convenient.  All the 
configuration files are placed in ~/.config/assimilate. If you run *Assimilate* without 
creating your configuration files, *Assimilate* will create some starter files for 
you.  A configuration is specified using Python, thus the content of these files 
is formatted as Python code and is read by a Python interpreter.

As a demonstration on how to configure *Assimilate*, imagine wanting to back up your 
home directory in two ways. First, you want to backup the files to an off-site 
server. Here the expectation is that you would backup once a day on average and 
you would do so interactively so that you can choose an appropriate time.  
Second, you have some free space on your machine that you would like to dedicate 
to recent snapshots of your files. The idea is that you find that you 
occasionally overwrite or delete files that you just spent time creating, and 
you want to run local backups every 10-15 minutes so that you can easily recover 
these files.  To accomplish these two things, you need three configuration 
files.


Shared Settings
^^^^^^^^^^^^^^^

The first file is the shared configuration file: 
``~/.config/assimilate/shared.conf.nt``:

.. code-block:: nestedtext

    default config: backups

The shared settings are shared between all configs.  In most cases particular 
settings can either be given in the shared settings file or in the settings file 
for a particular configuration.  But some, including *default_config* must be 
given in the shared settings file.


Configuration for a Remote Repository: *backups*
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The second file is the configuration file for *backups*: 
``~/.config/assimilate/backups.conf.nt``:

.. code-block:: nestedtext

    repository: backups:archives
    prefix: {host_name}-
    encryption: keyfile-blake2-chacha20-poly1305
    passphrase: crone excess mandate bedpost

    src_dirs: ~
    excludes:
        - ~/.cache
        - **/*~
        - **/.git
        - **/__pycache__
        - **/.*.swp
    exclude_if_present: .nobackup

    check_after_create: 'latest
    prune_after_create: 'yes
    compact_after_delete: 'yes
    keep_daily: 7
    keep_weekly: 4
    keep_monthly: 12
    keep_yearly: 2

This configuration assumes that you have a *backups* entry in your SSH config 
file that contains the appropriate user name, host name, port number, and such 
for the server that contains your remote repository.  It also assumes that you 
have shared an SSH key with this server so you do not need to specify a password 
each time you back up, and that that key is pre-loaded into your SSH agent.  The 
repository is actually in the *archives* directory on that server, and each 
back-up archive will be prefixed with your local host name, allowing you to 
share this repository with other machines.

You specify what to backup using *src_dirs* and what not to backup using 
*excludes*.  Nominally both *src_dirs* and *excludes* take lists of strings, but 
you can also specify them using a single string, in which case the strings are 
broken into individual lines, any blank lines or lines that begin with ``#`` are 
ignored, and then the white space is removed from the front and back of each 
line.

This configuration file ends with settings that tell *Assimilate* to run *check* and 
*prune* operations after creating a backup, and it gives the desired prune 
schedule.

This is just an example, and a rather minimal one at that.  You should not use 
it without understanding each of the settings. The *encryption* setting is 
a particularly important one for you to understand and set properly.  More 
comprehensive information about configuring *Assimilate* can be found in the section 
on :ref:`configuring_assimilate`.

With this configuration, you can now initialize your repository and use it to 
perform backups.  If the repository does not yet exist, initialize it using:

.. code-block:: bash

    $ assimilate init

Then perform a back up using:

.. code-block:: bash

    $ assimilate create

or simply:

.. code-block:: bash

    $ assimilate

This works because *create* is the default action and *backups* is the default 
configuration.

Then, you can convince yourself it is working as expected by moving a directory 
out of the way and using *Assimilate* to restore it:

.. code-block:: bash

    $ mv bin bin-saved
    $ assimilate restore bin


Configuration for a Local Repository: *snapshots*
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The third file is the configuration file for *snapshots*:
``~/.config/assimilate/snapshots.conf.nt``:

.. code-block:: nestedtext

    repository: /mnt/snapshots/{user_name}
    prefix: {config_name}-
    encryption: none

    src_dirs: ~
    excludes:
        - ~/.cache
        - **/*~
        - **/.git
        - **/__pycache__
        - **/.*.swp
    prune_after_create: 'yes
    compact_after_delete: 'yes
    keep_within: 1d

In this case the repository is on the local machine and it is not encrypted. It 
again backs up your home directory, but for this configuration the archives are 
only kept for a day.

The repository must be initialized before it can be used:

.. code-block:: bash

    $ assimilate -c snapshots init

Here the desired configuration was specified because it is not the default. Now, 
a *cron* entry can be created using ``crontab -e`` that creates a snapshot every 
10 minutes:

.. code-block:: text

    */10 * * * *  assimilate --config snapshots --mute create

Once it has run, you can pull a file from the latest snapshot using:

.. code-block:: bash

    $ assimilate -c snapshots restore passwords.gpg


Configuring Assimilate to Backup an Entire Machine
--------------------------------------------------

The primary difference between this example and the previous is that *Assimilate* 
needs to be configured and run by *root*. This allows all the files on the 
machine to be backed up regardless of who owns them.  Other than being root, the 
mechanics are very much the same.

To start, run *assimilate* as root to create the initial configuration files:

.. code-block:: bash

    # assimilate

This creates the /root/.config/assimilate directory in the root account and 
populates it with three files: *shared.conf.nt*, *root.conf.nt*, *home.conf.nt*.  
You can delete *home.conf.nt*.  And since there will only be one config, you can 
also delete *shared.conf.nt*.  Instead, all the settings can be placed in 
*root.conf.nt*:

.. code-block:: nestedtext

    repository: backups:backups/{host_name}
    archive: {config_name}-{{now}}
    passphrase: 'western teaser landfall spearhead'
    encryption: 'repokey-blake2-chacha20-poly1305'

    src_dirs: /
    excludes:
        - /dev
        - /home/*/.cache
        - /proc
        - /root/.cache
        - /run
        - /sys
        - /tmp
        - /var

    check_after_create: 'latest
    compact_after_delete: 'yes
    prune_after_create: 'yes
    keep_daily: 7
    keep_weekly: 4
    keep_monthly: 12

Again, this is a rather minimal example. In this case, *repokey* is used as the 
encryption method, which is only suitable if the repository is on a server you 
control.

When backing up the root file system it is important to exclude directories that 
cannot or should not be backed up.  Those include: /dev, /proc, /run, /sys, and 
/tmp.

As before you need to initialize the repository before it can be used:

.. code-block:: bash

    # assimilate repo-create

To assure that the backups are run daily, the following is added to 
/etc/cron.daily/assimilate:

.. code-block:: bash

    #/bin/sh
    # Run root backups

    assimilate --mute --config root create

This is preferred for laptops because cron.daily is guaranteed to run each day 
as long as machine is turned on for any reasonable length of time.
