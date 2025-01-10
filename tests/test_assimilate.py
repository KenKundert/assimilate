# DESCRIPTION {{{1
# This is the generic test code.  The actual tests are held in assimilate.nt, a
# NestedText file that contains both the stimulus and the expected response for
# a wide variety of scenarios.  You can run the tests directly using:
#     pytest
# Or you can run run then along with some other checks in a virtual environment
# using:
#     cd ..; tox

# IMPORTS {{{1
from fnmatch import fnmatch
from functools import partial
from inform import (
    cull, dedent, full_stop, indent, is_collection, is_str, fatal, os_error
)
from parametrize_from_file import parametrize, add_loader
from shlib import Run, cd, to_path, set_prefs as shlib_set_prefs
from voluptuous import Schema, Optional, Required, Any, Invalid
import nestedtext as nt
import arrow
import os
import pytest
import pwd
import socket
import re


# GLOBALS {{{1
TEST_SUITE = to_path('assimilate.nt')
SCRIPT_NAME = 'bu'
SCRIPT = dedent("""
    #!/bin/sh

    export HOME={home_dir}
    export XDG_DATA_HOME={home_dir}/.local/share
    assimilate $*
""", strip_nl='l')
TEST_DIR = to_path(__file__).parent
shlib_set_prefs(use_inform=True)
NAMES_SEEN = {}     # used to enforce that all test names are unique
                    # without this names could be repeated between levels,
                    # which might cause confusion when debugging
DEFAULT_UMASK = 0o77


# PARAMETERIZATION {{{1
# Adapt parametrize_for_file to read dictionary rather than list {{{2
def name_from_dict_keys(cases):
    return [{**v, 'scenario': k} for k,v in cases.items()]
parametrize = partial(parametrize, preprocess=name_from_dict_keys)

# customize the parameterize_from_file test-case loader so that duplicate match
# keys are allowed
def de_dup(key, state):
    keys = state['keys']
    if len(keys) == 6 and keys[2] == 'tests' and keys[4] == 'checks':
        if key not in state:
            state[key] = 1
        state[key] += 1
        return f"{key} #{state[key]}"
    raise KeyError(key)  # do not allow duplicates at the top level

def normalize_key(key, parent_keys):
    num_parents = len(parent_keys)
    if num_parents == 1:
        name, _, desc = key.partition('—')
        return name.strip()
    if num_parents == 3 and parent_keys[2] == 'tests':
        name, _, desc = key.partition('—')
        return name.strip()
    if num_parents == 4 and parent_keys[3] == 'create':
        return key
    if num_parents == 5 and parent_keys[4] == 'checks':
        return key
    return '_'.join(key.lower().split())  # convert key to snake case

def nt_loader(path):
    return nt.load(path, dict, normalize_key=normalize_key, on_dup=de_dup)

add_loader('.nt', nt_loader)

# SCHEMA {{{1
# id_with_desc() {{{2
def id_with_desc(arg):
    # I think this is no longer necessary ad normalize_key() strips the
    # description
    try:
        name, _, desc = arg.partition('—')
        return name.strip()   # discard description
    except AttributeError:
        raise Invalid("expected identifier with an optional description")

# as_str() {{{2
def as_str(arg):
    if is_str(arg):
        return arg
    raise Invalid(
        f"expected string, found {arg.__class__.__name__}."
    )

# as_str_expr() {{{2
def as_str_expr(arg):
    is_str(arg)
    try:
        if arg[0:1] == "!":
            arg = eval(arg[1:])
    except Exception as e:
        raise Invalid(
            f"{e.__class__.__name__}: {e!s}."
        )
    if is_str(arg):
        return arg
    raise Invalid(
        f"expected string, found {arg.__class__.__name__}."
    )

# as_int() {{{2
def as_int(arg):
    try:
        return str(int(arg, base=0))
    except ValueError:
        raise Invalid('expected integer')

# as_lines() {{{2
def as_lines(arg):
    if is_str(arg):
        return arg.splitlines()
    if isinstance(arg, list):
        return arg
    raise Invalid(
        'expected list or string that can be split into a list of lines'
    )


# schema {{{2
create_file_schema = {
    Optional("contents"): as_str_expr,
    Optional("mode"): as_str,
    Optional("mtime"): as_str,
}

checks_schema = {
    Optional("stdout"): {as_str: Any(as_str, [as_str])},
    Optional("stderr"): {as_str: Any(as_str, [as_str])},
    Optional("status"): as_int,
    as_str: {as_str: Any(as_str, [as_str])},   # key is a file path
}

file_ops_schema = Any(
    {
        "create": {as_str: Any(create_file_schema, '')},
        "remove": as_lines,
        "umask": as_int,
    },
    ''  # initialization may be empty
)

test_schema = {
    Optional('initialization'): file_ops_schema,
    Optional("run"): as_str,
    Optional("checks"): checks_schema,
    Optional('termination'): file_ops_schema,
}

scenario_schema = Schema({
    Required('scenario'): id_with_desc,  # this field is promoted to key by above code
    Required('initialization'): file_ops_schema,
            # I would prefer that initialization be optional, but parameterize_from_file
            # requires that all fields be specified at the top level
    Required('tests'): {id_with_desc: test_schema},
})

# UTILITIES {{{1
# expand_macro() {{{2
def expand_macro(macro, run_dir, matches):
    # expand run_dir, replace matches, and convert ⟪ and ⟫ to { and }
    try:
        return macro.format(
            run_dir=run_dir, hostname=hostname, username=username,
            **matches
        ).rstrip().replace('⟪', '{').replace('⟫', '}')
    except KeyError as e:
        raise KeyError(f"{e!s}: needs escaping in:\n{indent(macro)}")
    except ValueError as e:
        raise ValueError(f"{e!s} in:\n{indent(macro)}")

# Checker class {{{2
# Used to determine whether generated file contains expected text.
class Checker:
    def __init__(self, name, cmd, run_dir):
        self.name = name
        self.cmd = cmd
        self.run_dir = run_dir
        self.run_dir_wo_leading_slash = str(run_dir)[1:]
        self.matches = {}
        self.status = None

    def set_realized(self, path, contents):
        self.path = path
        self.contents = contents.rstrip()
        self.lines = contents.splitlines()

    def set_status(self, status):
        self.status = status

    def check(self, match_type, expected, matches):

        # strip off any de-dup marker off key
        match_type, _, _ = match_type.partition(' #')
        if match_type in ['contains_lines', 'contains_lines_in_order', 'excludes_lines']:
            expected = as_lines(expected)

        run_dir = self.run_dir_wo_leading_slash
        if is_str(expected):
            expected = expand_macro(expected, run_dir, matches)
        else:
            assert is_collection(expected)
            expected = (expand_macro(e, run_dir, matches) for e in expected)

        # check the match_type
        if match_type == 'matches_text':
            assert expected == self.contents, self.fail_message(match_type, expected)
        elif match_type == 'contains_line':
            assert expected in self.lines, self.fail_message(match_type, expected)
        elif match_type == 'contains_lines':
            for line in expected:
                assert line in self.lines, self.fail_message(match_type, line)
        elif match_type == 'excludes_lines':
            for line in expected:
                assert line not in self.lines, self.fail_message(match_type, line)
        elif match_type == 'contains_lines_in_order':
            # assure that all expected lines are present and in the right order
            prev_index = -1
            for line in expected:
                lines_remaining = self.lines[prev_index+1:]
                assert line in lines_remaining, self.fail_message(
                    match_type, line, f"line missing from [{prev_index}:..]"
                )
                prev_index = lines_remaining.index(line)
        elif match_type == 'contains_text':
            assert expected in self.contents, self.fail_message(match_type, expected)
        elif match_type == 'matches_regex':
            match = re.match(expected, self.contents, re.M)
            if match:
                self.matches.update(match.groupdict())
            assert match, self.fail_message(match_type, expected)
        elif match_type == 'contains_regex':
            match = re.search(expected, self.contents, re.M)
            if match:
                self.matches.update(match.groupdict())
            assert match, self.fail_message(match_type, expected)
        elif match_type == 'excludes_line':
            assert expected not in self.lines, self.fail_message(match_type, expected)
        elif match_type == 'excludes_text':
            assert expected not in self.contents, self.fail_message(match_type, expected)
        elif match_type == 'excludes_regex':
            assert not re.search(expected, self.contents, re.M), self.fail_message(match_type, expected)
        else:
            raise AssertionError(f'{self.name}: {match_type}: unknown match type.')

    def fail_message(self, match, expected=None, issue=None):

        if match and not issue:
            action, object, *_ = match.split('_')
            if object not in ['line', 'text', 'regex', 'lines']:
                raise AssertionError(f"{self.name}: {match}: unknown object of check.")
            if action not in ['matches', 'contains', 'excludes']:
                raise AssertionError(f"{self.name}: {match}: unknown action of check.")
            if action == 'matches':
                issue = "mismatch."
            elif action == 'contains':
                if object == 'lines':
                    issue = "could not find line."
                else:
                    issue = f"could not find {object}."
            else:
                issue = f"found {object}."

        if expected and '\n' in expected:
            expected = f"expected:\n{indent(expected)}"
        else:
            expected = f"expected: {expected}"

        if '\n' in self.contents:
            realized = f"realized:\n{indent(self.contents)}"
        else:
            realized = f"realized: {self.contents}"

        cmd = f"cmd: {self.cmd}" if self.cmd else None
        status = None if self.status is None else f"exit status: {self.status}"
        source = f"source: {self.path!s}" if self.path else None
        test = f"test: {self.name}" if self.name else None
        directory = f"directory: {self.run_dir!s}" if self.run_dir else None
        match = f"match type: {match}"

        if (
            '\n' in expected and
            'contains' not in match and
            'regex' not in match and
            'in order' not in match
        ):
            new = []
            for e, r in zip(expected.splitlines(), realized.splitlines()):
                okay = '✓' if e == r else '✗'
                new.append(f"{okay}: {e}")
            expected = '\n'.join(new)

        return '\n'.join(cull([
            full_stop(issue),
            test, directory, cmd, status, source, match, expected, realized
        ], remove=None))


# Skip class {{{2
class Skip:
    def __init__(self):
        self.skip_until = None
        try:
            self.run_only = nt.load(TEST_DIR / 'run-only.nt', dict)
            self.skip_until = self.run_only.get('skip_until')
            if self.skip_until:
                if isinstance(self.skip_until, str):
                    self.skip_until = self.skip_until.split('.')
                assert isinstance(self.skip_until, list)
                assert len(self.skip_until) == 4
        except nt.NestedTextError as e:
            e.terminate()
        except FileNotFoundError:
            pass
        except OSError as e:
            fatal(os_error(e))
        self.skipping = bool(self.skip_until)
        self.skip_until_case = None

    def skip_scenario(self, suite, category, scenario):
        # determine if this scenario was selected, and if so extract and save
        # list of cases for use by skip_test().

        if self.skipping:
            if self.skip_until[:3] == [suite, category, scenario]:
                self.skip_until_case = self.skip_until[3]
            else:
                self.cases = ()
                return False

        def get_selected(desired, available):
            for each in available:
                if fnmatch(desired, each):
                     return available[each]
            return {}

        suites = self.run_only.get('cases', {'*': {'*': {'*':'*'}}})
        categories = get_selected(suite, suites)
        scenarios = get_selected(category, categories)
        self.cases = get_selected(scenario, scenarios)
        if is_str(self.cases):
            self.cases = self.cases.split()
        return not bool(self.cases)

    def skip_test(self, test):
        if self.skipping and self.skip_until_case == test:
            self.skipping = False
        if self.skipping:
            return True
        return not any(fnmatch(test, c) for c in self.cases)

    def skip_check(self, path):
        return not fnmatch(path, self.run_only.get('checks', '*'))

to_skip = Skip()


# run_tests() {{{2
def run_tests(suite, category, scenario, initialization, tests, home_dir, subTest):
    if suite not in NAMES_SEEN:
        NAMES_SEEN[suite] = set()
    names_seen = NAMES_SEEN[suite]
    assert scenario not in names_seen, f"{scenario}: duplicate scenario name"
    names_seen.add(scenario)
    matches = {}
    run_dir = str(home_dir)[1:]  # strip leading slash

    full_scenario_name = f"{suite}.{category}.{scenario}"
        # the first two names are generally available from context and so are not needed
    #full_scenario_name = f"{scenario}"

    if to_skip.skip_scenario(suite, category, scenario):
        pytest.skip(f"{scenario} skipped at user request")

    os.environ['HOME'] = str(home_dir)
    os.environ['XDG_DATA_HOME'] = str(home_dir / ".local/share")
    with cd(home_dir):
        add_script(home_dir)
        if initialization:
            try:
                file_ops(initialization)
            except Exception as e:
                raise AssertionError(f"{scenario}: {e!s}") from None

        for test_name, test in tests.items():
            assert test_name not in names_seen, f"{test_name}: duplicate test name"
            names_seen.add(test_name)
            full_test_name = f"{full_scenario_name}.{test_name}"
            abbreviated_test_name = f"{scenario}.{test_name}"
            cmd = test['run']
            if cmd == "BREAK":
                break

            # add test name to command if command is assimilate
            try:
                cmd, args = cmd.split(maxsplit=1)
                if cmd == "assimilate":
                    cmd = f"{cmd} --name={test_name}"
                cmd = f"{cmd} {args}"
            except ValueError:
                pass

            try:
                cmd = expand_macro(cmd, run_dir, matches)
            except (ValueError, KeyError) as e:
                raise AssertionError(f"{full_test_name}: {e.__class__.__name__}: {e!s}") from None
            checker = Checker(full_test_name, cmd, home_dir)

            os.umask(DEFAULT_UMASK)

            initialization = test.get('initialization')
            if initialization:
                file_ops(initialization)

            with subTest(abbreviated_test_name):
                if to_skip.skip_test(test_name):
                    pytest.skip(f"{scenario}.{test_name} ignored at user request")

                response = Run(cmd, 'SOEW*')
                checker.set_status(response.status)

                checks = test.get('checks', {})

                # check default expectations on response
                if 'stderr' not in checks:
                    checker.set_realized('stderr', response.stderr)
                    checker.check('matches_text', '', matches)
                if 'stdout' not in checks:
                    checker.set_realized('stdout', response.stdout)
                    checker.check('matches_text', '', matches)
                if 'status' not in checks:
                    checker.set_realized('status', str(response.status))
                    checker.check('matches_text', '0', matches)

                for path, check in checks.items():
                    path = expand_macro(path, run_dir, matches)
                    try:
                        if path == 'stderr':
                            checker.set_realized(path, response.stderr)
                            for match, expected in check.items():
                                checker.check(match, expected, matches)
                        elif path == 'stdout':
                            checker.set_realized(path, response.stdout)
                            for match, expected in check.items():
                                checker.check(match, expected, matches)
                        elif path == 'status':
                            checker.set_realized(path, str(response.status))
                            checker.check('matches_text', check, matches)
                        else:
                            checker.set_realized(
                                to_path(path).resolve(),
                                to_path(path).read_text()
                            )
                            for match, expected in check.items():
                                checker.check(match, expected, matches)
                    except OSError as e:
                         raise AssertionError(f"{full_test_name}: {os_error(e)}") from None

            termination = test.get('termination')
            if termination:
                file_ops(termination)

            matches.update(checker.matches)

# file_ops() {{{2
def file_ops(operations):
    for type, ops in operations.items():
        if type == 'create':
            for filename, attributes in ops.items():
                if not attributes:
                    attributes = {}
                path = to_path(filename)

                if filename.endswith('/'):
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    contents = attributes.get("contents", "")
                    contents = expand_macro(contents, None, {})
                    path.write_text(contents)

                mode = attributes.get("mode", None)
                if mode:
                    path.chmod(int(mode, base=0))

                mtime = attributes.get("mtime", None)
                if mtime:
                    mtime = arrow.get(mtime)

                if mtime:
                    mod_time = mtime.timestamp()
                    os.utime(path, (mod_time, mod_time))

        elif type == 'remove':
            for filename in ops:
                to_path(filename).unlink()
        elif type == 'run':
            for cmd in ops:
                Run(cmd, 'SoeW')
        elif type == 'umask':
            os.umask(ops)
        else:
            raise NotImplementedError(type)

# add_script() {{{2
def add_script(home_dir):
    path = to_path(home_dir, SCRIPT_NAME)
    path.write_text(SCRIPT.format(home_dir=home_dir))
    path.chmod(0o777)

# gethostname {{{2
def gethostname():
    return socket.gethostname().split(".")[0]
hostname = gethostname()

# getusername {{{2
def getusername():
    return pwd.getpwuid(os.getuid()).pw_name
username = getusername()


# MAIN {{{1
@parametrize(
    path = to_path(TEST_DIR) / TEST_SUITE,
    key = "assimilate",
    schema = scenario_schema,
)
def test_assimilate(subtests, tmp_path, scenario, initialization, tests):
    run_tests(
        TEST_SUITE.stem,
        'assimilate',
            # above argument must match that given as key in decorator
            # if key was not given, it should match the function name
        scenario,
        initialization,
        tests,
        home_dir = tmp_path,
        subTest = subtests.test
    )
