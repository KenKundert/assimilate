.. include:: links.rst

.. _assimilate examples:

Example Configurations
======================

When first run, *Assimilate* creates the settings directory and populates it 
with three configurations that you can use as starting points. Those three 
configurations make up our first three examples.


.. _root example:

Root
----

The *root* configuration is a suitable starting point for someone that wants to 
backup an entire machine, including both system and user files. In order to have 
permission to access the files, one must run this configuration as the *root* 
user.

This configuration was constructed assuming that the backups would be run 
automatically at a fixed time using cron.  Since this user only has one 
configuration, it is largely arbitrary which file each setting resides in, 
however both files must exist, and the *settings* file must contain 
*default_configs*.

Here is the contents of the settings file: 
/root/.config/assimilate/shared.conf.nt:

.. code-block:: nestedtext

    # generic settings

    # basic settings
    default config: root
    default mount point: ~/ASSIMILATE
    notify: root@continuum.com

    # composite commands
    prune_after_create: 'yes
    check_after_create: 'latest
    compact_after_delete: 'yes

    # excludes
    exclude if present: .nobackup
    exclude caches: 'yes
    exclude nodump: 'yes

    # personalize assimilate
    command aliases:
        repo-list:
            - archives
            - recent --last 20
        list: files

    logging:
        keep for: 1w
        max entries: 20

    list formats:
        name: {path}
        short: {path}{Type}
        date: {MTime:ddd YYYY-MM-DD HH:mm:ss} {path}{Type}
        size: {size:8} {path}{Type}
        si: {Size:7.2b} {path}{Type}
        owner: {user:8} {path}{Type}
        group: {group:8} {path}{Type}
        long: {mode:10} {user:6} {group:6} {size:8} {mtime} {path}{extra}

    default list format: short

And here is the contents of the *root* configuration file: 
/root/.config/assimilate/root.conf.nt:

.. code-block:: nestedtext

    # root configuration

    # repository
    repository: backups:/mnt/backups/{host_name}-{user_name}-{config_name}
    archive: {config_name}-{{now:%Y%m%d}}
    encryption: repokey-blake2-chacha20-poly1305
    passphrase: carvery overhang vignette platitude pantheon sissy toddler truckle

    patterns:
        # directories to be backed up
        > R /etc
        > R /home
        > R /root
        > R /var
        > R /srv
        > R /opt
        > R /usr/local

        # specific directories/files to be excluded
        > - /var/cache
        > - /var/lock
        > - /var/run
        > - /var/tmp
        > - /root/.cache
        > - /home/*/.cache

    # prune settings
    keep daily: 7
    keep weekly: 4
    keep monthly: 6

In this case we are assuming that *backups* (used in *repository*) is an entry 
in your SSH config file that points to the server that stores your repository.  
To be able to run this configuration autonomously from cron, *backups* must be 
configured to use a private key that does not have a passphrase.

The account on the remote server that owns the repository should have an 
``~/ssh/authorized_keys`` file that contains::

    command="borg serve --lock-wait 600 --restrict-to-path 
    /mnt/borg-backups/repositories/dgcmail-root-root",restrict ssh-rsa AAAA...

where everything including and after *ssh-rsa* is the public ssh key that 
corresponds the SSH key used to access the host.  This prevents any other use 
for this particular key.  If you want to also be able to log into this machine, 
you should add another public key to your *authorized_keys* file, and this 
public key should be associated with a private key that has a pass phrase.:w

This file contains the encryption pass phrase, and so you should be careful to 
set its permissions so that nobody but root can see its contents. Also, this 
configuration uses *repokey* as the encryption method, which is suitable when 
you control the server that holds the repository and you know it to be secure.  

Once this configuration is complete and has been tested, you would want to add 
a crontab entry so that it runs on a routine schedule. On servers that are 
always running, you could use `crontab -e` and add an entry like this:

.. code-block:: text

    30 03 * * * assimilate --mute --config root create

For individual workstations or laptops that are likely to be turned off at 
night, one would instead create an executable script in /etc/cron.daily that 
contains the following:

.. code-block:: bash

    #/bin/sh
    # Run root backups

    assimilate --mute --config root create

Assume that this file is named *assimilate*. Then after creating it, you would make 
it executable with:

.. code-block:: bash

    $ chmod a+x /etc/cron.daily/assimilate

Scripts in /etc/cron.daily are run once a day, either at a fixed time generally 
early in the morning or, if not powered up at that time, shortly after being 
powered up.


.. _user examples:

User
----

The *home* configuration is a suitable starting point for someone that just 
wants to backup their home directory on their laptop.  In this example, two 
configurations are created, one to be run manually that copies all files to 
a remote repository, and a second that runs every few minutes and creates 
snapshots of key working directories.  It saves to a local repository.  This 
second config allows you to quickly recover from mistakes you make during the 
day without having to go back to yesterday's copy of a file as a starting point.

Here is the contents of the shared settings file: ~/.config/assimilate/settings.

.. code-block:: nestedtext

    # generic settings

    # basic settings
    default config: home
    default mount point: ~/ASSIMILATE
    notifier: notify-send -u normal {prog_name} "{msg}"

    # excludes
    exclude if present: .nobackup
    exclude caches: 'yes
    exclude nodump: 'yes

    # personalize assimilate
    command aliases:
        repo-list:
            - archives
            - recent --last 20
        list: files

    logging:
        keep for: 1w
        max entries: 20

    list formats:
        name: {path}
        short: {path}{Type}
        date: {MTime:ddd YYYY-MM-DD HH:mm:ss} {path}{Type}
        size: {size:8} {path}{Type}
        si: {Size:7.2b} {path}{Type}
        owner: {user:8} {path}{Type}
        group: {group:8} {path}{Type}
        long: {mode:10} {user:6} {group:6} {size:8} {mtime} {path}{extra}

    default list format: short


.. _home example:

Home
^^^^

Here is the contents of the *home* configuration file: 
~/.config/assimilate/home.conf.nt.
This configuration backs up to a remote untrusted repository and is expected to 
be run interactively, perhaps once per day.

.. code-block:: nestedtext

    # home configuration

    # repository
    repository: backups:borg-backups/{host_name}-{config_name}
    archive: {config_name}-{{now}}
    encryption: keyfile-blake2-chacha20-poly1305
    pass command: avendesora --stdout borg-backups

    # composite commands
    prune_after_create: 'yes
    check_after_create: 'latest
    compact_after_delete: 'yes

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
        - - ~/tmp

    # prune settings
    keep within: 1d
    keep daily: 7
    keep weekly: 4
    keep monthly: 6

In this case we are assuming that *backups* (used in *repository*) is an entry 
in your SSH config file that points to the server that stores your repository.  
*backups* should be configured to use a private key and that key should be 
preloaded into your SSH agent.

The passphrase for this configuration is kept in `Avendesora 
<https://avendesora.readthedocs.io>`_, and the encryption method is *keyfile*.  
As such, it is critical that you extract the keyfile from *Borg* and copy it and 
your *Avendesora* files to a safe place so that both the keyfile and passphrase 
are available if you lose your disk. You can use `SpareKeys 
<https://github.com/kalekundert/sparekeys>`_ to do this for you. Otherwise 
extract the keyfile using:

.. code-block:: bash

    $ assimilate borg key export @repo key.borg

*cron* is not used for this configuration because the machine, being a laptop, 
is not guaranteed to be on at any particular time of the day. So instead, you 
would simply run *Assimilate* on your own at a convenient time using:

.. code-block:: bash

    $ assimilate

You can use the *Assimilate due* command to remind you if a backup is overdue. You 
can wire it into status bar programs, such as *i3status* to give you a visual 
reminder, or you can configure cron to check every hour and notify you if they 
are overdue. This one triggers a notification:

.. code-block:: text

    0 * * * * assimilate --mute due --days 1 || notify-send 'Backups are overdue'

And this one sends an email:

.. code-block:: text

    0 * * * * assimilate --mute due --days 1 --mail me@mydomain.com

Alternately, you can use :ref:`assimilate overdue <assimilate_overdue>`.


.. _snapshot example:

Snap Shots
^^^^^^^^^^

And finally, here is the contents of the *snapshots* configuration file: 
~/.config/assimilate/snapshots.conf.nt.

.. code-block:: nestedtext

    # snap shots configuration

    # repository
    repository: ~/.cache/backups
    archive: {config_name}-{{now}}
    encryption: none

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
        - - ~/Music
        - - ~/Videos
        - - ~/Pictures
        - - ~/.cache

    # prune settings
    keep within: 1d
    keep hourly: 48

To run this configuration every 10 minutes, add the following entry to your 
crontab file using 'crontab -e':

.. code-block:: text

    0,10,20,30,40,50 * * * * assimilate --mute --config snapshots create


.. _rsync.net example:

Rsync.net
---------

*Rsync.net* is a commercial option for off-site storage. In fact, they give you 
a discount if you use `Borg Backup <https://www.rsync.net/products/attic.html>`_.

Once you sign up for *Rsync.net* you can access your storage using *sftp*, 
*scp*, *rsync* or *borg* of course.  *ssh* access is also available, but only 
for a limited set of commands.

You would configure *Assimilate* for *Rsync.net* in much the same way you would for 
any remote server.  Of course, you should use some form of *keyfile* based 
encryption to keep your files secure.  The only thing to be aware of is that by 
default they provide a old version of borg. To use a newer version, set the 
``remote_path`` to ``borg1``.

.. code-block:: nestedtext

    repository: fm2034@fm2034.rsync.net:repo
    encryption: keyfile-blake2-chacha20-poly1305
    remote_path: borg1

In this example, ``fm2034`` is the user name and ``fm2034.rsync.net`` is the 
server they assign to you.  ``repo`` is the name of the directory that is to 
contain your *Borg* repository. You are free to name it whatever you like and 
you can have as many as you like, with the understanding that you are 
constrained in the total amount of storage you consume.


.. _borgbase example:

BorgBase
--------

`BorgBase <https://www.borgbase.com>`_ is another commercial alternative for 
*Borg Backups*.  It allows full *Borg* access, append-only *Borg* access, and 
*rsync* access, though each form of access requires its own unique SSH key.

Again, you should use some form of *keyfile* encryption to keep your files 
secure, and *BorgBase* recommends *Blake2* encryption as being the fastest 
alternative.

.. code-block:: nestedtext

    repository: zMNZCv4B@zMNZCv4B.repo.borgbase.com:repo
    encryption: keyfile-blake2-chacha20-poly1305

In this example, ``zMNZCv4B`` is the user name and 
``zMNZCv4B.repo.borgbase.com`` is the server they assign to you.  You may 
request any number of repositories, with each repository getting its own 
username and hostname. ``repo`` is the name of the directory that contains your 
*Borg* repository and cannot be changed.
