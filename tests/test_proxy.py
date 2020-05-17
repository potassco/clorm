#------------------------------------------------------------------------------
# Unit tests for the clorm monkey patching
#------------------------------------------------------------------------------
import unittest

from clorm.proxy import ProxyMetaClass, proxy_init

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

class ProxyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_simple_proxy(self):

        class MyClass(object):
            def __init__(self,num): self._num = num
            def inc(self): self._num += 1
            @property
            def num(self): return self._num

        class McProxy(MyClass,metaclass=ProxyMetaClass):
            pass

        # Use the proxy on an existing object
        mcpr=McProxy(proxied_=MyClass(5))
        self.assertEqual(mcpr.num,5)
        mcpr.inc()
        self.assertEqual(mcpr.num,6)

        # Use the proxy to create a new object
        mcpr=McProxy(5)
        self.assertEqual(mcpr.num,5)
        mcpr.inc()
        self.assertEqual(mcpr.num,6)

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_proxy_with_overrides(self):

        class MyClass(object):
            def __init__(self,num): self._num = num
            def inc(self): self._num += 1
            @property
            def num(self): return self._num

        class McProxy(MyClass,metaclass=ProxyMetaClass):
            def __init__(self,*args,**kwargs):
                if "myclass_" in kwargs:
                    if len(args) != 0 and len(kwargs) != 1:
                        raise ValueError(("Invalid initialisation: the 'myclass_' argument "
                                          "cannot be combined with other arguments"))
                    proxy_init(self,proxied_=kwargs["myclass_"])
                else:
                    proxy_init(self,*args,**kwargs)
            @property
            def myclass_(self): return self._proxied

            def inc(self):
                self._proxied.inc()
                self._proxied.inc()

        # Use the proxy on an existing object
        myclass = MyClass(5)
        mcpr=McProxy(myclass_=myclass)
        self.assertEqual(mcpr.myclass_,myclass)
        self.assertEqual(mcpr.num,5)
        mcpr.inc()
        self.assertEqual(mcpr.num,7)

        # Use the proxy to create a new object
        mcpr=McProxy(5)
        self.assertEqual(type(mcpr.myclass_), MyClass)
        self.assertEqual(mcpr.num,5)
        mcpr.inc()
        self.assertEqual(mcpr.num,7)

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_bad_proxy(self):

        class MyClass(object):
            def __init__(self,num): self._num = num
            def inc(self): self._num += 1
            @property
            def num(self): return self._num

        class Other(object):
            def __init__(self):
                self._num2 = 5

        with self.assertRaises(TypeError) as ctx:
            class McProxy(MyClass,Other, metaclass=ProxyMetaClass):
                pass


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
