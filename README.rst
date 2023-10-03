|MIT license| |PyPI version fury.io| |PyPI pyversions| |PyPi djversions| |PyPI status| 
|Code Cov| |Test Status|

.. |MIT license| image:: https://img.shields.io/badge/License-MIT-blue.svg
   :target: https://lbesson.mit-license.org/

.. |PyPI version fury.io| image:: https://badge.fury.io/py/learn-python-server.svg
   :target: https://pypi.python.org/pypi/learn-python-server/

.. |PyPI pyversions| image:: https://img.shields.io/pypi/pyversions/learn-python-server.svg
   :target: https://pypi.python.org/pypi/learn-python-server/

.. |PyPI djversions| image:: https://img.shields.io/pypi/djversions/learn-python-server.svg
   :target: https://pypi.org/project/learn-python-server/

.. |PyPI status| image:: https://img.shields.io/pypi/status/learn-python-server.svg
   :target: https://pypi.python.org/pypi/learn-python-server

.. .. |Documentation Status| image:: https://readthedocs.org/projects/learn-python-server/badge/?version=latest
..    :target: http://learn-python-server.readthedocs.io/?badge=latest/

.. |Code Cov| image:: https://codecov.io/gh/bckohan/learn-python-server/branch/main/graph/badge.svg?token=0IZOKN2DYL
   :target: https://codecov.io/gh/bckohan/learn-python-server

.. |Test Status| image:: https://github.com/bckohan/learn-python-server/workflows/test/badge.svg
   :target: https://github.com/bckohan/learn-python-server/actions

.. _Django: https://www.djangoproject.com/
.. _learn-python: https://github.com/bckohan/learn-python
.. _PyPI: https://pypi.python.org/pypi/learn-python-server


Learn Python Server
###################

This is the companion course server to the learn-python_ class. It's built using the Django_ framework
and allows progress and error tracking for student repositories as they work through the course. It can
also be used to automate grading.

Installation
------------

.. code-block:: bash

    pip install learn-python-server


Security Considerations
-----------------------

This server occasionally runs untrusted code. Additional configuration can be done to make sure that
untrusted code is always run in a secure VM - but this is not the default. Only students that are
registered and enrolled will have their repository code run so be careful who you allow to register
and enroll and never run this server next to sensitive assets.

TODO
