# Hooks

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
from inform import Error, conjoin, full_stop, is_str, log, os_error, truth, warn
from .configs import add_setting, as_integer, as_string, as_dict, report_setting_error
from voluptuous import Any, Invalid, Schema
import requests

# Schema {{{1
# as_url() {{{2
def as_url(arg):
    as_string(arg)
    from urllib.parse import urlparse
    url = urlparse(arg)
    if url.scheme not in ['http', 'https'] or not url.hostname:
        raise Invalid('invalid url.')
    return arg

# as_action() {{{2
as_action = Any(
    as_string,
    dict(url=as_string, params=as_dict, post=Any(as_string, as_dict))
)

# schema {{{2
schema = {}

# Hooks base class {{{1
class Hooks:
    NAME = "monitoring"

    @classmethod
    def provision_hooks(cls):
        schema = {}

        for subclass in cls.__subclasses__():
            schema[subclass.NAME] = subclass.VALIDATOR

        add_setting(
            name = cls.NAME,
            desc = "services to notify upon backup",
            validator = Schema(schema)
        )

    def __init__(self, settings, dry_run=False):
        self.active_hooks = []
        self.dry_run = dry_run
        for subclass in self.__class__.__subclasses__():
            c = subclass(settings)
            if c.is_active():
                self.active_hooks.append(c)

    def get_settings(self, assimilate_settings):
        monitoring = assimilate_settings.monitoring
        if monitoring:
            return monitoring.get(self.NAME, {})
        return {}

    def report_results(self, borg):
        for hook in self.active_hooks:
            hook.borg = borg

    def __enter__(self):
        if not self.dry_run:
            for hook in self.active_hooks:
                try:
                    hook.signal_start()
                except Error as e:
                    warn(e)
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if not self.dry_run:
            for hook in self.active_hooks:
                try:
                    hook.signal_end(exc_value)
                except Error as e:
                    warn(e)

    def signal_start(self):
        url = self.START_URL.format(url=self.url, uuid=self.uuid)
        log(f'signaling start of backups to {self.NAME}: {url}.')
        try:
            requests.get(url, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise Error(f'{self.NAME} connection error.', codicil=full_stop(e))

    def signal_end(self, exception):
        if exception:
            url = self.FAIL_URL.format(url=self.url, uuid=self.uuid)
            result = 'failure'
        else:
            url = self.SUCCESS_URL.format(url=self.url, uuid=self.uuid)
            result = 'success'
        log(f'signaling {result} of backups to {self.NAME}: {url}.')
        try:
            requests.get(url, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise Error('{self.NAME} connection error.', codicil=full_stop(e))


# Custom class {{{1
class Custom(Hooks):
    NAME = 'custom'
    VALIDATOR = dict(
        id = as_string,
        url = as_url,
        start = as_action,
        success = as_action,
        failure = as_action,
        finish = as_action,
        timeout = as_integer,
    )

    def __init__(self, assimilate_settings):
        settings = self.get_settings(assimilate_settings)
        placeholders = dict(config=assimilate_settings.config_name)
        if 'id' in settings:
            placeholders['id'] = settings['id'].strip()
        try:
            if 'url' in settings:
                placeholders['url'] = settings['url'].format(**placeholders).strip()
        except TypeError as e:
            self.invalid_key('url', e)
        self.placeholders = placeholders
        self.settings = settings
        self.borg = None
        self.timeout = settings.get('timeout')
        if self.timeout:
            try:
                self.timeout = int(self.timeout)
            except ValueError:
                warn("invalid value given for timeout.", culprit=self.timeout)

    def is_active(self):
        return bool(self.settings)

    def invalid_key(self, keys, e):
        # unfortunately TypeErrors must be de-parsed to determine the key
        _, _, key = str(e).partition("'")
        key = key=key[:-1]
        error = 'unknown key: ‘{key}’'
        self.report_error(keys, error)

    def report_error(self, keys, error, codicil=None):
        if is_str(keys):
            keys = (keys,)
        keys = (Hooks.NAME, self.NAME) + keys
        report_setting_error(keys, error, codicil)

    def expand_value(self, keys, placeholders):
        value = self.settings
        for key in keys:
            if key not in value:
                return
            value = value[key]

        def expand_str(keys, value):
            try:
                return value.format(**placeholders)
            except TypeError as e:
                self.invalid_key(keys, e)
            except KeyError as e:
                self.report_error(
                    keys, f"unknown key: {e.args[0]}",
                    f"Choose from {conjoin(placeholders.keys(), conj=' or ')}."
                )

        if is_str(value):
            return expand_str(keys, value)
        else:
            data = {}
            for k, v in value.items():
                data[k] = expand_str(keys + (k,), v)
            return data

    def report(self, name, placeholders):
        if not self.settings:
            return

        reporter = self.settings.get(name)
        if not reporter:
            return

        # process reporter
        method = 'get'
        if is_str(reporter):
            url = self.expand_value((name,), placeholders)
            params = {}
        else:
            url = self.expand_value((name, 'url'), placeholders)
            params = self.expand_value((name, 'params'), placeholders)
            if 'post' in reporter:
                method = 'post'
                data = self.expand_value(
                    (name, 'post'), placeholders
                )

        if not url:
            self.report_error(name, 'missing url.')
        try:
            as_url(url)
        except Invalid:
            self.report_error((), 'invalid url.')

        log(f'signaling {name} of backups to {self.NAME}: {url} via {method}.')
        try:
            if method == 'get':
                requests.get(url, params=params, timeout=self.timeout)
            else:
                requests.post(url, params=params, data=data, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise Error('{self.NAME} connection error.', codicil=full_stop(e))

    def signal_start(self):
        self.report('start', self.placeholders)

    def signal_end(self, exception):
        if exception:
            names = ['failure', 'finish']
        else:
            names = ['success', 'finish']

        placeholders = self.placeholders.copy()
        placeholders['error'] = ''
        placeholders['stderr'] = ''
        placeholders['stdout'] = ''
        if exception:
            if isinstance(exception, OSError):
                placeholders['error'] = os_error(exception)
                placeholders['status'] = "2"
            elif isinstance(exception, KeyboardInterrupt):
                placeholders['error'] = "Killed by user."
                placeholders['status'] = "2"
            else:
                placeholders['error'] = str(exception)
                placeholders['status'] = str(getattr(exception, 'status', 2))
                placeholders['stderr'] = getattr(exception, 'stderr', '')
                placeholders['stdout'] = getattr(exception, 'stdout', '')
        elif self.borg:
            placeholders['status'] = str(self.borg.status)
            placeholders['stderr'] = self.borg.stderr
            placeholders['stdout'] = self.borg.stdout
        else:
            placeholders['status'] = '0'
        placeholders['success'] = truth(placeholders['status'] in '01')

        for name in names:
            self.report(name, placeholders)


# HealthChecks class {{{1
class HealthChecks(Hooks):
    NAME = 'healthchecks.io'
    VALIDATOR = dict(url=as_url, uuid=as_string)
    URL = 'https://hc-ping.com'

    def __init__(self, assimilate_settings):
        settings = self.get_settings(assimilate_settings)
        self.uuid = settings.get('uuid')
        self.url = settings.get('url')
        if not self.url:
            self.url = self.URL
        self.borg = None

    def is_active(self):
        return bool(self.uuid)

    def signal_start(self):
        url = f'{self.url}/{self.uuid}/start'
        log(f'signaling start of backups to {self.NAME}: {url}.')
        try:
            requests.post(url, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise Error('{self.NAME} connection error.', codicil=full_stop(e))

    def signal_end(self, exception):
        if exception:
            result = 'failure'
            if isinstance(exception, OSError):
                status = 1
                payload = os_error(exception)
            else:
                try:
                    status = exception.status
                    payload = exception.stderr
                except AttributeError:
                    status = 1
                    payload = str(exception)
        else:
            result = 'success'
            if self.borg:
                status = self.borg.status
                payload = self.borg.stderr
            else:
                status = 0
                payload = ''

        url = f'{self.url}/{self.uuid}/{status}'
        log(f'signaling {result} of backups to {self.NAME}: {url}.')
        try:
            if payload:
                requests.post(url, data=payload.encode('utf-8'), timeout=self.timeout)
            else:
                requests.post(url, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise Error('{self.NAME} connection error.', codicil=full_stop(e))


# CronHub class {{{1
class CronHub(Hooks):
    NAME = 'cronhub.io'
    VALIDATOR = dict(url=as_url, uuid=as_string)
    START_URL = '{url}/start/{uuid}'
    SUCCESS_URL = '{url}/finish/{uuid}'
    FAIL_URL = '{url}/fail/{uuid}'
    URL = 'https://cronhub.io'

    def __init__(self, assimilate_settings):
        settings = self.get_settings(assimilate_settings)
        self.uuid = settings.get('uuid')
        self.url = settings.get('url')
        if not self.url:
            self.url = self.URL

    def is_active(self):
        return bool(self.uuid)
