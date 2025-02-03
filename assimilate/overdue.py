# USAGE {{{1
"""
This command show you when all of your configurations were last backed up and
can notify you if backups have not been run recently.  It can be run either from
the server (the destination) or from the client (the source). It
simply lists those archives marking those are out-of-date.  If you specify
mail, email is sent that describes the situation if a backup is overdue.

Usage:
    assimilate overdue [options]

Options:
    -l, --local          Only report on local repositories
    -m, --mail           Send mail message if backup is overdue
    -n, --notify         Send notification if backup is overdue
    -N, --nt             Output summary in NestedText format
    -p, --no-passes      Do not show hosts that are not overdue
    -M, --message <msg>  Status message template for each repository

The program requires a special configuration file, which defaults to
overdue.conf.nt.  It should be placed in the configuration directory, typically
~/.config/assimilate.  The contents are described here:

    https://assimilate.readthedocs.io/en/stable/monitoring.html#overdue

The message given by ––message may contain the following keys in braces:
    description: replaced by the description field from the config file, a string.
    max_age: replaced by the max_age field from the config file, a quantity.
    mtime: replaced by modification time, a datetime object.
    age: replaced by the number of hours since last update, a quantity.
    updated: replaced by time since last update, a string.
    overdue: is the back-up overdue, a boolean.
    locked: is the back-up currently active, a boolean.

The status message is a Python formatted string, and so the various fields can
include formatting directives.  For example:
- strings than include field width and justification, ex. {description:>20}
- quantities can include width, precision, form and units, ex. {age:0.1phours}
- datetimes can include Arrow formats, ex: {mtime:DD MMM YY @ H:mm A}
- booleans can include true/false strings: ex. {overdue:PAST DUE!/current}
"""

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
import os
import pwd
import socket
import arrow
from collections import defaultdict
from inform import (
    Color,
    Error,
    InformantFactory,
    conjoin,
    cull,
    dedent,
    display,
    error,
    get_prog_name,
    os_error,
    plural,
    truth,
    warn,
)
import nestedtext as nt
from voluptuous import Schema
from .configs import (
    add_setting, add_parents_of_non_identifier_keys,
    as_color, as_emails, as_path, as_abs_path, as_string, as_name
)
from .preferences import DATA_DIR
from .utilities import output, read_latest, when, Quantity, InvalidNumber, Run, to_path

# GLOBALS {{{1
username = pwd.getpwuid(os.getuid()).pw_name
hostname = socket.gethostname()
now = arrow.now()
OVERDUE_USAGE = __doc__

# colors {{{2
current_color = "green"
overdue_color = "red"
locked_color = "magenta"

# message templates {{{2
verbose_status_message = dedent("""\
    HOST: {description}
        sentinel file: {path!s}
        last modified: {mtime}
        since last change: {age:0.1phours}
        maximum age: {max_age:0.1phours}
        overdue: {overdue}
        locked: {locked}
""", strip_nl='l')

terse_status_message = "{description}: {updated}{locked: (currently active)}{overdue: — PAST DUE}"

mail_status_message = dedent("""
    Backup of {description} is overdue:
       The sentinel file has not changed in {age:0.1phours}.
""", strip_nl='b')

error_message = dedent(f"""
    {get_prog_name()} generated the following error:
        from: {username}@{hostname} at {now}
        message: {{}}
""", strip_nl='b')

# VALIDATORS {{{1
# as_seconds {{{2
def as_seconds(arg, units=None):
    arg = as_string(arg)
    return Quantity(arg, units or 'h').scale('seconds')

# SCHEMA {{{1
validate_settings = Schema(
    dict(
        max_age = as_seconds,
        sentinel_root = as_abs_path,
        message = as_string,
        current_color = as_color,
        overdue_color = as_color,
        locked_color = as_color,
        repositories = {
            str: dict(
                config = as_name,
                sentinel_dir = as_path,
                host = as_string,
                max_age = as_seconds,
                notify = as_emails,
                command = as_string,
            )
        }
    )
)
add_setting("overdue", "settings for the overdue command", validate_settings)
add_parents_of_non_identifier_keys("overdue", "repositories")

# UTILITIES {{{1
# get_local_data {{{2
def get_local_data(description, config, path, max_age):
    if path:
        path = to_path(*path)
    if config:
        if not path:
            path = to_path(DATA_DIR)
        locked = (path /  f"{config}.lock").exists()
        path = path / f"{config}.latest.nt"
        latest = read_latest(path)
        mtime = latest.get('create last run')
        if not mtime:
            raise Error('create time is not available.', culprit=path)
    else:
        if not path:
           raise Error("‘sentinel_dir’ setting is required.", culprit=description)
        paths = list(path.glob("index.*"))
        if not paths:
            raise Error("no sentinel file found.", culprit=path)
        if len(paths) > 1:
            raise Error("too many sentinel files.", *paths, sep="\n    ")
        path = paths[0]
        mtime = arrow.get(path.stat().st_mtime)
        locked = path.parent.glob('lock.*')

    delta = now - mtime
    age = Quantity(24 * 60 * 60 * delta.days + delta.seconds, 'seconds')
    overdue = truth(age > max_age)
    locked = truth(locked)
    yield dict(
        description=description, path=path, mtime=mtime,
        age=age, max_age=max_age, overdue=overdue, locked=locked
    )

# get_remote_data {{{2
def get_remote_data(name, host, config, cmd):
    cmd = cmd or "assimilate overdue"
    display(f"\n{name}:")
    config = ['--config', config] if config else []
    try:
        ssh = Run(['ssh', host] + config + cmd.split() + ['--nt', '--local'], 'sOEW1')
        for repo_data in nt.loads(ssh.stdout, top=list):
            if 'description' not in repo_data:
                repo_data['description'] = repo_data.get('host', '')
            if 'mtime' in repo_data:
                repo_data['mtime'] = arrow.get(repo_data['mtime'])
            if 'overdue' in repo_data:
                repo_data['overdue'] = truth(repo_data['overdue'] == 'yes')
            if repo_data.get('hours'):
                repo_data['age'] = as_seconds(repo_data['hours'])
                del repo_data['hours']
            elif repo_data.get('age'):
                try:
                    repo_data['age'] = as_seconds(repo_data['age'])
                except InvalidNumber:
                    repo_data['age'] = as_seconds(0)
            if repo_data.get('max_age'):
                repo_data['max_age'] = as_seconds(repo_data['max_age'])
            repo_data['locked'] = truth(repo_data.get('locked') == 'yes')
            yield repo_data
    except Error as e:
        e.report(culprit=host)

# MAIN {{{1
def overdue(cmdline, args, settings, options):
    # gather needed settings
    default_notify = settings.notify
    od_settings = settings.overdue
    if not od_settings:
        raise Error("no ‘overdue’ settings found.", culprit=settings.config_name)
    default_max_age = od_settings.get("max_age", as_seconds('28h'))
    repositories = od_settings.get("repositories")
    root = od_settings.get("sentinel_root")
    message = od_settings.get("message", terse_status_message)

    if cmdline["--message"]:
        message = cmdline["--message"].replace(r'\n', '\n')
    if "verbose" in options:
        message = verbose_status_message

    report_as_current = InformantFactory(
        clone=display, message_color=od_settings.get("current_color", current_color),
    )
    report_as_overdue = InformantFactory(
        clone=display, message_color=od_settings.get("overdue_color", overdue_color),
        notify=cmdline['--notify'] and not Color.isTTY()
    )
    report_as_active = InformantFactory(
        clone=display, message_color=od_settings.get("locked_color", locked_color),
        notify=cmdline['--notify'] and not Color.isTTY()
    )

    overdue_by_recipient = defaultdict(list)
    exit_status = 0

    def send_mail(recipients, subject, body):
        if recipients:
            if 'verbose' in options:
                display(f"Reporting to {recipient}.\n")
            mail_cmd = ["mail", "-s", subject] + recipients
            if settings.notify_from:
                mail_cmd += ["-r", settings.notify_from]
            Run(mail_cmd, stdin=body, modes="soeW0")
        else:
            raise Error('must specify notify setting to send mail.')

    # check age of repositories
    for description, params in repositories.items():
        config = params.get('config')
        sentinel_dir = params.get('sentinel_dir')
        max_age = params.get('max_age') or default_max_age
        notify = params.get('notify') or default_notify or []
        host = params.get('host')
        command = params.get('command')

        failed = False
        try:
            if host:
                ignoring = ("max_age", "sentinel_dir")
                if not cmdline["--local"]:
                    repos_data = get_remote_data(description, host, config, command)
            else:
                ignoring = ("command",)
                repos_data = get_local_data(
                    description, config, cull([root, sentinel_dir]), max_age
                )
            ignored = set(ignoring) & params.keys()
            if ignored:
                culprit = (
                    "overdue", "repositories", description,
                )
                warn(f"ignoring {conjoin(sorted(ignored))}.", culprit=culprit)


            for repo_data in repos_data:
                repo_data['updated'] = when(repo_data['mtime'])
                overdue = repo_data['overdue']
                locked = repo_data['locked']
                description = repo_data['description']
                if locked:
                    report = report_as_active
                elif overdue:
                    report = report_as_overdue
                else:
                    report = report_as_current

                with Quantity.prefs(spacer=' '):
                    if overdue or locked or not cmdline["--no-passes"]:
                        if cmdline["--nt"]:
                            output(nt.dumps([repo_data], default=str))
                        else:
                            try:
                                report(message.format(**repo_data))
                            except ValueError as e:
                                raise Error(e, culprit=(description, 'message'))
                            except KeyError as e:
                                raise Error(
                                    f"‘{e.args[0]}’ is an unknown key.",
                                    culprit=(description, 'message'),
                                    codicil=f"Choose from: {conjoin(repo_data.keys())}."
                                )

                    if overdue:
                        exit_status = max(exit_status, 1)
                        msg = mail_status_message.format(**repo_data)
                        for email in notify:
                            overdue_by_recipient[email].append(msg)
        except OSError as e:
            failed = os_error(e)
            error(failed)
        except Error as e:
            failed = str(e)
            e.report()
        if failed:
            exit_status = max(exit_status, 2)
            if cmdline["--mail"]:
                send_mail(
                    notify,
                    f"{get_prog_name()} error",
                    error_message.format(msg),
                )

    if cmdline["--mail"]:
        for recipient, msgs in overdue_by_recipient.items():
            subject = f"{plural(msgs):backup/ is/s are} overdue"
            body = '\n'.join(msgs)
            send_mail([recipient], subject, body)

    return exit_status
