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

.. note:: The home of Clorm

   Going forward Clorm will be maintained within the Potassco suite of tools
   (home of Clingo and other ASP tools). The GitHub and Anaconda namespaces have
   been changed accordingly.


