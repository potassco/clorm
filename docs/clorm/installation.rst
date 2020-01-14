Installation
============

Clorm is an open-source project and can be installed from source. An `Anaconda
<https://en.wikipedia.org/wiki/Anaconda_(Python_distribution)>`_ installation is
provided for convenience.

Anaconda installation
---------------------

The easiest way to install Clorm is with Anaconda. Assuming you have already
installed some variant of Anaconda, first you need to install Clingo:

.. code-block:: bash

    $ conda install -c potassco clingo

Then install Clorm:

.. code-block:: bash

    $ conda install -c potassco clorm

Installing from source
----------------------

The project is hosted on github at https://github.com/potassco/clorm and can
also be installed using git:

.. code-block:: bash

    $ git clone https://github.com/potassco/clorm
    $ cd clorm
    $ python setup.py install

.. note::

   The above installation from source instructions assumes that you have already
   installed a version of Clingo that has been compiled with Python support, as
   well as the Python Clingo module.

   Unfortunately, the pre-compiled Clingo Ubuntu packages from the *apt*
   repository may not work. From what I can tell, even thought the ``clingo``
   executable has been compiled with Python support, the Clingo Python module
   itself is missing from these packages. So you may need to compile and install
   Clingo manually.

   For instructions on compiling and installing Clingo see:
   https://github.com/potassco/clingo/blob/master/INSTALL.md

