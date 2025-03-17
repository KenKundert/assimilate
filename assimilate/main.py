# Usage {{{1
"""
Assimilate Backups

Backs up the contents of a file hierarchy.  A front end for Borg's
encrypted incremental backup utility.

Usage:
    assimilate [options] [<command> [<args>...]]

Options:
    -c <cfgname>, --config <cfgname>  Specifies the configuration to use.
    -d, --dry-run                     Run Borg in dry run mode.
    -h, --help                        Output basic usage information.
    -m, --mute                        Suppress all output.
    -n, --narrate                     Send Assimilate and Borg narration to stdout.
    -N, --name <name>                 Apply <name> to this invocation in nt log file
    -q, --quiet                       Suppress optional output.
    -r, --relocated                   Acknowledge that repository was relocated.
    -v, --verbose                     Make Borg more verbose.
    --no-log                          Do not create log file.
"""

# License {{{1
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


# Imports {{{1
import os
import sys
from inform import (
    Error, Inform, LoggingCache, cull, display, error, os_error, terminate
)
from . import __released__, __version__
from .assimilate import ConfigQueue, Assimilate
from .command import Command
from .configs import read_settings
from .hooks import Hooks
from .utilities import process_cmdline

# Globals {{{1
version = f"{__version__} ({__released__})"
commands = """
Commands:
{commands}

Use 'assimilate help <command>' for information on a specific command.
Use 'assimilate help' for list of available help topics.
"""
synopsis = __doc__
expanded_synopsis = synopsis + commands.format(commands=Command.summarize())


# Main {{{1
def main():
    with Inform(
        error_status = 2,
        flush = True,
        logfile = LoggingCache(),
        prog_name = 'assimilate',
        stream_policy = 'all',
        version = version,
    ) as inform:

        try:
            worst_exit_status = 0
            exit_status = 0

            # assimilate fails if the current working directory does not exist and
            # the message returned by OSError does not make the problem obvious.
            try:
                os.getcwd()
            except OSError as e:
                raise Error(os_error(e), codicil="Does the current working directory exist?")

            # interpret command line
            cmdline = process_cmdline(expanded_synopsis, options_first=True, version=version)
            command = cmdline["<command>"]
            args = cmdline["<args>"]
            if cmdline["--mute"]:
                inform.mute = True
            if cmdline["--quiet"]:
                inform.quiet = True
            if cmdline["--relocated"]:
                os.environ['BORG_RELOCATED_REPO_ACCESS_IS_OK'] = 'YES'
            options = cull(
                {
                    "verbose": cmdline["--verbose"],
                    "narrate": cmdline["--narrate"],
                    "dry-run": cmdline["--dry-run"],
                    "no-log": cmdline["--no-log"],
                    "config": cmdline["--config"],
                        # config must be given in options as it is needed for
                        # overdue command, which is run early
                }
            )
            if cmdline["--narrate"]:
                inform.narrate = True

            # read shared settings
            Hooks.provision_hooks()
            shared_settings = read_settings('shared')

            # find the command
            cmd, cmd_name, alias_args = Command.find(command, shared_settings)
            args = alias_args + args

            # execute the command initialization
            exit_status = cmd.execute_early(cmd_name, args, None, options)
            if exit_status is not None:
                terminate(exit_status)

            queue = ConfigQueue(cmd)
            while queue:
                with Assimilate(
                    cmdline["--config"], options, shared_settings=shared_settings,
                    queue=queue, cmd_name=cmd_name, run_name=cmdline["--name"]
                ) as settings:
                    try:
                        exit_status = cmd.execute(
                            cmd_name, args, settings, options
                        )
                        exit_status = exit_status or 0
                    except Error as e:
                        exit_status = 2
                        settings.fail(e, cmd=' '.join(sys.argv))
                        e.report()

                if inform.errors_accrued(reset=True):
                    exit_status = min(exit_status, 2)
                worst_exit_status = max(worst_exit_status, exit_status)

            # execute the command termination
            exit_status = cmd.execute_late(cmd_name, args, None, options)
            exit_status = exit_status or 0
            worst_exit_status = max(worst_exit_status, exit_status)

        except Error as e:
            exit_status = 2
            e.report()
        except OSError as e:
            exit_status = 2
            error(os_error(e))
        except KeyboardInterrupt:
            display("Terminated by user.")
        terminate(max(worst_exit_status, exit_status))
