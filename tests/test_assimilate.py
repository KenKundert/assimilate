# DESCRIPTION {{{1
# This is the generic test code.  It applies the tests, which are found in
# assimilate.py, to assimilate and compares the response to the expected
# response.

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
import re


# GLOBALS {{{1
TEST_SUITE = to_path('assimilate.nt')
SCRIPT_NAME = 'bu'
SCRIPT = dedent("""
    #!/bin/sh

    export HOME={home_dir}
    export XDG_DATA_HOME={home_dir}/.local/share
    /home/ken/bin/assimilate $*
""", strip_nl='l')
TEST_DIR = to_path(__file__).parent
shlib_set_prefs(use_inform=True)
NAMES_SEEN = {}     # used to enforce that all test names are unique
                    # without this names could be repeated between levels,
                    # which might cause confusion when debugging


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
    raise KeyError  # do not allow duplicates at the top level

def normalize_key(key, parent_keys):
    num_parents = len(parent_keys)
    if num_parents == 1:
        return key
    if num_parents == 3 and parent_keys[2] == 'tests':
        return key
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
    try:
        return arg.split(maxsplit=1)[0]  # discard description
    except AttributeError:
        raise Invalid("expected identifier with an optional description")

# as_str() {{{2
def as_str(arg):
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
    Optional("contents"): str,
    Optional("mode"): str,
    Optional("ctime"): str,
}

checks_schema = {
    Optional("stdout"): {str: Any(str, [str])},
    Optional("stderr"): {str: Any(str, [str])},
    Optional("status"): as_int,
    str: {str: Any(str, [str])},   # key is a file path
}

file_ops_schema = Any(
    {
        "create": {str: Any(create_file_schema, '')},
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

        # expand run_dir and replace matches
        def expand(s):
            try:
                return s.format(run_dir=run_dir, **matches).rstrip()
            except KeyError as e:
                raise KeyError(f"{e!s}: needs escaping in:\n{indent(s)}")

        run_dir = self.run_dir_wo_leading_slash
        if is_str(expected):
            expected = expand(expected)
        else:
            assert is_collection(expected)
            expected = (expand(e) for e in expected)

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
                assert line in self.lines, self.fail_message(match_type, line)
                index = self.lines.index(line)
                assert prev_index < index, self.fail_message(match_type, line, 'line found out of order')
                prev_index = index
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

        if '\n' in expected and 'regex' not in match and 'in order' not in match:
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
            file_ops(initialization)

        for test_name, test in tests.items():
            assert test_name not in names_seen, f"{test_name}: duplicate test name"
            names_seen.add(test_name)
            full_test_name = f"{full_scenario_name}.{test_name}"
            abbreviated_test_name = f"{scenario}.{test_name}"
            cmd = test['run']
            if cmd == "BREAK":
                break
            cmd = cmd.format(run_dir=run_dir, **matches)
            checker = Checker(full_test_name, cmd, home_dir)

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
                    path = path.format(run_dir=run_dir, **matches)
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
                         raise AssertionError(f"{full_test_name}: {os_error(e)}")

            termination = test.get('termination')
            if termination:
                file_ops(termination)

            matches.update(checker.matches)

# file_ops() {{{2
def file_ops(operations):
    for type, ops in operations.items():
        if type == 'create':
            for filename, attributes in ops.items():
                path = to_path(filename)

                if filename.endswith('/'):
                    path.mkdir(parents=True, exist_ok=True)
                    continue

                path.parent.mkdir(parents=True, exist_ok=True)
                contents = attributes.get("contents", "")
                mode = attributes.get("mode", None)
                ctime = attributes.get("ctime", None)
                if ctime:
                    ctime = arrow.get(ctime)
                path.write_text(contents)
                if mode:
                    path.chmod(mode)
                if ctime:
                    create_time = ctime.timestamp()
                    os.utime(path, (create_time, create_time))
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


# MAIN {{{1
@parametrize(
    path = to_path(TEST_DIR) / TEST_SUITE,
    key = "assimilate",
    schema = scenario_schema,
)
def test_assimilate(subtests, tmp_path, scenario, initialization, tests):
    os.umask(0o77)
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
