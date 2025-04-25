# Commands

# License {{{1
# Copyright (C) 2016-2025 Kenneth S. Kundert
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
import json
import nestedtext as nt
import os
import sys
from textwrap import dedent, fill
import arrow
from contextlib import contextmanager
from inform import (
    Color,
    Error,
    conjoin,
    display,
    full_stop,
    get_informer,
    indent,
    is_collection,
    is_str,
    join,
    log,
    narrate,
    os_error,
    plural,
    title_case,
    truth,
    warn,
)
from time import sleep
from .assimilate import borg_commands_with_dryrun
from .configs import ASSIMILATE_SETTINGS, BORG_SETTINGS, READ_ONLY_SETTINGS
from .overdue import overdue, OVERDUE_USAGE
from .preferences import DEFAULT_COMMAND, PROGRAM_NAME
from .utilities import (
    gethostname, output, pager, process_cmdline, read_latest, table, to_date,
    to_days, to_seconds, two_columns, update_latest, when,
    Quantity, QuantiPhyError, UnknownConversion,
    Cmd, Run, cwd, lsd, mkdir, rm, split_cmd, to_path
)


# Globals {{{1
hostname = gethostname()
prune_intervals = """
    within last minutely hourly daily weekly monthly 3monthly 13weekly yearly
""".split()

# Utilities {{{1
# title() {{{2
def title(text):
    return full_stop(title_case(text))


# get_available_archives() {{{2
def get_available_archives(settings):
    # run borg
    borg = settings.run_borg(cmd="repo-list", args=["--json"])
    try:
        data = json.loads(borg.stdout)
        return data["archives"]
    except json.decoder.JSONDecodeError as e:  # pragma: no cover
        raise Error("Could not decode output of Borg list command.", codicil=e)


# get_latest_archive() {{{2
def get_latest_archive(settings):
    borg = settings.run_borg(cmd="repo-list", args=["--json", "--last=1"])
    try:
        data = json.loads(borg.stdout)
        if data["archives"]:
            return data["archives"][-1]
    except json.decoder.JSONDecodeError as e:  # pragma: no cover
        raise Error("Could not decode output of Borg list command.", codicil=e)

# find_archive() {{{2
def find_archive(settings, options):
    first_before = options.get('--before')
    first_after = options.get('--after')
    identifier = options.get('--archive')
    if first_before and first_after:
        raise Error('must not specify both --before and --after.')
    time_thresh = first_before or first_after
    if time_thresh and identifier:
        raise Error('must not specify both --archive and --before or --after.')

    def desc_and_id(archive):
        if not archive:  # pragma: no cover
            raise Error('no suitable archive found.')
        return f"aid:{archive['id']}", archive_desc(archive)
            # aid: prefix indicates that what follows is an archive id

    # find archive closest to time threshold
    if time_thresh:
        target = to_date(time_thresh)

        # find oldest archive that is younger than specified target
        older_archive = None
        for newer_archive in get_available_archives(settings):
            newer_time = arrow.get(newer_archive["time"], tzinfo='local')
            if newer_time >= target:
                # we have crossed the time threshold
                if first_after:
                    return desc_and_id(newer_archive)
                elif older_archive:
                    return desc_and_id(older_archive)
                else:
                    warn(
                        f'archive older than {time_thresh} ({target.humanize()}) was not found.',
                        codicil='Using oldest available.'
                    )
                    return desc_and_id(newer_archive)
            older_archive = newer_archive
        if older_archive:
            if first_after:
                warn(
                    f'archive younger than {time_thresh} ({target.humanize()}) was not found.',
                    codicil='Using youngest that is older than given date or age.'
                )
            return desc_and_id(older_archive)
        raise Error(
            "no archives available."
        )

    if identifier:
        # assume identifier is an index and return id of corresponding archive
        try:
            index = int(identifier)
            archives = get_available_archives(settings)
            try:
                archive = list(reversed(archives))[index]
                return desc_and_id(archive)
            except IndexError:
                raise Error("index out of range.")
        except ValueError:
            pass

        # not an index, return it and let borg figure it out
        return identifier, None

    # no identifier was given, so return the id of the most recent archive
    archive = get_latest_archive(settings)
    return desc_and_id(archive)

# archive_filter_options() {{{2
def archive_filter_options(settings, given_options, default):
    archive = "--archive" in given_options and given_options["--archive"]
    first_before = "--before" in given_options and given_options["--before"]
    first_after = "--after" in given_options and given_options["--after"]
    if archive or first_before or first_after:
        # user specified that only a single archive is desired
        archive, description = find_archive(settings, given_options)
        return [f"--match-archives={archive}"]

    processed_options = []
    age_opts = ('--older', '--oldest', '--newer', '--newest')
    seen = []
    for opt in age_opts:
        value = given_options.get(opt)
        if value:
            seen.append(opt)
            if opt in ('--older', '--newer'):
                target = to_date(value)
                seconds = (arrow.now() - target).total_seconds()
            else:
                seconds = to_seconds(value)
            days = round(seconds/60/60/24)
            processed_options.append(f"{opt}={days}d")
            # processed_options.append(f"{opt}={round(seconds)}S")
    if len(seen) > 1:
        raise Error(f"incompatible options: {', '.join(seen)}.")

    cardinality_opts = ('--first', '--last')
    seen = []
    for opt in cardinality_opts:
        value = given_options.get(opt)
        if value:
            try:
                v = int(value)
            except ValueError:
                v = 0
            if v <= 0:
                raise Error(f'expected positive integer, found ‘{value}’.', culprit=opt)
            seen.append(opt)
            processed_options.append(f"{opt}={value}")
    if len(seen) > 1:
        raise Error(f"incompatible options: {', '.join(seen)}.")

    if given_options.get('--deleted'):
        processed_options.append('--deleted')

    if not processed_options:
        if default == "latest":
            processed_options = ['--last=1']
        elif default != 'all':
            raise NotImplementedError
    return processed_options


# list_archives {{{2
def list_archives(data, cmdline):
    archives = []
    no_index = any(
        cmdline[n]
        for n in [
            "--first", "--newer", "--older", "--newest", "--oldest",
            "--include-external", "--deleted"
        ]
    )
    num_archives = len(data['archives'])
    for i, each in enumerate(data['archives']):
        id = each.get('id', '')[:8]
        date = each.get('time', '')
        if date:
            date = arrow.get(date)
            date = f"{date.format('YYYY-MM-DD h:mm A')} ({date.humanize()})"
        archive = each.get('archive', '')
        if no_index:
            archives.append((f"aid:{id}", archive, date))
        else:
            archives.append((f"{num_archives-i-1:<3} aid:{id}", archive, date))
    return '\n'.join(table(archives))

# archive_desc {{{2
def archive_desc(archive):
    name = archive.get('archive')
    id = archive.get('id')[:8]
    date = archive.get('time', '')
    if date:
        date = arrow.get(date)
        date = f" {date.format('YYYY-MM-DD h:mm A')} ({date.humanize()})"
    return f"{id} {name}{date}"

# get_archive_paths() {{{2
def get_archive_paths(paths, settings):
    # Need to construct a path to the file that is compatible with those
    # paths stored in borg, thus it must begin with a src_dir (cannot just
    # use the absolute path because the corresponding src_dir path may
    # contain a symbolic link, in which the absolute path would not be found
    # in the borg repository.
    # Convert to paths relative to the working directory.
    #
    paths_not_found = set(paths)
    resolved_paths = []
    settings.resolve_patterns([], skip_checks=True)
    for root_dir in settings.roots:
        resolved_root_dir = (settings.working_dir / root_dir).resolve()
        for name in paths:
            path = to_path(name)
            resolved_path = path.resolve()
            try:
                # get relative path from root_dir to path after resolving
                # symbolic links in both root_dir and path
                path = resolved_path.relative_to(resolved_root_dir)

                # add original root_dir (with sym links) to relative path
                path = to_path(settings.working_dir, root_dir, path)

                # get relative path from working dir to computed path
                # this will be the path contained in borg archive
                path = path.relative_to(settings.working_dir)

                resolved_paths.append(path)
                if name in paths_not_found:
                    paths_not_found.remove(name)
            except ValueError:
                pass
    if paths_not_found:
        raise Error(
            f"not contained in a source directory: {conjoin(paths_not_found)}."
        )
    return resolved_paths


# get_archive_path() {{{2
def get_archive_path(path, settings):
    paths = get_archive_paths([path], settings)
    assert len(paths) == 1
    return paths[0]

# make_quiet() {{{2
@contextmanager
def make_quiet():
    # Code to acquire resource, e.g.:
    try:
        informer = get_informer()
        prev_quiet = informer.quiet
        informer.quiet = True
        yield
    finally:
        informer.quiet = prev_quiet


# Command base class {{{1
class Command:
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "error"
        # possible values are:
        #     'error': emit error if applied to composite config
        #     'all'  : use all configs of composite config in sequence
        #     'first': only use the first config in a composite config
        #     'none' : do not use any of configs in composite config
    SHOW_CONFIG_NAME = True
    LOG_COMMAND = True

    @classmethod
    def commands(cls):
        for cmd in cls.__subclasses__():
            yield cmd

    @classmethod
    def commands_sorted(cls):
        for cmd in sorted(cls.commands(), key=lambda c: c.get_name()):
            yield cmd

    @classmethod
    def find(cls, name, shared_settings=None):
        # process aliases
        alias_args = {}
        args = []
        if not name:
            name = DEFAULT_COMMAND
        elif shared_settings:
            cls.cmd_name_map = {}
            cls.cmd_alias = {}
            for cmd, aliases in shared_settings.get('command_aliases', {}).items():
                for alias in aliases:
                    try:
                        alias, args = alias.split(maxsplit=1)
                        cls.cmd_alias[alias] = f"{cmd} {args}"
                        alias_args[alias] = args.split()
                    except ValueError:
                        pass
                    cls.cmd_name_map[alias] = cmd
            args = alias_args.get(name, [])
            name = cls.cmd_name_map.get(name, name)

        # find and return the command
        for command in cls.commands():
            if name in command.NAMES:
                return command, command.NAMES[0], args
        raise Error("unknown command.", culprit=name)

    @classmethod
    def execute_early(cls, name, args, settings, options):
        # execute_early() takes same arguments as run(), but is run before the
        # settings files have been read.  As such, the settings argument is None.
        # run_early() is used for commands that do not need settings and should
        # work even if the settings files do not exist or are not valid.

        # first check that command supports --dry-run if it was specified
        if 'dry-run' in options:
            if name not in borg_commands_with_dryrun:
                raise Error(f"--dry-run is not available with {name} command.")

        # now execute run_early if available
        if hasattr(cls, "run_early"):
            narrate(f"running pre-command: {name}")
            return cls.run_early(name, args if args else [], settings, options)

    @classmethod
    def execute(cls, name, args, settings, options):
        if hasattr(cls, "run"):
            narrate(f"running command: {name}")
            exit_status = cls.run(name, args if args else [], settings, options)
            return 0 if exit_status is None else exit_status

    @classmethod
    def execute_late(cls, name, args, settings, options):
        # execute_late() takes same arguments as run(), but is run after all the
        # configurations have been run.  As such, the settings argument is None.
        # run_late() is used for commands that want to create a summary that
        # includes the results from all the configurations.
        if hasattr(cls, "run_late"):
            narrate(f"running post-command: {name}")
            return cls.run_late(name, args if args else [], settings, options)

    @classmethod
    def summarize(cls, width=16):
        summaries = []
        for cmd in Command.commands_sorted():
            summaries.append(two_columns(", ".join(cmd.NAMES), cmd.DESCRIPTION))
        return "\n".join(summaries)

    @classmethod
    def get_name(cls):
        return cls.NAMES[0]

    @classmethod
    def help(cls):
        text = dedent(
            """
            {title}

            {usage}
            """
        ).strip()

        return text.format(title=title(cls.DESCRIPTION), usage=cls.USAGE,)


# BorgCommand command {{{1
class BorgCommand(Command):
    NAMES = "borg".split()
    DESCRIPTION = "run a raw borg command"
    USAGE = dedent(
        """
        Usage:
            assimilate borg <borg_args>...

        You can specify the repository to act on using “@repo”, which is
        replaced with the path to the repository.  The passphrase is set before
        the command is run.

        Be aware that the Borg is run from ‘working_dir’ (default is /), and
        so any relative paths given as command line arguments are relative to
        ‘working_dir’.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "error"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args, options_first=True)
        borg_args = cmdline["<borg_args>"]

        # run borg
        borg = settings.run_borg_raw(borg_args)
        out = borg.stderr or borg.stdout
        if out:
            output(out.rstrip())

        return borg.status


# BreakLockCommand command {{{1
class BreakLockCommand(Command):
    NAMES = "break-lock".split()
    DESCRIPTION = "breaks the repository and cache locks"
    USAGE = dedent(
        """
        Usage:
            assimilate break-lock

        Breaks both the local and the repository locks.  Use carefully and only
        if no *Borg* process (on any machine) is trying to access the cache or
        the repository.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = False
    COMPOSITE_CONFIGS = "error"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        process_cmdline(cls.USAGE, argv=[command] + args)

        # remove assimilate lock file
        rm(settings.lockfile)

        # run borg to break the lock
        borg = settings.run_borg(
            cmd="break-lock", assimilate_opts=options,
        )
        out = borg.stderr or borg.stdout
        if out:
            output(out.rstrip())

        return borg.status


# CheckCommand command {{{1
class CheckCommand(Command):
    NAMES = "check".split()
    DESCRIPTION = "checks the repository and its archives"
    USAGE = dedent(
        """
        Usage:
            assimilate check [options]

        Options:
            -a, --archive <archive>     name of the archive to mount
            -A, --after <date_or_age>   use first archive younger than given
            -B, --before <date_or_age>  use first archive older than given
            -f, --first <N>             consider first N archives that remain
            -l, --last <N>              consider last N archives that remain
            -n, --newer <age>           only consider archives newer than age
            -o, --older <age>           only consider archives older than age
            -N, --newest <range>        only consider archives between newest and
                                        newest-range
            -O, --oldest <range>        only consider archives between oldest and
                                        oldest+range
            -*, --all                   check all available archives
            -e, --include-external      check all archives in repository, not just
                                        those associated with chosen configuration
            -r, --repair                attempt to repair any inconsistencies found
            -v, --verify-data           perform a full integrity verification (slow)
            --archives-only             perform only archive checks
            --repository-only           perform only repository checks
            --find-lost-archives        look for orphaned archives (slow)

        The most recently created archive is checked if one is not specified
        unless ––all is given, in which case all archives are checked.

        You can select individual archives to check using the ––archive, ––before,
        and ––after command line options.  See the help message for list command
        for details on how to select individual archives.

        You can select groups archives to check using the ––first, ––last,
        ––newer, ––older, ––newest, and ––oldest options.  See the help message
        for repo-list command for details on how to select multiple archives.

        Be aware that the ––repair option is considered a dangerous operation
        that might result in the complete loss of corrupt archives.  It is
        recommended that you create a backup copy of your repository and check
        your hardware for the source of the corruption before using this
        option.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "all"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        check_all = cmdline["--all"]
        strip_archive_matcher = cmdline["--include-external"]
        # identify archive or archives to check
        default = 'all' if check_all else 'latest'
        borg_opts = archive_filter_options(settings, cmdline, default=default)

        # determine borg arguments
        args = []
        if cmdline["--archives-only"]:
            args.append("--archives-only")
        if cmdline["--repository-only"]:
            args.append("--repository-only")
            # strip off archive specific options
            strip_archive_matcher = True
            borg_opts = []
        elif cmdline["--verify-data"]:
            args.append("--verify-data")
        if cmdline["--find-lost-archives"]:
            args.append("--find-lost-archives")
        if cmdline["--repair"]:
            args.append("--repair")
            os.environ['BORG_CHECK_I_KNOW_WHAT_I_AM_DOING'] = 'YES'

        # run borg
        borg = settings.run_borg(
            cmd = "check",
            args = args,
            assimilate_opts = options,
            borg_opts = borg_opts,
            strip_archive_matcher = strip_archive_matcher,
        )
        if cmdline["--repair"]:
            out = borg.stdout
                # suppress borg's stderr during repairs
        else:
            out = borg.stderr or borg.stdout
        if out:
            output(out.rstrip())

        if borg.status:
            raise Error('repository is corrupt.')

        # update the date file
        if not("problems found" in borg.stderr or "errors found" in borg.stderr):
            update_latest('check', settings.date_file, options)


# CompactCommand command {{{1
class CompactCommand(Command):
    NAMES = "compact".split()
    DESCRIPTION = "compact segment files in the repository"
    USAGE = dedent(
        """
        Usage:
            assimilate compact [options]

        Options:
            -p, --progress   shows Borg progress
            -s, --stats      show Borg statistics

        This command frees repository space by compacting segments.

        Use this regularly to avoid running out of space, however you do not
        need to it after each Borg command. It is especially useful after
        deleting archives, because only compaction will really free repository
        space.

        Requires Borg version 1.2 or newer.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "all"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        borg_opts = []
        if cmdline["--progress"] or settings.show_progress:
            borg_opts.append("--progress")
        if cmdline["--stats"] or settings.show_stats:
            borg_opts.append("--stats")

        # run borg
        borg = settings.run_borg(
            cmd = "compact",
            borg_opts = borg_opts,
            assimilate_opts = options,
            show_borg_output = "--stats" in borg_opts,
        )
        out = borg.stderr or borg.stdout
        if out:
            output(out.rstrip())

        # update the date file
        update_latest('compact', settings.date_file, options)

        return borg.status


# CompareCommand command {{{1
class CompareCommand(Command):
    NAMES = "compare".split()
    DESCRIPTION = "compare local files or directories to those in an archive"
    USAGE = dedent(
        """
        Usage:
            assimilate compare [options] [<path>]

        Options:
            -a, --archive <archive>     name of the archive to compare against
            -A, --after <date_or_age>   use first archive younger than given
            -B, --before <date_or_age>  use first archive older than given
            -i, --interactive           perform an interactive comparison

        Reports and allows you to manage the differences between your local
        files and those in an archive.  The base command simply reports the
        differences:

            $ assimilate compare

        The ––interactive option allows you to manage those differences.
        Specifically, it will open an interactive file comparison tool that
        allows you to compare the contents of your files and copy differences
        from the files in the archive to your local files:

            $ assimilate compare -i

        You can specify the archive by name or by date or age or index, with 0
        being the most recent.  If you do not you will use the most recent
        archive.

            $ assimilate compare ––archive continuum-2020-12-04T17:41:28
            $ assimilate compare ––archive 2
            $ assimilate compare ––before 2020-12-04
            $ assimilate compare ––before 1w

        See the help message for list command for more detail on how to select
        an archive.

        You can specify a path to a file or directory to compare, if you do not
        you will compare the files and directories of the current working
        directory.

            $ assimilate compare tests
            $ assimilate compare ~/bin

        This command requires that the following settings be specified in your
        settings file: manage_diffs_cmd, report_diffs_cmd, and
        default_mount_point.

        The command operates by mounting the desired archive, performing the
        comparison, and then unmounting the directory.  Problems sometimes occur
        that can result in the archive remaining mounted.  In this case you will
        need to resolve any issues that are preventing the unmounting, and then
        explicitly run the :ref:`unmount command <umount>` before you can use
        this *Borg* repository again.

        This command differs from the :ref:`diff command <diff>` in that it
        compares local files to those in an archive where as :ref:`diff <diff>`
        compares the files contained in two archives.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "first"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        mount_point = settings.as_path("default_mount_point")
        if not mount_point:
            raise Error("must specify default_mount_point setting to use this command.")
        path = cmdline['<path>']
        if not path:
            path = '.'

        # get the desired archive
        if cmdline["--archive"]:
            archive = cmdline["--archive"]
        else:
            archive, description = find_archive(settings, cmdline)
            if description:
                display(f'archive: {description}')

        # get diff tool
        if cmdline['--interactive']:
            differ = settings.manage_diffs_cmd
            if not differ:
                narrate("manage_diffs_cmd not set, trying report_diffs_cmd.")
                differ = settings.report_diffs_cmd
        else:
            differ = settings.report_diffs_cmd
            if not differ:
                narrate("report_diffs_cmd not set, trying manage_diffs_cmd.")
                differ = settings.manage_diffs_cmd
        if not differ:
            raise Error("no diff command available.")

        # create mount point
        if mount_point.exists():
            raise Error(
                "attempting to mount onto existing file or directory",
                culprit = mount_point
            )
        try:
            mkdir(mount_point)
        except OSError as e:
            raise Error(os_error(e))

        # run borg to mount
        try:
            settings.run_borg(
                cmd = "mount",
                borg_opts = [f"--match-archives={archive}"],
                args = [mount_point],
                assimilate_opts = options,
            )

            # resolve the path relative to working directory
            archive_path = to_path(path).resolve().relative_to(settings.working_dir)
            candidate_paths = list(lsd(mount_point, select='*'))
                # the name used by borg for the archive is difficult to predict
                # but there should just be one, so use it
            if len(candidate_paths) == 1:
                archive_path = to_path(candidate_paths[0], archive_path)
            else:
                if candidate_paths:
                    codicil = join(
                        "The following archives were found:",
                        *[str(p) for p in candidate_paths],
                        sep='\n    '
                    )
                else:
                    codicil = None
                raise Error(
                    f"{plural(candidate_paths)://Too many/ No} archives available.",
                    culprit=mount_point, codicil=codicil
                )

            # run diff tool
            if is_str(differ):
                cmd = differ.format(
                    archive_path = str(archive_path),
                    local_path = str(path)
                )
                if cmd == differ:
                    cmd = split_cmd(differ) + [archive_path, path]
            else:
                cmd = differ + [archive_path, path]
            try:
                diff = Cmd(cmd, modes='soEW1')
                diff.run()
            except Error as e:
                codicil = e.stdout if e.stdout and not e.stderr else None
                e.report(codicil=codicil)
            except KeyboardInterrupt:
                log('user killed compare command.')
                diff.kill()

        finally:
            # run borg to un-mount
            sleep(0.25)
            settings.run_borg(
                cmd="umount", args=[mount_point], assimilate_opts=options,
            )
            try:
                mount_point.rmdir()
            except OSError as e:
                warn(os_error(e), codicil="You will need to unmount before proceeding.")

        return diff.status


# ConfigsCommand command {{{1
class ConfigsCommand(Command):
    NAMES = "configs".split()
    DESCRIPTION = "list available backup configurations"
    USAGE = dedent(
        """
        Usage:
            assimilate configs
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = False
    COMPOSITE_CONFIGS = "none"
    LOG_COMMAND = False

    @classmethod
    def run(cls, command, args, settings, options):
        # check command line for errors
        process_cmdline(cls.USAGE, argv=[command] + args)

        configs = list(settings.configs)
        if settings.composite_configs:
            composite_configs = [
                f"{k} = {', '.join(v.split())}"
                for k, v in settings.composite_configs.items()
            ]
            configs += composite_configs
        if configs:
            output("Available Configurations:", *sorted(configs), sep="\n    ")
        else:
            output("No configurations available.")

        output()

        default_config = settings.default_config
        if default_config:
            output("Default Configuration:", default_config, sep="\n    ")
        else:
            output("No default configuration available.")


# CreateCommand command {{{1
class CreateCommand(Command):
    NAMES = "create".split()
    DESCRIPTION = "create an archive of the current files"
    USAGE = dedent(
        """
        Usage:
            assimilate create [options]

        Options:
            -f, --fast       skip pruning and checking for a faster backup on a slow network
            -l, --list       list the files and directories as they are processed
            -p, --progress   shows Borg progress
            -s, --stats      show Borg statistics

        To see the files listed as they are backed up, use the Assimilate -v option.
        This can help you debug slow create operations.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "all"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        repo_size = None

        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        borg_opts = []
        if cmdline["--stats"] or settings.show_stats:
            borg_opts.append("--stats")
        if cmdline["--list"]:
            borg_opts.append("--list")
        if cmdline["--progress"] or settings.show_progress:
            borg_opts.append("--progress")
            announce = display
        else:
            announce = narrate

        # check the dependencies are available
        must_exist = settings.as_paths("must_exist")
        for path in must_exist:
            if not path.exists():
                raise Error(
                    "does not exist; perform setup and restart.",
                    culprit = ("must_exist", path),
                )

        # run commands specified to be run before a backup
        prerequisite_settings = []
        if settings.is_first_config():
            prerequisite_settings.append("run_before_first_backup")
        prerequisite_settings.append("run_before_backup")
        for setting in prerequisite_settings:
            for i, cmd in enumerate(settings.values(setting)):
                narrate(f"staging {setting}[{i}] pre-backup script")
                try:
                    Run(cmd, "SoEW")
                except Error as e:
                    e.reraise(culprit=(setting, i, cmd.split()[0]))

        # run borg
        src_dirs = settings.src_dirs
        with settings.hooks as hooks:
            try:
                tries_left = max(settings.value("create_retries", 1), 1)
                while tries_left:
                    try:
                        borg = settings.run_borg(
                            cmd = "create",
                            borg_opts = borg_opts.copy(),
                            args = [settings.value('archive')] + src_dirs,
                            assimilate_opts = options,
                            show_borg_output = "--stats" in borg_opts,
                            use_working_dir = True,
                        )
                        break
                    except Error as e:
                        if e.stderr and "is not a valid repository" in e.stderr:
                            e.reraise(codicil="Run 'assimilate init' to initialize the repository.")
                        tries_left -= 1
                        if tries_left:
                            narrate('Will try again.')
                        else:
                            raise
                        seconds = max(settings.value("create_retry_sleep", 0), 0)
                        narrate(f"waiting for {seconds:.0f} seconds.")
                        sleep(seconds)
                update_latest('create', settings.date_file, options)
                create_status = borg.status
                hooks.report_results(borg)
            finally:
                # run commands specified to be run after a backup
                postrequisite_settings = ["run_after_backup"]
                if settings.is_last_config():
                    postrequisite_settings.append("run_after_last_backup")
                for setting in postrequisite_settings:
                    for i, cmd in enumerate(settings.values(setting)):
                        narrate(f"staging {setting}[{i}] post-backup script")
                        try:
                            Run(cmd, "SoEW")
                        except Error as e:
                            e.reraise(culprit=(setting, i, cmd.split()[0]))

        if cmdline["--fast"]:
            # update the date file
            return create_status

        # check and prune the archives if requested
        try:
            with make_quiet():
                # check the archives if requested
                check_status = 0
                check_after_create = settings.check_after_create
                if check_after_create and check_after_create != "no":
                    activity = "checking"
                    announce("Checking repository ...")
                    args = []
                    if check_after_create == "all":
                        args = ["--all"]
                    elif check_after_create == "all_in_repository":
                        args = ["--all", "--include-external"]
                    check = CheckCommand()
                    try:
                        check.run("check", args, settings, options)
                    except Error:
                        check_status = 1

                # prune the repository if requested
                activity = "pruning"
                if settings.prune_after_create:
                    announce("Pruning repository ...")
                    prune = PruneCommand()
                    prune_status = prune.run("prune", [], settings, options)
                else:
                    prune_status = 0

                # get the size of the repository
                activity = "sizing"
                # now output the information from borg about the repository
                info = settings.run_borg(
                    cmd = "repo-info",
                    assimilate_opts = options,
                    borg_opts = ['--json'],
                    strip_archive_matcher = True,
                )
                data = json.loads(info.stdout)
                try:
                    repo_size = Quantity(data['cache']['stats']['unique_csize'], 'B')
                    repo_size = repo_size.render(prec='full')
                except KeyError:
                    repo_size = None
                    #KSK warn('repository size information is not available.')

        except Error as e:
            e.reraise(
                codicil = (
                    f"This error occurred while {activity} the repository.",
                    "No error was reported while creating the archive.",
                )
            )

        return max([create_status, check_status, prune_status, info.status])

# DeleteCommand command {{{1
class DeleteCommand(Command):
    NAMES = "delete".split()
    DESCRIPTION = "delete an archive currently contained in the repository"
    USAGE = dedent(
        """
        Usage:
            assimilate delete [options]

        Options:
            -a, --archive <archive>     name of the archive to mount
            -A, --after <date_or_age>   use first archive younger than given
            -B, --before <date_or_age>  use first archive older than given
            -f, --first <N>             consider first N archives that remain
            -l, --last <N>              consider last N archives that remain
            -n, --newer <age>           only consider archives newer than age
            -o, --older <age>           only consider archives older than age
            -N, --newest <range>        only consider archives between newest and
                                        newest-range
            -O, --oldest <range>        only consider archives between oldest and
                                        oldest+range
            -e, --include-external      include all archives in repository, not just
                                        those associated with chosen configuration
            -F, --fast                  skip compacting
            --list                      list deleted archives

        The delete command deletes the specified archives.  If no archive is
        specified, the latest is deleted.

        You can select individual archives to delete using the ––archive,
        ––before, and ––after command line options.  See the help message for
        list command for details on how to select individual archives.

        You can select groups archives to delete using the ––first, ––last,
        ––newer, ––older, ––newest, and ––oldest options.  See the help message
        for repo-list command for details on how to select multiple archives.

        The disk space associated with deleted archives is not reclaimed until
        the compact command is run.  You can specify that a compaction is
        performed as part of the deletion by setting compact_after_delete.  If
        set, the ––fast flag causes the compaction to be skipped.  If not set,
        the ––fast flag has no effect.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "error"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        borg_opts = archive_filter_options(settings, cmdline, default='latest')
        list_opt = ['--list'] if cmdline['--list'] or 'dry-run' in options else []
        include_external_archives = cmdline["--include-external"]

        # run borg
        borg = settings.run_borg(
            cmd = "delete",
            assimilate_opts = options,
            borg_opts = borg_opts + list_opt,
            strip_archive_matcher = include_external_archives,
        )
        out = borg.stderr or borg.stdout
        if out and not ('borg compact' in borg.stderr and settings.compact_after_delete):
            output(out.rstrip())
        delete_status = borg.status

        if cmdline["--fast"]:
            return delete_status

        try:
            # compact the repository if requested
            if settings.compact_after_delete and 'dry-run' not in options:
                narrate("Compacting repository ...")
                compact = CompactCommand()
                compact_status = compact.run("compact", [], settings, options)
            else:
                compact_status = 0

        except Error as e:
            e.reraise(
                codicil = (
                    "This error occurred while compacting the repository.",
                    "No error was reported while deleting the archive.",
                )
            )

        return max([delete_status, compact_status])


# DiffCommand command {{{1
class DiffCommand(Command):
    NAMES = "diff".split()
    DESCRIPTION = "show the differences between two archives"
    USAGE = dedent(
        """
        Usage:
            assimilate diff [options] <archive1> <archive2> [<path>]

        Options:
            -R, --recursive                     show files in sub directories
                                                when path is specified

        Shows the differences between two archives.  You can constrain the 
        output listing to only those files in a particular directory by 
        adding that path to the end of the command.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "error"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        archive1 = cmdline["<archive1>"]
        archive2 = cmdline["<archive2>"]
        path = cmdline['<path>']
        recursive = cmdline['--recursive']

        # resolve the path relative to working directory
        if path:
            path = str(get_archive_path(path, settings))
        else:
            path = ''

        # run borg
        borg = settings.run_borg(
            cmd = "diff",
            args = [archive1, archive2],
            assimilate_opts = options,
            borg_opts = ['--json-lines'],
        )

        # convert from JSON-lines to JSON
        json_data = '[' + ','.join(borg.stdout.splitlines()) + ']'
        diffs = json.loads(json_data)

        for diff in diffs:
            this_path = diff['path']
            if path:
                if not this_path.startswith(path):
                    continue  # skip files not on the path
                if not recursive:
                    if '/' in this_path[len(path)+1:]:
                        continue  # skip files is subdirs of specified path
            changes = diff['changes'][0]
            type = changes.get('type', '')
            if 'size' in changes:
                size = Quantity(changes['size'], 'B').render(prec=3)
            else:
                size = ''
            num_spaces = max(19 - len(type) - len(size), 1)
            sep = num_spaces * ' '
            desc = type + sep + size
            print(desc, this_path)

        return 1 if diffs else 0


# DueCommand command {{{1
class DueCommand(Command):
    NAMES = "due".split()
    DESCRIPTION = "days since last backup"
    USAGE = dedent(
        """
        Used with status bar programs, such as i3status, to make user aware that
        backups are due.

        Usage:
            assimilate due [options]

        Options:
            -b, --since-backup <days>   emit message if this many days have passed
                                        since last backup
            -s, --since-squeeze <days>  emit message if this many days have passed
                                        since last prune and compact
            -c, --since-check <days>    emit message if this many days have passed
                                        since last check
            -e, --email <addr>          send email message rather than print message
                                        may be comma separated list of addresses
            -S, --subject <subject>     subject line if sending email
            -m, --message <msg>         the message to emit
            -o, --oldest                with composite configuration, only report
                                        the oldest

        If you specify the days, then the message is only printed if the action
        is overdue.  If not overdue, nothing is printed.  The message is always
        printed if days is not specified.

        If you specify a simple value to -b, -s, or -c it is taken as a time
        interval measured in days.  However, you can also add one of the
        following units to the value: s, m, h, d, w, M, or y to represent
        seconds, minutes, hours, days, weeks, months, and years.  Thus, 1w
        represents one week.

        If you specify the message, the following replacements are available:
            since: the time that has elapsed since the backup, a quantity.
            elapsed: the time that has elapsed since the backup, a string.
            config: the name of the configuration, a string.
            cmd: the command name being reported on (‘create’, ‘prune’, or ‘compact’)
            action: the action being reported on (‘backup’ or ‘squeeze’)
        The message is treated as a Python formatted string and so the various keys
        can include formatting directives.

        Examples:
            > assimilate due
            root backup completed 9 hours ago.
            root squeeze completed 4.6 days ago.
            root check completed 12 days ago.

            > assimilate due -b1 -m "It has been {since:.1pdays} since the last {action}."
            It has been 1.8 days since the last backup.

            > assimilate due -s10 -m "It has been {elapsed} since the last {cmd} of {config}."
            It has been 2 weeks since the last prune of home.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = False
    COMPOSITE_CONFIGS = "all"
    LOG_COMMAND = False
    SHOW_CONFIG_NAME = False
    MESSAGES = {}       # type: dict[str, str]
    OLDEST_DATE = {}    # type: dict[str, str]
    OLDEST_CONFIG = {}  # type: dict[str, str]

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        email = cmdline["--email"]
        config = settings.config_name
        since_backup_thresh = cmdline.get("--since-backup")
        since_squeeze_thresh = cmdline.get("--since-squeeze")
        since_check_thresh = cmdline.get("--since-check")
        exit_status = None

        def gen_message(cmd):
            action = 'squeeze' if cmd in ['prune', 'compact'] else cmd
            date = last_run[cmd]
            if not date or date == arrow.get(0):
                return f"{config} {cmd} never run."
            elapsed = when(date)
            if cmdline["--message"]:
                days = to_days(date)
                replacements = dict(
                    since=days, elapsed=elapsed, config=config,
                    cmd=cmd, action=action
                )
                try:
                    with Quantity.prefs(spacer=" "):
                        return cmdline["--message"].format(**replacements)
                except UnknownConversion as e:
                    raise Error(e, culprit = "--message")
                except KeyError as e:
                    raise Error(
                        f"‘{e!s}’ is an unknown key.",
                        culprit = "--message",
                        codicil = f"Choose from: {conjoin(replacements.keys())}."
                    )
            else:
                return f"{config} {action} completed {elapsed} ago."

        def email_message(cmd):
            if not cmd:
                return
            action = 'squeeze' if cmd in ['prune', 'compact'] else cmd
            msg = gen_message(cmd)

            if config not in cls.MESSAGES:
                cls.MESSAGES[config] = {}
            cls.MESSAGES[config][action] = msg
            cls.MESSAGES['source'] = {}
            cls.MESSAGES['source']['host'] = hostname
            cls.MESSAGES['source']['roots'] = settings.get_roots()

        def save_message(cmd):
            if not cmd:
                return
            action = 'squeeze' if cmd in ['prune', 'compact'] else cmd
            msg = gen_message(cmd)
            if config not in cls.MESSAGES:
                cls.MESSAGES[config] = {}
            cls.MESSAGES[config][action] = msg

        deliver_message = email_message if email else save_message

        # Get date of last backup, and squeeze
        latest = read_latest(settings.date_file)
        last_run = dict(
            backup = latest.get('create last run'),
            prune = latest.get('prune last run'),
            compact = latest.get('compact last run'),
            check = latest.get('check last run'),
        )
        if not last_run['compact'] or not last_run['prune']:
            last_run['squeeze'] = None
            squeeze_cmd = 'compact'
        elif last_run['prune'] < last_run['compact']:
            last_run['squeeze'] = last_run['prune']
            squeeze_cmd = 'prune'
        else:
            last_run['squeeze'] = last_run['compact']
            squeeze_cmd = 'compact'

        # disable squeeze check if there are no prune settings
        prune_settings = [("keep_" + s) for s in prune_intervals]
        if not any(settings.value(s) for s in prune_settings):
            last_run['squeeze'] = None

        # Record the name of the oldest config
        for action in ['backup', 'squeeze', 'check']:
            if not last_run.get(action):
                last_run[action] = arrow.get(0)
            if (
                action not in cls.OLDEST_DATE or
                not cls.OLDEST_DATE[action] or last_run[action] < cls.OLDEST_DATE[action]
            ):
                cls.OLDEST_DATE[action] = last_run['check']
                cls.OLDEST_CONFIG[action] = config

        # Warn user if backup is overdue
        if since_backup_thresh and last_run['backup']:
            seconds = to_seconds(last_run['backup'])
            try:
                if seconds > to_seconds(since_backup_thresh):
                    deliver_message('backup')
                    exit_status = 1
            except ValueError:
                raise Error("expected a number for --backup-days.")
            if not since_squeeze_thresh and not since_check_thresh:
                return exit_status

        # Warn user if prune or compact is overdue
        if since_squeeze_thresh and last_run['squeeze']:
            since_last_squeeze = arrow.now() - last_run['squeeze']
            seconds = since_last_squeeze.total_seconds()
            try:
                if seconds > to_seconds(since_squeeze_thresh):
                    deliver_message(squeeze_cmd)
                    exit_status = 1
            except ValueError:
                raise Error("expected a number for --squeeze-days.")
            if not since_check_thresh:
                return exit_status

        # Warn user if check is overdue
        if since_check_thresh and last_run['check']:
            since_last_check = arrow.now() - last_run['check']
            seconds = since_last_check.total_seconds()
            try:
                if seconds > to_seconds(since_check_thresh):
                    deliver_message('check')
                    exit_status = 1
            except ValueError:
                raise Error("expected a number for --check-days.")
            return exit_status

        # Otherwise, simply report age of backups
        if not since_backup_thresh and not since_squeeze_thresh and not since_check_thresh:
            deliver_message('backup')
            deliver_message(squeeze_cmd)
            deliver_message('check')

    @classmethod
    def run_late(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        email = cmdline["--email"]

        # determine whether to give message for oldest or all configs
        messages = cls.MESSAGES
        if not messages:
            return
        if cmdline["--oldest"]:
            oldest = {}
            for action in ['backup', 'squeeze', 'check']:
                oldest_config = cls.OLDEST_CONFIG[action]
                if action in messages[oldest_config]:
                    if oldest_config not in oldest:
                        oldest[oldest_config] = {}
                    oldest[oldest_config][action] = messages[oldest_config][action]
            messages = oldest

        # convert messages to a indented table
        last_config = None
        lines = []
        for config in messages:
            if config == 'source':
                continue
            if last_config and last_config != config:
                lines.append("")
            last_config = config
            for action in messages[config]:
                message = messages[config][action].replace(r'\n', '\n')
                lines.append(message)

        # add source if given (is only given for email)
        source = messages.get('source')
        if source:
            lines.append('\nsource:')
            messages['source'] = source
            for key, value in source.items():
                if is_collection(value):
                    val = '\n    ' + '\n    '.join(value)
                    lines.append(indent(f"{key}: {val}"))
                else:
                    lines.append(indent(f"{key}: {value}"))

        message = '\n'.join(lines)

        # output the message
        if email:
            subject = cmdline["--subject"]
            if not subject:
                subject = f"{PROGRAM_NAME}: backup is overdue"
            Run(
                ["mail", "-s", subject] + email.split(','),
                stdin = message,
                modes = "soeW",
            )
        else:
            output(message)


# ExtractCommand command {{{1
class ExtractCommand(Command):
    NAMES = "extract".split()
    DESCRIPTION = "recover file or files from archive"
    USAGE = dedent(
        """
        Usage:
            assimilate extract [options] <path>...

        Options:
            -a, --archive <archive>     name of the archive to use
            -A, --after <date_or_age>   use first archive younger than given
            -B, --before <date_or_age>  use first archive older than given
            -f, --force                 extract even if it might overwrite
                                        the original file
            -l, --list                  list the files and directories as
                                        they are processed

        You extract a file or directory using:

            assimilate extract home/ken/src/avendesora/doc/overview.rst

        The path or paths given should match those found in the Borg archive.
        Use list to determine what path you should specify (the paths are
        relative to the working directory, which defaults to / but can be
        overridden in a configuration file).  The paths may point to
        directories, in which case the entire directory is extracted.

        You can specify the archive by name or by date or age or index, with 0
        being the most recent.  If you do not you will use the most recent
        archive.

            $ assimilate compare –-archive continuum-2020-12-04T17:41:28
            $ assimilate compare ––archive 2
            $ assimilate compare ––before 2020-12-04
            $ assimilate compare ––before 1w

        See the help message for list command for more detail on how to select
        an archive.

        The extracted files are placed in the current working directory with
        the original hierarchy.  Thus, the above commands create the file:

            ./home/ken/src/avendesora/doc/overview.rst

        Normally, extract refuses to run if your current directory is the
        working directory used by Assimilate so as to avoid overwriting an
        existing file.  If your intent is to overwrite the existing file, you
        can specify the ––force option.  Or, consider using the restore command;
        it overwrites the existing file regardless of what directory you run
        from.

        This command is very similar to the restore command except that it uses
        paths as they are given in the archive and so need not extract the files
        into their original location.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "first"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        paths = cmdline["<path>"]
        borg_opts = []
        if cmdline["--list"]:
            borg_opts.append("--list")
        if not cmdline["--force"]:
            if cwd().samefile(settings.working_dir):
                raise Error(
                    "Running from the working directory risks",
                    "over writing the existing file or files. ",
                    "Use --force if this is desired.",
                    wrap = True,
                )

        # convert absolute paths to paths relative to the working directory
        paths = [to_path(p) for p in paths]
        try:
            paths = [
                p.relative_to(settings.working_dir) if p.is_absolute() else p
                for p in paths
            ]
        except ValueError as e:
            raise Error(e)

        # get the desired archive
        archive, description = find_archive(settings, cmdline)
        if description:
            display(f'archive: {description}')

        # run borg
        borg = settings.run_borg(
            cmd = "extract",
            borg_opts = borg_opts,
            args = [archive] + paths,
            assimilate_opts = options,
            show_borg_output = bool(borg_opts),
        )
        out = borg.stderr or borg.stdout
        if out:
            output(out.rstrip())

        return borg.status


# HelpCommand {{{1
class HelpCommand(Command):
    NAMES = "help".split()
    DESCRIPTION = "give information about commands or other topics"
    USAGE = dedent(
        """
        Usage:
            assimilate help [<topic>]
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = False
    COMPOSITE_CONFIGS = "none"
    LOG_COMMAND = False

    @classmethod
    def run_early(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)

        from .help import HelpMessage

        cmd_name_map = getattr(cls, 'cmd_name_map', {})
        cmd_alias = getattr(cls, 'cmd_alias', {})

        topic = cmdline["<topic>"]
        cmd = cmd_name_map.get(topic, topic)
        alias = cmd_alias.get(topic, cmd)
        if cmd != topic:
            output(f"‘{topic}’ is an alias of ‘{alias}’.")
            output()
            topic = cmd
        HelpMessage.show(topic)

        return 0


# InfoCommand command {{{1
class InfoCommand(Command):
    NAMES = "info".split()
    DESCRIPTION = "display metadata for a repository or archive"
    USAGE = dedent(
        """
        Usage:
            assimilate info [options]

        Options:
            -a, --archive <archive>  the archive to report on
            -f, --fast               only report local information
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "all"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        fast = cmdline["--fast"]
        if cmdline["--archive"]:
            archive, description = find_archive(settings, cmdline)
            if description:
                display(f'archive: {description}')
        else:
            archive = None

        # report local information
        if archive:
            borg = settings.run_borg(
                cmd = "info",
                args = [archive],
                assimilate_opts = options,
                strip_archive_matcher = True,
            )
        else:
            output(f"              config: {settings.config_name}")
            output(f'               roots: {", ".join(settings.get_roots())}')
            output(f"         destination: {settings.repository}")
            output(f"  settings directory: {settings.config_dir}")
            output(f"             logfile: {settings.logfile}")
            try:
                latest = read_latest(settings.date_file)
                date = latest.get('create last run')
                if date:
                    output(f"     create last run: {date}, {when(date)} ago")
                date = latest.get('prune last run')
                if date:
                    output(f"      prune last run: {date}, {when(date)} ago")
                date = latest.get('compact last run')
                if date:
                    output(f"    compact last run: {date}, {when(date)} ago")
                date = latest.get('check last run')
                if date:
                    output(f"      check last run: {date}, {when(date)} ago")
            except FileNotFoundError as e:
                narrate(os_error(e))
            except arrow.parser.ParserError as e:
                narrate(e, culprit=settings.date_file)
            if fast:
                return

            # now output the information from borg about the repository/archive
            borg = settings.run_borg(
                cmd = "repo-info",
                assimilate_opts = options,
                strip_archive_matcher = True,
            )

        out = borg.stderr or borg.stdout
        if out:
            output()
            output(out.rstrip())

        return borg.status


# ListCommand command {{{1
class ListCommand(Command):
    NAMES = "list".split()
    DESCRIPTION = "list the files contained in an archive"
    USAGE = dedent(
        """
        Usage:
            assimilate list [options] [<path>]

        Options:
            -a, --archive <archive>     name of the archive to use
            -A, --after <date_or_age>   use first archive younger than given
            -B, --before <date_or_age>  use first archive older than given
            -c, --no-color              do not color based on health
            -s, --short                 use short listing format
            -l, --long                  use long listing format
            -n, --name                  use name only listing format
            -f, --format <fmt>          use <fmt> listing format
            -F, --show-formats          show available formats and exit
            -N, --sort-by-name          sort by filename
            -D, --sort-by-date          sort by date
            -S, --sort-by-size          sort by size
            -O, --sort-by-owner         sort by owner
            -G, --sort-by-group         sort by group
            -K, --sort-by-key <name>    sort by key (the Borg field name)
            -r, --reverse-sort          reverse the sort order
            -R, --recursive             show files in sub directories
                                        when path is specified

        Once a backup has been performed, you can list the files and directories
        available in your archive using::

            assimilate list

        This lists the files in the most recent archive.  If you specify the
        path, then the files listed are contained within that path.  For
        example::

            assimilate list .

        This command lists the files in the archive that were originally
        contained in the current working directory.  The path given should be a
        file system path, meaning it is either an absolute path or a relative
        path from the direction from which *Assimilae* is being run.  It is not
        a *Borg* path.

        You can specify a particular archive if you wish:

            assimilate list ––archive=kundert-2018-12-05T12:54:26

        You can specify the archive by its id (found using repo-list):

            assimilate list ––archive={aid}:724e7444

        Or you can specify the archive by index, with 0 being the most recent
        archive, 1 being the next most recent, etc.

            assimilate list ––archive 14

        Negative indices can be used (here you must use the full name of the
        option and the equals sign, i.e.: ––archive=-N):

            assimilate list ––archive=-1

        Or you choose an archive based on a date and time.  Specify ––after to
        select the first archive younger than the given date or time, and ––before
        to use the first that is older.  A variety of date formats are supported.

            assimilate list ––before 2021/04/01
            assimilate list ––before 2021-04-01
            assimilate list ––before 2020-12-05T12:39

        You can also the date in relative terms using s, m, h, d, w, M, y to
        indicate seconds, minutes, hours, days, weeks, months, and years:

            assimilate list ––before 2w

        There are a variety of ways that you use to sort the output.  For
        example, sort by size, use:

            assimilate list -S
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "first"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        path = cmdline["<path>"]
        recursive = cmdline["--recursive"]

        # resolve the path relative to working directory
        if path:
            path = get_archive_path(path, settings)

        # predefined formats
        formats = dict(
            name = "{path}",
            short = "{path}{Type}",
            date = "{mtime} {path}{Type}",
            size = "{size:8} {path}{Type}",
            si = "{Size:7.2b} {path}{Type}",
            owner = "{user:8} {path}{Type}",
            group = "{group:8} {path}{Type}",
            long = '{mode:10} {user:6} {group:6} {size:8} {mtime} {path}{extra}',
        )

        # choose format
        default_format = settings.list_default_format
        if not default_format:
            default_format = 'short'
        user_formats = settings.list_formats
        if user_formats:
            formats.update(user_formats)
        if cmdline["--show-formats"]:
            for k, v in formats.items():
                output(f'{k:>9}: {v}')
            output()
            output(f'default format: {default_format}')
            return

        # get the desired archive
        archive, description = find_archive(settings, cmdline)
        if description:
            display(f'archive: {description}')

        # process sort options
        fmt = default_format
        sort_key = None
        if cmdline["--sort-by-name"]:
            fmt = "short"
            sort_key = 'path'
        elif cmdline["--sort-by-date"]:
            fmt = "date"
            sort_key = 'mtime'
        elif cmdline["--sort-by-size"]:
            fmt = "si"
            sort_key = 'size'
        elif cmdline["--sort-by-owner"]:
            fmt = "owner"
            sort_key = 'user'
        elif cmdline["--sort-by-group"]:
            fmt = "group"
            sort_key = 'group'
        elif cmdline["--sort-by-key"]:
            sort_key = cmdline["--sort-by-key"]

        # process format options
        if cmdline["--name"]:
            fmt = "name"
        elif cmdline["--long"]:
            fmt = "long"
        elif cmdline["--short"]:
            fmt = "short"
        if cmdline['--format']:
            fmt = cmdline['--format']
            if fmt not in formats:
                raise Error(
                    'unknown format.',
                    culprit = fmt,
                    codicil = f"Choose from: {conjoin(formats)}."
                )

        # run borg
        template = formats[fmt]
        keys = template.lower()
            # lower case it so we get size when user requests Size
        if sort_key and '{' + sort_key not in keys:
            keys = keys + '{' + sort_key + '}'
        args = [
            '--json-lines',
            f'--format={keys}',
            archive,
        ]
        if path:
            args.append(str(path))

        borg = settings.run_borg(cmd="list", args=args, assimilate_opts=options)

        # convert from JSON-lines to JSON
        json_data = '[' + ','.join(borg.stdout.splitlines()) + ']'
        lines = json.loads(json_data)

        # sort the output
        if sort_key:
            try:
                lines = sorted(lines, key=lambda x: x[sort_key])
            except KeyError:
                raise Error('unknown key.', culprit=sort_key)
        if cmdline["--reverse-sort"]:
            lines.reverse()

        # generate formatted output
        no_color = lambda x: x
        if cmdline['--no-color']:
            healthy_color = broken_color = no_color
        else:
            healthy_color = Color("green", enable=Color.isTTY())
            broken_color = Color("red", enable=Color.isTTY())
        total_size = 0
        path = str(path or '')
        for values in lines:
            # this loop can be quite slow. the biggest issue is arrow. parsing
            # time is slow. also output() can be slow, so use print() instead.
            if path:
                if not values['path'].startswith(path):
                    continue  # skip files not on the path
                if not recursive:
                    if '/' in values['path'][len(path)+1:]:
                        continue  # skip files is subdirs of specified path
            if 'healthy' in values:
                colorize = healthy_color if values['healthy'] else broken_color
                values['healthy'] = truth(values['healthy'], formatter='healthy/broken')
            else:
                colorize = no_color
            type = values['mode'][0]
            values['Type'] = ''
            values['extra'] = ''
            if type == 'd':
                values['Type'] = '/'  # directory
            elif type == 'l':
                values['Type'] = '@'  # directory
                values['extra'] = ' —> ' + values['target']
            elif type == 'h':
                values['extra'] = ' links to ' + values['target']
            elif type == 'p':
                values['Type'] = '|'
            elif type != '-':
                log('UNKNOWN TYPE:', type, values['path'])
            if 'mtime' in values and 'MTime' in template:
                values['MTime'] = arrow.get(values['mtime'])
            if 'ctime' in values and 'CTime' in template:
                values['CTime'] = arrow.get(values['ctime'])
            if 'atime' in values and 'ATime' in template:
                values['ATime'] = arrow.get(values['atime'])
            if 'size' in values:
                total_size += values['size']
                if 'Size' in template:
                    values['Size'] = Quantity(values['size'], "B")
            if 'csize' in values and '{CSize' in template:
                values['CSize'] = Quantity(values['csize'], "B")
            if 'dsize' in values and '{DSize' in template:
                values['DSize'] = Quantity(values['dsize'], "B")
            if 'dcsize' in values and '{DCSize' in template:
                values['DCSize'] = Quantity(values['dcsize'], "B")
            try:
                # use print rather than output because it is faster
                print(colorize(template.format(**values)))
            except ValueError as e:
                raise Error(
                    full_stop(e),
                    'Likely due to a bad format specification in list_formats:',
                    codicil=template
                )
            except KeyError as e:
                raise Error('Unknown key in:', culprit=e, codicil=template)

        if total_size:
            total_size = Quantity(total_size, 'B')
            print(f"Total size = {total_size:0.2b}")

        return borg.status


# LogCommand command {{{1
class LogCommand(Command):
    NAMES = "log".split()
    DESCRIPTION = "display log for the last assimilate run"
    USAGE = dedent(
        """
        Usage:
            assimilate log
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = False
    COMPOSITE_CONFIGS = "all"
    LOG_COMMAND = False

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        process_cmdline(cls.USAGE, argv=[command] + args)

        try:
            pager(settings.logfile.read_text())
        except FileNotFoundError as e:
            narrate(os_error(e))


# MountCommand command {{{1
class MountCommand(Command):
    NAMES = "mount".split()
    DESCRIPTION = "mount a repository or archive"
    USAGE = dedent(
        """
        Usage:
            assimilate mount [options] [<mount_point>]

        Options:
            -a, --archive <archive>     name of the archive to use
            -A, --after <date_or_age>   use first archive younger than given
            -B, --before <date_or_age>  use first archive older than given
            -f, --first <N>             consider first N archives that remain
            -l, --last <N>              consider last N archives that remain
            -n, --newer <age>           only consider archives newer than age
            -o, --older <age>           only consider archives older than age
            -N, --newest <range>        only consider archives between newest and
                                        newest-range
            -O, --oldest <range>        only consider archives between oldest and
                                        oldest+range
            -e, --include-external      when mounting all archives, do
                                        not limit archives to only those
                                        associated with chosen configuration

        You can mount a repository or archive using:

            assimilate mount backups

        If the specified mount point (backups in this example) exists in the
        current directory, it must be a directory.  If it does not exist, it is
        created.  If you do not specify a mount point, the value of the
        default_mount_point setting is used if provided.  If you do not specify
        a mount point, the directory specified in the default_mount_point
        setting is used.

        If you do not specify an archive or date, the most recently created
        archive is mounted.

        You can select individual archives to mount using the ––archive,
        ––before, and ––after command line options.  See the help message for
        list command for details on how to select individual archives.

        You can select groups archives to mount using the ––first, ––last,
        ––newer, ––older, ––newest, and ––oldest options.  See the help message
        for repo-list command for details on how to select multiple archives.

        You should use `assimilate umount` when you are done.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "first"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        mount_point = cmdline["<mount_point>"]
        if mount_point:
            mount_point = settings.to_path(mount_point, resolve=False)
        else:
            mount_point = settings.as_path("default_mount_point")
        if not mount_point:
            raise Error("must specify directory to use as mount point.")
        display("mount point is:", mount_point)
        borg_opts = archive_filter_options(settings, cmdline, default='all')
        include_external_archives = cmdline["--include-external"]

        # create mount point if it does not exist
        if mount_point.exists():
            raise Error(
                "attempting to mount onto existing file or directory",
                culprit = mount_point
            )
        try:
            mkdir(mount_point)
        except OSError as e:
            raise Error(os_error(e))

        # run borg
        borg = settings.run_borg(
            cmd = "mount",
            args = [mount_point],
            assimilate_opts = options,
            borg_opts = borg_opts,
            strip_archive_matcher = include_external_archives,
        )
        out = borg.stderr or borg.stdout
        if out:
            output(out.rstrip())

        return borg.status


# OverdueCommand command {{{1
class OverdueCommand(Command):
    NAMES = "overdue".split()
    DESCRIPTION = "show status of known repositories"
    USAGE = OVERDUE_USAGE.strip()
    REQUIRES_EXCLUSIVITY = False
    COMPOSITE_CONFIGS = "first"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        informer = get_informer()
        prev_stream_policy = informer.stream_policy
        if cmdline['--nt']:
            informer.set_stream_policy('header')
        exit_status = overdue(cmdline, args, settings, options)
        informer.set_stream_policy(prev_stream_policy)
        return exit_status


# PruneCommand command {{{1
class PruneCommand(Command):
    NAMES = "prune".split()
    DESCRIPTION = "prune the repository of excess archives"
    USAGE = dedent(
        """
        Usage:
            assimilate prune [options]

        Options:
            -e, --include-external   prune all archives in repository, not just
                                     those associated with chosen configuration
            -f, --fast               skip compacting
            -l, --list               show fate of each archive

        The prune command deletes archives that are no longer needed as
        determined by the prune rules.  However, the disk space is not reclaimed
        until the compact command is run.  You can specify that a compaction is
        performed as part of the prune by setting compact_after_delete.  If set,
        the fast flag causes the compaction to be skipped.  If not set, the
        fast flag has no effect.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "all"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        include_external_archives = cmdline["--include-external"]
        borg_opts = []
        if cmdline["--list"]:
            borg_opts.append("--list")
        fast = cmdline["--fast"]

        # checking the settings
        prune_settings = [("keep_" + s) for s in prune_intervals]
        if not any(settings.value(s) for s in prune_settings):
            prune_settings = conjoin(prune_settings, ", or ")
            raise Error(
                "no prune settings available.",
                codicil = f"At least one of {prune_settings} must be specified.",
                wrap = True,
            )

        # run borg
        borg = settings.run_borg(
            cmd = "prune",
            borg_opts = borg_opts,
            assimilate_opts = options,
            strip_archive_matcher = include_external_archives,
        )
        out = borg.stderr or borg.stdout
        if out:
            output(out.rstrip())
        prune_status = borg.status

        # update the date file
        update_latest('prune', settings.date_file, options)

        if fast:
            return prune_status

        try:
            # compact the repository if requested
            if settings.compact_after_delete:
                narrate("Compacting repository ...")
                compact = CompactCommand()
                compact_status = compact.run("compact", [], settings, options)
            else:
                compact_status = 0

        except Error as e:
            e.reraise(
                codicil = (
                    "This error occurred while compacting the repository.",
                    "No error was reported while pruning the repository.",
                )
            )

        return max([prune_status, compact_status])


# RecreateCommand command {{{1
class RecreateCommand(Command):
    NAMES = "recreate".split()
    DESCRIPTION = "recreate archives"
    USAGE = dedent(
        """

        Usage:
            assimilate recreate [options] [<path> ...]

        Options:
            -f, --first <N>         consider first N archives that remain
            -l, --last <N>          consider last N archives that remain
            -n, --newer <age>       only consider archives newer than age
            -o, --older <age>       only consider archives older than age
            -N, --newest <range>    only consider archives between newest and
                                    newest-range
            -O, --oldest <range>    only consider archives between oldest and
                                    oldest+range
            -e, --include-external  list all archives in repository, not just
                                    those associated with chosen configuration

        The recreate command applies the current exclude rules to existing
        archives, which can reduce their size if the rules have changed since
        the archives were created.  The disk space is not reclaimed until a
        compact command is run.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "all"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):

        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        borg_opts = archive_filter_options(settings, cmdline, default='all')
        paths = get_archive_paths(cmdline['<path>'], settings)

        # args = [settings.value('archive')] + paths,
        # run borg
        borg = settings.run_borg(
            cmd = "recreate",
            borg_opts = borg_opts,
            args = paths,
            assimilate_opts = options,
            strip_archive_matcher = cmdline["--include-external"]
        )
        out = (borg.stderr or borg.stdout).rstrip()
        if out:
            output(out)
        return borg.status

# RepoCreateCommand command {{{1
class RepoCreateCommand(Command):
    NAMES = "repo-create".split()
    DESCRIPTION = "initialize the repository"
    USAGE = dedent(
        """
        Usage:
            assimilate [options] repo-create

        Options:
            -r, --reserve <B>         amount of space to keep in reserve [B]

        This must be done before you create your first archive.

        The number of bytes specified to ––reserve may employ SI or binary scale
        factors and may include the units (ex. 1GB, 1MiB).  Reserved space is
        always rounded up to use full reservation blocks of 64 MiB.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "all"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)

        # run borg repo-create
        borg = settings.run_borg(
            cmd="repo-create",
            assimilate_opts = cmdline
        )
        out = (borg.stderr or borg.stdout).rstrip()
        if out:
            out = out.replace('borg repo-space', 'assimilate repo-space')
            out = out.replace('borg key export -r REPOSITORY', 'assimilate borg key export -r @repo')
            output(out)
        if borg.status:
            return borg.status

        # run borg repo-space
        if cmdline["--reserve"]:
            try:
                space = Quantity(cmdline["--reserve"], binary=True, ignore_sf=False)
                if space.units and space.units not in ["B", "bytes", "byte"]:
                    raise Error('expected bytes.', culprit="--reserve")
                space = space.render(prec="full", show_units=False)
            except QuantiPhyError as e:
                raise Error(e, culprit=cmdline["--reserve"])

            borg = settings.run_borg(
                cmd="repo-space",
                borg_opts = [f"--reserve={space}"],
                assimilate_opts = cmdline
            )

            out = borg.stderr or borg.stdout
            if out:
                output(out.rstrip())

        settings.date_file.touch()
        return borg.status


# RepoListCommand command {{{1
class RepoListCommand(Command):
    NAMES = "repo-list".split()
    DESCRIPTION = "display available archives"
    USAGE = dedent(
        """
        Usage:
            assimilate repo-list [options]

        Options:
            -f, --first <N>         consider first N archives that remain
            -l, --last <N>          consider last N archives that remain
            -n, --newer <age>       only consider archives newer than age
            -o, --older <age>       only consider archives older than age
            -N, --newest <range>    only consider archives between newest and
                                    newest-range
            -O, --oldest <range>    only consider archives between oldest and
                                    oldest+range
            -e, --include-external  list all archives in repository, not just
                                    those associated with chosen configuration
            -d, --deleted           only consider archives marked for deletion

        By default all archives will listed, however you can limit the
        number shown using various command line options.

        Select the oldest N archives using ––first=N.
        Select the youngest N archives using ––last=N.

        Select the archives older than a given date or time using ––older.
        Select the archives younger than a given date or time using ––newer.
        The date may be given using a variety of formats:

            $ assimilate repo-list ––before 2021-04-01

        or given as a relative time:

            $ assimilate repo-list ––before 1w

        Finally you can select archives that were created within a specified
        time of the first (––newest) or last (––oldest) archive created:

            $ assimilate repo-list ––oldest 1y
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "first"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        include_external_archives = cmdline["--include-external"]

        # run borg
        borg_opts = archive_filter_options(settings, cmdline, default='all')
        borg = settings.run_borg(
            cmd = "repo-list",
            assimilate_opts = options,
            borg_opts = borg_opts + ['--json'],
            strip_archive_matcher = include_external_archives,
        )
        if not borg.status:
            archives = list_archives(json.loads(borg.stdout), cmdline)
            if archives:
                output(archives)
        return borg.status


# RepoSpaceCommand command {{{1
class RepoSpaceCommand(Command):
    NAMES = "repo-space".split()
    DESCRIPTION = "manage the amount of space kept in reserve"
    USAGE = dedent(
        """
        Usage:
            assimilate [options] repo-space

        Options:
            -r, --reserve <B>         amount of space to keep in reserve [B]
            -f, --free                free all reserved space

        Borg can not work in disk-full conditions.  Specifically it cannot lock
        the repository and so cannot run prune/delete or compact operations
        to free space).

        To protect against dead-end situations like that, you can put some
        objects into a repository that take up some disk space. If you then ever
        run into a disk-full situation, you can free that space, allowing Borg
        to operate normally, which allows to free more disk space by using the
        prune, delete, and compact commands.

        After recovering sufficient space to operate normally again, don’t
        forget to reserve space again, in case you run into that situation again
        at a later time.

        The number of bytes specified to ––reserve may employ Si or binary scale
        factors and may include the units (ex. 1GB, 1MiB).  Reserved space is
        always rounded up to use full reservation blocks of 64 MiB.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "all"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        borg_opts = []
        if cmdline["--reserve"]:
            try:
                space = Quantity(cmdline["--reserve"], binary=True, ignore_sf=False)
                if space.units and space.units not in ["B", "bytes", "byte"]:
                    raise Error('expected bytes.', culprit="--reserve")
                space = space.render(prec="full", show_units=False)
                borg_opts.append(f"--reserve={space}")
            except QuantiPhyError as e:
                raise Error(e, culprit=cmdline["--reserve"])
        if cmdline["--free"]:
            borg_opts.append("--free")

        # run borg
        borg = settings.run_borg(
            cmd="repo-space",
            borg_opts = borg_opts,
            assimilate_opts = options
        )
        out = borg.stderr or borg.stdout
        if out:
            output(out.rstrip())

        settings.date_file.touch()
        return borg.status


# RestoreCommand command {{{1
class RestoreCommand(Command):
    NAMES = "restore".split()
    DESCRIPTION = "restore requested files or directories in place"
    USAGE = dedent(
        """
        Usage:
            assimilate restore [options] <path>...

        Options:
            -a, --archive <archive>           name of the archive to use
            -A, --after <date_or_age>         use first archive younger than given
            -B, --before <date_or_age>        use first archive older than given
            -l, --list                        list the files and directories
                                              as they are processed

        The path or paths given are the paths on the local filesystem.  The
        corresponding paths in the archive are computed by assuming that the
        location of the files has not changed since the archive was created.
        The intent is to replace the files in place.

        You can specify the archive by name or by date or age or index, with 0
        being the most recent.  If you do not you will use the most recent
        archive.

            $ assimilate compare ––archive continuum-2020-12-04T17:41:28
            $ assimilate compare ––archive 2
            $ assimilate compare ––before 2020-12-04
            $ assimilate compare ––before 1w

        See the help message for list command for more detail on how to select
        an archive.

        This command is very similar to the extract command except that it is
        meant to be replace files while in place.  The extract command is
        preferred if you would like to extract the files to a new location.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "first"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        paths = cmdline["<path>"]
        borg_opts = []
        if cmdline["--list"]:
            borg_opts.append("--list")

        # convert given paths into the equivalent paths found in the archive
        paths = get_archive_paths(paths, settings)

        # get the desired archive
        archive, description = find_archive(settings, cmdline)
        if description:
            display(f'archive: {description}')

        # run borg
        borg = settings.run_borg(
            cmd = "extract",
            borg_opts = borg_opts,
            args = [archive] + paths,
            assimilate_opts = options,
            show_borg_output = bool(borg_opts),
            use_working_dir = True,
        )
        out = borg.stderr or borg.stdout
        if out:
            output(out.rstrip())

        return borg.status


# SettingsCommand command {{{1
class SettingsCommand(Command):
    NAMES = "settings setting".split()
    DESCRIPTION = "display settings of chosen configuration"
    USAGE = dedent(
        """
        Usage:
            assimilate settings [options] [<name>]
            assimilate setting [options] [<name>]

        Options:
            -a, --available   list available settings and give their
                              descriptions rather than their values

        If given without an argument all specified settings of a config are
        listed and their values displayed.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = False
    COMPOSITE_CONFIGS = "first"
    LOG_COMMAND = False

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        show_available = cmdline["--available"]
        width = 26
        leader = (width+2)*' '
        unknown = Color("yellow", enable=Color.isTTY())
        known = Color("cyan", enable=Color.isTTY())
        resolved = Color("magenta", enable=Color.isTTY())
        read_only = Color("blue", enable=Color.isTTY())
        len_color_codes = len(known('x')) - 1

        def render(value):
            val = nt.dumps(value, default=str)
            if val.startswith('> ') and not str(v).startswith('> '):
                return val[2:]
            return indent(val, stops=7, first=-7)

        if show_available:
            def show_setting(name, desc):
                desc = fill(desc, 74-width-2)
                text = indent(
                    f"{known(name):>{width + len_color_codes}}: {desc}",
                    leader = leader,
                    first = -1
                )
                output(text)

            output("Assimilate settings:")
            for name in sorted(ASSIMILATE_SETTINGS):
                if name not in READ_ONLY_SETTINGS:
                    show_setting(name, ASSIMILATE_SETTINGS[name]['desc'])

            output()
            output("Borg settings:")
            for name in sorted(BORG_SETTINGS):
                attrs = BORG_SETTINGS[name]
                show_setting(name, attrs['desc'])

            output()
            output("Read-only:")
            for name in sorted(ASSIMILATE_SETTINGS):
                if name in READ_ONLY_SETTINGS:
                    show_setting(name, ASSIMILATE_SETTINGS[name]['desc'])

            return 0

        if settings:
            requested = cmdline['<name>']
            for k, v in sorted(settings):
                is_known = k in ASSIMILATE_SETTINGS or k in BORG_SETTINGS
                if is_known:
                    key = read_only(k) if k in READ_ONLY_SETTINGS else known(k)
                else:
                    key = unknown(k)
                if requested and requested != k:
                    continue
                if k == "passphrase":
                    v = "❬set❭"
                if not is_str(v) or '\n' in v:
                    v = render(v)
                output(f"{key:>{width + len_color_codes}}: {v}")
                try:
                    if "{" in v and k not in settings.do_not_expand:
                        rv = settings.resolve_any(k)
                        if rv != v:
                            # settings.value() does not resolve collections
                            rv = render(rv)
                            key = "❬when resolved❭"
                            output(resolved(
                                f"{key:>{width}}: {rv}"
                            ))
                except Error:
                    pass

    run_early = run
        # --available is handled in run_early


# UmountCommand command {{{1
class UmountCommand(Command):
    NAMES = "umount".split()
    DESCRIPTION = "un-mount a previously mounted repository or archive"
    USAGE = dedent(
        """
        Usage:
            assimilate umount [<mount_point>]
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "first"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        mount_point = cmdline["<mount_point>"]
        if mount_point:
            mount_point = settings.to_path(mount_point, resolve=False)
        else:
            mount_point = settings.as_path("default_mount_point")
        if not mount_point:
            raise Error("must specify directory to use as mount point.")
        if not mount_point.exists():
            display("no such file or directory.", culprit=mount_point)
            return 0

        # run borg
        try:
            borg = settings.run_borg(
                cmd="umount", args=[mount_point], assimilate_opts=options,
            )
            try:
                mount_point.rmdir()
            except OSError as e:
                warn(os_error(e))
        except Error as e:
            if "busy" in str(e):
                e.reraise(
                    codicil = f"Try running 'lsof +D {mount_point!s}' to find culprit."
                )
        return borg.status


# UndeleteCommand command {{{1
class UndeleteCommand(Command):
    NAMES = "undelete".split()
    DESCRIPTION = "remove deletion marker from selected archives"
    USAGE = dedent(
        """
        Usage:
            assimilate undelete [options]

        Options:
            -a, --archive <archive>     name of the archive to mount
            -A, --after <date_or_age>   use first archive younger than given
            -B, --before <date_or_age>  use first archive older than given
            -f, --first <N>             consider first N archives that remain
            -l, --last <N>              consider last N archives that remain
            -n, --newer <age>           only consider archives newer than age
            -o, --older <age>           only consider archives older than age
            -N, --newest <range>        only consider archives between newest and
                                        newest-range
            -O, --oldest <range>        only consider archives between oldest and
                                        oldest+range
            -e, --include-external      include all archives in repository, not just
                                        those associated with chosen configuration
            --list                      list undeleted archives

        You can apply the undelete command to any archives deleted with the
        delete or prune commands.  However, undeleting archives is only possible
        before compacting.

        You can select individual archives to undelete using the ––archive,
        ––before, and ––after command line options.  See the help message for
        list command for details on how to select individual archives.

        You can select groups archives to undelete using the ––first, ––last,
        ––newer, ––older, ––newest, and ––oldest options.  See the help message
        for repo-list command for details on how to select multiple archives.

        All archives that were selected and are marked for deletion will be
        undeleted (they will no longer be marked for deletion).  If no archives
        are selected, all archives marked for deletion will be undeleted.
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = True
    COMPOSITE_CONFIGS = "error"
    LOG_COMMAND = True

    @classmethod
    def run(cls, command, args, settings, options):
        # read command line
        cmdline = process_cmdline(cls.USAGE, argv=[command] + args)
        list_opt = ['--list'] if cmdline['--list'] or 'dry-run' in options else []
        include_external_archives = cmdline["--include-external"]
        borg_opts = archive_filter_options(settings, cmdline, default='all')
        borg_opts.append("--match-archives=sh:*")
            # adding this to end makes the default to undelete all

        # run borg
        borg = settings.run_borg(
            cmd = "undelete",
            assimilate_opts = options,
            borg_opts = borg_opts + list_opt,
            strip_archive_matcher = include_external_archives,
        )
        out = borg.stderr or borg.stdout
        if out:
            output(out.rstrip())
        return borg.status


# VersionCommand {{{1
class VersionCommand(Command):
    NAMES = ("version",)
    DESCRIPTION = "display assimilate version"
    USAGE = dedent(
        """
        Usage:
            assimilate version
        """
    ).strip()
    REQUIRES_EXCLUSIVITY = False
    COMPOSITE_CONFIGS = "none"
    LOG_COMMAND = False

    @classmethod
    def run_early(cls, command, args, settings, options):

        # get the Python version
        python = "Python {}.{}.{}".format(
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro,
        )

        # output the Assimilate version along with the Python version
        from . import __version__, __released__

        output(f"assimilate version: {__version__}  ({__released__}) [{python}].")
