# This site-customize file is used by tox/pytest.
# It activates coverage data collection for the assimilate subprocesses created
# by pytest.
# It inserted into the Python startup process using PYTHONPATH in tox.ini.

import coverage

coverage.process_startup()
