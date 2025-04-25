# Assimilate Settings

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
import errno
import os
import sys
import arrow
from inform import (
    Color,
    Error,
    LoggingCache,
    comment,
    conjoin,
    cull,
    dedent,
    display,
    done,
    errors_accrued,
    full_stop,
    get_informer,
    indent,
    is_str,
    is_collection,
    is_mapping,
    join,
    log,
    narrate,
    plural,
    render,
    warn,
)
from ntlog import NTlog
from .collection import Collection, split_lines
from .configs import (
    ASSIMILATE_SETTINGS,
    BORG_SETTINGS,
    convert_name_to_option,
    get_available_configs,
    set_config_dir,
    read_settings,
    report_setting_error
)
from .hooks import Hooks
from .patterns import (
    check_excludes,
    check_excludes_files,
    check_patterns,
    check_patterns_files,
    check_roots,
)
from .preferences import (
    BORG,
    CONFIG_DIR,
    DATA_DIR,
    DATE_FILE,
    DEFAULT_ENCRYPTION,
    INITIAL_CACHE_CONFIG_FILE_CONTENTS,
    INITIAL_HOME_CONFIG_FILE_CONTENTS,
    INITIAL_ROOT_CONFIG_FILE_CONTENTS,
    INITIAL_SHARED_SETTINGS_FILE_CONTENTS,
    LOCK_FILE,
    LOG_FILE,
    PROGRAM_NAME,
    SHARED_SETTINGS_FILE,
)
from . import overdue
    # unused here, but needed so that overdue extensions to settings file are
    # added before the files are read
from .utilities import (
    getfullhostname, gethostname, getusername, output,
    Run, cd, cwd, render_command, set_shlib_prefs, to_path,
)
import nestedtext as nt

# Globals {{{1
borg_commands_with_dryrun = "compact create delete extract prune upgrade recreate undelete".split()

# Utilities {{{1
hostname = gethostname()
fullhostname = getfullhostname()
username = getusername()

# borg_options_arg_count {{{2
borg_options_arg_count = {
    "borg": 1,
    "--exclude": 1,
    "--exclude-from": 1,
    "--first": 1,
    "--format": 1,
    "--last": 1,
    "--pattern": 1,
    "--patterns-from": 1,
    "--encryption": 1,
    "--repo": 1,
    "-r": 1,
}
for name, attrs in BORG_SETTINGS.items():
    if "arg" in attrs and attrs["arg"]:
        borg_options_arg_count[convert_name_to_option(name)] = 1

# ConfigQueue {{{1
class ConfigQueue:
    def __init__(self, command=None):
        self.uninitialized = True
        if command:
            self.requires_exclusivity = command.REQUIRES_EXCLUSIVITY
            self.composite_config_response = command.COMPOSITE_CONFIGS
            self.show_config_name = command.SHOW_CONFIG_NAME
            self.log_command = command.LOG_COMMAND
        else:
            # This is a result of an API call.
            # This will largely constrain use to scalar configs, if a composite
            # config is given, the only thing the user will be able to do is to
            # ask for the child configs.
            self.requires_exclusivity = True
            self.composite_config_response = 'restricted'
            self.show_config_name = False
            self.log_command = True

    def initialize(self, name, settings):
        self.uninitialized = False
        simple_configs = get_available_configs()
        composite_configs = settings.get('composite_configs', {})
        known_configs = composite_configs.keys() | simple_configs

        if not name:
            name = settings.get('default_config')
            if not name and len(known_configs) == 1:
                name = tuple(known_configs)[0]
            if not name:
                raise Error(
                    "you must specify a config.",
                    codicil=f"Choose from: {conjoin(sorted(known_configs), ', or ')}."
                )

        # check that name is known
        if name not in known_configs:
            raise Error(
                'unknown config.',
                codicil=f"Choose from: {conjoin(sorted(known_configs), ', or ')}.",
                culprit=name
            )

        if name in composite_configs:
            sub_configs = composite_configs[name].split()
            unknown_configs = set(sub_configs) - known_configs
            if unknown_configs:
                report_setting_error(
                    "composite_configs",
                    f"unknown {plural(unknown_configs):config/s}:",
                    f"{', '.join(sorted(unknown_configs))}.",
                )
            if name in sub_configs:
                report_setting_error("composite_configs", "recursion is not allowed.")
        else:
            sub_configs = [name]

        # set the config queue
        # convert configs to list while preserving order and eliminating dupes
        num_configs = len(sub_configs)
        if num_configs > 1:
            if self.composite_config_response == "error":
                raise Error("command does not support composite configs.", culprit=name)
        elif num_configs < 1:
            sub_configs = [name]
        self.configs = sub_configs

        comment(
            config = name,
            sub_configs = ', '.join(sub_configs),
            template = ("config: {config} => ({subconfigs})", "config: {config}")
        )

        if self.composite_config_response == "first":
            self.remaining_configs = sub_configs[0:1]
        elif self.composite_config_response == "none":
            self.remaining_configs = [None]
        else:
            self.remaining_configs = list(reversed(sub_configs))

        # determine whether to display sub-config name
        if self.show_config_name:
            self.show_config_name = 'first'
            if len(self.remaining_configs) <= 1:
                self.show_config_name = False


    def get_active_config(self):
        active_config = self.remaining_configs.pop()
        if self.show_config_name:
            if self.show_config_name != 'first':
                display()
            display("===", active_config, "===")
            self.show_config_name = True
        return active_config

    def __bool__(self):
        return bool(self.uninitialized or self.remaining_configs)


# Assimilate class {{{1
class Assimilate:
    """Assimilate Settings

    config (str):
        Name of desired configuration.  Default is the default configuration as
        specified in the shared settings file.
    assimilate_opts ([str])
        A list of Assimilate options chosen from “verbose”, “narrate”,
        “dry-run”, “no-log”, “config” (config may either be given directly or in
        assimilate_opts, whichever is most convenient.
    config_dir (path)
        A path to the directory that contains the configuration files.  This
        allows you to override the normal configuration directory, which is
        typically ~/.config/assimilate.
    """
    # Constructor {{{2
    def __init__(
        self, config=None, assimilate_opts=None, config_dir=None,
        shared_settings=None, **kwargs
    ):
        self.config_dir = set_config_dir(config_dir)

        # assimilate options
        if assimilate_opts is None:
            assimilate_opts = {"no-log": True}
                # no-log as True is suitable for API default
        self.assimilate_opts = assimilate_opts
        if config:
            if assimilate_opts.get("config"):
                assert config == assimilate_opts.get("config")
        else:
            config = assimilate_opts.get("config")

        # read shared setting if not already available
        if shared_settings is None:
            Hooks.provision_hooks()
            shared_settings = read_settings('shared')
        self.run_name = kwargs.pop('run_name', None)

        # reset the logfile so anything logged after this is placed in the
        # logfile for this config
        get_informer().set_logfile(LoggingCache())
        self.read_config(config, shared_settings, **kwargs)
        self.check()
        if self.encoding:
            set_shlib_prefs(encoding=self.encoding)
        self.hooks = Hooks(self, dry_run='dry-run' in assimilate_opts)
        self.borg_ran = False

        # set colorscheme
        if self.colorscheme:
            colorscheme = self.colorscheme.lower()
            if colorscheme == 'none':
                get_informer().colorscheme = None
            elif colorscheme in ('light', 'dark'):
                get_informer().colorscheme = colorscheme

        # determine the do_not_expand list
        do_not_expand = set(['monitoring', 'command_aliases', 'overdue'])
        for key, value in ASSIMILATE_SETTINGS.items():
            if value.get('do_not_expand'):
                do_not_expand.add(key)
        for key, value in BORG_SETTINGS.items():
            if value.get('do_not_expand'):
                do_not_expand.add(key)
        do_not_expand |= set(self.do_not_expand)
        self.do_not_expand = do_not_expand


    # read_config() {{{2
    def read_config(self, name, shared_settings, **kwargs):
        assert '_include_path' not in kwargs
        parent = self.config_dir
        if not parent.exists():
            # config dir does not exist, create and populate it
            narrate("creating config directory:", str(parent))
            parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            for fname, contents in [
                (SHARED_SETTINGS_FILE, INITIAL_SHARED_SETTINGS_FILE_CONTENTS),
                ("root.conf.nt", INITIAL_ROOT_CONFIG_FILE_CONTENTS),
                ("home.conf.nt", INITIAL_HOME_CONFIG_FILE_CONTENTS),
                ("cache.conf.nt", INITIAL_CACHE_CONFIG_FILE_CONTENTS),
            ]:
                path = parent / fname
                path.write_text(contents)
                path.chmod(0o600)
            output(
                "Configuration directory created:",
                f"    {parent!s}",
                "Includes example settings files. Edit them to suit your needs.",
                "Search for and replace any fields delimited with ❬ and ❭.",
                "Delete any configurations you do not need.",
                sep="\n",
            )
            done()

        # initialize the config queue
        queue = kwargs.get('queue')
        if not queue:
            # this is a request through the API
            queue = ConfigQueue()
        if queue.uninitialized:
            self.simple_configs = get_available_configs()
            queue.initialize(name, shared_settings)
        config = queue.get_active_config()
        self.configs = queue.configs
        self.log_command = queue.log_command
        self.requires_exclusivity = queue.requires_exclusivity
        if 'exclusive' in kwargs:
            self.requires_exclusivity = kwargs['exclusive']

        # save config name
        self.config_name = config
        if not config:
            # this happens on composite configs for commands that do not
            # need access to a specific config, such as help and configs
            self.settings = shared_settings
            return

        self.settings = read_settings(config, shared_settings=shared_settings)
        self.settings["config_name"] = config

        # add command name to settings so it can be used in expansions
        self.settings['cmd_name'] = kwargs.get('cmd_name', '')


    # check() {{{2
    def check(self):
        # add some possibly useful placeholders into settings
        home_dir = os.environ.get("HOME")
        if home_dir and "home_dir" not in self.settings:
            self.settings["home_dir"] = home_dir
        self.settings["config_dir"] = CONFIG_DIR
        self.settings["log_dir"] = DATA_DIR
        self.settings["host_name"] = hostname
        self.settings["user_name"] = username
        self.settings["prog_name"] = PROGRAM_NAME
        self.do_not_expand = Collection(self.settings.get("do_not_expand", ""))

        # gather the string valued settings together (can be used by resolve)
        self.str_settings = {k: v for k, v in self.settings.items() if is_str(v)}

        if not self.config_name:
            # running a command that does not need settings, such as configs
            return

        # complain about required settings that are missing
        missing = []
        required_settings = "repository".split()
        for each in required_settings:
            if not self.settings.get(each):
                missing.append(each)
        if missing:
            m = conjoin(missing)
            raise Error(f"{m}: no value given for {plural(missing):setting}.")

        self.working_dir = to_path(self.settings.get("working_dir", "/"))
        if not self.working_dir.exists():
            report_setting_error("working_dir", f"{self.working_dir!s} not found.")
        if not self.working_dir.is_absolute():
            report_setting_error("working_dir", "must be an absolute path.")

    # handle errors {{{2
    def fail(self, *msg, cmd='❬unknown❭'):
        msg = join(*msg)
        try:
            msg = msg.decode('ascii', errors='replace')
        except AttributeError:
            pass
        try:
            if self.notify and not Color.isTTY():
                to_run = ["mail", "-s", f"{PROGRAM_NAME} failed on {username}@{hostname}"]
                if self.notify_from:
                    to_run.extend(["-r", self.notify_from])
                to_run.extend(self.notify)
                report = {
                    "source": PROGRAM_NAME,
                    "message": msg,
                    "command": cmd,
                    "config": self.config_name,
                    "user": username,
                    "host": fullhostname,
                    "roots": self.roots,
                    "destination":  self.repository,
                    "time": arrow.now(),
                }
                message = nt.dumps(report, default=str)
                Run(to_run, stdin=message, modes="soeW")
        except Error:
            pass
        try:
            notifier = self.settings.get("notifier")
            # don't use self.value as we don't want arguments expanded yet
            if notifier and not Color.isTTY():
                Run(
                    self.notifier.format(
                        cmd=cmd,
                        msg=msg,
                        hostname = hostname,
                        user_name = username,
                        prog_name = PROGRAM_NAME,
                    ),
                    modes="SoeW"
                    # need to use the shell as user will generally quote msg
                )
        except Error:
            pass
        except KeyError as e:
            warn("unknown key.", culprit=(self.settings_file, "notifier", e))

    # get value {{{2
    def value(self, name, default=""):
        """Gets value of scalar setting."""
        value = self.settings.get(name, default)
        if (
            name in self.do_not_expand or
            not (is_str(value) or is_collection(value))
        ):
            return value
        return self.resolve(name, value)

    # get list values {{{2
    def values(self, name, default=()):
        """Gets value of list setting."""
        values = Collection(
            self.settings.get(name, default),
            split_lines,
            comment="#",
            strip=True,
            cull=True,
        )
        if name in self.do_not_expand:
            return values
        return [self.resolve(name, v) for v in values]

    # get dict values {{{2
    def dict_values(self, name, default=None):
        """Gets value of dict setting."""
        if default is None:
            default = {}
        values = Collection(
            self.settings.get(name, default),
            split_lines,
            comment="#",
            strip=True,
            cull=True,
        )
        if name in self.do_not_expand:
            return values
        return {k:self.resolve(name, v) for k,v in values.items()}

    # resolve all values {{{2
    def resolve_any(self, name):
        """Calls value(), values(), or dict_values() as appropriate for requested value"""
        value = self.settings.get(name)
        if is_str(value):
            return self.value(name)
        if is_mapping(value):
            return self.dict_values(name)
        if is_collection(value):
            return self.values(name)

    # resolve {{{2
    def resolve(self, name, value):
        """Expand any embedded names in value"""

        # escape any double braces
        try:
            value = value.replace("{{", r"\b").replace("}}", r"\e")
        except AttributeError:
            if is_collection(value):
                return [self.resolve(name, v) for v in value]
            if isinstance(value, int) and not isinstance(value, bool):
                return str(value)
            return value

        # expand names contained in braces
        try:
            resolved = value.format(**self.str_settings)
        except KeyError as e:
            k = e.args[0]
            if k in self.settings and k not in self.str_settings:
                raise Error("not a text setting.", culprit=k)
            raise Error("unknown setting.", culprit=k)
        except ValueError as e:
            raise Error(full_stop(e), codicil=name)
        if resolved != value:
            resolved = self.resolve(name, resolved)

        # restore escaped double braces with single braces
        return resolved.replace(r"\b", "{").replace(r"\e", "}")

    # to_path() {{{2
    def to_path(self, s, resolve=True, culprit=None):
        """Converts a string to a path."""
        p = to_path(s)
        if resolve:
            p = to_path(self.working_dir, p)
        if culprit:
            if not p.exists():
                raise Error(f"{p!s} not found.", culprit=culprit)
        return p

    # as_path() {{{2
    def as_path(self, name, resolve=True, must_exist=False, default=None):
        """Converts a setting to a path, without resolution."""
        s = self.value(name, default)
        if s:
            return self.to_path(s, resolve, name if must_exist else None)

    # resolve_patterns() {{{2
    def resolve_patterns(self, borg_opts, skip_checks=False):
        roots = self.src_dirs[:]

        patterns = self.values("patterns")
        if patterns:
            for pattern in check_patterns(
                patterns, roots, self.working_dir, "patterns",
                skip_checks=skip_checks
            ):
                borg_opts.append(f"--pattern={pattern}")

        excludes = self.values("excludes")
        if excludes:
            for exclude in check_excludes(excludes, roots, "excludes"):
                borg_opts.append(f"--exclude={exclude}")

        patterns_froms = self.as_paths("patterns_from", must_exist=True)
        if patterns_froms:
            check_patterns_files(
                patterns_froms, roots, self.working_dir, skip_checks=skip_checks
            )
            for patterns_from in patterns_froms:
                borg_opts.append(f"--patterns-from={patterns_from}")

        exclude_froms = self.as_paths("exclude_from", must_exist=True)
        if exclude_froms:
            check_excludes_files(exclude_froms, roots)
            for exclude_from in exclude_froms:
                borg_opts.append(f"--exclude-from={exclude_from}")

        if not skip_checks:
            check_roots(roots, self.working_dir)

        if errors_accrued():
            raise Error("stopping due to previously reported errors.")
        self.roots = roots

    # as_paths() {{{2
    def as_paths(self, name, resolve=True, must_exist=False):
        """Convert setting to paths, without resolution."""
        return [
            self.to_path(s, resolve, name if must_exist else None)
            for s in self.settings.get(name, ())
        ]

    # borg_options() {{{2
    def borg_options(self, cmd, borg_opts, assimilate_opts, strip_archive_matcher):
        if not borg_opts:
            borg_opts = []
        borg_opts.append(f"--repo={self.repository!s}")

        # handle special cases first {{{3
        if self.value("verbose"):
            assimilate_opts["verbose"] = True
        if assimilate_opts.get("verbose"):
            borg_opts.append("--verbose")
        if assimilate_opts.get("dry-run") and cmd in borg_commands_with_dryrun:
            borg_opts.append("--dry-run")

        if cmd == "create":
            if assimilate_opts.get("verbose") and "--list" not in borg_opts:
                borg_opts.append("--list")
            self.resolve_patterns(borg_opts)

        elif cmd == "extract":
            if assimilate_opts.get("verbose"):
                borg_opts.append("--list")

        elif cmd == "repo-create":
            if self.passphrase or self.passcommand or self.avendesora_account:
                encryption = self.encryption or DEFAULT_ENCRYPTION
                borg_opts.append(f"--encryption={encryption}")
                if encryption == "none":
                    warn("passphrase given but not needed as encryption set to none.")
                if encryption.startswith("keyfile"):
                    warn(
                        dedent(f"""
                            you should use “borg key export” to export the
                            encryption key, and then keep that key in a safe
                            place.  You can do this with assimilate using
                            “assimilate --config {self.config_name} borg key
                            export @repo ❬/.../out-file❭”.  If you lose this
                            key you lose access to your backups.
                        """).strip(),
                        wrap=True,
                    )
            else:
                encryption = self.encryption if self.encryption else "none"
                if encryption != "none":
                    raise Error("passphrase not specified.")
                borg_opts.append(f"--encryption={encryption}")

        if (
            cmd in ["create"]
            and not assimilate_opts.get("dry-run")
            and not ("--list" in borg_opts or "--progress" in borg_opts)
        ):
            # By default we ask for stats to go in the log file.  However if
            # opts contains --list, then the stats will be displayed to user
            # rather than going to logfile, in this case, do not request stats
            # automatically, require user to do it manually.
            if '--stats' not in borg_opts:
                borg_opts.append("--stats")

        # add the borg command line options appropriate to this command {{{3
        for name, attrs in BORG_SETTINGS.items():
            if strip_archive_matcher and name == "match_archives":
                continue
            if cmd in attrs["cmds"] or "all" in attrs["cmds"]:
                opt = convert_name_to_option(name)
                val = self.value(name)
                if val:
                    if name == "match_archives":
                        borg_opts.extend([f"{opt}={v.strip()!s}" for v in val])
                    elif "arg" in attrs and attrs["arg"]:
                        borg_opts.append(f"{opt}={val!s}")
                    else:
                        borg_opts.append(opt)
        return borg_opts

    # publish_passcode() {{{2
    def publish_passcode(self):
        for v in ['BORG_PASSPHRASE', 'BORG_PASSCOMMAND', 'BORG_PASSPHRASE_FD']:
            if v in os.environ:
                narrate(f"Using existing {v}.")
                return
        if self.encryption == 'none':
            return

        passcommand = self.value('passcommand')
        passcode = self.passphrase

        # process passcomand
        if passcommand:
            if passcode:
                warn("passphrase unneeded.", culprit="passcommand")
            narrate("Setting BORG_PASSCOMMAND.")
            os.environ['BORG_PASSCOMMAND'] = passcommand
            self.borg_passcode_env_var_set_by_assimilate = 'BORG_PASSCOMMAND'
            return

        # get passphrase from avendesora
        if not passcode and self.avendesora_account:
            narrate("running avendesora to access passphrase.")
            try:
                from avendesora import PasswordGenerator

                pw = PasswordGenerator()
                account_spec = self.value("avendesora_account")
                account_spec = ':'.join(account_spec.split())
                passcode = str(pw.get_value(account_spec))
            except ImportError:
                raise Error(
                    "Avendesora is not available",
                    "you must specify passphrase in settings.",
                    sep=", ",
                )
            # no need to catch PasswordError as it is subclass of Error

        if passcode:
            os.environ['BORG_PASSPHRASE'] = passcode
            narrate("Setting BORG_PASSPHRASE.")
            self.borg_passcode_env_var_set_by_assimilate = 'BORG_PASSPHRASE'
            return

        if self.encryption is None:
            self.encryption = "none"
        if self.encryption == "none" or self.encryption.startswith('authenticated'):
            comment("Encryption is disabled.")
            return
        raise Error("Cannot determine the encryption passphrase.")

    # run_user_commands() {{[2
    def run_user_commands(self, setting):
        for i, cmd in enumerate(self.values(setting)):
            narrate(f"staging {setting}[{i}] command.")
            try:
                Run(cmd, "SoEW" if is_str(cmd) else 'soEW')
            except Error as e:
                if is_str(cmd):
                    cmd = cmd.split()
                if 'before' in setting:
                    e.reraise(culprit=(setting, i, cmd[0]))
                elif 'after' in setting:
                    e.report(culprit=(setting, i, cmd[0]))
                else:
                    raise NotImplementedError

        # the following two statements are only useful from run_before_borg
        self.settings[setting] = []  # erase the setting so it is not run again
        self.borg_ran = True  # indicate that before has run so after should run

    # run_borg() {{{2
    def run_borg(
        self,
        cmd,
        args=(),
        borg_opts=None,
        assimilate_opts=None,
        strip_archive_matcher=False,
        show_borg_output=False,
        use_working_dir=False,
    ):
        assimilate_opts = assimilate_opts or {}

        # run the run_before_borg commands
        self.run_user_commands('run_before_borg')

        # prepare the command
        self.publish_passcode()
        if "BORG_PASSPHRASE" in os.environ:
            os.environ["BORG_DISPLAY_PASSPHRASE"] = "no"
        if self.ssh_command:
            os.environ["BORG_RSH"] = self.ssh_command
        environ = {k: v for k, v in os.environ.items() if k.startswith("BORG_")}
        if "BORG_PASSPHRASE" in environ:
            environ["BORG_PASSPHRASE"] = "❬redacted❭"
        executable = to_path(self.value("borg_executable", BORG))
        borg_opts = self.borg_options(
            cmd, borg_opts, assimilate_opts, strip_archive_matcher
        )
        command = [executable] + cmd.split() + borg_opts + list(args)
        narrate("Borg-related environment variables:", render(environ))

        # check if ssh agent is present
        if self.needs_ssh_agent:
            if "SSH_AUTH_SOCK" not in os.environ:
                warn(
                    "SSH_AUTH_SOCK environment variable not found.",
                    "Is ssh-agent running?",
                )

        # run the command
        with cd(self.working_dir if use_working_dir else "."):
            narrate("running in:", cwd())
            if "--json" in command or "--json-lines" in command:
                narrating = False
            else:
                narrating = (
                    show_borg_output
                    or "--verbose" in borg_opts
                    or "--progress" in borg_opts
                    or "--list" in borg_opts
                    or assimilate_opts.get("verbose")
                    or assimilate_opts.get("narrate")
                )
            if narrating:
                modes = "soeW1"
            else:
                modes = "sOEW1"
            narrate(
                "running:\n{}".format(
                    indent(render_command(command, borg_options_arg_count))
                )
            )
            starts_at = arrow.now()
            log("starts at: {!s}".format(starts_at))
            try:
                borg = Run(command, modes=modes, stdin="", env=os.environ, log=False)
            except Error as e:
                self.report_borg_error(e, cmd)
            finally:
                # remove passcode env variables created by assimilate
                if self.borg_passcode_env_var_set_by_assimilate:
                    narrate(f"Unsetting {self.borg_passcode_env_var_set_by_assimilate}.")
                    del os.environ[self.borg_passcode_env_var_set_by_assimilate]
                ends_at = arrow.now()
                log("ends at: {!s}".format(ends_at))
                log("elapsed: {!s}".format(ends_at - starts_at))
        narrate("Borg exit status:", borg.status)
        if borg.status == 1 and borg.stderr:
            warnings = borg.stderr.partition(72*'-')[0]
            warn('warning emitted by Borg:', codicil=warnings)
        if borg.stdout:
            narrate("Borg stdout:")
            narrate(indent(borg.stdout.rstrip()))
        else:
            narrate("Borg stdout: ❬empty❭")
        if borg.stderr:
            narrate("Borg stderr:")
            narrate(indent(borg.stderr.rstrip()))
        else:
            narrate("Borg stderr: ❬empty❭")

        return borg

    # run_borg_raw() {{{2
    def run_borg_raw(self, args):

        # run the run_before_borg commands
        self.run_user_commands('run_before_borg')

        # prepare the command
        self.publish_passcode()
        os.environ["BORG_DISPLAY_PASSPHRASE"] = "no"
        executable = self.value("borg_executable", BORG)
        remote_path = self.value("remote_path")
        remote_path = ["--remote-path", remote_path] if remote_path else []
        repository = str(self.repository)
        command = (
            [executable]
            + remote_path
            + [a.replace('@repo', repository) for a in args]
        )

        # run the command
        narrate(
            "running:\n{}".format(
                indent(render_command(command, borg_options_arg_count))
            )
        )
        with cd(self.working_dir):
            narrate("running in:", cwd())
            starts_at = arrow.now()
            log("starts at: {!s}".format(starts_at))
            try:
                borg = Run(command, modes="soeW1", env=os.environ, log=False)
            except Error as e:
                self.report_borg_error(e, executable)
            ends_at = arrow.now()
            log("ends at: {!s}".format(ends_at))
            log("elapsed: {!s}".format(ends_at - starts_at))
        if borg.status == 1:
            warn('warning emitted by Borg, see logfile for details.')
        if borg.status:
            narrate("Borg exit status:", borg.status)

        return borg

    # report_borg_error() {{{2
    def report_borg_error(self, e, cmd):
        narrate('Borg terminates with exit status:', e.status)
        if e.stdout:
            log('borg stdout:', indent(e.stdout), sep='\n')
        else:
            log('borg stdout: ❬empty❭')
        if e.stderr:
            log('borg stderr:', indent(e.stderr), sep='\n')
        else:
            log('borg stderr: ❬empty❭')
        codicil = None
        if e.stderr:
            if 'previously located at' in e.stderr:
                codicil = dedent(f'''
                    If repository was intentionally relocated, re-run with --relocated:
                        assimilate --relocated {cmd} ...
                ''', strip_nl='b')
            if 'Failed to create/acquire the lock' in e.stderr:
                codicil = dedent('''
                    - If another Assimilate or Borg process is using this repository,
                      please wait for it to finish.
                    - Perhaps you still have an archive mounted?
                      If so, use ‘assimilate umount’ to unmount it.
                    - Perhaps a previous run was killed or terminated with an error?
                      If so, use ‘assimilate break-lock’ to clear the lock.
                ''', strip_nl='b')

            if 'Mountpoint must be a writable directory' in e.stderr:
                codicil = 'Perhaps an archive is already mounted there?'

        e.reraise(culprit=cull((cmd, self.config_name)), codicil=codicil)

    # get_roots() {{{2
    def get_roots(self):
        try:
            # run borg_options('create') to populate settings.roots
            self.borg_options('create', None, {}, False)
            return [str(to_path(self.working_dir, r)) for r in self.roots]
        except Error:
            return []


    # is_config() {{{2
    def is_first_config(self):
        return self.config_name == self.configs[0]

    def is_last_config(self):
        return self.config_name == self.configs[-1]

    # get attribute {{{2
    def __getattr__(self, name):
        return self.settings.get(name)

    # iterate through settings {{{2
    def __iter__(self):
        for key in sorted(self.settings.keys()):
            yield key, self.settings[key]

    # enter {{{2
    def __enter__(self):
        if not self.config_name:
            # this command does not require config
            return self

        self.borg_passcode_env_var_set_by_assimilate = None

        # resolve src directories
        self.src_dirs = self.as_paths("src_dirs", resolve=False)

        # set repository
        repository = self.value("repository")
        if ":" not in repository:
            # is a local repository
            repository = to_path(repository)
            if not repository.is_absolute():
                raise Error(
                    "local repository must be specified using an absolute path.",
                    culprit=repository,
                )
        self.repository = repository

        # default archive if not given
        if "archive" not in self.settings:
            self.settings["archive"] = "{host_name}-{user_name}-{config_name}-{{now}}"
        archive = self.settings["archive"]
        match_archives = archive.replace('{{now}}', '*')
        match_archives = match_archives.replace('{{utcnow}}', '*')
        self.match_local_archives = 'sh:' + match_archives
        if "match_archives" not in self.settings:
            self.settings["match_archives"] = ['sh:' + match_archives]
        for ma in self.settings["match_archives"]:
            prefix, _, identifier = ma.partition(':')
            if not identifier:
                warn(f"match_archives={ma} should have a type prefix.")

        # resolve other files and directories
        data_dir = to_path(DATA_DIR)
        if not data_dir.exists():
            # data dir does not exist, create it
            data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.date_file = data_dir / self.resolve('DATE_FILE', DATE_FILE)
        self.data_dir = data_dir

        # perform locking
        lockfile = self.lockfile = data_dir / self.resolve('LOCK_FILE', LOCK_FILE)
            # This must be outside if statement because of breaklock command.
            # It want to remove lock file even though it does not require exclusivity.

        if self.requires_exclusivity:
            # check for existence of lockfile
            if lockfile.exists():
                report = True
                try:
                    # check to see if the process is still running
                    lock_contents = nt.load(lockfile, dict)
                    pid = lock_contents.get('pid')
                    assert pid > 0
                    os.kill(pid, 0)     # does not actually kill the process
                except ProcessLookupError as e:
                    if e.errno == errno.ESRCH:
                        report = False  # process no longer exists
                except Exception as e:
                    log("garbled lock file:", e)

                if report:
                    raise Error(f"currently running (see {lockfile} for details).")

            # create lockfile
            now = arrow.now()
            pid = os.getpid()
            contents = dict(
                cmdline = ' '.join(sys.argv),
                started = str(now),
                pid = pid
            )
            nt.dump(contents, lockfile)

        # open logfile
        # do this after checking lock so we do not overwrite logfile
        # of assimilate process that is currently running
        self.logfile = data_dir / self.resolve('LOG_FILE', LOG_FILE)
        log_command = self.log_command and not self.assimilate_opts.get("no-log")

        # create composite logfile
        if log_command:
            sect = 3*'{'
            description = self.settings.get('cmd_name')
            if self.run_name:
                description = f"{description} ({self.run_name})"
            kwargs = dict(
                retain_temp = True,
                keep_for = '1w',
                day_header = f'D MMMM YYYY  {sect}1',
                entry_header = f'h:mm A  {sect}2',
                description = description,
                editor = 'vim',
            )
            kwargs.update(self.dict_values('logging'))
            ntlog = NTlog(temp_log_file=self.logfile, **kwargs)
            get_informer().set_logfile(ntlog)

        log("working directory:", self.working_dir)
        return self

    # exit {{{2
    def __exit__(self, exc_type, exc_val, exc_tb):

        # flush stdout
        print(end='', flush=True)

        # delete lockfile
        if self.requires_exclusivity:
            self.lockfile.unlink()

        # run the run_after_borg commands
        if self.borg_ran:
            self.run_user_commands('run_after_borg')

