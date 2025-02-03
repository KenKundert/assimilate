# Hard-Coded Preferences

# LICENSE {{{1
# Copyright (C) 2018-2025 Kenneth S. Kundert
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses.

# IMPORTS {{{1
from appdirs import user_config_dir, user_data_dir
from inform import dedent
import os


# PRERERENCES {{{1
# Executables {{{2
PROGRAM_NAME = "assimilate"
BORG = "borg"  # default command name for borg backup executable

# Directories {{{2
# Use XDG environment variables to override location of config and data
# directories
if 'XDG_CONFIG_HOME' in os.environ:
    CONFIG_DIR = os.sep.join([os.environ['XDG_CONFIG_HOME'], PROGRAM_NAME])
else:
    CONFIG_DIR = user_config_dir(PROGRAM_NAME)
if 'XDG_DATA_HOME' in os.environ:
    DATA_DIR = os.sep.join([os.environ['XDG_DATA_HOME'], PROGRAM_NAME])
else:
    DATA_DIR = user_data_dir(PROGRAM_NAME)

# Files {{{2
SHARED_SETTINGS_FILE = "shared.conf.nt"
OVERDUE_FILE = "overdue.conf.nt"
LOG_FILE = "{config_name}.log"
LOCK_FILE = "{config_name}.lock"
DATE_FILE = "{config_name}.latest.nt"

# Miscellaneous settings {{{2
INCLUDE_SETTING = "include"
DEFAULT_ENCODING = "utf-8"
DEFAULT_COMMAND = "create"
DEFAULT_ENCRYPTION = "none"

# Initial contents of files {{{2
# Shared settings {{{3
INITIAL_SHARED_SETTINGS_FILE_CONTENTS = dedent("""
    # These settings are common to all configurations
        ## edit this file as desired

    default config: ❬default-config❭
    composite configs: ❬composite-configs❭
        ## delete this line or leave empty if there are no composite configs

    # mount
    default mount point: ~/ASSIMILATE

    # how to notify you if things go wrong
    notify: ❬your-email-address❭
        ## who to notify when things go wrong, requires working mail command
    notifier: notify-send -u normal {prog_name} "{msg}"
        ## interactive notifier program

    # composite commands
    prune after create: 'yes
    check after create: 'latest
    compact after delete: 'yes

    # excludes
    exclude if present: .nobackup
    exclude caches: 'yes
    exclude nodump: 'yes

    # personalize assimilate
    command aliases:
        repo-list:
            - archives
            - a
            - recent --last=20
        list:
            - paths
            - l
            - ln -N
            - ls -S
            - ld -D
        overdue: od
        umount: unmount

    # composite log file
    logging:
        keep for: 1w
        max entries: 20

    # list formats
    default list format: short
    list formats:
        name: {path}
        short: {path}{Type}
        date: {MTime:ddd YYYY-MM-DD HH:mm:ss} {path}{Type}
        size: {size:8} {path}{Type}
        si: {Size:7.2b} {path}{Type}
        owner: {user:8} {path}{Type}
        group: {group:8} {path}{Type}
        long: {mode:10} {user:6} {group:6} {size:8} {mtime} {path}{extra}

    # overdue command
    overdue:
        max age: 36 h
        message: {description}: {updated} ago{locked: (currently active)}{overdue: — PAST DUE}
        repositories:
            # local
            cache@❬host❭ (/home/❬user❭):
                config: cache
                max age: 15m
            home@❬host❭ (/home/❬user❭):
                config: home

            # remote
            ❬remote-host❭:
                host: ❬remote-host❭
""", strip_nl='l')

# Root settings {{{3
INITIAL_ROOT_CONFIG_FILE_CONTENTS = dedent("""
    # Example config for root.
    # Backs up user and main system directories, avoiding those that contain
    # easily replaceable files (ex. /usr) and those that should not be backed up
    # (/dev).
    # Edit this file as desired, remove it if not needed.

    # repository
    repository: ❬host❭:❬path❭/{host_name}-{user_name}-{config_name}
    archive: {host_name}-{{now}}
    encryption: ❬encryption❭
    passphrase: ❬passcode❭
        # passphrase that unlocks encryption key
    pass command: ❬command❭
        # alternately, command that provides passphrase

    patterns:
        # directories to be backed up
        - R /etc
        - R /home
        - R /root
        - R /var
        - R /srv
        - R /opt
        - R /usr/local

        # directories/files to be excluded
        - - /var/cache
        - - /var/lock
        - - /var/run
        - - /var/tmp
        - - /root/.cache
        - - /home/*/.cache

    # prune settings
    keep within: 1d
    keep daily: 7
    keep weekly: 4
    keep monthly: 6
""", strip_nl='l')

# Home settings {{{3
INITIAL_HOME_CONFIG_FILE_CONTENTS = dedent("""
    # Example config for normal user.
    # Backs up user's home directory, avoiding uninteresting or easily
    # replaceable files.
    # Edit this file as desired, remove it if not needed.

    # repository
    repository: ❬host❭:❬path❭/{host_name}-{user_name}-{config_name}
    archive: {config_name}-{{now}}
    encryption: ❬encryption❭
    passphrase: ❬passcode❭
        # passphrase that unlocks encryption key
    pass command: ❬command❭
        # alternately, command that provides passphrase

    patterns:
        # directories to be backed up
        - R ~

        # patterns are applied in order
        # get rid of some always uninteresting files early so they do not get
        # pulled back in by inclusions later
        - - **/*~
        - - **/__pycache__
        - - **/.*.sw[ponml]

        # directories/files to be excluded
        - - .cache

    # prune settings
    keep within: 1d
    keep daily: 7
    keep weekly: 4
    keep monthly: 6
""", strip_nl='l')

# Cache settings {{{3
INITIAL_CACHE_CONFIG_FILE_CONTENTS = dedent("""
    # Example caching config for normal user.
    # Backs up user's home directory, avoiding uninteresting or easily
    # replaceable files.  Differs from home in that it has relatively short
    # prune settings.  Intended to be run frequently (ex. every 10 minutes) and
    # should focus on directories that contain files that you edit extensively
    # (ex. documents, source code directories).  Allow you to recover from goofs
    # you make during the day.  Generally want to locate repository on the local
    # machine in fast storage to reduce the load from frequent backups.
    # Edit this file as desired, remove it if not needed.

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
        - - **/.sw[ponml]

        # directories/files to be excluded
        - - Music
        - - Videos
        - - Pictures
        - - .cache

    # prune settings
    keep within: 1d
    keep hourly: 48
""", strip_nl='l')
