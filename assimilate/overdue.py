# USAGE {{{1
"""
This command show you when all of your configurations were last backed up and
can notify you if backups have not been run recently.  It can be run either from
the server (the destination) or from the client (the source). It
simply lists those archives marking those are out-of-date.  If you specify
--mail, email is sent that describes the situation if a backup is overdue.

Usage:
    assimilate overdue [options]

Options:
    -c, --no-color       Do not color the output
    -h, --help           Output basic usage information
    -m, --mail           Send mail message if backup is overdue
    -n, --notify         Send notification if backup is overdue
    -N, --nt             Output summary in NestedText format
    -p, --no-passes      Do not show hosts that are not overdue
    -q, --quiet          Suppress output to stdout
    -v, --verbose        Give more information about each repository
    -M, --message <msg>  Status message template for each repository
    --version            Show software version

The program requires a special configuration file, which defaults to
overdue.conf.nt.  It should be placed in the configuration directory, typically
~/.config/assimilate.  The contents are described here:

    https://assimilate.readthedocs.io/en/stable/monitoring.html#overdue

The message given by --message may contain the following keys in braces:
    description: replaced by the description field from the config file, a string.
    max_age: replaced by the max_age field from the config file, a quantity.
    mtime: replaced by modification time, a datetime object.
    age: replaced by the number of hours since last update, a quantity.
    updated: replaced by time since last update, a string.
    overdue: is the back-up overdue, a boolean.
    locked: is the back-up currently active, a boolean.

The status message is a Python formatted string, and so the various fields can include
formatting directives.  For example:
- strings than include field width and justification, ex. {description:>20}
- quantities can include width, precision, form and units, ex. {age:0.1phours}
- datetimes can include Arrow formats, ex: {mtime:DD MMM YY @ H:mm A}
- booleans can include true/false strings: ex. {overdue:PAST DUE!/current}
"""

# LICENSE {{{1
# Copyright (C) 2018-2024 Kenneth S. Kundert
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
import functools
from inform import (
    Color,
    Error,
    InformantFactory,
    conjoin,
    cull,
    dedent,
    display,
    error,
    fatal,
    get_informer,
    get_prog_name,
    output,
    os_error,
    terminate,
    truth,
    warn,
)
import nestedtext as nt
from quantiphy import Quantity, UnitConversion
from voluptuous import Schema, Invalid, MultipleInvalid
from .preferences import CONFIG_DIR, DATA_DIR, OVERDUE_FILE
from .shlib import Run, to_path, set_prefs as set_shlib_prefs
from .utilities import read_latest, report_voluptuous_errors

# GLOBALS {{{1
set_shlib_prefs(use_inform=True, log_cmd=True)
Quantity.set_prefs(form='fixed', prec=1, ignore_sf=True)
username = pwd.getpwuid(os.getuid()).pw_name
hostname = socket.gethostname()
now = arrow.now()
OVERDUE_USAGE = __doc__

# colors {{{2
default_colorscheme = "dark"
current_color = "green"
overdue_color = "red"

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
       the backup sentinel file has not changed in {age:0.1phours}.
""", strip_nl='b')

error_message = dedent(f"""
    {get_prog_name()} generated the following error:
        from: {username}@{hostname} at {now}
        message: {{}}
""", strip_nl='b')

# VALIDATORS {{{1
# as_string {{{2
# raise error if value is not simple text
def as_string(arg):
    if isinstance(arg, dict):
        raise Invalid('expected text, found key-value pair')
    if isinstance(arg, list):
        raise Invalid('expected text, found list item')
    return arg

# as_identifier {{{2
# raise error if value is not an identifier
def as_identifier(arg):
    arg = as_string(arg).strip()
    if not arg.isidentifier():
        raise Invalid(f"expected an identifier, found {arg}")
    return arg

# as_command {{{2
# a command is an identifier than may contain dashes
def as_command(arg):
    arg = as_string(arg).strip()
    if arg.replace('-', '_').isidentifier and arg[0] != '-':
        return arg
    raise Invalid(f"expected a command, found {arg}")

# as_email {{{2
# raise error if value is not an email address
# only performs simple-minded tests
def as_email(arg):
    email = as_string(arg).strip()
    user, _, host = email.partition('@')
    if '.' in host and '@' not in host:
        return arg
    raise Invalid(f"expected email address, found {arg}")

# as_path {{{2
# raise error if value is not text
# coverts it to a path while expanding ~, env vars
def as_path(arg):
    arg = as_string(arg)
    return to_path(arg)

# as_abs_path {{{2
# raise error if value is not text
# coverts it to a path while expanding ~, env vars
def as_abs_path(arg):
    arg = as_string(arg)
    path = to_path(arg)
    if not path.is_absolute():
        raise Invalid("expected absolute path.")
    return path

# as_enum {{{2
# decorator used to specify the choices that are valid for an enum
def as_enum(*choices):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(arg):
            arg = as_string(arg).lower()
            if arg not in choices:
                raise Invalid(f"expected {conjoin(choices, conj=' or ')}.")
            return func(arg)
        return wrapper
    return decorator

# as_colorscheme {{{2
@as_enum("'light", "'dark", "'none")
def as_colorscheme(arg):
    return None if  arg == "none" else arg

# time conversions {{{2
UnitConversion('s', 'sec second seconds')
UnitConversion('s', 'm min minute minutes', 60)
UnitConversion('s', 'h hr hour hours', 60*60)
UnitConversion('s', 'd day days', 24*60*60)
UnitConversion('s', 'w week weeks', 7*24*60*60)
UnitConversion('s', 'M month months', 30*24*60*60)
UnitConversion('s', 'y year years', 365*24*60*60)

# as_seconds {{{2
def as_seconds(arg, units=None):
    arg = as_string(arg)
    return Quantity(arg, units or 'h').scale('s')

# normalize_key {{{2
# converts key to snake case
# downcase; replace whitespace and dashes with underscores
def normalize_key(key, parent_keys):
    if parent_keys == ("repositories",):
        return key
    return '_'.join(key.lower().replace('-', '_').split())


# SCHEMA {{{1
validate_settings = Schema(
    dict(
        to_email = as_email,
        from_email = as_email,
        max_age = as_seconds,
        root = as_abs_path,
        color_scheme = as_colorscheme,
        message = as_string,
        repositories = {
            str: dict(
                config = as_command,
                repo = as_path,
                host = as_string,
                max_age = as_seconds,
                to_email = as_email,
                command = as_command,
            )
        }
    )
)

# UTILITIES {{{1
# get_local_data {{{2
def get_local_data(description, config, path, max_age):
    if path:
        path = to_path(*path)
    if config:
        if not path:
            path = to_path(DATA_DIR)
        latest = read_latest(path / f"{config}.latest.nt")
        locked = (path /  f"{config}.lock").exists()
        mtime = latest.get('create last run')
        if not mtime:
            raise Error('create time is not available.', culprit=path)
    else:
        if not path:
           raise Error("‘repo’ setting is required.", culprit=description)
        paths = list(path.glob("index.*"))
        if not paths:
            raise Error("no sentinel file found.", culprit=path)
        if len(paths) > 1:
            raise Error("too many sentinel files.", *paths, sep="\n    ")
        path = paths[0]
        mtime = arrow.get(path.stat().st_mtime)
        locked = path.parent.glob('lock.*')

    delta = now - mtime
    age = Quantity(24 * 60 * 60 * delta.days + delta.seconds, 's')
    overdue = truth(age > max_age)
    locked = truth(locked)
    yield dict(
        description=description, path=path, mtime=mtime,
        age=age, max_age=max_age, overdue=overdue, locked=locked
    )

# get_remote_data {{{2
def get_remote_data(name, host, config, cmd):
    cmd = cmd or "assimilate"
    display(f"\n{name}:")
    config = ['--config', config] if config else []
    try:
        ssh = Run(['ssh', host] + config + [cmd, 'overdue', '--nt'], 'sOEW1')
        for repo_data in nt.loads(ssh.stdout, top=list):
            if 'mtime' in repo_data:
                repo_data['mtime'] = arrow.get(repo_data['mtime'])
            if 'overdue' in repo_data:
                repo_data['overdue'] = truth(repo_data['overdue'] == 'yes')
            if 'age' in repo_data:
                repo_data['age'] = as_seconds(repo_data['age'])
            if 'max_age' in repo_data:
                repo_data['max_age'] = as_seconds(repo_data['max_age'])
            if 'locked' in repo_data:
                repo_data['locked'] = truth(repo_data['locked'] == 'yes')
            else:
                repo_data['locked'] = truth(False)
            yield repo_data
    except Error as e:
        e.report(culprit=host)

# MAIN {{{1
def overdue(cmdline, args, settings, options):
    inform = get_informer()

    # read the settings file
    config_file = options.get('config')
    if config_file:
        if '.' not in config_file:
            config_file += '.conf.nt'
    else:
        config_file = OVERDUE_FILE
    settings_file = to_path(CONFIG_DIR, config_file)

    try:
        keymap = {}
        settings = nt.load(
            settings_file, top=dict, keymap=keymap, normalize_key=normalize_key
        )
        settings = validate_settings(settings)
    except MultipleInvalid as e:  # report schema violations
        report_voluptuous_errors(e, keymap, settings_file)
        terminate()
    except nt.NestedTextError as e:
        e.terminate()
    except OSError as e:
        fatal(os_error(e))

    # gather needed settings
    default_to_email = settings.get("to_email")
    default_max_age = settings.get("max_age", as_seconds('28h'))
    from_email = settings.get("from_email", f"{username}@{hostname}")
    repositories = settings.get("repositories")
    root = settings.get("root")
    colorscheme = settings.get("color_scheme", default_colorscheme)
    colorscheme = None if colorscheme == "none" else colorscheme
    message = settings.get("message", terse_status_message)

    if cmdline["--quiet"]:
        inform.quiet = True
        inform.narrate = False
        inform.verbose = False

    problem = False
    if cmdline["--message"]:
        message = cmdline["--message"]
    if cmdline["--no-color"]:
        colorscheme = None
    if cmdline["--verbose"]:
        message = verbose_status_message

    report_as_current = InformantFactory(
        clone=display, message_color=current_color
    )
    report_as_overdue = InformantFactory(
        clone=display, message_color=overdue_color,
        notify=cmdline['--notify'] and not Color.isTTY()
    )

    overdue_hosts = {}

    def send_mail(recipient, subject, message):
        if cmdline["--mail"]:
            if cmdline['--verbose']:
                display(f"Reporting to {recipient}.\n")
            mail_cmd = ["mailx", "-r", from_email, "-s", subject, recipient]
            Run(mail_cmd, stdin=message, modes="soeW0")

    # check age of repositories
    for description, params in repositories.items():
        config = params.get('config')
        repo = params.get('repo')
        max_age = params.get('max_age')
        max_age = max_age if max_age else default_max_age
        to_email = params.get('to_email')
        to_email = default_to_email if not to_email else to_email
        host = params.get('host')
        command = params.get('command')

        try:
            if host:
                ignoring = ("max_age", "repo")
                repos_data = get_remote_data(description, host, config, command)
            else:
                ignoring = ("command",)
                repos_data = get_local_data(
                    description, config, cull([root, repo]), max_age
                )
            ignored = set(ignoring) & params.keys()
            if ignored:
                culprit = (
                    settings_file, "repositories", description,
                    '{}-{}'.format(*nt.get_line_numbers(
                        ("repositories", description), keymap=keymap)
                    )
                )
                warn(f"ignoring {conjoin(sorted(ignored))}.", culprit=culprit)


            for repo_data in repos_data:
                repo_data['updated'] = repo_data['mtime'].humanize()
                overdue = repo_data['overdue']
                locked = repo_data['locked']
                report = report_as_overdue if overdue else report_as_current

                if overdue or locked or not cmdline["--no-passes"]:
                    if cmdline["--nt"]:
                        output(nt.dumps([repo_data], default=str))
                    else:
                        saved_colorscheme = inform.colorscheme
                        inform.colorscheme = colorscheme
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
                        finally:
                            inform.colorscheme = saved_colorscheme

                if overdue:
                    problem = True
                    overdue_hosts[host] = mail_status_message.format(**repo_data)
        except OSError as e:
            problem = True
            msg = os_error(e)
            error(msg)
            if to_email:
                send_mail(
                    to_email,
                    f"{get_prog_name()} error",
                    error_message.format(msg),
                )
        except Error as e:
            problem = True
            e.report()
            if to_email:
                send_mail(
                    to_email,
                    f"{get_prog_name()} error",
                    error_message.format(str(e)),
                )

    if overdue_hosts:
        if len(overdue_hosts) > 1:
            subject = "backups are overdue"
        else:
            subject = "backup is overdue"
        messages = '\n\n'.join(overdue_hosts.values())
        if settings.notify:
            send_mail(settings.notify, subject, messages)
        else:
            raise Error('must specify notify setting to send mail.')

    terminate(problem)
