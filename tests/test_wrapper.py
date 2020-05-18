#------------------------------------------------------------------------------
# Unit tests for the clorm monkey patching
#------------------------------------------------------------------------------
import unittest

from clorm.wrapper import WrapperMetaClass, init_wrapper

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

class WrapperTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_simple_wrapper(self):

        class My(object):
            def __init__(self,num): self._num = num
            def inc(self): self._num += 1

            # A getter only
            @property
            def num1(self): return self._num

            # A getter and setter
            @property
            def num2(self): return self._num

            @num2.setter
            def num2(self,x): self._num = x


        class MyWrapper(My,metaclass=WrapperMetaClass):
            pass

        # Despite the specification McWrapper is a subclass of object
        self.assertEqual(len(MyWrapper.__bases__),1)
        self.assertEqual(MyWrapper.__bases__[0],object)

        # Use the wrapper to create a new object
        mypr=MyWrapper(5)
        self.assertEqual(mypr.num1,5)

        # Use the wrapper on an existing object
        my=My(5)
        mypr=MyWrapper(wrapped_=my)
        self.assertEqual(mypr.num1,5)
        mypr.inc()
        self.assertEqual(mypr.num1,6)
        self.assertEqual(mypr.__doc__,my.__doc__)

        # Test that the num2 setter is also wrapped
        mypr.num2 = 2
        self.assertEqual(my.num2,2)
        self.assertEqual(my.num2,mypr.num1)

        # Test that trying to set the getter only num1 fails
        with self.assertRaises(AttributeError) as ctx:
            mypr.num1 = 5

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_wrapper_with_overrides(self):

        class My(object):
            '''My Class'''
            def __init__(self,num): self._num = num
            def inc(self): self._num += 1

            @property
            def num(self): return self._num

            def __str__(self):  return "My({})".format(self._num)

        class MyWrapper(My,metaclass=WrapperMetaClass):
            def __init__(self,*args,**kwargs):
                if "my_" in kwargs:
                    if len(args) != 0 and len(kwargs) != 1:
                        raise ValueError(("Invalid initialisation: the 'my_' argument "
                                          "cannot be combined with other arguments"))
                    init_wrapper(self,wrapped_=kwargs["my_"])
                else:
                    init_wrapper(self,*args,**kwargs)
            @property
            def my_(self): return self._wrapped

            def inc(self):
                self._wrapped.inc()
                self._wrapped.inc()

        # Use the wrapper on an existing object
        my = My(5)
        mypr=MyWrapper(my_=my)
        self.assertEqual(mypr.my_,my)
        self.assertEqual(mypr.num,5)
        mypr.inc()
        self.assertEqual(mypr.num,7)
        self.assertEqual(str(mypr),str(my))
        self.assertEqual(mypr.__doc__,my.__doc__)
        self.assertNotEqual(repr(mypr),repr(my))

        # Use the wrapper to create a new object
        mypr=MyWrapper(5)
        self.assertEqual(type(mypr.my_), My)
        self.assertEqual(mypr.num,5)

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_bad_wrapper(self):

        class MyClass(object):
            def __init__(self,num): self._num = num
            def inc(self): self._num += 1
            @property
            def num(self): return self._num

        class Other(object):
            def __init__(self):
                self._num2 = 5

        with self.assertRaises(TypeError) as ctx:
            class McWrapper(MyClass,Other, metaclass=WrapperMetaClass):
                pass


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
