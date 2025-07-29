Installation
============

Clorm requires Python 3.9+ and Clingo 5.6+ (as of writing Clingo 5.8.0 is the
latest version). There are many ways to install Clorm. In order of simplicity,
it can be installed using `pip`, `conda`, from the `Potassco PPA
<https://launchpad.net/~potassco>`_ (for Ubuntu users), and finally from source.

Installing from a Python package manager
----------------------------------------

The `pip` package can be installed from PyPI:

.. code-block:: bash

    $ pip install clorm

For `conda` installation, assuming you have already installed some variant of
`Anaconda <https://en.wikipedia.org/wiki/Anaconda_(Python_distribution)>`_,
first you need to install Clingo:

.. code-block:: bash

    $ conda install -c potassco clingo

Then install Clorm:

.. code-block:: bash

    $ conda install -c potassco clorm

Installing from the Potassco PPA
--------------------------------

Ubuntu users can install Clorm (and Clingo) from the `Potassco PPA
<https://launchpad.net/~potassco>`_:

.. code-block:: bash

    $ sudo add-apt-repository ppa:potassco/stable
    $ sudo apt-get update
    $ sudo apt install python3-clorm


.. note::

   Unfortunately, the Clingo Ubuntu packages from the standard Ubuntu repository
   do not work correctly with Python. Even though the ``clingo`` executable has
   been compiled with Python support, the Clingo Python module itself is missing
   from these packages.

Installing from source
----------------------

The project is hosted on github at https://github.com/potassco/clorm and can
also be installed using git:

.. code-block:: bash

    $ git clone https://github.com/potassco/clorm
    $ cd clorm
    $ pip install .        # or `python setup.py install` if you don't have pip

.. note::

   The above instructions for installing from source assumes that you have
   already installed a version of Clingo that has been compiled with Python
   support, as well as the Python Clingo module.

   For instructions on compiling and installing Clingo see:
   https://github.com/potassco/clingo/blob/master/INSTALL.md

