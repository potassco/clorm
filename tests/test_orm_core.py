#------------------------------------------------------------------------------
# Unit tests for Clorm ORM RawField, Predicates and associated functions and
# classes.

# Note: I'm trying to clearly separate tests of the official Clorm API from
# tests of the internal implementation. Tests for the API have names
# "test_api_XXX" while non-API tests are named "test_nonapi_XXX". This is still
# to be completed.
# ------------------------------------------------------------------------------

import inspect
import unittest
import datetime
import operator
import collections
from .support import check_errmsg

from clingo import Control, Number, String, Function, SymbolType

# Official Clorm API imports
from clorm.orm import \
    RawField, IntegerField, StringField, ConstantField, SimpleField,  \
    Predicate, ComplexTerm, refine_field, combine_fields, \
    define_nested_list_field, simple_predicate, path, hashable_path, alias

# Implementation imports
from clorm.orm.core import get_field_definition, PredicatePath


#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

__all__ = [
    'FieldTestCase',
    'PredicateTestCase',
    'PredicatePathTestCase',
    'PredicateInternalUnifyTestCase',
    ]


#------------------------------------------------------------------------------
# Test the RawField class and sub-classes and definining simple sub-classes
#------------------------------------------------------------------------------

class FieldTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    #--------------------------------------------------------------------------
    # Test the Field conversion functions for the primitive fields
    # (StringField/ConstantField/IntegerField) as well as sub-classing
    # --------------------------------------------------------------------------
    def test_api_primtive_field_conversion(self):

        symstr = String("SYM")
        self.assertEqual(type(StringField.cltopy(symstr)), str)
        self.assertEqual(StringField.cltopy(symstr), "SYM")
        self.assertEqual(StringField.pytocl("SYM"), symstr)

        symstr = Function("const")
        self.assertEqual(type(ConstantField.cltopy(symstr)), str)
        self.assertEqual(ConstantField.cltopy(symstr), "const")
        self.assertEqual(ConstantField.pytocl("const"), symstr)

        symstr = Function("const",[],False)
        self.assertEqual(type(ConstantField.cltopy(symstr)), str)
        self.assertEqual(ConstantField.cltopy(symstr), "-const")
        self.assertEqual(ConstantField.pytocl("-const"), symstr)

        symstr = Number(1)
        self.assertEqual(type(IntegerField.cltopy(symstr)), int)
        self.assertEqual(IntegerField.cltopy(symstr), 1)
        self.assertEqual(IntegerField.pytocl(1), symstr)


    #--------------------------------------------------------------------------
    # Test that the simple field unify functions work as expected
    #--------------------------------------------------------------------------
    def test_api_pytocl_and_cltopy_and_unifies(self):
        num1 = 1
        str1 = "string"
        sim1 = "name"
        sim2 = "-name"
        cnum1 = Number(num1)
        cstr1 = String(str1)
        csim1 = Function(sim1)
        csim2 = Function(sim1,[],False)

        self.assertEqual(num1, IntegerField.cltopy(cnum1))
        self.assertEqual(str1, StringField.cltopy(cstr1))
        self.assertEqual(sim1, ConstantField.cltopy(csim1))
        self.assertEqual(sim2, ConstantField.cltopy(csim2))

        self.assertEqual(cnum1, IntegerField.pytocl(num1))
        self.assertEqual(cstr1, StringField.pytocl(str1))
        self.assertEqual(csim1, ConstantField.pytocl(sim1))
        self.assertEqual(csim2, ConstantField.pytocl(sim2))

        self.assertTrue(IntegerField.unifies(cnum1))
        self.assertTrue(StringField.unifies(cstr1))
        self.assertTrue(ConstantField.unifies(csim1))
        self.assertTrue(ConstantField.unifies(csim2))

        self.assertFalse(IntegerField.unifies(csim1))
        self.assertFalse(StringField.unifies(cnum1))
        self.assertFalse(ConstantField.unifies(cstr1))

        fint = IntegerField()
        fstr = StringField()
        fconst = ConstantField()

        self.assertTrue(fint.unifies(cnum1))
        self.assertTrue(fstr.unifies(cstr1))
        self.assertTrue(fconst.unifies(csim1))
        self.assertTrue(fconst.unifies(csim2))

    #--------------------------------------------------------------------------
    # Test user-defined RawField sub-classes as well as raising exceptions for
    # badly defined fields.
    # --------------------------------------------------------------------------
    def test_api_user_defined_subclass(self):

        class DateField(StringField):
            pytocl = lambda dt: dt.strftime("%Y%m%d")
            cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()

        symstr = String("20180101")
        dt = datetime.date(2018,1,1)
        self.assertEqual(DateField.cltopy(symstr), dt)
        self.assertEqual(DateField.pytocl(dt), symstr)

        class PartialField(StringField):
            pytocl = lambda dt: dt.strftime("%Y%m%d")

        dt = datetime.date(2018,1,1)
        self.assertEqual(PartialField.pytocl(dt), symstr)
        with self.assertRaises(NotImplementedError) as ctx:
            symstr = String("20180101")
            dt = datetime.date(2018,1,1)
            self.assertEqual(PartialField.cltopy(symstr), dt)


        with self.assertRaises(TypeError) as ctx:
            class DateField(StringField, StringField):
                pass

    #--------------------------------------------------------------------------
    # When instantiating a field a default value can be given. It can also take
    # a function/functor which will be called when the Field's default property
    # is queried.
    # --------------------------------------------------------------------------
    def test_api_field_defaults(self):
        val=0
        def inc():
            nonlocal val
            val +=1
            return val

        # Note: we can distinguish between having no default value and a default
        # value of None
        fld = RawField()
        self.assertEqual(fld.default, None)
        self.assertFalse(fld.has_default)

        fld = RawField(default=None)
        self.assertEqual(fld.default, None)
        self.assertTrue(fld.has_default)

        fld = IntegerField(default=5)
        self.assertEqual(fld.default, 5)
        self.assertTrue(fld.has_default)

        fld = IntegerField(default=inc)
        self.assertTrue(fld.has_default)
        self.assertEqual(fld.default, 1)
        self.assertEqual(fld.default, 2)

        # Added test for bug fix to distinguish a value that evaluates to False
        # from a None value
        fld = IntegerField(default=0)
        self.assertEqual(fld.default, 0)
        self.assertTrue(fld.has_default)

        # A default can also be specified as a position argument
        fld = IntegerField(0)
        self.assertEqual(fld.default, 0)
        self.assertTrue(fld.has_default)


    #--------------------------------------------------------------------------
    # Test catching invalid instantiation of a filed (such as giving a bad
    # default values for a field).
    # --------------------------------------------------------------------------
    def test_api_catch_bad_field_instantiation(self):
        with self.assertRaises(TypeError) as ctx:
            fld = IntegerField(default="bad")
        check_errmsg("Invalid default value \"bad\" for IntegerField", ctx)

        with self.assertRaises(TypeError) as ctx:
            fld5=IntegerField(unknown=5)
        check_errmsg("Field constructor got an", ctx)

        with self.assertRaises(TypeError) as ctx:
            fld5=IntegerField(unknown1=5,unknown2="f")
        check_errmsg(("Field constructor got unexpected keyword arguments: "
                      "unknown1,unknown2"), ctx)

    #--------------------------------------------------------------------------
    # Test setting the index flag for a field
    #--------------------------------------------------------------------------
    def test_api_field_index(self):
        fint1 = IntegerField()
        fstr1 = StringField()
        fconst1 = ConstantField()
        fint2 = IntegerField(index=True)
        fstr2 = StringField(index=True)
        fconst2 = ConstantField(index=True)

        self.assertFalse(fint1.index)
        self.assertFalse(fstr1.index)
        self.assertFalse(fconst1.index)
        self.assertTrue(fint2.index)
        self.assertTrue(fstr2.index)
        self.assertTrue(fconst2.index)

        # Specify with positional arguments
        f = IntegerField(1,True)
        self.assertTrue(f.index)

    #--------------------------------------------------------------------------
    # Test the SimpleField class that handles all primitive types
    # (Integer, String, Constant).
    # --------------------------------------------------------------------------
    def test_api_simplefield(self):
        symint=Number(10)
        symstr=String("A string")
        symconst=Function("aconst")

        self.assertEqual(SimpleField.cltopy(symint),10)
        self.assertEqual(SimpleField.cltopy(symstr),"A string")
        self.assertEqual(SimpleField.cltopy(symconst),"aconst")

        self.assertEqual(SimpleField.pytocl(10),symint)
        self.assertEqual(SimpleField.pytocl("A string"),symstr)
        self.assertEqual(SimpleField.pytocl("aconst"),symconst)

        self.assertEqual(SimpleField.pytocl("_d"), Function("_d"))
        self.assertEqual(SimpleField.pytocl("a'"), Function("a'"))

        self.assertEqual(SimpleField.pytocl("_"), String("_"))
        self.assertEqual(SimpleField.pytocl("$"), String("$"))

        # Bad inputs to SimpleField that throw exceptions
        symbad1=Function("notaconst",[],positive=False)
        symbad2=Function("notaconst",[String("blah")])

        with self.assertRaises(TypeError) as ctx:
            t=SimpleField.cltopy(symbad1)
        check_errmsg("Not a simple term",ctx)

        with self.assertRaises(TypeError) as ctx:
            t=SimpleField.cltopy(symbad2)
        check_errmsg("Not a simple term",ctx)

        with self.assertRaises(TypeError) as ctx:
            t=SimpleField.pytocl(3.14)
        check_errmsg("No translation to a simple term",ctx)


    #--------------------------------------------------------------------------
    # Test making a restriction of a field using a list of values
    #--------------------------------------------------------------------------
    def test_api_refine_field_by_values(self):
        rf = refine_field

        ABCField = rf("ABCField", ConstantField, ["a","b","c"])

        # Make sure it works
        r_a = Function("a",[])
        r_b = Function("b",[])
        r_c = Function("c",[])
        r_d = Function("d",[])
        r_1 = Number(1)

        # Test the pytocl direction
        self.assertEqual(ABCField.pytocl("a"), r_a)
        self.assertEqual(ABCField.pytocl("b"), r_b)
        self.assertEqual(ABCField.pytocl("c"), r_c)

        # Test the cltopy direction
        self.assertEqual(ABCField.cltopy(r_a), "a")
        self.assertEqual(ABCField.cltopy(r_b), "b")
        self.assertEqual(ABCField.cltopy(r_c), "c")

        self.assertTrue(ABCField.unifies(r_a))
        self.assertTrue(ABCField.unifies(r_b))
        self.assertTrue(ABCField.unifies(r_c))
        self.assertFalse(ABCField.unifies(r_d))
        self.assertFalse(ABCField.unifies(r_1))

        # Test a version with no class name
        ABCField2 = rf(ConstantField, ["a","b","c"])
        self.assertEqual(ABCField2.pytocl("a"), r_a)

        # Some conversions that fail
        with self.assertRaises(TypeError) as ctx:
            v = ABCField.pytocl("d")
        with self.assertRaises(TypeError) as ctx:
            v = ABCField.pytocl(1)
        with self.assertRaises(TypeError) as ctx:
            v = ABCField.cltopy(r_d)
        with self.assertRaises(TypeError) as ctx:
            v = ABCField.cltopy(r_1)

        # Detect bad input parameters to refine_field

        with self.assertRaises(TypeError) as ctx:
            class Something(object):
                def __init__(self): self._a = 1

            fld = rf("fld", Something, ["a","b"])

        with self.assertRaises(TypeError) as ctx:
            fld = rf("fld", "notaclass", ["a","b"])

        with self.assertRaises(TypeError) as ctx:
            fld = rf("fld", IntegerField, ["a"])

        # But only 2 and 3 arguments are valid
        with self.assertRaises(TypeError) as ctx:
            ABCField3 = rf(["a","b","c"])
        with self.assertRaises(TypeError) as ctx:
            ABCField4 = rf("ABCField", ConstantField, ["a","b","c"], 1)


    #--------------------------------------------------------------------------
    # Test making a restriction of a field using a value functor
    #--------------------------------------------------------------------------
    def test_api_refine_field_by_functor(self):
        rf = refine_field

        # A good restriction
        PosIntField = rf("PosIntField", IntegerField, lambda x: x >= 0)

        # Make sure it works
        r_neg1 = Number(-1)
        r_0 = Number(0)
        r_1 = Number(1)
        r_a = Function("a",[])

        # Test the pytocl direction
        self.assertEqual(PosIntField.pytocl(0), r_0)
        self.assertEqual(PosIntField.pytocl(1), r_1)

        with self.assertRaises(TypeError) as ctx:
            v = PosIntField.pytocl("a")

        with self.assertRaises(TypeError) as ctx:
            v = PosIntField.pytocl(-1)

        # Test the cltopy direction
        self.assertEqual(PosIntField.cltopy(r_0), 0)
        self.assertEqual(PosIntField.cltopy(r_1), 1)
        with self.assertRaises(TypeError) as ctx:
            v = PosIntField.cltopy(r_neg1)
        with self.assertRaises(TypeError) as ctx:
            v = PosIntField.cltopy(r_a)

        self.assertTrue(PosIntField.unifies(r_0))
        self.assertTrue(PosIntField.unifies(r_1))
        self.assertFalse(PosIntField.unifies(r_neg1))
        self.assertFalse(PosIntField.unifies(r_a))

    #--------------------------------------------------------------------------
    # Test making a new field that is a combination of other fields
    #--------------------------------------------------------------------------
    def test_api_combine_fields(self):

        # Make sure the basic class is setup
        defn=combine_fields([IntegerField,ConstantField])
        self.assertTrue(issubclass(defn,RawField))
        defn=combine_fields("MixedField", [IntegerField,ConstantField])
        self.assertTrue(issubclass(defn,RawField))
        self.assertEqual(defn.__name__,"MixedField")

        # Test some bad class setup
        with self.assertRaises(TypeError) as ctx:
            defn=combine_fields("a","b",[IntegerField,ConstantField])
        with self.assertRaises(TypeError) as ctx:
            defn=combine_fields("a",[IntegerField])
        with self.assertRaises(TypeError) as ctx:
            defn=combine_fields("a","b")

        # Test the pytocl and cltopy functions for combined Integer-Constant
        MF=combine_fields("MixedField", [IntegerField,ConstantField])

        # Test pytocl
        self.assertEqual(MF.pytocl(10), Number(10))
        self.assertEqual(MF.pytocl("aconst"), Function("aconst"))

        # A bad value
        with self.assertRaises(TypeError) as ctx:
            t=MF.pytocl([])
        check_errmsg("No combined pytocl()",ctx)

        # Test cltopy
        self.assertEqual(MF.cltopy(Number(10)),10)
        self.assertEqual(MF.cltopy(Function("aconst")),"aconst")

        # A bad value
        with self.assertRaises(AttributeError) as ctx:
            t=MF.cltopy([])
        check_errmsg("'list' object has no attribute 'type'",ctx)
        with self.assertRaises(TypeError) as ctx:
            t=MF.cltopy(String("blah"))
        check_errmsg("No combined cltopy()",ctx)
        with self.assertRaises(TypeError) as ctx:
            t=MF.cltopy(Function("blah",[Number(1)]))
        check_errmsg("No combined cltopy()",ctx)

    #--------------------------------------------------------------------------
    # Test some non-api aspects of combine field
    #--------------------------------------------------------------------------
    def test_nonapi_combine_fields(self):

        # If no class name is given then an anonymous name is assigned
        defn=combine_fields([IntegerField,ConstantField])
        self.assertEqual(defn.__name__,"AnonymousCombinedRawField")

    #--------------------------------------------------------------------------
    # Test defining a field that handles python lists/sequences as logic
    # programming nested lists.
    # --------------------------------------------------------------------------
    def test_api_nested_list_field(self):
        INLField = define_nested_list_field("INLField",IntegerField)
        CNLField = define_nested_list_field(ConstantField)

        empty_list = Function("",[])
        inl_1st = Function("",[Number(3),empty_list])
        inl_2nd = Function("",[Number(2),inl_1st])
        inl_3rd = Function("",[Number(1),inl_2nd])

        cnl_1st = Function("",[Function("c"),empty_list])
        cnl_2nd = Function("",[Function("b"),cnl_1st])
        cnl_3rd = Function("",[Function("a"),cnl_2nd])

        # Test pytocl for INLField
        self.assertEqual(INLField.pytocl([]), empty_list)
        self.assertEqual(INLField.pytocl([3]), inl_1st)
        self.assertEqual(INLField.pytocl([2,3]), inl_2nd)
        self.assertEqual(INLField.pytocl([1,2,3]), inl_3rd)

        # Test pytocl for CNLField
        self.assertEqual(CNLField.pytocl([]), empty_list)
        self.assertEqual(CNLField.pytocl(["c"]), cnl_1st)
        self.assertEqual(CNLField.pytocl(["b","c"]), cnl_2nd)
        self.assertEqual(CNLField.pytocl(["a","b","c"]), cnl_3rd)

        # Test cltopy for INLField
        self.assertEqual(INLField.cltopy(empty_list),[])
        self.assertEqual(INLField.cltopy(inl_1st),[3])
        self.assertEqual(INLField.cltopy(inl_2nd),[2,3])
        self.assertEqual(INLField.cltopy(inl_3rd),[1,2,3])

        # Test cltopy for CNLField
        self.assertEqual(CNLField.cltopy(empty_list),[])
        self.assertEqual(CNLField.cltopy(cnl_1st),["c"])
        self.assertEqual(CNLField.cltopy(cnl_2nd),["b","c"])
        self.assertEqual(CNLField.cltopy(cnl_3rd),["a","b","c"])

        # Test some failures
        with self.assertRaises(TypeError) as ctx:
            tmp = CNLField.cltopy(inl_1st)
        check_errmsg("Clingo symbol object '3'",ctx)

        with self.assertRaises(TypeError) as ctx:
            tmp = INLField.pytocl([1,"b",3])
        check_errmsg("an integer is required",ctx)

        with self.assertRaises(TypeError) as ctx:
            tmp = INLField.pytocl(1)
        check_errmsg("'1' is not a collection",ctx)

        # Some badly defined fields
        with self.assertRaises(TypeError) as ctx:
            tmp = define_nested_list_field("FG","FG")
        check_errmsg("'FG' is not a ",ctx)

        # Some badly defined fields
        with self.assertRaises(TypeError) as ctx:
            tmp = define_nested_list_field("FG", IntegerField,ConstantField)
        check_errmsg("define_nested_list_field() missing or invalid",ctx)

#------------------------------------------------------------------------------
# Test definition predicates/complex terms
#------------------------------------------------------------------------------

class PredicateTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    #--------------------------------------------------------------------------
    # Test the get_field_definition function that smartly returns field definitions
    #--------------------------------------------------------------------------
    def test_get_field_definition(self):
        # Simple case of a RawField instance - return the input
        tmp = RawField()
        self.assertEqual(get_field_definition(tmp), tmp)
        tmp = IntegerField()
        self.assertEqual(get_field_definition(tmp), tmp)
        tmp = ConstantField()
        self.assertEqual(get_field_definition(tmp), tmp)

        # A raw field subclass returns an instance of the subclass
        self.assertTrue(isinstance(get_field_definition(RawField), RawField))
        self.assertTrue(isinstance(get_field_definition(StringField), StringField))

        # Throws an erorr on an unrecognised object
        with self.assertRaises(TypeError) as ctx:
            t = get_field_definition("error")

        # Throws an erorr on an unrecognised class object
        with self.assertRaises(TypeError) as ctx:
            t = get_field_definition(int)
        with self.assertRaises(TypeError) as ctx:
            class Blah(object): pass
            t = get_field_definition(Blah)

        # A simple tuple definition
        td = get_field_definition((IntegerField(), ConstantField()))
        self.assertTrue(isinstance(td,RawField))

        # Test the positional and named argument access of result
        clob = Function("",[Number(1),Function("blah")])
        pyresult = td.cltopy(clob)
        self.assertEqual(pyresult[0], 1)
        self.assertEqual(pyresult.arg1, 1)
        self.assertEqual(pyresult[1], "blah")
        self.assertEqual(pyresult.arg2, "blah")

        clresult = td.pytocl((1,"blah"))
        self.assertEqual(clresult, clob)

    #--------------------------------------------------------------------------
    # Test that we can define predicates using the class syntax and test that
    # the getters and setters are connected properly to the predicate classes.
    # --------------------------------------------------------------------------
    def test_simple_predicate_defn(self):

        # A simple unary predicate definition
        class P(Predicate):
            pass
        self.assertEqual(P.meta.arity,0)
        self.assertEqual(P.meta.name, "p")

        # The redicate's meta properly is initialised with the predicate itself
        # as the meta's parent property.
        self.assertEqual(P.meta.parent,P)

        # A simple predicate definition
        class P(Predicate):
            a = IntegerField
            b = ConstantField
        self.assertEqual(P.meta.arity,2)
        self.assertEqual(P.meta.name, "p")

        # A predicate definition is allowed to have an internal class (other
        # than Meta) only if it is a ComplexTerm
        class P(Predicate):
            class Q(ComplexTerm): d = IntegerField
            a = IntegerField
            b = IntegerField
            c = Q.Field

        self.assertEqual(P.meta.arity,3)
        self.assertEqual(P.meta.name, "p")
        self.assertEqual(P.Q.meta.arity,1)
        self.assertEqual(P.Q.meta.name, "q")

        # Test declaration of predicate with an implicit name
        class ImplicitlyNamedPredicate(Predicate):
            aterm = IntegerField()

        inp1 = ImplicitlyNamedPredicate(aterm=2)
        inp2 = Function("implicitlyNamedPredicate",[Number(2)])
        self.assertEqual(inp1.raw, inp2)

        # Test declaration of a unary predicate
        class UnaryPredicate(Predicate):
            class Meta: name = "unary"

        self.assertEqual(UnaryPredicate.meta.parent, UnaryPredicate)

        up1 = UnaryPredicate()
        up2 = Function("unary",[])
        self.assertEqual(up1.raw, up2)

        # Test the class properties; when access from the class and the object.
        self.assertEqual(up1.meta.name, "unary")
        self.assertEqual(UnaryPredicate.meta.name, "unary")
        self.assertEqual(len(up1.meta), 0)
        self.assertEqual(len(UnaryPredicate.meta), 0)

    #--------------------------------------------------------------------------
    # Test where there is a value missing or the parameter name is incorrect
    #--------------------------------------------------------------------------
    def test_bad_predicate_instantiation(self):

        class P(Predicate):
            val = IntegerField()

        # a missing parameter
        with self.assertRaises(TypeError) as ctx:
            p = P()
        check_errmsg("Missing argument for field \"val\"",ctx)

        # an unexpected parameter
        with self.assertRaises(TypeError) as ctx:
            p = P(val=4, val2=1)
#        with self.assertRaises(ValueError) as ctx:

    #--------------------------------------------------------------------------
    # Test that default terms work and that not specifying a value raises
    # an exception
    # --------------------------------------------------------------------------
    def test_predicate_with_default_field(self):

        class P(Predicate):
            first = IntegerField(default=0)

        p = P(first=15)
        raw_p = Function("p",[Number(15)])
        self.assertEqual(p.raw, raw_p)

        p = P()
        raw_p = Function("p",[Number(0)])
        self.assertEqual(p.raw, raw_p)

        # Test a boundary case that someone could create a Field sub-class where
        # None is a legit value and can therefore be set as a default value.
        class DumbField(StringField):
            pytocl = lambda d: "silly" if d  is None else "ok"
            cltopy = lambda s: None if d is "silly" else "ok"
        class Q(Predicate):
            first = DumbField(default=None)

        q = Q()
        raw_q = Function("q",[String("silly")])
        self.assertEqual(q.raw, raw_q)


    #--------------------------------------------------------------------------
    # Test predicates with default fields
    # --------------------------------------------------------------------------
    def test_predicate_with_multi_field(self):

        # Test declaration of predicates with Simple and String terms
        class MultiFieldPredicate(Predicate):
            aterm1 = StringField()
            aterm2 = ConstantField()
            class Meta: name = "mfp"

        mfp1 = MultiFieldPredicate(aterm1="astring", aterm2="asimple")
        mfp2 = Function("mfp", [String("astring"), Function("asimple",[])])
        self.assertEqual(mfp1.raw, mfp2)

        # Test that the appropriate term properties are set up properly
        self.assertEqual(mfp1.aterm1, "astring")
        self.assertEqual(mfp1.aterm2, "asimple")

    #--------------------------------------------------------------------------
    # Test bad predicate definitions
    # --------------------------------------------------------------------------
    def test_bad_predicate_defn(self):

        #---------------------------------------------------------------------
        # Some bad definitions
        #---------------------------------------------------------------------

        # "meta" is a reserved word
        with self.assertRaises(ValueError) as ctx:
            class P(Predicate):
                meta = IntegerField

        # "raw" is a reserved word
        with self.assertRaises(ValueError) as ctx:
            class P(Predicate):
                raw = IntegerField

        # "clone" is a reserved word
        with self.assertRaises(ValueError) as ctx:
            class P(Predicate):
                clone = IntegerField

        # "sign" is a reserved word
        with self.assertRaises(ValueError) as ctx:
            class P(Predicate):
                sign = IntegerField

        # "Field" is a reserved word
        with self.assertRaises(ValueError) as ctx:
            class P(Predicate):
                Field = IntegerField

        # The term name starts with an "_"
        with self.assertRaises(ValueError) as ctx:
            class P(Predicate):
                _a = IntegerField

        #------------------------------------------
        # Test incorrect Meta attributes

        # Empty 'name' is invalid
        with self.assertRaises(ValueError) as ctx:
            class P(Predicate):
                a = IntegerField
                class Meta: name = ""

        # Name and is_tuple=True is invalid
        with self.assertRaises(ValueError) as ctx:
            class P(Predicate):
                a = IntegerField
                class Meta: name = "blah" ;  is_tuple = True

        # is_tuple=True and sign=None
        with self.assertRaises(ValueError) as ctx:
            class P(Predicate):
                a = IntegerField
                class Meta: sign = None ;  is_tuple = True

        # is_tuple=True and sign=False
        with self.assertRaises(ValueError) as ctx:
            class P(Predicate):
                a = IntegerField
                class Meta: sign = False ;  is_tuple = True

        # Can't declare an inner class other than Meta that is not a ComplexTerm
        with self.assertRaises(TypeError) as ctx:
            class P(Predicate):
                a = IntegerField
                class Something: pass

        with self.assertRaises(TypeError) as ctx:
            class Q(ComplexTerm):
                b = IntegerField
            class P(Predicate):
                a = IntegerField
                Z = Q

        # Can't declare a non-field
        with self.assertRaises(TypeError) as ctx:
            class P(Predicate):
                a = IntegerField
                def dfd(self): pass


        with self.assertRaises(TypeError) as ctx:
            class P(Predicate):
                a = IntegerField
                b = "string"

    #--------------------------------------------------------------------------
    # Test fields with a predicate that are specified as indexed
    #--------------------------------------------------------------------------
    def test_predicate_defn_containing_indexed_fields(self):
        class CT(ComplexTerm):
            a = IntegerField
            b = StringField(index=True)
            c = (IntegerField(index=True),ConstantField)
        class P(Predicate):
            d = CT.Field(index=True)
            e = CT.Field()

        # Indexes fields for P are: P.d, P.d.b, P.d.c.arg1, P.e.b, P.e.c.arg1
        indexes = set([hashable_path(p) for p in P.meta.indexes])
        self.assertTrue(len(indexes), 5)
        self.assertTrue(hashable_path(P.d) in indexes)
        self.assertTrue(hashable_path(P.d.b) in indexes)
        self.assertTrue(hashable_path(P.d.c.arg1) in indexes)
        self.assertTrue(hashable_path(P.e.b) in indexes)
        self.assertTrue(hashable_path(P.e.c.arg1) in indexes)
        self.assertFalse(hashable_path(P.e) in indexes)
        self.assertFalse(hashable_path(P.d.a) in indexes)
        self.assertFalse(hashable_path(P.d.c.arg2) in indexes)

    #--------------------------------------------------------------------------
    # Test predicate with nested list field
    # --------------------------------------------------------------------------
    def test_predicate_with_nested_list_field(self):

        # Test declaration of predicates with a nested field
        class F(Predicate):
            a = IntegerField
            b = define_nested_list_field(SimpleField)
            c = IntegerField

        f1 = F(101,[1,"b","G"],202)
        raw_3rd = Function("",[String("G"),Function("")])
        raw_2nd = Function("",[Function("b"),raw_3rd])
        raw_1st = Function("",[Number(1),raw_2nd])
        raw_f1 = Function("f",[Number(101),raw_1st, Number(202)])

        self.assertEqual(f1.raw, raw_f1)
        self.assertEqual(F(raw=raw_f1), f1)

        self.assertEqual(str(F(101,[],202)), """f(101,(),202)""")
        self.assertEqual(str(F(1,[1,2,3,4],2)),
                             """f(1,(1,(2,(3,(4,())))),2)""")
        self.assertEqual(str(F(1,["A","b",3,4],2)),
                             """f(1,("A",(b,(3,(4,())))),2)""")

    #--------------------------------------------------------------------------
    # Test that we can distinguish between user defined and anonymous
    # predicate/complex-terms.
    # --------------------------------------------------------------------------
    def test_anon_nonlogicalsymbol(self):
        class Blah(ComplexTerm):
            a = (IntegerField(), IntegerField())
            b = StringField()

        self.assertFalse(Blah.meta.anonymous)
        self.assertTrue(Blah.a.meta.field.complex.meta.anonymous)

    #--------------------------------------------------------------------------
    # Test that we can distinguish Predicate tuples
    # --------------------------------------------------------------------------
    def test_tuple_nonlogicalsymbol(self):
        class NotTuple(ComplexTerm):
            a = IntegerField()
            b = StringField()

        class Tuple(ComplexTerm):
            a = IntegerField()
            b = StringField()
            class Meta: is_tuple=True

        self.assertFalse(NotTuple.meta.is_tuple)
        self.assertTrue(Tuple.meta.is_tuple)


    #--------------------------------------------------------------------------
    # Test that we can get the arity of a Predicate class; using the arity property
    # and the len function.
    # --------------------------------------------------------------------------
    def test_arity_len_nonlogicalsymbol(self):
        class Tuple(ComplexTerm):
            a = IntegerField()
            b = StringField()
            c = (IntegerField(), ConstantField())

        t = Tuple(a=1,b="asd", c=(1,"dfd"))
        self.assertEqual(len(t), 3)
        self.assertEqual(len(t.meta), 3)
        self.assertEqual(t.meta.arity, 3)
        self.assertEqual(len(Tuple.meta), 3)
        self.assertEqual(Tuple.meta.arity, 3)
        self.assertEqual(len(t.c), 2)
        self.assertEqual(len(Tuple.c.meta.field.complex.meta),2)

    #--------------------------------------------------------------------------
    # Test that we can return access the Predicate class fields using positional
    # arguments as well as iterating over them (for both the class itself as
    # well as an instance).
    # --------------------------------------------------------------------------
    def test_iter_bool_nonlogicalsymbol(self):
        class Empty(ComplexTerm):
            pass

        class Blah(ComplexTerm):
            a = IntegerField()
            b = StringField()
            c = (IntegerField(), ConstantField())

        # Test the Predicate class
        self.assertEqual(Blah.a, Blah[0])
        self.assertEqual(Blah.b, Blah[1])
        self.assertEqual(Blah.c, Blah[2])
        for idx,f in enumerate(Blah.meta):
            self.assertEqual(f,Blah[idx])

        # Test an instance
        b = Blah(a=1,b="asd", c=(1,"dfd"))
        self.assertEqual(b.a, b[0])
        self.assertEqual(b.b, b[1])
        self.assertEqual(b.c, b[2])
        for idx,v in enumerate(b):
            self.assertEqual(v,b[idx])

        self.assertTrue(b)
        e = Empty()
        self.assertFalse(e)


    #--------------------------------------------------------------------------
    # As part of the get_field_definition function to flexibly deal with tuples
    # extend the complex-term Field() pytocol function to handle tuples in the
    # input (with the arity matches).
    # --------------------------------------------------------------------------
    def test_complex_term_field_tuple_pytocl(self):
        class Blah(ComplexTerm):
            a = IntegerField()
            b = StringField()
        class BlahBlah(ComplexTerm):
            a = IntegerField()
            b = Blah.Field()

        BF = Blah.Field
        BBF = BlahBlah.Field
        blah1 = Function("blah",[Number(1),String("a")])
        blahblah1 = Function("blahBlah",[Number(1),blah1])
        self.assertEqual(BF.pytocl((1,"a")), blah1)
        self.assertEqual(BBF.pytocl((1,(1,"a"))), blahblah1)

        # Throws an erorr if its not a tuple or the arity of conversion fails
        with self.assertRaises(TypeError) as ctx:
            v = BF.pytocl([1,"a"])
        with self.assertRaises(TypeError) as ctx:
            v = BF.pytocl(("b","a"))
        with self.assertRaises(ValueError) as ctx:
            v = BF.pytocl(("b",))
        with self.assertRaises(ValueError) as ctx:
            v = BF.pytocl((1,"b","c"))


        class BlahBlah2(ComplexTerm):
            a = IntegerField()
            b = (IntegerField(), StringField())

        class BlahBlah3(ComplexTerm):
            a = IntegerField
            b = (IntegerField, StringField)

        b2_field =  BlahBlah2.meta["b"]
        b2_complex = b2_field.defn.complex
        self.assertTrue(issubclass(type(b2_field.defn), RawField))
        self.assertEqual(len(b2_complex.meta), 2)

        b3_field =  BlahBlah2.meta["b"]
        b3_complex = b3_field.defn.complex
        self.assertTrue(issubclass(type(b3_field.defn), RawField))
        self.assertEqual(len(b3_complex.meta), 2)

        blahblah2_raw = Function("blahBlah2",
                                 [Number(1),Function("",[Number(1),String("b")])])
        blahblah2 = BlahBlah2(a=1, b=b2_complex(1,"b"))
        self.assertEqual(blahblah2.raw, blahblah2_raw)
        blahblah2 = BlahBlah2(a=1, b=(1,"b"))
        self.assertEqual(blahblah2.raw, blahblah2_raw)
        self.assertTrue(isinstance(blahblah2.b, b2_complex))


    #--------------------------------------------------------------------------
    # As part of the get_field_definition function extended the field definition to
    # include a complex class property that returns the complex-term class if
    # the field is based on a complex term or None otherwise.
    # --------------------------------------------------------------------------

    def test_field_complex_class_property(self):
        self.assertEqual(IntegerField.complex, None)
        self.assertEqual(IntegerField().complex, None)

        class Blah(ComplexTerm):
            a = IntegerField()
            b = StringField()

        self.assertEqual(Blah.Field.complex, Blah)

        class BlahBlah(ComplexTerm):
            a = IntegerField()
            b = Blah.Field()

        self.assertEqual(BlahBlah.Field().complex, BlahBlah)

    #--------------------------------------------------------------------------
    # Test the mapping of class names to predicate/complex-term names
    # --------------------------------------------------------------------------
    def test_predicate_default_predicate_names(self):

        # Basic camel-case example
        class MyPred1(Predicate): a = StringField()
        self.assertEqual(MyPred1.meta.name, "myPred1")

        # Complex camel-case example
        class MYpRed1A(Predicate): a = StringField()
        self.assertEqual(MYpRed1A.meta.name, "mypRed1A")

        # Basic snake-case example 1
        class My_Pred1(Predicate): a = StringField()
        self.assertEqual(My_Pred1.meta.name, "my_pred1")

        # Basic snake-case example 2
        class My_Pred_1(Predicate): a = StringField()
        self.assertEqual(My_Pred_1.meta.name, "my_pred_1")

        # Complex snake-case example 1
        class MY_PREd1(Predicate): a = StringField()
        self.assertEqual(MY_PREd1.meta.name, "my_pred1")

        # Complex snake-case example 2
        class MY_PREd_1A(Predicate): a = StringField()
        self.assertEqual(MY_PREd_1A.meta.name, "my_pred_1a")

        # acronym example 1
        class MP1(Predicate): a = StringField()
        self.assertEqual(MP1.meta.name, "mp1")

        # acronym example 1
        class MP1A(Predicate): a = StringField()
        self.assertEqual(MP1A.meta.name, "mp1a")

        # Do nothing
        class myPred1(Predicate): a = StringField()
        self.assertEqual(myPred1.meta.name, "myPred1")

    #--------------------------------------------------------------------------
    # Test that the Predicate meta class only allows a single sub-class derived
    # from Predicate.
    # --------------------------------------------------------------------------
    def test_subclassing_nonlogicalsymbol(self):

        class Ok1(Predicate):
            astr = StringField()

        class Ok2(Predicate):
            aint = IntegerField()

        # Test that you cannot instantiate Predicate
        with self.assertRaises(TypeError) as ctx:
            a = Predicate()

        with self.assertRaises(TypeError):
            class Bad1(Ok1,Ok2):
                pass

        with self.assertRaises(TypeError):
            class Bad2(Ok1,Predicate):
                pass


#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

class PredicateInternalUnifyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


    #--------------------------------------------------------------------------
    # Test that we can define predicates using the class syntax and test that
    # the getters and setters are connected properly to the predicate classes.
    # --------------------------------------------------------------------------
    def test_predicate_init(self):

        class Fact(Predicate):
            anum = IntegerField(default=1)
            astr = StringField()

        func=Function("fact",[Number(1),String("test")])
        f1=Fact(astr="test")
        f2=Fact(1,"test")

        self.assertEqual(Fact.meta.parent, Fact)
        self.assertEqual(f1, f2)
        self.assertEqual(f1.raw, func)

        with self.assertRaises(ValueError) as ctx:
            func2=Function("fact",[String("1"),String("test")])
            f=Fact(raw=func2)

    # --------------------------------------------------------------------------
    # Test the RawField.unifies() function
    # --------------------------------------------------------------------------

    def test_rawfield_unifies(self):

        class Fact(Predicate):
            astr = StringField()

        good=Function("fact",[String("astring")])
        bad=Function("fact",[Number(1)])

        self.assertTrue(RawField.unifies(good))
        self.assertTrue(ConstantField.unifies(Function("fact",[])))
        self.assertFalse(ConstantField.unifies(String("fact")))
        self.assertTrue(Fact.Field.unifies(good))
        self.assertFalse(Fact.Field.unifies(bad))


    #--------------------------------------------------------------------------
    # Test that we can define predicates and initialise negative literals.
    # --------------------------------------------------------------------------
    def test_predicate_init_neg_literals_simple(self):

        class F(Predicate):
            a = IntegerField

        # Test the different ways of initialising the literals
        func=Function("f",[Number(1)])
        f=F(1)
        f_alt1=F(1,sign=True)
        f_alt2=F(a=1,sign=True)
        self.assertEqual(func, f.raw)
        self.assertEqual(func, f_alt1.raw)
        self.assertEqual(func, f_alt2.raw)

        neg_func=Function("f",[Number(1)],False)
        neg_f=F(1,sign=False)
        neg_f_alt1=F(a=1,sign=False)
        neg_f_alt2=F(raw=neg_func)
        self.assertEqual(neg_func, neg_f.raw)
        self.assertEqual(neg_func, neg_f_alt1.raw)
        self.assertEqual(neg_func, neg_f_alt2.raw)

        self.assertFalse(f == neg_f)

        # Test that the sign property works correctly
        self.assertTrue(func.positive)
        self.assertTrue(f.sign)
        self.assertFalse(neg_func.positive)
        self.assertFalse(neg_f.sign)

        # Clone with negating the sign
        neg_f2 = f.clone(sign=False)
        self.assertEqual(neg_f, neg_f2)

        neg_f2 = f.clone(sign=not f.sign)
        self.assertEqual(neg_f, neg_f2)

    #--------------------------------------------------------------------------
    # Test that we can define predicates which only allow for specifically
    # signed instances.
    # --------------------------------------------------------------------------
    def test_predicate_init_neg_literals_signed_predicates(self):

        # F1 can handle both positive and negative
        class F1(Predicate):
            a = IntegerField
            class Meta:
                name="f"
                sign=None

        # F2 can only handle positive
        class F2(Predicate):
            a = IntegerField
            class Meta:
                name="f"
                sign=True

        # F3 can only handle negative
        class F3(Predicate):
            a = IntegerField
            class Meta:
                name="f"
                sign=False

        class G(Predicate):
            a = IntegerField
            b = IntegerField
            class Meta: is_tuple = True

        self.assertEqual(F1.meta.sign, None)
        self.assertEqual(F2.meta.sign, True)
        self.assertEqual(F3.meta.sign, False)

        # Tuple can only unify with positive literals
        self.assertEqual(G.meta.sign, True)

        # Test that how we initialise the different Predicate versions
        pos_raw=Function("f",[Number(1)])
        neg_raw=Function("f",[Number(1)],False)

        # F1 handles all
        pos_f1=F1(1,sign=True) ; neg_f1=F1(1,sign=False)
        pos_f1_alt=F1(raw=pos_raw) ; neg_f1_alt=F1(raw=neg_raw)
        self.assertEqual(pos_f1,pos_f1_alt)
        self.assertEqual(neg_f1,neg_f1_alt)
        self.assertEqual(pos_f1.clone(sign=False).raw, neg_f1.raw)

        # F2 handles positive only
        pos_f1=F2(1,sign=True) ;
        pos_f1_alt=F2(raw=pos_raw) ;
        self.assertEqual(pos_f1,pos_f1_alt)

        with self.assertRaises(ValueError) as ctx:
            neg_f1=F2(a=1,sign=False)
        with self.assertRaises(ValueError) as ctx:
            neg_f1=F2(1,sign=False)
        with self.assertRaises(ValueError) as ctx:
            neg_f1=F2(raw=neg_raw)

        with self.assertRaises(ValueError) as ctx:
            neg_tuple_g = G(1,2,sign=False)

        g1 = G(1,2)
        self.assertEqual(g1.raw, Function("",[Number(1),Number(2)]))
        with self.assertRaises(ValueError) as ctx:
            neg_g1 = g1.clone(sign=False)

        # F3 handles negative only
        neg_f1=F3(1,sign=False) ;
        neg_f1_alt=F3(raw=neg_raw) ;
        self.assertEqual(neg_f1,neg_f1_alt)

        with self.assertRaises(ValueError) as ctx:
            pos_f1=F3(a=1,sign=True)
        with self.assertRaises(ValueError) as ctx:
            pos_f1=F3(1,sign=True)
        with self.assertRaises(ValueError) as ctx:
            pos_f1=F3(raw=pos_raw)

    #--------------------------------------------------------------------------
    # Test predicate equality
    # --------------------------------------------------------------------------
    def test_predicate_comparison_operator_overload_signed(self):
        class P(Predicate):
            a = IntegerField
        class Q(Predicate):
            a = IntegerField

        p1 = P(1) ; neg_p1=P(1,sign=False) ; p2 = P(2) ; neg_p2=P(2,sign=False)
        q1 = Q(1)

        self.assertTrue(neg_p1 < neg_p2)
        self.assertTrue(neg_p1 < p1)
        self.assertTrue(neg_p1 < p2)
        self.assertTrue(neg_p2 < p1)
        self.assertTrue(neg_p2 < p2)
        self.assertTrue(p1 < p2)

        self.assertTrue(p2 > p1)
        self.assertTrue(p2 > neg_p2)
        self.assertTrue(p2 > neg_p1)
        self.assertTrue(p1 > neg_p2)
        self.assertTrue(p1 > neg_p1)
        self.assertTrue(neg_p2 > neg_p1)

        # Different predicate sub-classes are incomparable
#        with self.assertRaises(TypeError) as ctx:
#            self.assertTrue(p1 < q1)

    #--------------------------------------------------------------------------
    # Test a simple predicate with a field that has a function default
    # --------------------------------------------------------------------------
    def test_predicate_with_function_default(self):
        val=0
        def inc():
            nonlocal val
            val +=1
            return val

        class Fact(Predicate):
            anum = IntegerField(default=inc)
            astr = StringField()

        func=Function("fact",[Number(1),String("test")])
        f1=Fact(1,"test")
        f2=Fact(astr="test")        # uses the default
        f3=Fact(astr="test")        # second use of the default
        f4=Fact(astr="test")        # third use of the default

        self.assertEqual(f2.anum, 1)
        self.assertEqual(f3.anum, 2)
        self.assertEqual(f4.anum, 3)
        self.assertEqual(f1, f2)
        self.assertEqual(f1.raw, func)

    #--------------------------------------------------------------------------
    # Test that we can initialise using positional arguments
    # --------------------------------------------------------------------------
    def test_predicate_init_positional(self):

        class Fact(Predicate):
            anum = IntegerField(default=1)
            astr = StringField()

        func=Function("fact",[Number(1),String("test")])
        f1=Fact(1, "test")

        self.assertEqual(f1.raw, func)

        # Test trying to initialise with the wrong number of arguments - note
        # cannot use default values when initialising with positional arguments.
        with self.assertRaises(ValueError) as ctx:
            f4=Fact(1,"test",2)

        with self.assertRaises(ValueError) as ctx:
            f2=Fact(1)

        with self.assertRaises(ValueError) as ctx:
            f3=Fact("test")

    #--------------------------------------------------------------------------
    # Test that we can initialise using keyword arguments
    # --------------------------------------------------------------------------
    def test_predicate_init_named(self):

        class F(Predicate):
            a = IntegerField
            b = ConstantField(default="foo")

        # Initialise with named arguments
        f=F(a=1,b="bar")
        self.assertEqual(f.a,1)
        self.assertEqual(f.b,"bar")
        self.assertTrue(f.sign)

        f=F(a=1,b="bar",sign=False)
        self.assertEqual(f.a,1)
        self.assertEqual(f.b,"bar")
        self.assertFalse(f.sign)

        # Initialise with named arguments and default
        f=F(a=1)
        self.assertEqual(f.a,1)
        self.assertEqual(f.b,"foo")
        self.assertTrue(f.sign)

        f=F(a=1,sign=False)
        self.assertEqual(f.a,1)
        self.assertEqual(f.b,"foo")
        self.assertFalse(f.sign)

        # Initialise with wrong arguments
        with self.assertRaises(TypeError) as ctx:
            f=F(a=1,b="bar",c=3)
        with self.assertRaises(TypeError) as ctx:
            f=F(a=1,c=3)

    #--------------------------------------------------------------------------
    # Test that we can predicate fields using positional arguments
    # --------------------------------------------------------------------------
    def test_predicate_positional_access(self):

        class Fact(Predicate):
            anum = IntegerField(default=1)
            astr = StringField()

        func=Function("fact",[Number(1),String("test")])
        f1=Fact(1, "test")

        self.assertEqual(f1[0], 1)
        self.assertEqual(f1[1], "test")

        with self.assertRaises(IndexError) as ctx:
            a = f1[2]

    #--------------------------------------------------------------------------
    # Test that we can iterate over the predicate field values
    # --------------------------------------------------------------------------
    def test_predicate_iterable(self):

        class Fact(Predicate):
            a1 = IntegerField
            a2 = IntegerField
            a3 = IntegerField

        f=Fact(1,2,3)
        self.assertTrue(isinstance(f,collections.Iterable))
        self.assertEqual(list(f), [1,2,3])


    #--------------------------------------------------------------------------
    # Test that we can define predicates with Function and Tuple terms
    # --------------------------------------------------------------------------
    def test_complex_predicate_defn(self):

        class FloatApproxField(IntegerField):
            pytocl = lambda x: int(x*100)
            cltopy = outfunc=lambda x: x/100.0

        class Fun(ComplexTerm):
            aint = FloatApproxField()
            astr = StringField()

        class MyTuple(ComplexTerm):
            aint = IntegerField()
            astr = StringField()
            class Meta: is_tuple = True

        # Check the automatically generated term definition class
        mtd = MyTuple.Field
        self.assertTrue(inspect.isclass(mtd))
        self.assertEqual(mtd.__name__, "MyTupleField")

        # Alternative fact definition
        class Fact(Predicate):
            aint = IntegerField()
            # note: don't need to specify defn keyword
            atup = MyTuple.Field(default=MyTuple(aint=2,astr="str"))
            afunc = Fun.Field(default=Fun(aint=2.0,astr="str"))
#            atup = ComplexField(MyTuple,default=MyTuple(aint=2,astr="str"))
#            afunc = ComplexField(defn=Fun,default=Fun(aint=2.0,astr="str"))

        af1=Fact(aint=1)
        af2=Fact(aint=2, atup=MyTuple(aint=4,astr="XXX"),
                 afunc=Fun(aint=5.5,astr="YYY"))

        f1 = Function("fact",[Number(1),
                              Function("",[Number(2),String("str")]),
                              Function("fun",[Number(200),String("str")])])
        f2 = Function("fact",[Number(2),
                              Function("",[Number(4),String("XXX")]),
                              Function("fun",[Number(550),String("YYY")])])

        self.assertEqual(f1, af1.raw)
        self.assertEqual(f2, af2.raw)
        self.assertEqual(af2.atup.aint,4)


    #--------------------------------------------------------------------------
    # Test the simple_predicate function as a mechanism for defining
    # predicates
    # --------------------------------------------------------------------------
    def test_simple_predicate_function(self):
        class Pred2(Predicate):
            astr = StringField()
            anum = IntegerField()
            class Meta: name="predicate"
        class Pred3(Predicate):
            astr = StringField()
            anum = IntegerField()
            aconst = ConstantField()
            class Meta: name="predicate"
        class Bad3(Predicate):
            astr = StringField()
            anum = IntegerField()
            aconst = ConstantField()
            class Meta: name="bad"

        p2 = Pred2("string1",10)
        p3 = Pred3("string1",10,"constant")
        b3 = Bad3("string1",10,"constant")

        # Define an anonymous predicate
        AnonPred3 = simple_predicate("predicate",3)

        # Should unify
        ap3 = AnonPred3(raw=p3.raw)
        self.assertEqual(ap3.raw, p3.raw)
        self.assertEqual(ap3.arg1, String("string1"))
        self.assertEqual(ap3[0], String("string1"))
        self.assertEqual(ap3.arg2, Number(10))
        self.assertEqual(ap3[1], Number(10))

        # Mismatched arity so unify will fail
        with self.assertRaises(ValueError) as ctx:
            fail1 = AnonPred3(raw=p2.raw)
        # Mismatched predicate name so unify will fail
        with self.assertRaises(ValueError) as ctx:
            fail2 = AnonPred3(raw=b3.raw)


        # Define predicate with a class name
        AnonPred4 = simple_predicate("AnonPred4", "predicate",3)

        # Should unify
        ap4 = AnonPred4(raw=p3.raw)
        self.assertEqual(ap4.raw, p3.raw)

    #--------------------------------------------------------------------------
    # Test the clone operator
    # --------------------------------------------------------------------------
    def test_clone(self):
        class Fact(Predicate):
            anum = IntegerField()
            astr = StringField()

        f1 = Fact(anum=1,astr="astr")
        f2 = f1.clone(anum=2)

        self.assertNotEqual(f1,f2)
        self.assertEqual(f1.astr, f2.astr)
        self.assertEqual(f1.anum, 1)
        self.assertEqual(f2.anum, 2)

        with self.assertRaises(ValueError) as ctx:
            f3 = f1.clone(anum=3,anot=4)

    #--------------------------------------------------------------------------
    # Test accessing values by index
    # --------------------------------------------------------------------------
    def test_predicate_value_by_index(self):
        class Fact(Predicate):
            anum = IntegerField()
            astr = StringField()

        f = Fact(1,"fun")
        self.assertEqual(f.anum, 1)
        self.assertEqual(f[0], 1)
#        f[0]=2
#        self.assertEqual(f.anum, 2)

        (anum,astr) = f
#        self.assertEqual(anum, 2)
        self.assertEqual(astr, "fun")

#        with self.assertRaises(IndexError) as ctx: f[3] = 4
#        with self.assertRaises(TypeError) as ctx: f['bob'] = 4

    #--------------------------------------------------------------------------
    # Test predicate equality
    # --------------------------------------------------------------------------
    def test_predicate_comparison_operator_overloads(self):

        f1 = Function("fact", [Number(1)])
        f2 = Function("fact", [Number(2)])

        class Fact(Predicate):
            anum = IntegerField()

        af1 = Fact(anum=1)
        af2 = Fact(anum=2)
        af1_c = Fact(anum=1)

        self.assertEqual(f1, af1.raw)
        self.assertEqual(af1, af1_c)
        self.assertNotEqual(af1, af2)
        self.assertEqual(str(f1), str(af1))

        # comparing predicates of different types or to a raw should return
        # false even if the underlying raw symbol is identical
        class Fact2(Predicate):
            anum = IntegerField()
            class Meta: name = "fact"
        ag1 = Fact2(anum=1)

        self.assertEqual(f1, af1.raw)
        self.assertEqual(af1.raw, f1)
        self.assertEqual(af1.raw, ag1.raw)
        self.assertNotEqual(af1, ag1)
        self.assertNotEqual(af1, f1)
        self.assertNotEqual(f1, af1)

        self.assertTrue(af1 <  af2)
        self.assertTrue(af1 <=  af2)
        self.assertTrue(af2 >  af1)
        self.assertTrue(af2 >=  af1)

        # clingo.Symbol currently does not implement NotImplemented for
        # comparison between Symbol and some unknown type so the following
        # assertions will fail. This may change in later versions of clingo
        # (maybe 5.3.2 ?).
        test_clingo_symbol_comparison = False
        if test_clingo_symbol_comparison:
            self.assertEqual(af1, f1)
            self.assertEqual(f1, af1)
            self.assertTrue(f2 >  af1)
            self.assertTrue(af1 <  f2)
            self.assertTrue(af1 <=  f2)
            self.assertTrue(f2 >=  af1)

    #--------------------------------------------------------------------------
    # Test predicate equality
    # --------------------------------------------------------------------------
    def test_comparison_operator_overloads_complex(self):

        class SwapField(IntegerField):
            pytocl = lambda x: 100 - x
            cltopy = lambda x: 100 - x

        class AComplex(ComplexTerm):
            swap=SwapField()
            norm=IntegerField()

        f1 = AComplex(swap=99,norm=1)
        f2 = AComplex(swap=98,norm=2)
        f3 = AComplex(swap=97,norm=3)
        f4 = AComplex(swap=97,norm=3)

        rf1 = f1.raw
        rf2 = f2.raw
        rf3 = f3.raw
        for rf in [rf1,rf2,rf3]:
            self.assertEqual(rf.arguments[0],rf.arguments[1])

        # Test the the comparison operator for the complex term is using the
        # swapped values so that the comparison is opposite to what the raw
        # field says.
        self.assertTrue(rf1 < rf2)
        self.assertTrue(rf2 < rf3)
        self.assertTrue(f1 > f2)
        self.assertTrue(f2 > f3)
        self.assertTrue(f2 < f1)
        self.assertTrue(f3 < f2)
        self.assertEqual(f3,f4)
    #--------------------------------------------------------------------------
    # Test unifying a symbol with a predicate
    # --------------------------------------------------------------------------
    def test_unifying_symbol_and_predicate(self):
        class Fact(Predicate):
            anum = IntegerField()
            astr = StringField()
            asim = ConstantField()

        gfact1_sym = Function("fact",[Number(1),String("Dave"),Function("ok",[])])
        gfact1_pred = Fact._unify(gfact1_sym)
        self.assertEqual(gfact1_pred.anum, 1)
        self.assertEqual(gfact1_pred.astr, "Dave")
        self.assertEqual(gfact1_pred.asim, "ok")

        bfact1_sym = Function("fact",[String("1"),String("Dave"),Function("ok",[])])
        with self.assertRaises(ValueError) as ctx:
            bfact1_pred = Fact._unify(bfact1_sym)

    #--------------------------------------------------------------------------
    # Test unifying a symbol with a predicate
    # --------------------------------------------------------------------------
    def test_unifying_symbol_and_complex_predicate(self):

        class Fact(Predicate):
            class Fun(ComplexTerm):
                aint=IntegerField()
                astr=StringField()

#            afun = ComplexField(defn=Fun)
            afun = Fun.Field()

        good_fact_symbol1 = Function("fact",[Function("fun",[Number(1),String("Dave")])])
        good_fact_symbol2 = Function("fact",[Function("fun",[Number(3),String("Dave")])])
        good_fact_symbol3 = Function("fact",[Function("fun",[Number(4),String("Bob")])])
        good_fact_pred1 = Fact._unify(good_fact_symbol1)
        self.assertEqual(good_fact_pred1.afun, Fact.Fun(1,"Dave"))

        bad_fact_symbol1 = Function("fact",[Function("fun",[Number(1)])])
        with self.assertRaises(ValueError) as ctx:
            bad_fact_pred1 = Fact._unify(bad_fact_symbol1)

        # A field value can only be set at construction
        with self.assertRaises(AttributeError) as ctx:
            good_fact_pred1.afun.aint = 3




#------------------------------------------------------------------------------
# Test the PredicatePath class and supporting classes/functions
#------------------------------------------------------------------------------

class PredicatePathTestCase(unittest.TestCase):
    def setUp(self):
        class F(ComplexTerm):
            a = IntegerField

        class G(ComplexTerm):
            a = StringField
            b = ConstantField
            class Meta: is_tuple = True

        class H(Predicate):
            a = IntegerField
            b = F.Field
            c = G.Field

        self.F = F
        self.G = G
        self.H = H

    #-----------------------------------------------------------------------------
    # Test that there is an appropriate PredicatePath associated with each
    # Predicate and that it has the appropriate attributes.
    # -----------------------------------------------------------------------------
    def test_path_class(self):

        F = self.F
        G = self.G
        H = self.H
        FPP = F.meta.path_class
        GPP = G.meta.path_class
        HPP = H.meta.path_class

        # Check that all the appropriate attributes are defined
        self.assertTrue('a' in FPP.__dict__)
        self.assertTrue('sign' in FPP.__dict__)

        self.assertTrue('a' in GPP.__dict__)
        self.assertTrue('b' in GPP.__dict__)
        self.assertTrue('sign' not in GPP.__dict__)

        self.assertTrue('a' in HPP.__dict__)
        self.assertTrue('b' in HPP.__dict__)
        self.assertTrue('c' in HPP.__dict__)
        self.assertTrue('sign' in HPP.__dict__)

    def test_path_instance(self):

        F = self.F
        G = self.G
        H = self.H
        fpath = F.meta.path
        gpath = G.meta.path
        hpath = H.meta.path

        self.assertTrue(fpath.meta.is_root)
        self.assertTrue(gpath.meta.is_root)
        self.assertTrue(gpath.meta.is_root)

        # The path is associated with a predicate
        self.assertEqual(fpath.meta.predicate,F)
        self.assertEqual(gpath.meta.predicate,G)
        self.assertEqual(hpath.meta.predicate,H)

        # Make sure that sub-paths determined by attribute matches to the
        # indexed sub-paths. Note: we can't directly compare two paths because
        # of the overloaded comparison operators. However, since paths should
        # always reference the same object we can use object identity.
        self.assertTrue(fpath.a is fpath[0])
        self.assertTrue(gpath.a is gpath[0])
        self.assertTrue(gpath.b is gpath[1])
        self.assertTrue(hpath.a is hpath[0])
        self.assertTrue(hpath.b is hpath[1])
        self.assertTrue(hpath.c is hpath[2])
        self.assertTrue(hpath.b.a is hpath[1][0])
        self.assertTrue(hpath.b.sign is hpath[1].sign)
        self.assertTrue(hpath.c.a is hpath[2][0])
        self.assertTrue(hpath.c.b is hpath[2][1])

        # Test the intuitive syntax (ie., acccess the path through the
        # Predicate class).
        self.assertTrue(fpath is path(F))
        self.assertTrue(gpath is path(G))
        self.assertTrue(hpath is path(H))
        self.assertTrue(fpath.a is F.a)
        self.assertTrue(fpath.sign is F.sign)
        self.assertTrue(gpath.a is G.a)
        self.assertTrue(gpath.b is G.b)
        self.assertTrue(hpath.a is H.a)
        self.assertTrue(hpath.b is H.b)
        self.assertTrue(hpath.b.a is H.b.a)
        self.assertTrue(hpath.b.sign is H.b.sign)
        self.assertTrue(hpath.c.a is H.c.a)
        self.assertTrue(hpath.c.b is H.c.b)

        # Test that the string representation is correct
        self.assertEqual(str(path(F)), "F")
        self.assertEqual(str(path(G)), "G")
        self.assertEqual(str(path(H)), "H")
        self.assertEqual(str(F.a), "F.a")
        self.assertEqual(str(F.sign), "F.sign")
        self.assertEqual(str(G.a), "G.a")
        self.assertEqual(str(G.b), "G.b")
        self.assertEqual(str(H.a), "H.a")
        self.assertEqual(str(H.b), "H.b")
        self.assertEqual(str(H.b.a), "H.b.a")
        self.assertEqual(str(H.b.sign), "H.b.sign")
        self.assertEqual(str(H.c.a), "H.c.a")
        self.assertEqual(str(H.c.b), "H.c.b")

        with self.assertRaises(AttributeError) as ctx:
            sign = G.sign

    def test_path_and_hashable_path_inputs(self):

        F = self.F
        H = self.H

        self.assertTrue(isinstance(path(F), PredicatePath))
        self.assertEqual(path(F).meta.predicate, F)
        self.assertEqual(path(F), path(path(F)))
        self.assertEqual(path(hashable_path(F)), path(F))
        self.assertEqual(hashable_path(F), F.meta.path.meta.hashable)
        self.assertEqual(hashable_path(F.meta.path), F.meta.path.meta.hashable)
        self.assertEqual(hashable_path(F.meta.path.meta.hashable),
                         F.meta.path.meta.hashable)
        fpath = path(F)
        hpath = path(H)

        self.assertEqual(hashable_path(fpath), hashable_path(F))
        self.assertEqual(str(hashable_path(F.a)), str(F.a))
        self.assertTrue(hashable_path(F.a) == hashable_path(fpath.a))
        self.assertTrue(hashable_path(F.a) != hashable_path(H.a))
        self.assertEqual(id(hashable_path(F.a).path), id(F.a))

        hp2p = { hashable_path(p) : p for p in [H.a,H.b.a,H.c.a] }

        self.assertEqual(id(hp2p[hashable_path(H.a)]), id(H.a))
        self.assertEqual(id(hp2p[hashable_path(H.b.a)]), id(H.b.a))
        self.assertEqual(id(hp2p[hashable_path(H.c.a)]), id(H.c.a))


    def test_resolve_fact_wrt_path(self):

        F = self.F
        G = self.G
        H = self.H

        f1_pos = F(a=1)
        f1_neg = F(a=2,sign=False)

        self.assertEqual(path(F)(f1_pos), f1_pos)
        self.assertEqual(path(F)(f1_neg), f1_neg)
        self.assertEqual(F.a(f1_pos), f1_pos.a)
        self.assertEqual(F.a(f1_neg), f1_neg.a)
        self.assertEqual(F.sign(f1_pos), f1_pos.sign)
        self.assertEqual(F.sign(f1_neg), f1_neg.sign)

        g1 = G(a="a",b="b")
        self.assertEqual(path(G)(g1), g1)
        self.assertEqual(G.a(g1), g1.a)
        self.assertEqual(G.b(g1), g1.b)

        h1_pos = H(a=10,b=f1_pos,c=g1)
        h1_neg = H(a=10,b=f1_pos,c=g1,sign=False)
        h2_pos = H(a=10,b=f1_neg,c=g1)

        self.assertEqual(path(H)(h1_pos), h1_pos)
        self.assertEqual(path(H)(h1_neg), h1_neg)
        self.assertEqual(path(H)(h2_pos), h2_pos)
        self.assertEqual(H.a(h1_pos), h1_pos.a)
        self.assertEqual(H.b(h1_pos), f1_pos)
        self.assertEqual(H.b.a(h1_pos), f1_pos.a)
        self.assertEqual(H.b.sign(h1_pos), f1_pos.sign)
        self.assertEqual(H.sign(h1_pos), h1_pos.sign)
        self.assertEqual(H.sign(h1_neg), h1_neg.sign)
        self.assertEqual(H.sign(h2_pos), h2_pos.sign)


    def test_predicate_path_alias(self):

        H = self.H

        Hpath = path(H)
        X = alias(H,"X")

        self.assertTrue(isinstance(X, PredicatePath))
        self.assertEqual(type(X), type(path(H)))

        # The path names for the alias follows the normal pattern
        self.assertEqual(str(X.a), "X.a")
        self.assertEqual(str(X.b), "X.b")
        self.assertEqual(str(X.b.a), "X.b.a")
        self.assertEqual(str(X.b.sign), "X.b.sign")
        self.assertEqual(str(X.c.a), "X.c.a")
        self.assertEqual(str(X.c.b), "X.c.b")

        # The PredicatePath subclasses are the same
        self.assertEqual(type(H.a), type(X.a))
        self.assertEqual(type(H.b), type(X.b))
        self.assertEqual(type(H.b.a), type(X.b.a))
        self.assertEqual(type(H.b.sign), type(X.b.sign))
        self.assertEqual(type(H.c.a), type(X.c.a))
        self.assertEqual(type(H.c.a), type(X.c.a))

        # The path and alias refer to the same root predicate
        self.assertEqual(X.meta.predicate, path(H).meta.predicate)
        self.assertEqual(X.a.meta.predicate, H.a.meta.predicate)
        self.assertEqual(X.b.meta.predicate, H.b.meta.predicate)
        self.assertEqual(X.b.sign.meta.predicate, H.b.sign.meta.predicate)

        # But the paths are not equal
        def _h(a): return hashable_path(a)

        self.assertNotEqual(_h(X), _h(H))
        self.assertNotEqual(_h(X.a), _h(H.a))
        self.assertNotEqual(_h(X.b), _h(H.b))
        self.assertNotEqual(_h(X.b.a), _h(H.b.a))

        # No alias name specified so generate a random one
        Y = alias(H)        # No default name
        self.assertTrue(str(Y))

    def test_nonapi_predicate_path_root(self):

        H = self.H
        X = alias(H,"X")

        def _h(a): return hashable_path(a)

        self.assertEqual(_h(path(H).meta.root), _h(H))
        self.assertEqual(_h(H.c.b.meta.root) ,_h(H))
        self.assertEqual(_h(X.c.b.meta.root) ,_h(X))
        self.assertEqual(_h(X.c.b.meta.root) ,_h(X))
        self.assertNotEqual(_h(X.c.b.meta.root), _h(H))


#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
