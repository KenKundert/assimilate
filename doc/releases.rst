.. include:: links.rst

Releases
========

*Assimilate* is suitable for use with *BorgBackup* version 2.0 or later.  For 
earlier versions of *Borg* you should use Emborg_.

.. important::

    *Assimilate* is designed to work with *Borg Backup v2.0*.  *Borg 2.0* is 
    currently in beta release, so neither *Borg* nor *Assimilate* should be used 
    in a production setting.  *Assimilate* is currently being tested against 
    *Borg v2.0.0b14*.

    Known issues:

    1. Normally the *Assimilate* :ref:`repo-create` command is expected to 
       create the parent directories needed to hold the repository.  It counts 
       on the ``--make-parent-dirs`` option to the *Borg* repo-create command, 
       which does not seem to be working.

    2. Normally *Assimilate* saves the size of the repository to the *latest.nt* 
       file.  However the repository size is not yet available in *Borg 2*.

    3. Currently the resolution of ``--newer``, ``--older``, ``--newest``, 
       ``--oldest`` is constrained to one day by *Borg*. That should be fixed in 
       the next release.


Latest development release
--------------------------
| Version: 0.0b6
| Released: 2025-02-08

0.0.0 (2025-??-??)
------------------
- Initial release
