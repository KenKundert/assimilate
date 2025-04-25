# Read Configurations
#

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
from .preferences import CONFIG_DIR
from .utilities import (
    report_voluptuous_errors, Quantity, InvalidNumber, lsf, to_path, chmod, getmod
)
from collections import defaultdict
from inform import (
    Error, codicil, conjoin, is_str, join, narrate, warn, terminate, truth
)
from voluptuous import Schema, Invalid, MultipleInvalid, Extra
import nestedtext as nt
import functools


# VALIDATORS {{{1
# read_only {{{2
# raise error if given
def read_only(arg):
    raise Invalid('cannot override internally computed value')

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
        raise Invalid(f"expected identifier, found {arg}")
    return arg

# as_name {{{2
# raise error if value is not a name
# a name is an identifier that uses dashes rather than underscores
def as_name(arg):
    arg = as_string(arg)
    if arg.replace('-', '_').isidentifier() and arg[0] != '-':
        return arg
    raise Invalid(f"expected name, found {arg}")

# as_email {{{2
# raise error if value is not an email address
# only performs simple-minded tests
def as_email(arg):
    email = as_string(arg).strip()
    user, _, host = email.partition('@')
    if '.' in host and '@' not in host:
        return arg
    raise Invalid(f"expected email address, found {arg}")

# as_emails {{{2
# raise error if value is not one or more email addresses
def as_emails(arg):
    emails = as_list(arg)
    for email in emails:
        as_email(email)
    return emails

# as_integer {{{2
# raise error if value is a string that cannot be cast to an integer
def as_integer(arg):
    arg = as_string(arg).strip()
    try:
        arg = int(arg)
    except ValueError:
        raise Invalid(f"expected integer, found ‘{arg}’")
    return arg

# as_quantity {{{2
# raise error if value is a string that cannot be cast to an quantity
def as_quantity(arg):
    arg = as_string(arg).strip()
    try:
        arg = Quantity(arg)
    except InvalidNumber:
        raise Invalid(f"expected number, found ‘{arg}’")
    return arg

# as_lines {{{2
# raise error if value is not a list of strings
# converts a string to a list by splitting on newlines
def as_lines(arg):
    if isinstance(arg, str):
        arg = arg.splitlines()
    if isinstance(arg, dict):
        raise Invalid('expected list')
    for each in arg:
        as_string(each)
    return [line.strip() for line in arg]

# as_list {{{2
# raise error if value is not a list of strings
# converts a string to a list by splitting on whitespace
def as_list(arg):
    if isinstance(arg, str):
        arg = arg.split()
    if isinstance(arg, dict):
        raise Invalid('expected list')
    for each in arg:
        as_string(each)
    return [line.strip() for line in arg]

# as_identifiers {{{2
# raise error if value is not a list of identifiers
# converts a string to a list by splitting on whitespace
def as_identifiers(arg):
    if isinstance(arg, str):
        arg = arg.split()
    if isinstance(arg, dict):
        raise Invalid('expected list of identifiers')
    for each in arg:
        as_identifier(each)
    return arg

# as_path {{{2
# raise error if value is not text
# coverts it to a path while expanding ~, env vars
def as_path(arg):
    arg = as_string(arg)
    return to_path(arg.strip())

# as_abs_path {{{2
# raise error if value is not text
# coverts it to a path while expanding ~, env vars
def as_abs_path(arg):
    arg = as_string(arg)
    path = to_path(arg.strip())
    if not path.is_absolute():
        raise Invalid("expected absolute path.")
    return path

# as_paths {{{2
# raise error if value is not a list of strings
# converts a string to a list by splitting on newlines
# converts lines to paths while skipping empty lines
def as_paths(arg):
    arg = as_lines(arg)
    return [to_path(line.strip()) for line in arg if line]

# as_patterns {{{2
# raise error if value is not a list of text lines
# converts a string to a list by splitting on newlines
# each line must have two parts, the first being a valid path prefix
def as_patterns(arg):
    arg = as_lines(arg)
    for line in arg:
        columns = line.split(maxsplit=1)
        num_columns = len(columns)
        if num_columns == 2:
            prefix = columns[0]
            expected = ['R', 'P', '+', '-', '!']
            if prefix not in expected:
                raise Invalid(join(
                    f"unknown path prefix, found ‘{prefix}’,",
                    f"expected {conjoin(expected, conj=' or ', fmt='‘{}’')}"
                ))
        elif num_columns == 1:
            raise Invalid(f"expected prefix and path, found ‘{columns[0]}’.")
        else:
            pass
    return arg

# as_dict {{{2
# raise error if value is not a dictionary
# converts an empty string to an empty dictionary
# only one level is supported; all keys must be names, all values must be strings
def as_dict(arg):
    # converts empty field to empty dictionary
    if isinstance(arg, str) and arg.strip() == "":
        arg = {}
    if not isinstance(arg, dict):
        raise Invalid('expected key-value pair')
    for key, value in arg.items():
        as_name(key)
        if not is_str(value):
            raise Invalid(f"expected string as value to ‘{key}’.")
    return arg

# as_dict_of_lists {{{2
# raise error if value is not a dictionary of lists
# converts dictionary string value to single item list
# only one level is supported; all list values must be strings
def as_dict_of_lists(arg):
    # converts empty field to empty dictionary
    if isinstance(arg, str) and arg.strip() == "":
        arg = {}
    if not isinstance(arg, dict):
        raise Invalid('expected key-value pair')
    new = {}
    for key, value in arg.items():
        if is_str(value):
            value = [value]
        for i, each in enumerate(value):
            if not is_str(each):
                raise Invalid(f"expected string as value to ‘{key}[{i}]’.")
        new[key]=value
    return new

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

# as_bool {{{2
@as_enum("'yes", "'no", "'true", "'false")
def as_bool(arg):
    return truth(arg in ["'yes", "'true"], formatter="yes/no")

# as_colorscheme {{{2
@as_enum("'light", "'dark")
def as_colorscheme(arg):
    return arg[1:]

# as_color{{{2
@as_enum(
    "'black", "'red", "'green", "'yellow", "'blue",
    "'magenta", "'cyan", "'white", "'none"
)
def as_color(arg):
    return arg[1:]

# as_check{{{2
@as_enum("'no", "'yes", "'latest", "'all", "'all_in_repository")
def as_check(arg):
    return arg[1:]

# normalize_key {{{2
# converts key to snake case
# downcase; replace whitespace and dashes with underscores
parents_of_non_identifier_keys = [
    ("command_aliases",)
]

def add_parents_of_non_identifier_keys(*parents):
    parents_of_non_identifier_keys.append(parents)

def normalize_key(key, parent_keys):
    if parent_keys in parents_of_non_identifier_keys:
        return key.lower()
    return '_'.join(key.lower().replace('-', '_').split())

# SETTINGS {{{1
# Assimilate settings {{{2
# Any setting found in the users settings files that is not found in
# ASSIMILATE_SETTINGS or BORG_SETTINGS is highlighted as a unknown setting by
# the settings command.  Such settings would be largely ignored but can be used
# as placeholders.
ASSIMILATE_SETTINGS = dict(
    archive = dict(
        desc = "template Borg should use when creating archive names",
        validator = as_string,
    ),
    avendesora_account = dict(
        desc = "account name that holds passphrase for encryption key in Avendesora",
        validator = as_string,
    ),
    borg_executable = dict(
        desc = "path to borg",
        validator = as_path
    ),
    check_after_create = dict(
        desc = "run check after archive creation",
        validator = as_check,
    ),
    colorscheme = dict(
        desc = "the color scheme",
        validator = as_colorscheme,
    ),
    composite_configs = dict(
        desc = "composite configurations and their children",
        validator = as_dict,
    ),
    create_retries = dict(
        desc = "number of times to retry a create if failures occur",
        validator = as_integer,
    ),
    create_retry_sleep = dict(
        desc = "time to sleep between retries [s]",
        validator = as_quantity,
    ),
    default_config = dict(
        desc = "default Assimilate configuration",
        validator = as_name,
    ),
    default_mount_point = dict(
        desc = "directory to use as mount point if one is not specified",
        validator = as_path,
    ),
    do_not_expand = dict(
        desc = "names of settings that must not undergo setting evaluation",
        validator = as_identifiers,
    ),
    encoding = dict(
        desc = "encoding when talking to borg",
        validator = as_string,
    ),
    encryption = dict(
        desc = "encryption method (see Borg documentation)",
        validator = as_name,
    ),
    excludes = dict(
        desc = "list of glob strings of files or directories to skip",
        validator = as_lines,
    ),
    exclude_from = dict(
        desc = "file that contains exclude patterns",
        validator = as_path,
    ),
    include = dict(
        desc = "include the contents of another file",
        validator = as_path,
    ),
    manage_diffs_cmd = dict(
        desc = "command to use to manage differences in files and directories",
        validator = as_string,
    ),
    list_formats = dict(
        desc = "named format strings available to list command",
        validator = as_dict,
        do_not_expand = True,
    ),
    default_list_format = dict(
        desc = "the format that the list command should use if none is specified",
        validator = as_identifier,
    ),
    must_exist = dict(
        desc = "if set, each of these files or directories must exist or create will quit with an error",
        validator = as_paths,
    ),
    needs_ssh_agent = dict(
        desc = "when set Assimilate complains if ssh_agent is not available",
        validator = as_bool,
    ),
    notifier = dict(
        desc = "notification program",
        validator = as_string,
    ),
    notify = dict(
        desc = "email address to notify when things go wrong",
        validator = as_emails,
    ),
    notify_from = dict(
        desc = "the email address of the sender for notifications",
        validator = as_email,
    ),
    passcommand = dict(
        desc = "command used by Borg to acquire the passphrase",
        validator = as_string,
    ),
    passphrase = dict(
        desc = "passphrase for encryption key (if specified, Avendesora is not used)",
        validator = as_string,
    ),
    patterns = dict(
        desc = "patterns that indicate whether a path should be included or excluded",
        validator = as_patterns,
    ),
    patterns_from = dict(
        desc = "file that contains patterns",
        validator = as_path,
    ),
    prune_after_create = dict(
        desc = "run prune after creating an archive",
        validator = as_bool,
    ),
    compact_after_delete = dict(
        desc = "run compact after deleting an archive or pruning a repository",
        validator = as_bool,
    ),
    report_diffs_cmd = dict(
        desc = "shell command to use to report differences in files and directories",
        validator = as_string,
    ),
    repository = dict(
        desc = "path to remote directory that contains repository",
        validator = as_string,
    ),
    run_after_backup = dict(
        desc = "commands to run after archive has been created",
        validator = as_lines,
    ),
    run_before_backup = dict(
        desc = "commands to run before archive is created",
        validator = as_lines,
    ),
    run_after_last_backup = dict(
        desc = "commands to run after last archive has been created",
        validator = as_lines,
    ),
    run_before_first_backup = dict(
        desc = "commands to run before first archive is created",
        validator = as_lines,
    ),
    run_after_borg = dict(
        desc = "commands to run after last Borg command has run",
        validator = as_lines,
    ),
    run_before_borg = dict(
        desc = "commands to run before first Borg command is run",
        validator = as_lines,
    ),
    show_progress = dict(
        desc = "show borg progress when running create or compact commands",
        validator = as_bool,
    ),
    show_stats = dict(
        desc = "show borg statistics when running create or compact commands",
        validator = as_bool,
    ),
    src_dirs = dict(
        desc = "the directories to archive",
        validator = as_lines,
    ),
    ssh_command = dict(
        desc = "command to use for SSH, can be used to specify SSH options",
        validator = as_string,
    ),
    verbose = dict(
        desc = "make Borg more verbose",
        validator = as_bool,
    ),
    working_dir = dict(
        desc = "working directory",
        validator = as_path,
    ),
    command_aliases = dict(
        desc = "command aliases",
        validator = as_dict_of_lists,
    ),
    logging = dict(
        desc = "logging options",
        validator = as_dict,
    ),

# Read only values
    cmd_name = dict(
        desc = "name of the Assimilate command being run",
        validator = read_only,
    ),
    config_dir = dict(
        desc = "path to Assimilate’s configuration directory",
        validator = read_only
    ),
    config_name = dict(
        desc = "name of active configuration",
        validator = read_only,
    ),
    home_dir = dict(
        desc = "path to the user’s home directory",
        validator = read_only,
    ),
    host_name = dict(
        desc = "name of the computer running Assimlate",
        validator = read_only,
    ),
    log_dir = dict(
        desc = "path to Assimilate’s log directory",
        validator = read_only,
    ),
    prog_name = dict(
        desc = "name of the command that runs Assimilate",
        validator = read_only,
    ),
    user_name = dict(
        desc = "login name of the user running Assimilate",
        validator = read_only,
    ),
)
READ_ONLY_SETTINGS = set(k for k, v in ASSIMILATE_SETTINGS.items() if v["validator"] == read_only)

# add_setting() {{{3
def add_setting(name, desc, validator):
    assert name not in ASSIMILATE_SETTINGS
    ASSIMILATE_SETTINGS[name] = dict(desc=desc, validator=validator)

# Borg settings {{{2
BORG_SETTINGS = dict(
    append_only = dict(
        cmds = ["repo-create"],
        desc = "create an append-only mode repository",
        validator = as_bool,
    ),
    chunker_params = dict(
        cmds = ["create", "recreate"],
        arg = "PARAMS",
        desc = "specify the chunker parameters",
        validator = as_string,
    ),
    compression = dict(
        cmds = ["create", "recreate"],
        arg = "COMPRESSION",
        desc = "compression algorithm",
        validator = as_string,
    ),
    exclude_caches = dict(
        cmds = ["create", "recreate"],
        desc = "exclude directories that contain a CACHEDIR.TAG file",
        validator = as_bool,
    ),
    exclude_nodump = dict(
        cmds = ["create"],
        desc = "exclude files flagged NODUMP",
        validator = as_bool,
    ),
    exclude_if_present = dict(
        cmds = ["create", "recreate"],
        arg = "NAME",
        desc = "exclude directories that are tagged by containing a filesystem object with the given NAME",
        validator = as_string,
    ),
    lock_wait = dict(
        cmds = ["all"],
        arg = "SECONDS",
        desc = "wait at most SECONDS for acquiring a repository/cache lock (default: 1)",
        validator = as_integer,
    ),
    keep_within = dict(
        cmds = ["prune"],
        arg = "INTERVAL",
        desc = "keep all archives within this time interval",
        validator = as_string,
    ),
    keep_last = dict(
        cmds = ["prune"],
        arg = "NUM",
        desc = "number of the most recent archives to keep",
        validator = as_integer,
    ),
    keep_minutely = dict(
        cmds = ["prune"],
        arg = "NUM",
        desc = "number of minutely archives to keep",
        validator = as_integer,
    ),
    keep_hourly = dict(
        cmds = ["prune"],
        arg = "NUM",
        desc = "number of hourly archives to keep",
        validator = as_integer,
    ),
    keep_daily = dict(
        cmds = ["prune"],
        arg = "NUM",
        desc = "number of daily archives to keep",
        validator = as_integer,
    ),
    keep_weekly = dict(
        cmds = ["prune"],
        arg = "NUM",
        desc = "number of weekly archives to keep",
        validator = as_integer,
    ),
    keep_monthly = dict(
        cmds = ["prune"],
        arg = "NUM",
        desc = "number of monthly archives to keep",
        validator = as_integer,
    ),
    keep_3monthly = dict(
        cmds = ["prune"],
        arg = "NUM",
        desc = "number of 3 month quarter archives to keep",
        validator = as_integer,
    ),
    keep_13weekly = dict(
        cmds = ["prune"],
        arg = "NUM",
        desc = "number of 13 week quarter archives to keep",
        validator = as_integer,
    ),
    keep_yearly = dict(
        cmds = ["prune"],
        arg = "NUM",
        desc = "number of yearly archives to keep",
        validator = as_integer,
    ),
    one_file_system = dict(
        cmds = ["create"],
        desc = "stay in the same file system and do not store mount points of other file systems",
        validator = as_bool,
    ),
    remote_path = dict(
        cmds = ["all"],
        arg = "CMD",
        desc = "name of borg executable on remote platform",
        validator = as_string,
    ),
    # # this is commented out as it is not supported as a setting.
    # reserve = dict(
    #     cmds = ["repo-space"],
    #     desc = "amount of space to keep in reserve [B]",
    #     validator = as_quantity,
    # ),
    sparse = dict(
        cmds = ["create"],
        desc = "detect sparse holes in input (supported only by fixed chunker)",
        validator = as_bool,
    ),
    threshold = dict(
        cmds = ["compact"],
        arg = "PERCENT",
        desc = "set minimum threshold in percent for saved space when compacting (default: 10)",
        validator = as_integer,
    ),
    umask = dict(
        cmds = ["all"],
        arg = "M",
        desc = "set umask to M (local and remote, default: 0077)",
        validator = as_integer,
    ),
    upload_buffer = dict(
        cmds = ["all"],
        arg = "UPLOAD_BUFFER",
        desc = "set network upload buffer size in MiB (default: 0=no buffer)",
        validator = as_integer,
    ),
    upload_ratelimit = dict(
        cmds = ["all"],
        arg = "RATE",
        desc = "set rate limit in kiB/s, used when writing to a remote network (default: 0=unlimited)",
        validator = as_integer,
    ),
    match_archives = dict(
        cmds = [
            "analyze",
            "check",
            "delete",
            "info",
            "mount",
            "prune",
            "recreate",
            "repo-list",
            "tag",
            "transfer",
            "undelete"
        ],
        arg = "PATTERNS",
        desc = "only consider archive names that match the given glob pattern",
        validator = as_lines,
    ),
)
assert not (ASSIMILATE_SETTINGS.keys() & BORG_SETTINGS.keys())

# SCHEMA {{{1
# build_validator() {{{2
def build_validator():
    schema = {
        'include': as_path,
        Extra: as_string
    }
    schema.update({
        k:v['validator']
        for k, v in ASSIMILATE_SETTINGS.items()
        if v['validator'] is not False
    })
    schema.update({
        k:v['validator']
        for k, v in BORG_SETTINGS.items()
        if v['validator'] is not False
    })
    return Schema(schema)


# CODE {{{1
# set_config_dir() {{{2
config_dir = to_path(CONFIG_DIR)
def set_config_dir(dir):
    global config_dir
    if dir:
        config_dir = to_path(dir)
    return config_dir


# get_available_configs() {{{2
available_configs = {}
def get_available_configs(keep_shared=False):
    if not available_configs:
        config_files = lsf(config_dir, select="*.conf.nt")
        configs = {p.name[:-8]: p for p in config_files}

        # warn about non-compliant config names
        for name, path in configs.items():
            try:
                as_name(name)
            except Invalid:
                warn(
                    "improper name for config file.",
                    culprit = path,
                    codicil = "name should consist only of letters, digits and dashes"
                )
        available_configs.update(configs)

    if keep_shared:
        return available_configs
    return {k:v for k, v in available_configs.items() if k != 'shared'}

# report_setting_error() {{{2
keymaps = defaultdict(dict)
def report_setting_error(keys, *args, **kwargs):
    if is_str(keys):
        keys = tuple(keys.split())
    if 'codicil' in kwargs:
        codicil = kwargs.pop('codicil')
        if is_str(codicil):
            codicil = tuple(codicil.split())
    else:
        codicil = ()

    for path in reversed(keymaps.keys()):
        keymap = keymaps[path]
        loc = keymap.get(keys)
        if loc:
            culprit = (path,) + keys
            raise Error(
                *args,
                culprit=(path,)+keys,
                codicil=codicil + (loc.as_line(),),
                **kwargs
            )
    raise Error(*args, culprit=culprit, codicil=codicil **kwargs)


# read_config() {{{2
def read_config(path, validate_settings):
    # read a file and recursively process includes
    try:
        keymap = keymaps[str(path)]
        settings = nt.load(
            path, top=dict, keymap=keymap, normalize_key=normalize_key
        )
        settings = validate_settings(settings)
    except MultipleInvalid as e:  # report schema violations
        report_voluptuous_errors(e, keymap, path)
        terminate(2)

    # check file permissions
    if settings.get("passphrase"):
        file_mode = getmod(path)
        if file_mode & 0o077:
            warn("file permissions are too loose.", culprit=path)
            chmod(file_mode & 0o700, path)
            codicil(f"Mode changed to {file_mode & 0o700:o}.")

    include = settings.pop('include', None)
    if include:
        include = to_path(path.parent, include)
        included_settings = read_config(include, validate_settings)
        included_settings.update(settings)
        settings = included_settings

    return settings

# read_settings() {{{2
def read_settings(name, config_dir=None, shared_settings=None):
    settings = shared_settings.copy() if shared_settings else {}
    set_config_dir(config_dir)
    configs = get_available_configs(True)

    if not configs:
        return settings

    # read the settings file
    if name in configs:
        new_settings = read_config(configs[name], build_validator())
    else:
        new_settings = {}  # this can happen for name == 'shared'

    if name != 'shared':
        new_settings['config_name'] = name
        if new_settings.pop('default_config', None):
            warn('default_config only valid in shared.conf.nt.', culprit=name)
        if new_settings.pop('composite_configs', None):
            warn('composite_configs only valid in shared.conf.nt.', culprit=name)
        if new_settings.pop('command_aliases', None):
            warn('command_aliases only valid in shared.conf.nt.', culprit=name)

    settings.update(new_settings)

    # log the user-defined settings
    unknown = (
        settings.keys()
        - ASSIMILATE_SETTINGS.keys()
        - BORG_SETTINGS.keys()
    )
    if unknown:
        narrate("The following user-defined settings were specified:")
        for each in unknown:
            narrate("   ", each)

    return settings

# convert_name_to_option() {{{2
# utility function that converts setting names to borg option names
def convert_name_to_option(name):
    return "--" + name.replace("_", "-")

