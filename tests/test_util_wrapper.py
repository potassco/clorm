# ------------------------------------------------------------------------------
# Unit tests for the clorm monkey patching
# ------------------------------------------------------------------------------
import unittest

from clorm.util.wrapper import WrapperMetaClass, init_wrapper, make_class_wrapper

from .support import check_errmsg

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------


class WrapperMetaClassTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    def test_simple_wrapper(self):
        class My(object):
            def __init__(self, num):
                self._num = num

            def inc(self):
                self._num += 1

            # A getter only
            @property
            def num1(self):
                return self._num

            # A getter and setter
            @property
            def num2(self):
                return self._num

            @num2.setter
            def num2(self, x):
                self._num = x

        class MyWrapper(My, metaclass=WrapperMetaClass):
            pass

        # Despite the specification MyWrapper is a subclass of object and not My
        self.assertEqual(len(MyWrapper.__bases__), 1)
        self.assertEqual(MyWrapper.__bases__[0], object)

        # Use the wrapper to create a new object
        mypr = MyWrapper(5)
        self.assertEqual(mypr.num1, 5)

        # Use the wrapper on an existing object
        my = My(5)
        mypr = MyWrapper(wrapped_=my)
        self.assertEqual(mypr.num1, 5)
        mypr.inc()
        self.assertEqual(mypr.num1, 6)
        self.assertEqual(mypr.__doc__, my.__doc__)

        # Test that the num2 setter is also wrapped
        mypr.num2 = 2
        self.assertEqual(my.num2, 2)
        self.assertEqual(my.num2, mypr.num1)

        # Test that trying to set the getter only num1 fails
        with self.assertRaises(AttributeError) as ctx:
            mypr.num1 = 5

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    def test_wrapper_with_overrides(self):
        class My(object):
            """My Class"""

            def __init__(self, num):
                self._num = num

            def inc(self):
                self._num += 1

            @property
            def num(self):
                return self._num

            def __str__(self):
                return "My({})".format(self._num)

        class MyWrapper(My, metaclass=WrapperMetaClass):
            def __init__(self, *args, **kwargs):
                if "my_" in kwargs:
                    if len(args) != 0 and len(kwargs) != 1:
                        raise ValueError("Missing 'my_' argument ")
                    init_wrapper(self, wrapped_=kwargs["my_"])
                else:
                    init_wrapper(self, *args, **kwargs)

            @property
            def my_(self):
                return self._wrapped

            def inc(self):
                self._wrapped.inc()
                self._wrapped.inc()

        # Use the wrapper on an existing object
        my = My(5)
        mypr = MyWrapper(my_=my)
        self.assertEqual(mypr.my_, my)
        self.assertEqual(mypr.num, 5)
        mypr.inc()
        self.assertEqual(mypr.num, 7)
        self.assertEqual(str(mypr), str(my))
        self.assertEqual(mypr.__doc__, my.__doc__)
        self.assertNotEqual(repr(mypr), repr(my))

        # Use the wrapper to create a new object
        mypr = MyWrapper(5)
        self.assertEqual(type(mypr.my_), My)
        self.assertEqual(mypr.num, 5)

    # --------------------------------------------------------------------------
    # Test that we can actually use an object of a different type instead of the
    # officially wrapped type. Allows a form of duck-typing.
    # --------------------------------------------------------------------------
    def test_wrapper_diff_type(self):
        class My1(object):
            def __init__(self, num):
                self._num = num

            def inc(self):
                self._num += 1

            @property
            def num(self):
                return self._num

        class My2(object):
            def __init__(self, num):
                self._num = num

            def inc(self):
                self._num += 2

            @property
            def num(self):
                return self._num + 1

        class MyWrapper(My1, metaclass=WrapperMetaClass):
            pass

        ok1 = My1(5)
        ok2 = My2(5)
        wrapper1 = MyWrapper(wrapped_=ok1)
        wrapper2 = MyWrapper(wrapped_=ok2)

        self.assertEqual(wrapper1.num, 5)
        self.assertEqual(wrapper2.num, 6)
        wrapper1.inc()
        wrapper2.inc()
        self.assertEqual(wrapper1.num, 6)
        self.assertEqual(wrapper2.num, 8)

    # --------------------------------------------------------------------------
    # Test that we can wrap a wrapper.
    # --------------------------------------------------------------------------
    def test_wrapper_of_wrapper(self):
        class My(object):
            def __init__(self, num):
                self._num = num

            def inc(self):
                self._num += 1

            @property
            def num(self):
                return self._num

        class MyWrapper(My, metaclass=WrapperMetaClass):
            def inc(self):
                self._wrapped.inc()
                self._wrapped.inc()

            @property
            def num(self):
                return self._wrapped.num + 1

        my1 = My(5)
        my2 = MyWrapper(wrapped_=my1)
        my3 = MyWrapper(wrapped_=my2)

        self.assertEqual(my1.num, 5)
        self.assertEqual(my2.num, 6)
        self.assertEqual(my3.num, 7)

        # Incrementing the underlying object
        my1.inc()
        self.assertEqual(my1.num, 6)
        self.assertEqual(my2.num, 7)
        self.assertEqual(my3.num, 8)

        # Incrementing the first level wrapper
        my2.inc()
        self.assertEqual(my1.num, 8)
        self.assertEqual(my2.num, 9)
        self.assertEqual(my3.num, 10)

        # Incrementing the second level wrapper
        my3.inc()
        self.assertEqual(my1.num, 12)
        self.assertEqual(my2.num, 13)
        self.assertEqual(my3.num, 14)

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    def test_bad_wrapper(self):
        class MyClass(object):
            def __init__(self, num):
                self._num = num

            def inc(self):
                self._num += 1

            @property
            def num(self):
                return self._num

        class Other(object):
            def __init__(self, num):
                self._num2 = num

        # Multiple inheritence is not allowed
        with self.assertRaises(TypeError) as ctx:

            class MyWrapper(MyClass, Other, metaclass=WrapperMetaClass):
                pass

        check_errmsg("ProxyMetaClass requires exactly one", ctx)

        # Using an object of the wrong class with missing attribute
        with self.assertRaises(AttributeError) as ctx:

            class MyWrapper(MyClass, metaclass=WrapperMetaClass):
                pass

            other = Other(4)
            my = MyWrapper(wrapped_=other)
            my.num
        check_errmsg("'Other' object has no attribute 'num'", ctx)


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------


class WrapperFunctionTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    def test_simple_wrapper(self):
        class My(object):
            def __init__(self, num):
                self._num = num

            def inc(self):
                self._num += 1

            # A getter only
            @property
            def num1(self):
                return self._num

            # A getter and setter
            @property
            def num2(self):
                return self._num

            @num2.setter
            def num2(self, x):
                self._num = x

        class MyWrapperT(object):
            pass

        MyWrapper = make_class_wrapper(My, MyWrapperT)

        # Despite the specification MyWrapper is a subclass of object and not My
        self.assertEqual(len(MyWrapper.__bases__), 1)
        self.assertEqual(MyWrapper.__bases__[0], object)

        # Use the wrapper to create a new object
        mypr = MyWrapper(5)
        self.assertEqual(mypr.num1, 5)

        # Use the wrapper on an existing object
        my = My(5)
        mypr = MyWrapper(wrapped_=my)
        self.assertEqual(mypr.num1, 5)
        mypr.inc()
        self.assertEqual(mypr.num1, 6)
        self.assertEqual(mypr.__doc__, my.__doc__)

        # Test that the num2 setter is also wrapped
        mypr.num2 = 2
        self.assertEqual(my.num2, 2)
        self.assertEqual(my.num2, mypr.num1)

        # Test that trying to set the getter only num1 fails
        with self.assertRaises(AttributeError) as ctx:
            mypr.num1 = 5

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    def test_wrapper_with_overrides(self):
        class My(object):
            """My Class"""

            def __init__(self, num):
                self._num = num

            def inc(self):
                """Inc"""
                self._num += 1

            @property
            def num(self):
                """Num"""
                return self._num

            def __str__(self):
                return "My({})".format(self._num)

        class MyOverride(object):
            def __init__(self, *args, **kwargs):
                if "my_" in kwargs:
                    if len(args) != 0 and len(kwargs) != 1:
                        raise ValueError("Missing 'my_' argument ")
                    init_wrapper(self, wrapped_=kwargs["my_"])
                else:
                    init_wrapper(self, *args, **kwargs)

            @property
            def my_(self):
                return self._wrapped

            def inc(self):
                self._wrapped.inc()
                self._wrapped.inc()

        MyWrapper = make_class_wrapper(My, MyOverride)

        self.assertEqual(MyWrapper.__doc__, My.__doc__)
        self.assertEqual(MyWrapper.num.__doc__, My.num.__doc__)
        self.assertEqual(MyWrapper.inc.__doc__, My.inc.__doc__)
        # Use the wrapper on an existing object
        my = My(5)
        mypr = MyWrapper(my_=my)
        self.assertEqual(mypr.my_, my)
        self.assertEqual(mypr.num, 5)
        mypr.inc()
        self.assertEqual(mypr.num, 7)
        self.assertEqual(str(mypr), str(my))
        self.assertEqual(mypr.__doc__, my.__doc__)
        self.assertNotEqual(repr(mypr), repr(my))

        # Use the wrapper to create a new object
        mypr = MyWrapper(5)
        self.assertEqual(type(mypr.my_), My)
        self.assertEqual(mypr.num, 5)

    # --------------------------------------------------------------------------
    # Test that we can actually use an object of a different type instead of the
    # officially wrapped type. Allows a form of duck-typing.
    # --------------------------------------------------------------------------
    def test_wrapper_diff_type(self):
        class My1(object):
            def __init__(self, num):
                self._num = num

            def inc(self):
                self._num += 1

            @property
            def num(self):
                return self._num

        class My2(object):
            def __init__(self, num):
                self._num = num

            def inc(self):
                self._num += 2

            @property
            def num(self):
                return self._num + 1

        MyWrapper = make_class_wrapper(My1)

        ok1 = My1(5)
        ok2 = My2(5)
        wrapper1 = MyWrapper(wrapped_=ok1)
        wrapper2 = MyWrapper(wrapped_=ok2)

        self.assertEqual(wrapper1.num, 5)
        self.assertEqual(wrapper2.num, 6)
        wrapper1.inc()
        wrapper2.inc()
        self.assertEqual(wrapper1.num, 6)
        self.assertEqual(wrapper2.num, 8)

    # --------------------------------------------------------------------------
    # Test that we can wrap a wrapper.
    # --------------------------------------------------------------------------
    def test_wrapper_of_wrapper(self):
        class My(object):
            def __init__(self, num):
                self._num = num

            def inc(self):
                self._num += 1

            @property
            def num(self):
                return self._num

        class MyOverride(object):
            def inc(self):
                self._wrapped.inc()
                self._wrapped.inc()

            @property
            def num(self):
                return self._wrapped.num + 1

        MyWrapper = make_class_wrapper(My, MyOverride)

        my1 = My(5)
        my2 = MyWrapper(wrapped_=my1)
        my3 = MyWrapper(wrapped_=my2)

        self.assertEqual(my1.num, 5)
        self.assertEqual(my2.num, 6)
        self.assertEqual(my3.num, 7)

        # Incrementing the underlying object
        my1.inc()
        self.assertEqual(my1.num, 6)
        self.assertEqual(my2.num, 7)
        self.assertEqual(my3.num, 8)

        # Incrementing the first level wrapper
        my2.inc()
        self.assertEqual(my1.num, 8)
        self.assertEqual(my2.num, 9)
        self.assertEqual(my3.num, 10)

        # Incrementing the second level wrapper
        my3.inc()
        self.assertEqual(my1.num, 12)
        self.assertEqual(my2.num, 13)
        self.assertEqual(my3.num, 14)

    # --------------------------------------------------------------------------
    #
    # --------------------------------------------------------------------------
    def test_bad_wrapper(self):
        class MyClass(object):
            def __init__(self, num):
                self._num = num

            def inc(self):
                self._num += 1

            @property
            def num(self):
                return self._num

        class Other(object):
            def __init__(self, num):
                self._num2 = num

        # Using an object of the wrong class with missing attribute
        with self.assertRaises(AttributeError) as ctx:
            MyWrapper = make_class_wrapper(MyClass)
            other = Other(4)
            my = MyWrapper(wrapped_=other)
            my.num
        check_errmsg("'Other' object has no attribute 'num'", ctx)


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError("Cannot run modules")
