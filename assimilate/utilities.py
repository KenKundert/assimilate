# Utilities

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
# along with this program.  If not, see http://www.gnu.org/licenses/.

# Imports {{{1
import arrow
import pwd
import os
import socket
import sys
import nestedtext as nt
from docopt import docopt, DocoptExit
from inform import (
    Error, conjoin, cull, full_stop, is_str, join, os_error,
    error, narrate, output as output_raw, terminate, warn
)
from quantiphy import (
    Quantity, UnitConversion, QuantiPhyError, InvalidNumber, UnknownConversion
)
from .preferences import DEFAULT_ENCODING
from .shlib import (
    Cmd, Run, cd, chmod, cwd, lsd, lsf, getmod, mkdir, rm, render_command,
    set_prefs as set_shlib_prefs, split_cmd, to_path
)

# preferences {{{1
Quantity.set_prefs(spacer='', ignore_sf=True, form='fixed', prec=1)
set_shlib_prefs(use_inform=True, log_cmd=True, encoding=DEFAULT_ENCODING)


# output {{{1
# create new version of output that always writes to stout regardless of Inform
# stream_policy.
output = output_raw
output.stream = sys.stdout


# gethostname {{{1
# returns short version of the hostname (the hostname without any domain name)
def gethostname():
    return socket.gethostname().split(".")[0]


def getfullhostname():
    return socket.gethostname()


# getusername {{{1
def getusername():
    return pwd.getpwuid(os.getuid()).pw_name


# pager {{{1
def pager(text):
    program = os.environ.get("PAGER", "less")
    Run([program], stdin=text, modes="Woes")


# two_columns {{{1
def two_columns(col1, col2, width=16, indent=True):
    indent = "    "
    if len(col1) > width:
        return "%s%s\n%s%s%s" % (indent, col1, indent, "  " + width * " ", col2)
    else:
        return "%s%-*s  %s" % (indent, width, col1, col2)


# when {{{1
def when(time, relative_to=None, as_past=None, as_future=None):
    """Converts time into a human friendly description of a time difference

    Takes a time and returns a string that is intended for people.  It is a
    short description of the time difference between the given time and the
    current time or a reference time.  It is like arrow.humanize(), but provides
    more resolution.  It is suitable for use with time differences that exceed
    1 second.  Any smaller than that will round to 0.

    Arguments:
        time (datetime):
            The time of the event. May either be in the future or the past.
        relative_to (datetime):
            Time to compare against to form the time difference.  If not given,
            the current time is used.
        as_past (bool or str):
            If true, the word “ago” will be added to the end of the returned
            time difference if it is negative, indicating it occurred in the
            past.  If it a string, it should contain ‘{}’, which is replaced
            with the time difference.
        as_future (bool or str):
            If true, the word “in” will be added to the front of the returned
            time difference if it is positive, indicating it occurs in the
            past.  If it a string, it should contain ‘{}’, which is replaced
            with the time difference.
    Returns:
        A user friendly string that describes the time difference.

    Examples:

        >>> import arrow
        >>> now = arrow.now()
        >>> print(when(now.shift(seconds=60.1)))
        1 minute

        >>> print(when(now.shift(seconds=2*60), as_future=True))
        in 2 minutes

        >>> print(when(now.shift(seconds=-60*60), as_past=True))
        60 minutes ago

        >>> print(when(now.shift(seconds=3.5*60), as_future="{} from now"))
        3.5 minutes from now

        >>> print(when(now.shift(days=-2*365), as_past="last run {} ago"))
        last run 2 years ago
    """

    if relative_to is None:
        relative_to = arrow.now()
    difference = time - relative_to
    seconds = 60*60*24*difference.days + difference.seconds

    def fmt(dt, prec, unit):
        if prec:
            num = f'{dt:0.1f}'
            if num.endswith('.0'):
                num = num[:-2]
        else:
            num = f'{dt:0.0f}'
        if num == '1':
            offset = f'{num} {unit}'
        else:
            offset = f'{num} {unit}s'
        return offset

    if seconds < 0 and as_past:
        if as_past is True:
            as_past = "{} ago"

        def annotate(dt, prec, unit):
            return as_past.format(fmt(dt, prec, unit))

    elif seconds >= 0 and as_future:
        if as_future is True:
            as_future = "in {}"

        def annotate(dt, prec, unit):
            return as_future.format(fmt(dt, prec, unit))

    else:
        annotate = fmt

    seconds = abs(seconds)
    if seconds < 60:
        return annotate(seconds, 0, "second")
    minutes = seconds / 60
    if minutes < 10:
        return annotate(minutes, 1, "minute")
    if minutes < 120:
        return annotate(minutes, 0, "minute")
    hours = minutes / 60
    if hours < 10:
        return annotate(hours, 1, "hour")
    if hours < 36:
        return annotate(hours, 0, "hour")
    days = hours / 24
    if days < 14:
        return annotate(days, 1, "day")
    weeks = days / 7
    if weeks < 8:
        return annotate(weeks, 0, "week")
    months = days / 30
    if months < 18:
        return annotate(months, 0, "month")
    years = days / 365
    if years < 10:
        return annotate(years, 1, "year")
    return annotate(years, 0, "year")


# update_latest {{{1
def update_latest(commands, path, options, repo_size=None):
    if 'dry-run' in options:
        return
    if is_str(commands):
        commands = [commands]
    narrate(f"updating date file for {conjoin(commands)}: {str(path)}")
    if is_str(commands):
        commands = [commands]
    latest = {}
    try:
        latest = nt.load(path, dict)
    except nt.NestedTextError as e:
        warn(e)
    except FileNotFoundError:
        pass
    except OSError as e:
        warn(os_error(e))
    now = str(arrow.now())
    for command in commands:
        latest[f"{command} last run"] = now
    if repo_size:
        latest['repository size'] = repo_size
    elif 'repository size' in latest:
        if repo_size is False:
            del latest['repository size']

    try:
        nt.dump(latest, path, sort_keys=True)
    except nt.NestedTextError as e:
        warn(e)
    except OSError as e:
        warn(os_error(e))

# read_latest {{{1
def read_latest(path):
    try:
        latest = nt.load(path, dict)
        for k, v in latest.items():
            if "last run" in k:
                try:
                    latest[k] = arrow.get(v)
                except arrow.parser.ParserError:
                    warn(f"{k}: date not given in iso format.", culprit=path)
        return latest
    except nt.NestedTextError as e:
        raise Error(e)

# voluptuous_error {{{1
# A convenience function used for reporting voluptuous errors.  Uses Inform's
# error() function when reporting the errors as it allows for multiple errors to
# be reported.

voluptuous_error_msg_mappings = {
    "extra keys not allowed": ("unknown key", "key"),
    "expected a dictionary": ("expected a key-value pair", "value"),
    "required key not provided": ("required key is missing", "value"),
}

def report_voluptuous_errors(multiple_invalid, keymap, source=None, sep="›", path_fmt="{path}@{lines}"):
    source = str(source) if source else ""

    for err in multiple_invalid.errors:

        # convert message to something easier for non-savvy user to understand
        msg, kind = voluptuous_error_msg_mappings.get(
            err.msg, (err.msg, 'value')
        )

        # get metadata about error
        if keymap:
            culprit = nt.get_keys(err.path, keymap=keymap, strict="found", sep=sep)
            line_nums = nt.get_line_numbers(err.path, keymap, kind=kind, sep="-", strict=False)
            loc = nt.get_location(err.path, keymap)
            if loc:
                codicil = loc.as_line(kind)
            else:  # required key is missing
                missing = nt.get_keys(err.path, keymap, strict="missing", sep=sep)
                codicil = f"‘{missing}’ was not found."

            file_and_lineno = path_fmt.format(path=str(source), lines=line_nums)
            culprit = cull((file_and_lineno, culprit))
        else:
            keys = sep.join(str(c) for c in err.path)
            culprit = cull([source, keys])
            codicil = None

        # report error
        error(full_stop(msg), culprit=culprit, codicil=codicil)

# table {{{1
def table(rows):
    if not rows:
        return []
    cols = len(rows[0]) * [0]
    for row in rows:
        for i, col in enumerate(row):
            width = len(col)
            cols[i] = max(cols[i], width)
    table = []
    for row in rows:
        table.append('  '.join(f"{c:<{cols[i]}}" for i, c in enumerate(row)))
    return table

# process_cmdline {{{1
def process_cmdline(*args, **kwargs):
    try:
        return docopt(*args, **kwargs)
    except DocoptExit as e:
        sys.stderr.write(str(e) + '\n')
        terminate(3)

# time conversions {{{1
UnitConversion('seconds', 's sec second')
UnitConversion('seconds', 'm min minute minutes', 60)
UnitConversion('seconds', 'h hr hour hours', 60*60)
UnitConversion('seconds', 'D d day days', 24*60*60)
UnitConversion('seconds', 'W w week weeks', 7*24*60*60)
UnitConversion('seconds', 'M month months', 30*24*60*60)
UnitConversion('seconds', 'Y y year years', 365*24*60*60)
UnitConversion('days', 's sec second seconds', 1/60/60/24)
UnitConversion('days', 'm min minute minutes', 1/60/24)
UnitConversion('days', 'h hr hour hours', 1/24)
UnitConversion('days', 'D d day', 1)
UnitConversion('days', 'W w week weeks', 7)
UnitConversion('days', 'M month months', 30)
UnitConversion('days', 'Y y year years', 365)
Quantity.set_prefs(ignore_sf=True, spacer='')

# to_seconds() {{{2
def to_seconds(time_spec, default_units='d'):
    # The time_spec may be an absolute format (an arrow date format) or it may
    # be a relative time format (Ny, NM, Nw, Nd, Nm, Ns).
    # If an absolute format is given, then the return value is the number of
    # seconds in from now to the given date (is positive if date is in past).
    # A Quantity with units of 'seconds' is returned.
    try:
        target = arrow.get(time_spec, tzinfo='local')
        return Quantity((arrow.now() - target).total_seconds(), 'seconds')
    except arrow.parser.ParserError:
        return Quantity(time_spec, default_units, scale='seconds')

# to_days() {{{2
def to_days(time_spec, default_units='seconds'):
    # The time_spec may be an absolute format (an arrow date format) or it may
    # be a relative time format (Ny, NM, Nw, Nd, Nm, Ns).
    # If an absolute format is given, then the return value is the number of
    # seconds in from now to the given date (is positive if date is in past).
    # A Quantity with units of 'days' is returned.
    try:
        target = arrow.get(time_spec, tzinfo='local')
        return Quantity((arrow.now() - target).total_seconds(), 'seconds', scale='days')
    except arrow.parser.ParserError:
        return Quantity(time_spec, default_units, scale='days')

# to_date() {{{2
def to_date(time_spec, default_units='d'):
    # The time_spec may be an absolute format (an arrow date format) or it may
    # be a relative time format (Ny, NM, Nw, Nd, Nm, Ns).
    # An arrow datetime object is returned.
    try:
        return arrow.get(time_spec, tzinfo='local')
    except arrow.parser.ParserError as e:
        try:
            seconds = Quantity(time_spec, default_units, scale='seconds')
            return arrow.now().shift(seconds=-seconds)
        except QuantiPhyError:
            codicil = join(
                full_stop(e),
                'Alternatively, relative time formats are accepted:',
                'Ns, Nm, Nh, Nd, Nw, NM, Ny.  Example 2w is 2 weeks.'
            )
            raise Error(
                "invalid date specification.",
                culprit=time_spec, codicil=codicil, wrap=True
            )

