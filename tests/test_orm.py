#------------------------------------------------------------------------------
# Unit tests for the clorm ORM interface
#------------------------------------------------------------------------------

import inspect
import unittest
import datetime
import calendar
import operator
import collections
from .support import check_errmsg

from clingo import Number, String, Function,  __version__ as clingo_version
from clingo import Control
from clorm.orm import \
    Predicate, ComplexTerm, \
    IntegerField, StringField, ConstantField, RawField, \
    _get_field_defn, refine_field, simple_predicate, \
    not_, and_, or_, StaticComparator, BoolComparator, \
    ph_, ph1_, ph2_, _PositionalPlaceholder, _NamedPlaceholder, \
    _FactIndex, _FactMap, PredicatePath, path, hashable_path, \
    unify, desc, asc, FactBase, SymbolPredicateUnifier,  \
    TypeCastSignature, _get_annotations, make_function_asp_callable, \
    make_method_asp_callable, \
    ContextBuilder

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

__all__ = [
    'RawFieldTestCase',
    'PredicateDefnTestCase',
    'ORMTestCase',
    'PredicatePathTestCase',
    'FactIndexTestCase',
    'FactMapTestCase',
    'FactBaseTestCase',
    'SelectTestCase',
    'TypeCastSignatureTestCase',
    'ContextBuilderTestCase',
    ]


#------------------------------------------------------------------------------
# Test the RawField class and sub-classes and definining simple sub-classes
#------------------------------------------------------------------------------

class RawFieldTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    #--------------------------------------------------------------------------
    # Test the Simple Fields conversion functions
    # (StringField/ConstantField/IntegerField) as well as sub-classing
    # --------------------------------------------------------------------------
    def test_simpleterms(self):

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


        with self.assertRaises(TypeError) as ctx:
            class DateField(StringField, StringField):
                pass

        class DateField(StringField):
            pytocl = lambda dt: dt.strftime("%Y%m%d")
            cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()

        symstr = String("20180101")
        dt = datetime.date(2018,1,1)
        self.assertEqual(DateField.cltopy(symstr), dt)
        self.assertEqual(DateField.pytocl(dt), symstr)

        class PartialField(StringField):
            pytocl = lambda dt: dt.strftime("%Y%m%d")

        with self.assertRaises(NotImplementedError) as ctx:
            symstr = String("20180101")
            dt = datetime.date(2018,1,1)
            self.assertEqual(PartialField.cltopy(symstr), dt)

    #--------------------------------------------------------------------------
    # Test that the simple field unify functions work as expected
    #--------------------------------------------------------------------------
    def test_pytocl_and_cltopy_and_unifies(self):
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
    # A default can take arbitrary non-None values. It can also take a
    # function/functor will be called when the Field's default property is
    # queried.
    # --------------------------------------------------------------------------
    def test_field_defaults(self):
        val=0
        def inc():
            nonlocal val
            val +=1
            return val

        # Note: distinguish no default value and a default value of None
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
    # Test catching invalid default values for a field
    #--------------------------------------------------------------------------
    def test_catch_bad_field_defaults(self):
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
    # Test setting index for a term
    #--------------------------------------------------------------------------
    def test_term_index(self):
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
    # Test making a restriction of a field using a list of values
    #--------------------------------------------------------------------------
    def test_refine_field_values(self):
        rf = refine_field

        # Some bad calls
        with self.assertRaises(TypeError) as ctx:
            class Something(object):
                def __init__(self): self._a = 1

            fld = rf("fld", Something, ["a","b"])

        with self.assertRaises(TypeError) as ctx:
            fld = rf("fld", "notaclass", ["a","b"])

        with self.assertRaises(TypeError) as ctx:
            fld = rf("fld", IntegerField, ["a"])

        # A good restriction
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

        with self.assertRaises(TypeError) as ctx:
            v = ABCField.pytocl("d")

        with self.assertRaises(TypeError) as ctx:
            v = ABCField.pytocl(1)

        # Test the cltopy direction
        self.assertEqual(ABCField.cltopy(r_a), "a")
        self.assertEqual(ABCField.cltopy(r_b), "b")
        self.assertEqual(ABCField.cltopy(r_c), "c")
        with self.assertRaises(TypeError) as ctx:
            v = ABCField.cltopy(r_d)
        with self.assertRaises(TypeError) as ctx:
            v = ABCField.cltopy(r_1)

        self.assertTrue(ABCField.unifies(r_a))
        self.assertTrue(ABCField.unifies(r_b))
        self.assertTrue(ABCField.unifies(r_c))
        self.assertFalse(ABCField.unifies(r_d))
        self.assertFalse(ABCField.unifies(r_1))

        # Test a version with no class name
        ABCField2 = rf(ConstantField, ["a","b","c"])
        self.assertEqual(ABCField2.pytocl("a"), r_a)

        # But only 2 and 3 arguments are valid
        with self.assertRaises(TypeError) as ctx:
            ABCField3 = rf(["a","b","c"])
        with self.assertRaises(TypeError) as ctx:
            ABCField4 = rf("ABCField", ConstantField, ["a","b","c"], 1)


    #--------------------------------------------------------------------------
    # Test making a restriction of a field using a value functor
    #--------------------------------------------------------------------------
    def test_refine_field_functor(self):
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

#------------------------------------------------------------------------------
# Test definition predicates/complex terms
#------------------------------------------------------------------------------

class PredicateDefnTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    #--------------------------------------------------------------------------
    # Test the _get_field_defn function that smartly returns field definitions
    #--------------------------------------------------------------------------
    def test_get_field_defn(self):
        # Simple case of a RawField instance - return the input
        tmp = RawField()
        self.assertEqual(_get_field_defn(tmp), tmp)
        tmp = IntegerField()
        self.assertEqual(_get_field_defn(tmp), tmp)
        tmp = ConstantField()
        self.assertEqual(_get_field_defn(tmp), tmp)

        # A raw field subclass returns an instance of the subclass
        self.assertTrue(isinstance(_get_field_defn(RawField), RawField))
        self.assertTrue(isinstance(_get_field_defn(StringField), StringField))

        # Throws an erorr on an unrecognised object
        with self.assertRaises(TypeError) as ctx:
            t = _get_field_defn("error")

        # Throws an erorr on an unrecognised class object
        with self.assertRaises(TypeError) as ctx:
            t = _get_field_defn(int)
        with self.assertRaises(TypeError) as ctx:
            class Blah(object): pass
            t = _get_field_defn(Blah)

        # A simple tuple definition
        td = _get_field_defn((IntegerField(), ConstantField()))
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
    # As part of the _get_field_defn function to flexibly deal with tuples
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
    # As part of the _get_field_defn function extended the field definition to
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

class ORMTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    #--------------------------------------------------------------------------
    # Simple test to make sure that raw terms unify correctly
    #--------------------------------------------------------------------------
    def test_predicate_instance_raw_term(self):

        raw1 = Function("func",[Number(1)])
        raw2 = Function("bob",[String("no")])
        rf1 = RawField()
        rt1 = Function("tmp", [Number(1), raw1])
        rt2 = Function("tmp", [Number(1), raw2])
        self.assertTrue(rf1.unifies(raw1))

        class Tmp(Predicate):
            n1 = IntegerField()
            r1 = RawField()

        self.assertTrue(Tmp._unifies(rt1))
        self.assertTrue(Tmp._unifies(rt2))
        t1 = Tmp(1,raw1)
        t2 = Tmp(1,raw2)

        self.assertEqual(set([f for f in unify([Tmp], [rt1,rt2])]),set([t1,t2]))
        self.assertEqual(t1.r1, raw1)
        self.assertEqual(t2.r1, raw2)

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
        with self.assertRaises(TypeError) as ctx:
            self.assertTrue(p1 < q1)

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



    #--------------------------------------------------------------------------
    #  Test a generator that takes n-1 Predicate types and a list of raw symbols
    #  as the last parameter, then tries to unify the raw symbols with the
    #  predicate types.
    #  --------------------------------------------------------------------------

    def test_unify(self):
        raws = [
            Function("afact",[Number(1),String("test")]),
            Function("afact",[Number(2),Number(3),String("test")]),
            Function("afact",[Number(1),Function("fun",[Number(1)])]),
            Function("bfact",[Number(3),String("test")])
            ]

        class Afact1(Predicate):
            anum=IntegerField()
            astr=StringField()
            class Meta: name = "afact"

        class Afact2(Predicate):
            anum1=IntegerField()
            anum2=IntegerField()
            astr=StringField()
            class Meta: name = "afact"

        class Afact3(Predicate):
            class Fun(ComplexTerm):
                fnum=IntegerField()

            anum=IntegerField()
            afun=Fun.Field()
#            afun=ComplexField(Fun)
            class Meta: name = "afact"

        class Bfact(Predicate):
            anum=IntegerField()
            astr=StringField()

        af1_1=Afact1(anum=1,astr="test")
        af2_1=Afact2(anum1=2,anum2=3,astr="test")
        af3_1=Afact3(anum=1,afun=Afact3.Fun(fnum=1))
        bf_1=Bfact(anum=3,astr="test")

        g1=list(unify([Afact1],raws))
        g2=list(unify([Afact2],raws))
        g3=list(unify([Afact3],raws))
        g4=list(unify([Bfact],raws))
        g5=list(unify([Afact1,Bfact],raws))
        self.assertEqual([af1_1], g1)
        self.assertEqual([af2_1], g2)
        self.assertEqual([af3_1], g3)
        self.assertEqual([bf_1], g4)
        self.assertEqual([af1_1,bf_1], g5)

        # Test the ordered option that returns a list of facts that preserves
        # the order of the original symbols.
        g1=unify([Afact1,Afact2,Bfact], raws, ordered=True)
        self.assertEqual(g1, [af1_1,af2_1,bf_1])

    #--------------------------------------------------------------------------
    #   Test unifying between predicates which have the same name-arity
    #   signature. There was a bug in the unify() function where only of the
    #   unifying classes was ignored leading to failed unification.
    #   --------------------------------------------------------------------------
    def test_unify_same_sig(self):
        class ATuple(ComplexTerm):
            aconst=ConstantField()
            bint = IntegerField()
            class Meta: is_tuple = True

        class Fact1(Predicate):
            aint = IntegerField()
            aconst = ConstantField()
            class Meta: name = "fact"

        class Fact2(Predicate):
            aint = IntegerField()
            atuple = ATuple.Field()
            class Meta: name = "fact"

        r1 = Function("fact",[Number(1), Function("bob",[])])
        r2 = Function("fact",[Number(1), Function("", [Function("bob",[]),Number(1)])])

        # r1 only unifies with Fact1 and r2 only unifies with Fact2
        f1 = Fact1(raw=r1)
        self.assertEqual(f1.raw, r1)
        with self.assertRaises(ValueError) as ctx:
            f2 = Fact1(raw=r2)
        f2 = Fact2(raw=r2)
        self.assertEqual(f2.raw, r2)
        with self.assertRaises(ValueError) as ctx:
            f1 = Fact2(raw=r1)

        # The unify() function should correctly unify both facts
        res = unify([Fact1,Fact2],[r1,r2])
        self.assertEqual(len(res), 2)

    #--------------------------------------------------------------------------
    #   Test unifying between predicates which have the same name-arity
    #   signature to make sure the order of the predicate classes correctly
    #   corresponds to the order in which the facts are unified.
    #   --------------------------------------------------------------------------
    def test_unify_same_sig2(self):

        class Fact1(Predicate):
            aint = IntegerField()
            aconst = ConstantField()
            class Meta: name = "fact"

        class Fact2(Predicate):
            aint = IntegerField()
            araw = RawField()
            class Meta: name = "fact"

        r1 = Function("fact",[Number(1), Function("bob",[])])
        r2 = Function("fact",[Number(1), Function("", [Function("bob",[]),Number(1)])])

        # r1 only unifies with Fact1 but both r1 and r2 unify with Fact2
        f1 = Fact1(raw=r1)
        self.assertEqual(f1.raw, r1)
        with self.assertRaises(ValueError) as ctx:
            f2 = Fact1(raw=r2)
        f1_alt = Fact2(raw=r1)
        self.assertEqual(f1_alt.raw, r1)
        f2 = Fact2(raw=r2)
        self.assertEqual(f2.raw, r2)

        # unify() unifies r1 with Fact1 (f1) and r2 with Fact2 (f2)
        res = unify([Fact1,Fact2],[r1,r2])
        self.assertEqual(len(res), 2)
        self.assertTrue(f1 in res)
        self.assertTrue(f2 in res)

        # unify() unifies r1 and r2 with Fact2 (f1_alt and f2)
        res = unify([Fact2,Fact1],[r1,r2])
        self.assertEqual(len(res), 2)
        self.assertTrue(f1_alt in res)
        self.assertTrue(f2 in res)

    #--------------------------------------------------------------------------
    # Test unifying with negative facts
    #--------------------------------------------------------------------------
    def test_unify_signed_literals(self):
        class F1(Predicate):
            a = IntegerField
            class Meta:
                name = "f"
                sign = True

        class F2(Predicate):
            a = IntegerField
            class Meta:
                name = "f"
                sign = False

        pos_raw1 = Function("f",[Number(1)])
        pos_raw2 = Function("f",[Number(2)])
        neg_raw1 = Function("f",[Number(1)],False)
        neg_raw2 = Function("f",[Number(2)],False)

        pos1 = F1(a=1)
        pos2 = F1(a=2)
        neg1 = F2(a=1,sign=False)
        neg2 = F2(a=2,sign=False)

        # unify with all raw
        fb = unify([F1,F2], [ pos_raw1, pos_raw2, neg_raw1, neg_raw2])
        self.assertEqual(len(fb), 4)
        self.assertEqual(set(fb.select(F1).get()), set([pos1,pos2]))
        self.assertEqual(set(fb.select(F2).get()), set([neg1,neg2]))

        fb = unify([F1], [ pos_raw1, pos_raw2, neg_raw1, neg_raw2])
        self.assertEqual(len(fb), 2)
        self.assertEqual(fb.select(F1).count(), 2)

        fb = unify([F2], [ pos_raw1, pos_raw2, neg_raw1, neg_raw2])
        self.assertEqual(len(fb), 2)
        self.assertEqual(fb.select(F2).count(), 2)

        with self.assertRaises(ValueError) as ctx:
            bad1 = F1(a=1,sign=False)

    #--------------------------------------------------------------------------
    #  Test that the fact comparators work
    #--------------------------------------------------------------------------

    def test_comparators(self):

        def is_static(fc):
            return isinstance(fc, StaticComparator)

        class Afact(Predicate):
            anum1=IntegerField()
            anum2=IntegerField()
            astr=StringField()
        class Bfact(Predicate):
            anum=IntegerField()
            astr=StringField()

        af1 = Afact(1,1,"bbb")
        af2 = Afact(2,3,"aaa")
        af3 = Afact(1,3,"aaa")
        bf1 = Bfact(1,"aaa")

        e1 = Afact.anum1 == 2
        e2 = Afact.anum1 == Afact.anum2
        e3 = Afact.anum1 == Afact.anum1
        e4 = Bfact.astr == "aaa"

        # generated test comparators through positional arguments
        ep1 = Afact[0] == 2
        ep2 = Afact[0] == Afact.anum2
        ep3 = Afact[0] == Afact.anum1
        ep4 = Bfact[1] == "aaa"


#        self.assertEqual(e1, _get_term_comparators(e1)[0])
#        self.assertEqual(e2, _get_term_comparators(e2)[0])
#        self.assertEqual(e3, _get_term_comparators(e3)[0])
#        self.assertEqual([], _get_term_comparators(e3.simplified()))

#        self.assertEqual(ep1, _get_term_comparators(ep1)[0])
#        self.assertEqual(ep2, _get_term_comparators(ep2)[0])
#        self.assertEqual(ep3, _get_term_comparators(ep3)[0])
#        self.assertEqual([], _get_term_comparators(ep3.simplified()))

        self.assertFalse(is_static(e1.simplified()))
        self.assertFalse(is_static(e2.simplified()))
        self.assertTrue(is_static(e3.simplified()))
        self.assertFalse(is_static(e4.simplified()))

        self.assertFalse(is_static(ep1.simplified()))
        self.assertFalse(is_static(ep2.simplified()))
        self.assertTrue(is_static(ep3.simplified()))
        self.assertFalse(is_static(ep4.simplified()))

        self.assertFalse(e1(af1))
        self.assertTrue(e1(af2))

        self.assertFalse(ep1(af1))
        self.assertTrue(ep1(af2))

        # Testing the PredicatePathComparator on the wrong fact type
        with self.assertRaises(TypeError) as ctx:
            self.assertFalse(e1(bf1))

        # Testing the PredicatePathComparator on the wrong fact type
        with self.assertRaises(TypeError) as ctx:
            self.assertFalse(ep1(bf1))

        self.assertTrue(e2(af1))
        self.assertFalse(e2(af2))
        self.assertTrue(ep2(af1))
        self.assertFalse(ep2(af2))
#        self.assertFalse(e2(bf1))

        self.assertTrue(e3(af1))
        self.assertTrue(e3(af2))
        self.assertTrue(ep3(af1))
        self.assertTrue(ep3(af2))
#        self.assertTrue(e3(bf1))

#        self.assertFalse(e4(af1))
#        self.assertFalse(e4(af2))

        self.assertTrue(e4(bf1))
        self.assertTrue(ep4(bf1))

        es1 = [Afact.anum1 == 2, Afact.anum2 == 3]

        ac = and_(*es1)

        self.assertFalse(is_static(ac.simplified()))
        self.assertFalse(ac(af1))
        self.assertTrue(ac(af2))
#        self.assertFalse(ac(bf1))

        nc = not_(ac)
        self.assertFalse(is_static(nc.simplified()))
        self.assertTrue(nc(af1))
        self.assertFalse(nc(af2))
 #       self.assertTrue(nc(bf1))

        oc = or_(*es1)
        self.assertFalse(is_static(oc.simplified()))
        self.assertFalse(oc(af1))
        self.assertTrue(oc(af2))
        self.assertTrue(oc(af3))
  #      self.assertFalse(oc(bf1))

        es2 = [Afact.anum1 == Afact.anum1, True]
        ac2 = and_(*es2)
        self.assertTrue(is_static(ac2.simplified()))

        es3 = [Afact.anum1 == 1, Afact.anum2 == 1, Bfact.anum == 2, True]
        ac3 = and_(*es3)
        self.assertFalse(is_static(ac3.simplified()))

        self.assertEqual(str(Afact.anum1), "Afact.anum1")

        # This cannot be simplified
        es4 = [Afact.anum1 == Afact.anum1, lambda x: False]
        ac4 = and_(*es4)
        self.assertFalse(is_static(ac4.simplified()))


    #--------------------------------------------------------------------------
    #  Test the overloaded bitwise comparators (&,|,~)
    #--------------------------------------------------------------------------
    def test_query_bitwise_comparator_overloads(self):
        class Afact(Predicate):
            anum1=IntegerField
            anum2=IntegerField
            astr=StringField

        fc1 = Afact.anum1 == 1 ; fc2 = Afact.anum1 == 2
        ac = fc1 & fc2
        self.assertTrue(type(ac), BoolComparator)
        self.assertTrue(ac.boolop, operator.or_)
        self.assertTrue(ac.args, [fc1,fc2])

        oc = (Afact.anum1 == 1) | (Afact.anum2 == 2)
        self.assertTrue(type(oc), BoolComparator)
        self.assertTrue(oc.boolop, operator.or_)

        nc1 = ~fc1
        self.assertTrue(type(nc1), BoolComparator)
        self.assertTrue(nc1.boolop, operator.not_)
        self.assertTrue(nc1.args, [fc1])

        nc2 = ~(Afact.anum1 == 1)
        self.assertTrue(type(nc2), BoolComparator)
        self.assertTrue(nc2.boolop, operator.not_)


    #--------------------------------------------------------------------------
    # Test that simplification is working for the boolean comparator
    #--------------------------------------------------------------------------
    def test_bool_comparator_simplified(self):

        def is_static(fc):
            return isinstance(fc, StaticComparator)

        class Afact(Predicate):
            anum1=IntegerField()
            anum2=IntegerField()
            astr=StringField()
        class Bfact(Predicate):
            anum=IntegerField()
            astr=StringField()

        af1 = Afact(1,1,"bbb")
        af2 = Afact(2,3,"aaa")
        af3 = Afact(1,3,"aaa")
        bf1 = Bfact(1,"aaa")

        e1 = Afact.anum1 == 2
        e2 = Afact.anum1 == Afact.anum2
        e3 = Afact.anum1 == Afact.anum1
        e4 = Afact.anum2 != Afact.anum2
        e5 = Bfact.astr == "aaa"

        and1 = and_(e1, e3)
        and2 = and_(e2, e4)
        or1 = or_(e1, e3)
        sand1 = and1.simplified()
        sand2 = and2.simplified()
        sor1 = or1.simplified()

        self.assertEqual(str(sand1), "Afact.anum1 == 2")
        self.assertEqual(str(sand2), "False")
        self.assertEqual(str(sor1), "True")

        or2 = or_(or1,and1)
        sor2 = or2.simplified()
        self.assertEqual(str(sor2),"True")

        and3 = and_(and1,and2)
        sand3 = and3.simplified()
        self.assertEqual(str(sand3),"False")

        or4 = or_(and3,e1)
        sor4 = or4.simplified()
        self.assertEqual(str(sor4), "Afact.anum1 == 2")


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

    def test_hashable_path(self):

        F = self.F
        H = self.H
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

    def test_path_comparator(self):

        F = self.F
        G = self.G
        H = self.H

        f1_pos = F(a=1)
        f1_neg = F(a=2,sign=False)
        g1 = G(a="a",b="b")
        h1_pos = H(a=1,b=f1_pos,c=g1)
        h1_pos2 = H(a=1,b=f1_pos,c=g1)
        h1_neg = H(a=1,b=f1_pos,c=g1,sign=False)
        h2_pos = H(a=2,b=f1_neg,c=g1)

        comp = path(H) == h1_pos
        self.assertTrue(comp(h1_pos))
        self.assertTrue(comp(h1_pos2))
        self.assertFalse(comp(h1_neg))
        self.assertFalse(comp(h2_pos))

        comp = H.sign == True
        self.assertTrue(comp(h1_pos))
        self.assertTrue(comp(h2_pos))
        self.assertFalse(comp(h1_neg))

        comp = H.c.a == "a"
        self.assertTrue(comp(h1_pos))
        self.assertTrue(comp(h2_pos))
        self.assertTrue(comp(h1_neg))

        comp = H.c.a != "a"
        self.assertFalse(comp(h1_pos))
        self.assertFalse(comp(h2_pos))
        self.assertFalse(comp(h1_neg))

        comp = H.a < 2
        self.assertTrue(comp(h1_pos))
        self.assertTrue(comp(h1_neg))
        self.assertFalse(comp(h2_pos))

        comp = H.a <= 2
        self.assertTrue(comp(h1_pos))
        self.assertTrue(comp(h1_neg))
        self.assertTrue(comp(h2_pos))

        comp = H.a > 1
        self.assertFalse(comp(h1_pos))
        self.assertFalse(comp(h1_neg))
        self.assertTrue(comp(h2_pos))

        comp = H.a > 2
        self.assertFalse(comp(h1_pos))
        self.assertFalse(comp(h1_neg))
        self.assertFalse(comp(h2_pos))

        comp = H.a == H.b.a
        self.assertTrue(comp(h1_pos))


#------------------------------------------------------------------------------
# Test the _FactIndex class
#------------------------------------------------------------------------------

class FactIndexTestCase(unittest.TestCase):
    def setUp(self):
        class Afact(Predicate):
            num1=IntegerField()
            str1=StringField()

        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()

        self.Afact = Afact
        self.Bfact = Bfact

    def test_create(self):
        Afact = self.Afact
        fi1 = _FactIndex(Afact.num1)
        self.assertTrue(fi1)

        # Should only accept fields
        with self.assertRaises(TypeError) as ctx:
            f2 = _FactIndex(1)
        with self.assertRaises(TypeError) as ctx:
            f2 = _FactIndex(Afact)

    def test_add(self):
        Afact = self.Afact
        Bfact = self.Bfact
        fi1 = _FactIndex(Afact.num1)
        fi2 = _FactIndex(Afact.str1)
        self.assertEqual(fi1.keys, [])

        fi1.add(Afact(num1=1, str1="c"))
        fi2.add(Afact(num1=1, str1="c"))
        self.assertEqual(fi1.keys, [1])
        self.assertEqual(fi2.keys, ["c"])

        fi1.add(Afact(num1=2, str1="b"))
        fi2.add(Afact(num1=2, str1="b"))
        self.assertEqual(fi1.keys, [1,2])
        self.assertEqual(fi2.keys, ["b","c"])

        fi1.add(Afact(num1=3, str1="b"))
        fi2.add(Afact(num1=3, str1="b"))
        self.assertEqual(fi1.keys, [1,2,3])
        self.assertEqual(fi2.keys, ["b","c"])

    def test_remove(self):
        Afact = self.Afact
        Bfact = self.Bfact

        af1a = Afact(num1=1, str1="a")
        af2a = Afact(num1=2, str1="a")
        af2b = Afact(num1=2, str1="b")
        af3a = Afact(num1=3, str1="a")
        af3b = Afact(num1=3, str1="b")

        fi = _FactIndex(Afact.num1)
        for f in [ af1a, af2a, af2b, af3a, af3b ]: fi.add(f)
        self.assertEqual(fi.keys, [1,2,3])

        fi.remove(af1a)
        self.assertEqual(fi.keys, [2,3])

        fi.discard(af1a)
        with self.assertRaises(KeyError) as ctx:
            fi.remove(af1a)

        fi.remove(af2a)
        self.assertEqual(fi.keys, [2,3])

        fi.remove(af3a)
        self.assertEqual(fi.keys, [2,3])

        fi.remove(af2b)
        self.assertEqual(fi.keys, [3])

        fi.remove(af3b)
        self.assertEqual(fi.keys, [])

    def test_find(self):
        Afact = self.Afact

        af1a = Afact(num1=1, str1="a")
        af2a = Afact(num1=2, str1="a")
        af2b = Afact(num1=2, str1="b")
        af3a = Afact(num1=3, str1="a")
        af3b = Afact(num1=3, str1="b")

        fi = _FactIndex(Afact.num1)
        allfacts = [ af1a, af2a, af2b, af3a, af3b ]
        for f in allfacts: fi.add(f)

        self.assertEqual(fi.find(operator.eq, 1), set([af1a]))
        self.assertEqual(fi.find(operator.eq, 2), set([af2a, af2b]))
        self.assertEqual(fi.find(operator.ne, 5), set(allfacts))
        self.assertEqual(fi.find(operator.eq, 5), set([]))
        self.assertEqual(fi.find(operator.lt, 1), set([]))
        self.assertEqual(fi.find(operator.lt, 2), set([af1a]))
        self.assertEqual(fi.find(operator.le, 2), set([af1a, af2a, af2b]))
        self.assertEqual(fi.find(operator.gt, 2), set([af3a, af3b]))
        self.assertEqual(fi.find(operator.ge, 3), set([af3a, af3b]))
        self.assertEqual(fi.find(operator.gt, 3), set([]))

    def test_clear(self):
        Afact = self.Afact
        fi = _FactIndex(Afact.num1)
        fi.add(Afact(num1=1, str1="a"))
        fi.clear()
        self.assertEqual(fi.keys,[])

    #--------------------------------------------------------------------------
    # Test accessing the value of attributes through a FieldPathBuilder properties
    #--------------------------------------------------------------------------
    def test_subfield_access(self):
        class F(ComplexTerm):
            anum=IntegerField()
        class G(Predicate):
            ct1=F.Field()
            ct2=(IntegerField(),IntegerField())

        f1 = F(1)
        g1 = G(f1,(2,3))

        self.assertEqual(f1.anum,1)
        self.assertEqual(g1.ct1.anum,1)
        self.assertEqual(g1.ct2[0],2)
        self.assertEqual(g1.ct2[1],3)

#        tmp1 = G.ct1.anum.meta.path
#        print("TMP: {}, type: {}".format(tmp1,type(tmp1)))

#        tmp2 = G.ct1.sign
#        print("TMP: {}, type: {}".format(tmp1,type(tmp1)))

#        self.assertEqual(F.anum(f1), 1)

    #--------------------------------------------------------------------------
    # Test the support for indexes of subfields
    #--------------------------------------------------------------------------
    def test_subfields(self):
        class CT(ComplexTerm):
            num1=IntegerField()
            str1=StringField()
        class Fact(Predicate):
            ct1=CT.Field()
            ct2=(IntegerField(),IntegerField())

        fi1 = _FactIndex(Fact.ct1.num1)
        fi2 = _FactIndex(Fact.ct2[1])
        fi3 = _FactIndex(Fact.ct1)

        f1=Fact(CT(10,"a"),(1,4))
        f2=Fact(CT(20,"b"),(2,3))
        f3=Fact(CT(30,"c"),(5,2))
        f4=Fact(CT(40,"d"),(6,1))

        fi1.add(f1); fi2.add(f1); fi3.add(f1)
        fi1.add(f2); fi2.add(f2); fi3.add(f2)
        fi1.add(f3); fi2.add(f3); fi3.add(f3)
        fi1.add(f4); fi2.add(f4); fi3.add(f4)

        self.assertEqual(fi1.keys, [10,20,30,40])
        self.assertEqual(fi2.keys, [1,2,3,4])
        self.assertEqual(set(fi3.keys),
                         set([CT(10,"a"),CT(20,"b"),CT(30,"c"),CT(40,"d")]))

#------------------------------------------------------------------------------
# Test the _FactMap and _Select _Delete class
#------------------------------------------------------------------------------

class FactMapTestCase(unittest.TestCase):
    def setUp(self):

        class Afact(Predicate):
            num1=IntegerField()
            str1=StringField()
            str2=ConstantField()

        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()
            str2=ConstantField()

        self.Afact = Afact
        self.Bfact = Bfact

    def test_init(self):
        Afact = self.Afact
        Bfact = self.Bfact

        fm1 = _FactMap(Afact)
        self.assertEqual(fm1.indexes, ())

        fm1 = _FactMap(Afact, [Afact.num1, Afact.str1])
        self.assertEqual(fm1.indexes, (Afact.num1, Afact.str1))

        with self.assertRaises(TypeError) as ctx:
            fm = _FactMap(1)

        with self.assertRaises(TypeError) as ctx:
            fm = _FactMap(Afact.num1)

        with self.assertRaises(TypeError) as ctx:
            fm = _FactMap(Afact, [Bfact.num1])

    def test_add_and_container_ops(self):
        Afact = self.Afact
        fm = _FactMap(Afact, [Afact.num1, Afact.str1])

        af1a = Afact(num1=1, str1="a", str2="a")
        af2a = Afact(num1=2, str1="a", str2="a")
        af2b = Afact(num1=2, str1="b", str2="a")
        af3a = Afact(num1=3, str1="a", str2="c")
        af3b = Afact(num1=3, str1="b", str2="c")

        # Test add() and  __contains__()
        allfacts = [ af1a, af2a, af2b, af3a, af3b ]
        for f in allfacts: fm.add(f)
        self.assertTrue(af2b in fm)
        self.assertTrue(af2a in fm)
        self.assertFalse(Afact(num1=1, str1="a", str2="b") in fm)
        for f in allfacts: fm.add(f)
        self.assertTrue(af2b in fm)

        # Test __bool__ and __len__
        fm2 = _FactMap(Afact, [Afact.num1, Afact.str1])
        self.assertTrue(bool(fm))
        self.assertFalse(fm2)
        self.assertEqual(len(fm), 5)
        self.assertEqual(len(fm2), 0)

        # Test __iter__
        self.assertEqual(set(fm), set(allfacts))
        self.assertEqual(set(fm2), set())

    def test_remove_discard_clear(self):
        Afact = self.Afact
        fm = _FactMap(Afact, [Afact.num1, Afact.str1])

        af1a = Afact(num1=1, str1="a", str2="a")
        af2a = Afact(num1=2, str1="a", str2="a")
        af2b = Afact(num1=2, str1="b", str2="a")
        af3a = Afact(num1=3, str1="a", str2="c")
        af3b = Afact(num1=3, str1="b", str2="c")

        allfacts = [ af1a, af2a, af2b, af3a, af3b ]
        for f in allfacts: fm.add(f)

        fm.remove(af1a)
        fm.discard(af1a)
        with self.assertRaises(KeyError) as ctx:
            fm.remove(af1a)

        fm.clear()
        self.assertFalse(af1a in fm)
        self.assertFalse(af2a in fm)
        self.assertFalse(af2b in fm)
        self.assertFalse(af3a in fm)
        self.assertFalse(af3b in fm)

    def test_set_comparison_ops(self):
        Afact = self.Afact
        fm1 = _FactMap(Afact)
        fm2 = _FactMap(Afact)
        fm3 = _FactMap(Afact)
        fm1_alt = _FactMap(Afact)

        af1 = Afact(num1=1, str1="a", str2="a")
        af2 = Afact(num1=2, str1="a", str2="a")
        af3 = Afact(num1=3, str1="b", str2="a")
        af4 = Afact(num1=4, str1="a", str2="c")
        af5 = Afact(num1=5, str1="b", str2="c")

        fm1.add([af1,af2])
        fm2.add([af1,af2,af3])
        fm3.add([af1,af2,af3,af4])

        fm1_alt.add([af1,af2])

        # Test __eq__ and __ne__
        self.assertTrue(fm1 == fm1_alt)
        self.assertTrue(fm1 != fm2)

        # Test __lt__, __le__, __gt__, __ge__
        self.assertFalse(fm1 < fm1_alt)
        self.assertFalse(fm1 > fm1_alt)
        self.assertTrue(fm1 <= fm1_alt)
        self.assertTrue(fm1 >= fm1_alt)
        self.assertTrue(fm1 < fm2)
        self.assertFalse(fm1 > fm2)
        self.assertTrue(fm1 <= fm2)
        self.assertFalse(fm1 >= fm2)
        self.assertFalse(fm2 < fm1)
        self.assertFalse(fm2 <= fm1)

    def test_set_ops(self):
        Afact = self.Afact
        fm1 = _FactMap(Afact)
        fm2 = _FactMap(Afact)
        fm3 = _FactMap(Afact)
        fm4 = _FactMap(Afact)
        fm5 = _FactMap(Afact)
        fm6 = _FactMap(Afact)
        fm7 = _FactMap(Afact)

        af1 = Afact(num1=1, str1="a", str2="a")
        af2 = Afact(num1=2, str1="b", str2="b")
        af3 = Afact(num1=3, str1="c", str2="c")
        af4 = Afact(num1=4, str1="d", str2="d")
        af5 = Afact(num1=5, str1="e", str2="e")

        fm1.add([af1,af2])
        fm2.add([af2,af3])
        fm3.add([af3,af4])
        fm4.add([af1,af2,af3,af4])
        fm5.add([])
        fm6.add([af1])
        fm7.add([af1,af3])

        fmo1=fm1.union(fm2,fm3)
        fmo2=fm1.intersection(fm2,fm3)
        fmo3=fm1.difference(fm2)
        fmo4=fm1.symmetric_difference(fm2)
        self.assertEqual(fm4,fmo1)
        self.assertEqual(fm5,fmo2)
        self.assertEqual(fm6,fmo3)
        self.assertEqual(fm7,fmo4)

        # Symmetric difference too many arguments
        with self.assertRaises(TypeError) as ctx:
            fmo4=fm3.symmetric_difference(fm1,fm4)

        # Test copy function
        r=fm1.copy() ; self.assertEqual(fm1,r)

        # Update function
        fm6.update(fm3,fm7)
        self.assertEqual(fm6.facts(), set([af1,af3,af3,af4]))

        # Intersection update function
        fm6.intersection_update(fm3,fm7)
        self.assertEqual(fm6.facts(), set([af3]))

        # Difference update function
        fm7.difference_update(fm6,fm5)
        self.assertEqual(fm7.facts(), set([af1]))
        fm7.difference_update(fm3)
        self.assertEqual(fm7.facts(), set([af1]))

        # Symmetric difference update function
        fm1 = _FactMap(Afact)
        fm2 = _FactMap(Afact)
        fm1.add([af1,af2,af3])
        fm2.add([af2,af3,af4])
        fm1.symmetric_difference_update(fm2)
        self.assertEqual(fm1.facts(), set([af1,af4]))

#------------------------------------------------------------------------------
# Test the FactBase
#------------------------------------------------------------------------------
class FactBaseTestCase(unittest.TestCase):
    def setUp(self):

        class Afact(Predicate):
            num1=IntegerField()
            str1=StringField()
            str2=ConstantField()

        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()
            str2=ConstantField()

        class Cfact(Predicate):
            num1=IntegerField()

        self._Afact = Afact
        self._Bfact = Bfact
        self._Cfact = Cfact

    def tearDown(self):
        pass

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_factbase_normal_init(self):

        Afact = self._Afact
        Bfact = self._Bfact
        Cfact = self._Cfact

        af1 = Afact(1,10,"bbb")
        bf1 = Bfact(1,"aaa", "bbb")
        cf1 = Cfact(1)

        fs1 = FactBase([af1,bf1,cf1])
        self.assertTrue(af1 in fs1)
        self.assertTrue(bf1 in fs1)
        self.assertTrue(cf1 in fs1)

        fs2 = FactBase()
        fs2.add([af1,bf1,cf1])
        self.assertTrue(af1 in fs2)
        self.assertTrue(bf1 in fs2)
        self.assertTrue(cf1 in fs2)

        fs3 = FactBase()
        fs3.add([af1])
        asp_str = fs3.asp_str().lstrip().rstrip()
        self.assertEqual(asp_str, "{}.".format(str(af1)))

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_delayed_init(self):

        Afact = self._Afact
        Bfact = self._Bfact
        Cfact = self._Cfact

        af1 = Afact(1,10,"bbb")
        bf1 = Bfact(1,"aaa","bbb")
        cf1 = Cfact(1)

        fs1 = FactBase(lambda: [af1,bf1])
        self.assertTrue(fs1._delayed_init)
        self.assertTrue(af1 in fs1)
        self.assertFalse(cf1 in fs1)
        fs1.add(cf1)
        self.assertTrue(bf1 in fs1)
        self.assertTrue(cf1 in fs1)

        fs2 = FactBase([af1,bf1])
        self.assertFalse(fs2._delayed_init)


    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_container_ops(self):

        Afact = self._Afact
        Bfact = self._Bfact

        delayed_init=lambda: []

        af1 = Afact(num1=1, str1="1", str2="a")
        af2 = Afact(num1=1, str1="1", str2="b")
        bf1 = Bfact(num1=1, str1="1", str2="a")

        fb = FactBase([af1])
        fb3 = FactBase(facts=lambda: [])
        self.assertTrue(af1 in fb)
        self.assertFalse(af2 in fb)
        self.assertFalse(bf1 in fb)
        self.assertFalse(bf1 in fb3)

        # Test __bool__
        fb2 = FactBase()
        fb3 = FactBase(facts=lambda: [])
        self.assertTrue(fb)
        self.assertFalse(fb2)
        self.assertFalse(fb3)

        # Test __len__
        self.assertEqual(len(fb2), 0)
        self.assertEqual(len(fb), 1)
        self.assertEqual(len(FactBase([af1,af2])),2)
        self.assertEqual(len(FactBase(facts=lambda: [af1,af2, bf1])), 3)

        # Test __iter__
        input = set([])
        self.assertEqual(set(FactBase(input)), input)
        input = set([af1])
        self.assertEqual(set(FactBase(input)), input)
        input = set([af1,af2])
        self.assertEqual(set(FactBase(input)), input)
        input = set([af1,af2,bf1])
        self.assertEqual(set(FactBase(input)), input)
        input = set([af1,af2,bf1])
        self.assertEqual(set(FactBase(facts=lambda: input)), input)

        # Test pop()
        fb1 = FactBase([af1])
        fb2 = FactBase([bf1])
        fb3 = FactBase([af1,bf1])
        f = fb3.pop()
        if f == af1:
            self.assertEqual(fb3,fb2)
            self.assertEqual(fb3.pop(), bf1)
        else:
            self.assertEqual(fb3,fb1)
            self.assertEqual(fb3.pop(), af1)
        self.assertFalse(fb3)

        # popping from an empty factbase should raise error
        with self.assertRaises(KeyError) as ctx: fb3.pop()


    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_comparison_ops(self):
        Afact = self._Afact
        Bfact = self._Bfact

        af1 = Afact(num1=1, str1="1", str2="a")
        af2 = Afact(num1=1, str1="1", str2="b")
        bf1 = Bfact(num1=1, str1="1", str2="a")

        fb1 = FactBase([af1,af2])
        fb2 = FactBase([af1,af2,bf1])
        fb3 = FactBase([af1,af2,bf1])
        fb4 = FactBase(facts=lambda: [af1,af2])
        fb5 = FactBase([af2, bf1])

        self.assertTrue(fb1 != fb2)
        self.assertFalse(fb1 == fb2)
        self.assertFalse(fb2 == fb5) # a case with same predicates keys

        self.assertTrue(fb1 == fb4)
        self.assertFalse(fb1 != fb4)
        self.assertTrue(fb2 == fb3)
        self.assertFalse(fb2 != fb3)

        # Test comparison against sets and lists
        self.assertTrue(fb2 == [af1,af2,bf1])
        self.assertTrue([af1,af2,bf1] == fb2)
        self.assertTrue(fb2 == set([af1,af2,bf1]))


    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_set_comparison_ops(self):
        Afact = self._Afact
        Bfact = self._Bfact

        af1 = Afact(num1=1, str1="1", str2="a")
        af2 = Afact(num1=1, str1="1", str2="b")
        af3 = Afact(num1=1, str1="1", str2="c")
        bf1 = Bfact(num1=1, str1="1", str2="a")
        bf2 = Bfact(num1=1, str1="1", str2="b")
        bf3 = Bfact(num1=1, str1="1", str2="c")

        fb1 = FactBase([af1,af2,bf1])
        fb2 = FactBase([af1,af2,bf1,bf2])
        fb3 = FactBase()

        self.assertTrue(fb1 <= fb1)
        self.assertTrue(fb1 < fb2)
        self.assertTrue(fb1 <= fb2)
        self.assertTrue(fb2 > fb1)
        self.assertTrue(fb2 >= fb1)

        self.assertFalse(fb1 > fb1)
        self.assertFalse(fb1 >= fb2)
        self.assertFalse(fb1 > fb2)
        self.assertFalse(fb2 <= fb1)
        self.assertFalse(fb2 < fb1)

        # Test comparison against sets and lists
        self.assertTrue(fb1 <= [af1,af2,bf1])
        self.assertTrue(fb1 < [af1,af2,bf1,bf2])
        self.assertTrue(fb1 <= [af1,af2,bf1,bf2])
        self.assertTrue(fb2 > [af1,af2,bf1])
        self.assertTrue(fb2 >= [af1,af2,bf1])
        self.assertTrue([af1,af2,bf1,bf2] >= fb1)

    #--------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------
    def test_set_ops(self):
        Afact = self._Afact
        Bfact = self._Bfact
        Cfact = self._Cfact

        af1 = Afact(num1=1, str1="1", str2="a")
        af2 = Afact(num1=1, str1="1", str2="b")
        af3 = Afact(num1=1, str1="1", str2="c")
        bf1 = Bfact(num1=1, str1="1", str2="a")
        bf2 = Bfact(num1=1, str1="1", str2="b")
        bf3 = Bfact(num1=1, str1="1", str2="c")
        cf1 = Cfact(num1=1)
        cf2 = Cfact(num1=2)
        cf3 = Cfact(num1=3)

        fb0 = FactBase()
        fb1 = FactBase([af1,bf1])
        fb1_alt = FactBase(lambda: [af1,bf1])
        fb2 = FactBase([bf1,bf2])
        fb3 = FactBase([af2,bf3])
        fb4 = FactBase([af1,af2,bf1,bf2,bf3])
        fb5 = FactBase([af1,bf1,bf2])

        # Test union
        r=fb1.union(fb1); self.assertEqual(r,fb1)
        r=fb1.union(fb1_alt); self.assertEqual(r,fb1)
        r=fb0.union(fb1,fb2); self.assertEqual(r,fb5)
        r=fb1.union(fb2,[af2,bf3]); self.assertEqual(r,fb4)
        r = fb1 | fb2 | [af2,bf3]; self.assertEqual(r,fb4)  # overload version

        # Test intersection
        r=fb0.intersection(fb1); self.assertEqual(r,fb0)
        r=fb1.intersection(fb1_alt); self.assertEqual(r,fb1)
        r=fb1.intersection(fb2); self.assertEqual(r,FactBase([bf1]))
        r=fb4.intersection(fb2,fb3); self.assertEqual(r,fb0)
        r=fb4.intersection([af2,bf3]); self.assertEqual(r,fb3)
        r=fb4.intersection(FactBase([af1])); self.assertEqual(r,FactBase([af1]))

        r = fb5 & [af1,af2,bf1] ; self.assertEqual(r,[af1,bf1])

        # Test difference
        r=fb0.difference(fb1); self.assertEqual(r,fb0)
        r=fb1.difference(fb1_alt); self.assertEqual(r,fb0)
        r=fb2.difference([af1,bf1]); self.assertEqual(r,FactBase([bf2]))
        r=fb4.difference(fb5); self.assertEqual(r, FactBase([af2,bf3]))
        r = fb4 - fb5;  self.assertEqual(r, FactBase([af2,bf3]))

        # Test symmetric difference
        r=fb1.symmetric_difference(fb1_alt); self.assertEqual(r,fb0)
        r=fb1.symmetric_difference([af2,bf3]); self.assertEqual(r,FactBase([af1,bf1,af2,bf3]))
        r =fb1 ^ [af2,bf3]; self.assertEqual(r,FactBase([af1,bf1,af2,bf3]))

        # Test copy
        r=fb1.copy(); self.assertEqual(r,fb1)

        # Test update()
        fb=FactBase([af1,af2])
        fb.update(FactBase([af3,bf1]),[cf1,cf2])
        self.assertEqual(fb, FactBase([af1,af2,af3,bf1,cf1,cf2]))
        fb=FactBase([af1,af2])
        fb |= [af3,bf1]
        self.assertEqual(fb,FactBase([af1,af2,af3,bf1]))

        # Test intersection()
        fb=FactBase([af1,af2,bf1,cf1])
        fb.intersection_update(FactBase([af1,bf2]))
        self.assertEqual(fb, FactBase([af1]))
        fb=FactBase([af1,af2,bf1,cf1])
        fb.intersection_update(FactBase([af1,bf2]),[af1])
        self.assertEqual(fb, FactBase([af1]))
        fb=FactBase([af1,af2,bf1,cf1])
        fb &= [af1,bf2]
        self.assertEqual(fb, FactBase([af1]))

        # Test difference_update()
        fb=FactBase([af1,af2,bf1])
        fb.difference_update(FactBase([af2,bf2]),[bf3,cf1])
        self.assertEqual(fb, FactBase([af1,bf1]))
        fb=FactBase([af1,af2,bf1])
        fb -= [af2,bf1]
        self.assertEqual(fb, FactBase([af1]))

        # Test symmetric_difference_update()
        fb=FactBase([af1,af2,bf1])
        fb.symmetric_difference_update(FactBase([af2,bf2]))
        self.assertEqual(fb, FactBase([af1,bf1,bf2]))
        fb=FactBase([af1,af2,bf1])
        fb ^= FactBase([cf2])
        self.assertEqual(fb, FactBase([af1,af2,bf1,cf2]))

    #--------------------------------------------------------------------------
    # Test the factbasehelper with double decorators
    #--------------------------------------------------------------------------
    def test_symbolpredicateunifier(self):

        # Using the SymbolPredicateUnifier as a decorator
        spu1 = SymbolPredicateUnifier()
        spu2 = SymbolPredicateUnifier()
        spu3 = SymbolPredicateUnifier(suppress_auto_index=True)

        # decorator both
        @spu3.register
        @spu2.register
        @spu1.register
        class Afact(Predicate):
            num1=IntegerField(index=True)
            num2=IntegerField()
            str1=StringField()

        # decorator without argument
        @spu1.register
        class Bfact(Predicate):
            num1=IntegerField(index=True)
            str1=StringField()

        self.assertEqual(spu1.predicates, (Afact,Bfact))
        self.assertEqual(spu2.predicates, (Afact,))
        self.assertEqual(spu3.predicates, (Afact,))
        self.assertEqual(spu1.indexes, (Afact.num1,Afact.num1))
        self.assertEqual(spu2.indexes, (Afact.num1,))
        self.assertEqual(spu3.indexes, ())

    #--------------------------------------------------------------------------
    # Test the symbolpredicateunifier when there are subfields defined
    #--------------------------------------------------------------------------
    def test_symbolpredicateunifier_with_subfields(self):
        spu = SymbolPredicateUnifier()

        class CT(ComplexTerm):
            a = IntegerField
            b = StringField(index=True)
            c = (IntegerField(index=True),ConstantField)

        @spu.register
        class P(Predicate):
            d = CT.Field(index=True)
            e = CT.Field()

        expected=set([hashable_path(P.d),
                      hashable_path(P.d.b), hashable_path(P.d.c.arg1),
                      hashable_path(P.e.b), hashable_path(P.e.c.arg1)])
        self.assertEqual(spu.predicates, (P,))
        self.assertEqual(set([hashable_path(p) for p in spu.indexes]), set(expected))

        ct_func=Function("ct",[Number(1),String("aaa"),
                               Function("",[Number(1),Function("const",[])])])
        p1=Function("p",[ct_func,ct_func])
        fb=spu.unify(symbols=[p1],raise_on_empty=True)
        self.assertEqual(len(fb),1)
        self.assertEqual(set([hashable_path(p) for p in fb.indexes]), expected)

    #--------------------------------------------------------------------------
    # Test that subclass factbase works and we can specify indexes
    #--------------------------------------------------------------------------

    def test_symbolpredicateunifier_symbols(self):

        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()
            str1=StringField()
        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()
        class Cfact(Predicate):
            num1=IntegerField()

        af1 = Afact(1,10,"bbb")
        af2 = Afact(2,20,"aaa")
        af3 = Afact(3,20,"aaa")
        bf1 = Bfact(1,"aaa")
        bf2 = Bfact(2,"bbb")
        cf1 = Cfact(1)

        raws = [
            Function("afact",[Number(1), Number(10), String("bbb")]),
            Function("afact",[Number(2), Number(20), String("aaa")]),
            Function("afact",[Number(3), Number(20), String("aaa")]),
            Function("bfact",[Number(1),String("aaa")]),
            Function("bfact",[Number(2),String("bbb")]),
            Function("cfact",[Number(1)])
            ]
        spu = SymbolPredicateUnifier(predicates=[Afact,Bfact,Cfact])

        # Test the different ways that facts can be added
        fb = spu.unify(symbols=raws)
        self.assertFalse(fb._delayed_init)
        self.assertEqual(set(fb.predicates), set([Afact,Bfact,Cfact]))
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        fb = spu.unify(symbols=raws, delayed_init=True)
        self.assertTrue(fb._delayed_init)
        self.assertEqual(set(fb.predicates), set([Afact,Bfact,Cfact]))
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        fb = FactBase()
        fb.add([af1,af2,af3])
####        self.assertEqual(fb.add([af1,af2,af3]),3)
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        fb = FactBase()
        fb.add(af1)
        fb.add(af2)
        fb.add(af3)
####        self.assertEqual(fb.add(af1),1)
####        self.assertEqual(fb.add(af2),1)
####        self.assertEqual(fb.add(af3),1)
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        # Test that adding symbols can handle symbols that don't unify
        fb = spu.unify(symbols=raws)
        s_af_all = fb.select(Afact)
        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))

        return

        # Test the specification of indexes
        class MyFactBase3(FactBase):
            predicates = [Afact, Bfact]

        spu = SymbolPredicateUnifier(predicates=[Afact,Bfact,Cfact],
                                     indexes=[Afact.num1, Bfact.num1])

        fb = spu.unify(symbols=raws)
        s = fb.select(Afact).where(Afact.num1 == 1)
        self.assertEqual(s.get_unique(), af1)
        s = fb.select(Bfact).where(Bfact.num1 == 1)
        self.assertEqual(s.get_unique(), bf1)


    #--------------------------------------------------------------------------
    # Test that subclass factbase works and we can specify indexes
    #--------------------------------------------------------------------------

    def test_factbase_copy(self):
        class Afact(Predicate):
            num=IntegerField(index=True)
            pair=(IntegerField, IntegerField(index=True))

        af1=Afact(num=5,pair=(1,2))
        af2=Afact(num=6,pair=(1,2))
        af3=Afact(num=5,pair=(2,3))

        fb1=FactBase([af1,af2,af3],indexes=Afact.meta.indexes)
        fb2=FactBase(list(fb1))
        fb3=FactBase(fb1)

        # The data is the same so they are all equal
        self.assertEqual(fb1, fb2)
        self.assertEqual(fb2, fb3)

        # But the indexes can be different
        self.assertEqual(list(fb1.indexes), list(Afact.meta.indexes))
        self.assertEqual(list(fb2.indexes), [])
        self.assertEqual(list(fb3.indexes), list(fb1.indexes))

#------------------------------------------------------------------------------
# Test the _Select class
#------------------------------------------------------------------------------

class SelectTestCase(unittest.TestCase):
    def setUp(self):
        pass

    #--------------------------------------------------------------------------
    # Test initialising a placeholder (named and positional)
    #--------------------------------------------------------------------------
    def test_placeholder_instantiation(self):

        # Named placeholder with and without default
        p = ph_("test")
        self.assertEqual(type(p), _NamedPlaceholder)
        self.assertFalse(p.has_default)
        self.assertEqual(p.default,None)
        self.assertEqual(str(p), "ph_(\"test\")")

        p = ph_("test",default=0)
        self.assertEqual(type(p), _NamedPlaceholder)
        self.assertTrue(p.has_default)
        self.assertEqual(p.default,0)
        self.assertEqual(str(p), "ph_(\"test\",0)")

        p = ph_("test",default=None)
        self.assertEqual(type(p), _NamedPlaceholder)
        self.assertTrue(p.has_default)
        self.assertEqual(p.default,None)

        # Positional placeholder
        p = ph_(1)
        self.assertEqual(type(p), _PositionalPlaceholder)
        self.assertEqual(p.posn, 0)
        self.assertEqual(str(p), "ph1_")

        # Some bad initialisation
        with self.assertRaises(TypeError) as ctx: ph_(1,2)
        with self.assertRaises(TypeError) as ctx: ph_("a",2,3)
        with self.assertRaises(TypeError) as ctx: ph_("a",default=2,arg=3)

    #--------------------------------------------------------------------------
    #   Test that the select works
    #--------------------------------------------------------------------------
    def test_select_over_factmap(self):
        class Afact1(Predicate):
            num1=IntegerField()
            num2=StringField()
            str1=StringField()
            class Meta: name = "afact"

        fm1 = _FactMap(Afact1, [Afact1.num1,Afact1.str1])
        fm2 = _FactMap(Afact1)
        f1 = Afact1(1,1,"1")
        f3 = Afact1(3,3,"3")
        f4 = Afact1(4,4,"4")
        f42 = Afact1(4,42,"42")
        f10 = Afact1(10,10,"10")
        fm1.add(f1)
        fm1.add(f3)
        fm1.add(f4)
        fm1.add(f42)
        fm1.add(f10)
        fm2.add(f1)
        fm2.add(f3)
        fm2.add(f4)
        fm2.add(f42)
        fm2.add(f10)

        s1_all = fm1.select()
        s1_num1_eq_4 = fm1.select().where(Afact1.num1 == 4)
        s1_num1_ne_4 = fm1.select().where(Afact1.num1 != 4)
        s1_num1_lt_4 = fm1.select().where(Afact1.num1 < 4)
        s1_num1_le_4 = fm1.select().where(Afact1.num1 <= 4)
        s1_num1_gt_4 = fm1.select().where(Afact1.num1 > 4)
        s1_num1_ge_4 = fm1.select().where(Afact1.num1 >= 4)
        s1_str1_eq_4 = fm1.select().where(Afact1.str1 == "4")
        s1_num2_eq_4 = fm1.select().where(Afact1.num2 == 4)

        s2_all = fm1.select()
        s2_num1_eq_4 = fm2.select().where(Afact1.num1 == 4)
        s2_num1_ne_4 = fm2.select().where(Afact1.num1 != 4)
        s2_num1_lt_4 = fm2.select().where(Afact1.num1 < 4)
        s2_num1_le_4 = fm2.select().where(Afact1.num1 <= 4)
        s2_num1_gt_4 = fm2.select().where(Afact1.num1 > 4)
        s2_num1_ge_4 = fm2.select().where(Afact1.num1 >= 4)
        s2_str1_eq_4 = fm2.select().where(Afact1.str1 == "4")
        s2_num2_eq_4 = fm2.select().where(Afact1.num2 == 4)

        self.assertFalse(s1_all._debug())
        self.assertEqual(s1_num1_eq_4._debug()[0], Afact1.num1)
        self.assertTrue(s1_num1_ne_4._debug())
        self.assertTrue(s1_num1_lt_4._debug())
        self.assertTrue(s1_num1_le_4._debug())
        self.assertTrue(s1_num1_gt_4._debug())
        self.assertTrue(s1_num1_ge_4._debug())
        self.assertEqual(s1_str1_eq_4._debug()[0], Afact1.str1)
        self.assertFalse(s1_num2_eq_4._debug())

        self.assertFalse(s2_all._debug())
        self.assertFalse(s2_num1_eq_4._debug())
        self.assertFalse(s2_num1_ne_4._debug())
        self.assertFalse(s2_num1_lt_4._debug())
        self.assertFalse(s2_num1_le_4._debug())
        self.assertFalse(s2_num1_gt_4._debug())
        self.assertFalse(s2_num1_ge_4._debug())
        self.assertFalse(s2_str1_eq_4._debug())
        self.assertFalse(s2_num2_eq_4._debug())

        self.assertEqual(set(list(s1_all.get())), set([f1,f3,f4,f42,f10]))
        self.assertEqual(set(list(s1_num1_eq_4.get())), set([f4,f42]))
        self.assertEqual(set(list(s1_num1_ne_4.get())), set([f1,f3,f10]))
        self.assertEqual(set(list(s1_num1_lt_4.get())), set([f1,f3]))
        self.assertEqual(set(list(s1_num1_le_4.get())), set([f1,f3,f4,f42]))
        self.assertEqual(set(list(s1_num1_gt_4.get())), set([f10]))
        self.assertEqual(set(list(s1_num1_ge_4.get())), set([f4,f42,f10]))
        self.assertEqual(s1_str1_eq_4.get_unique(), f4)
        self.assertEqual(s1_num2_eq_4.get_unique(), f4)

        self.assertEqual(set(list(s2_all.get())), set([f1,f3,f4,f42,f10]))
        self.assertEqual(set(list(s2_num1_eq_4.get())), set([f4,f42]))
        self.assertEqual(set(list(s2_num1_ne_4.get())), set([f1,f3,f10]))
        self.assertEqual(set(list(s2_num1_lt_4.get())), set([f1,f3]))
        self.assertEqual(set(list(s2_num1_le_4.get())), set([f1,f3,f4,f42]))
        self.assertEqual(set(list(s2_num1_gt_4.get())), set([f10]))
        self.assertEqual(set(list(s2_num1_ge_4.get())), set([f4,f42,f10]))
        self.assertEqual(s2_str1_eq_4.get_unique(), f4)
        self.assertEqual(s2_num2_eq_4.get_unique(), f4)


        # Test simple conjunction select
        s1_conj1 = fm1.select().where(Afact1.str1 == "42", Afact1.num1 == 4)
        s1_conj2 = fm1.select().where(Afact1.num1 == 4, Afact1.str1 == "42")
        s1_conj3 = fm1.select().where(lambda x: x.str1 == "42", Afact1.num1 == 4)

        self.assertEqual(s1_conj1._debug()[0], Afact1.num1)
        self.assertEqual(s1_conj2._debug()[0], Afact1.num1)
        self.assertEqual(s1_conj3._debug()[0], Afact1.num1)
        self.assertEqual(s1_conj1.get_unique(), f42)
        self.assertEqual(s1_conj2.get_unique(), f42)
        self.assertEqual(s1_conj3.get_unique(), f42)

        # Test select with placeholders
        s1_ph1 = fm1.select().where(Afact1.num1 == ph_("num1"))
        s1_ph2 = fm1.select().where(Afact1.str1 == ph_("str1","42"),
                                    Afact1.num1 == ph_("num1"))
        self.assertEqual(set(s1_ph1.get(num1=4)), set([f4,f42]))
        self.assertEqual(set(list(s1_ph1.get(num1=3))), set([f3]))
        self.assertEqual(set(list(s1_ph1.get(num1=2))), set([]))
        self.assertEqual(s1_ph2.get_unique(num1=4), f42)
        self.assertEqual(s1_ph2.get_unique(str1="42",num1=4), f42)

        with self.assertRaises(ValueError) as ctx:
            tmp = list(s1_ph1.get_unique(num1=4))  # fails because of multiple values
        with self.assertRaises(TypeError) as ctx:
            tmp = list(s1_ph2.get(num2=5))         # fails because of no values
        with self.assertRaises(TypeError) as ctx:
            tmp = list(s1_ph2.get(str1="42"))


    #--------------------------------------------------------------------------
    # Test select by the predicate object itself (and not a field). This is a
    # boundary case.
    # --------------------------------------------------------------------------

    def test_select_by_predicate(self):

        class Fact(Predicate):
            num1=IntegerField()
            str1=StringField()

        f1 = Fact(1,"bbb")
        f2 = Fact(2,"aaa")
        f2b = Fact(2,"bbb")
        f3 = Fact(3,"aaa")
        f4 = Fact(4,"aaa")
        facts=[f1,f2,f2b,f3,f4]

        self.assertTrue(f1 <= f2)
        self.assertTrue(f1 <= f2b)
        self.assertTrue(f2 <= f2b)
        self.assertTrue(f2b <= f2b)
        self.assertFalse(f3 <= f2b)

        fpb = path(Fact)
        self.assertEqual(f1, fpb(f1))
        self.assertFalse(f2 == fpb(f1))

        fb1 = FactBase(facts=facts, indexes=[path(Fact)])
        fb2 = FactBase(facts=facts)
        self.assertEqual(fb1, fb2)
        self.assertEqual(len(fb1), len(facts))

        s1 = fb1.select(Fact).where(fpb == ph1_)
        self.assertEqual(s1.get(f1), [f1])
        s1 = fb2.select(Fact).where(fpb == ph1_)
        self.assertEqual(s1.get(f1), [f1])

        s2 = fb1.select(Fact).where(fpb <= ph1_).order_by(fpb)
        self.assertEqual(s2.get(f2b), [f1,f2,f2b])
        s2 = fb2.select(Fact).where(fpb <= ph1_).order_by(fpb)
        self.assertEqual(s2.get(f2b), [f1,f2,f2b])

    #--------------------------------------------------------------------------
    # Test basic insert and selection of facts in a factbase
    #--------------------------------------------------------------------------

    def test_factbase_select(self):

        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()
            str1=StringField()
        class Bfact(Predicate):
            num1=IntegerField()
            str1=StringField()
        class Cfact(Predicate):
            num1=IntegerField()

        af1 = Afact(1,10,"bbb")
        af2 = Afact(2,20,"aaa")
        af3 = Afact(3,20,"aaa")
        bf1 = Bfact(1,"aaa")
        bf2 = Bfact(2,"bbb")
        cf1 = Cfact(1)

#        fb = FactBase([Afact.num1, Afact.num2, Afact.str1])
        fb = FactBase()
        facts=[af1,af2,af3,bf1,bf2,cf1]
        fb.add(facts)
#####        self.assertEqual(fb.add(facts), 6)

        self.assertEqual(set(fb.facts()), set(facts))
        self.assertEqual(set(fb.predicates), set([Afact,Bfact,Cfact]))

        s_af_all = fb.select(Afact)
        s_af_num1_eq_1 = fb.select(Afact).where(Afact.num1 == 1)
        s_af_num1_le_2 = fb.select(Afact).where(Afact.num1 <= 2)
        s_af_num2_eq_20 = fb.select(Afact).where(Afact.num2 == 20)
        s_bf_str1_eq_aaa = fb.select(Bfact).where(Bfact.str1 == "aaa")
        s_bf_str1_eq_ccc = fb.select(Bfact).where(Bfact.str1 == "ccc")
        s_cf_num1_eq_1 = fb.select(Cfact).where(Cfact.num1 == 1)

        self.assertEqual(set(s_af_all.get()), set([af1,af2,af3]))
        self.assertEqual(s_af_all.count(), 3)
        self.assertEqual(set(s_af_num1_eq_1.get()), set([af1]))
        self.assertEqual(set(s_af_num1_le_2.get()), set([af1,af2]))
        self.assertEqual(set(s_af_num2_eq_20.get()), set([af2, af3]))
        self.assertEqual(set(s_bf_str1_eq_aaa.get()), set([bf1]))
        self.assertEqual(set(s_bf_str1_eq_ccc.get()), set([]))
        self.assertEqual(set(s_cf_num1_eq_1.get()), set([cf1]))

        fb.clear()
        self.assertEqual(set(s_af_all.get()), set())
        self.assertEqual(set(s_af_num1_eq_1.get()), set())
        self.assertEqual(set(s_af_num1_le_2.get()), set())
        self.assertEqual(set(s_af_num2_eq_20.get()), set())
        self.assertEqual(set(s_bf_str1_eq_aaa.get()), set())
        self.assertEqual(set(s_bf_str1_eq_ccc.get()), set())
        self.assertEqual(set(s_cf_num1_eq_1.get()), set())

        # Test that the select can work with an initially empty factbase
        fb2 = FactBase()
        s2 = fb2.select(Afact).where(Afact.num1 == 1)
        self.assertEqual(set(s2.get()), set())
        fb2.add([af1,af2])
        self.assertEqual(set(s2.get()), set([af1]))

        # Test select with placeholders
#        fb3 = FactBase([Afact.num1])
        fb3 = FactBase()
        fb3.add([af1,af2,af3])
####        self.assertEqual(fb3.add([af1,af2,af3]),3)
        s3 = fb3.select(Afact).where(Afact.num1 == ph_("num1"))
        self.assertEqual(s3.get_unique(num1=1), af1)
        self.assertEqual(s3.get_unique(num1=2), af2)
        self.assertEqual(s3.get_unique(num1=3), af3)


        # Test placeholders with positional arguments
        s4 = fb3.select(Afact).where(Afact.num1 < ph1_)
        self.assertEqual(set(list(s4.get(1))), set([]))
        self.assertEqual(set(list(s4.get(2))), set([af1]))
        self.assertEqual(set(list(s4.get(3))), set([af1,af2]))

        s5 = fb3.select(Afact).where(Afact.num1 <= ph1_, Afact.num2 == ph2_)
        self.assertEqual(set(s5.get(3,10)), set([af1]))

        with self.assertRaises(TypeError) as ctx:
            self.assertEqual(set(list(s5.get(1))), set([]))

        # Test that the fact base index
        fb = FactBase(indexes=[Afact.num2, Bfact.str1])
        self.assertEqual(set([hashable_path(p) for p in fb.indexes]),
                         set([hashable_path(Afact.num2),
                              hashable_path(Bfact.str1)]))

    #--------------------------------------------------------------------------
    # Test factbase select with complex where clause
    #--------------------------------------------------------------------------

    def test_factbase_select_complex_where(self):

        class Afact(Predicate):
            num1=IntegerField
            num2=IntegerField
            str1=StringField

        af1 = Afact(1,10,"bbb")
        af2 = Afact(2,20,"aaa")
        af3 = Afact(3,20,"aaa")
        fb = FactBase([af1,af2,af3])

        q=fb.select(Afact).where((Afact.num1 == 2) | (Afact.num2 == 10))
        self.assertEqual(set([af1,af2]), set(q.get()))

        q=fb.select(Afact).where((Afact.num1 == 2) & (Afact.num2 == 20))
        self.assertEqual(set([af2]), set(q.get()))

        q=fb.select(Afact).where(~(Afact.num1 == 2) & (Afact.num2 == 20))
        self.assertEqual(set([af3]), set(q.get()))

        q=fb.select(Afact).where(~((Afact.num1 == 2) & (Afact.num2 == 20)))
        self.assertEqual(set([af1,af3]), set(q.get()))

    #--------------------------------------------------------------------------
    #   Test that we can use the same placeholder multiple times
    #--------------------------------------------------------------------------
    def test_factbase_select_multi_placeholder(self):
        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()

        fm1 = _FactMap(Afact, [Afact.num1])
        f1 = Afact(1,1)
        f2 = Afact(1,2)
        f3 = Afact(1,3)
        f4 = Afact(2,1)
        f5 = Afact(2,2)

        fm1.add(f1) ; fm1.add(f2) ; fm1.add(f3) ; fm1.add(f4) ; fm1.add(f5)

        s1 = fm1.select().where(Afact.num1 == ph1_, Afact.num2 == ph1_)
        self.assertTrue(set([f for f in s1.get(1)]), set([f1]))
        self.assertTrue(set([f for f in s1.get(2)]), set([f5]))

        s2 = fm1.select().where(Afact.num1 == ph_("a",1), Afact.num2 == ph_("a",2))
        self.assertTrue(set([f for f in s2.get(a=1)]), set([f1]))
        self.assertTrue(set([f for f in s2.get(a=2)]), set([f5]))
        self.assertTrue(set([f for f in s2.get()]), set([f2]))

        # test that we can do different parameters with normal functions
        def tmp(f,a,b=2):
            return f.num1 == a and f.num2 == 2

        s3 = fm1.select().where(tmp)
        with self.assertRaises(TypeError) as ctx:
            r=[f for f in s3.get()]

        self.assertTrue(set([f for f in s3.get(a=1)]), set([f2]))
        self.assertTrue(set([f for f in s3.get(a=1,b=3)]), set([f3]))

        # Test manually created positional placeholders
        s1 = fm1.select().where(Afact.num1 == ph1_, Afact.num2 == ph_(1))
        self.assertTrue(set([f for f in s1.get(1)]), set([f1]))
        self.assertTrue(set([f for f in s1.get(2)]), set([f5]))

    #--------------------------------------------------------------------------
    #   Test that select works with order_by
    #--------------------------------------------------------------------------
    def test_factbase_select_order_by(self):
        class Afact(Predicate):
            num1=IntegerField()
            str1=StringField()
            str2=ConstantField()

        f1 = Afact(num1=1,str1="1",str2="5")
        f2 = Afact(num1=2,str1="3",str2="4")
        f3 = Afact(num1=3,str1="5",str2="3")
        f4 = Afact(num1=4,str1="3",str2="2")
        f5 = Afact(num1=5,str1="1",str2="1")
        fb = FactBase(facts=[f1,f2,f3,f4,f5])

        q = fb.select(Afact).order_by(Afact.num1)
        self.assertEqual([f1,f2,f3,f4,f5], q.get())

        q = fb.select(Afact).order_by(Afact.num1.meta.asc())
        self.assertEqual([f1,f2,f3,f4,f5], q.get())

        q = fb.select(Afact).order_by(asc(Afact.num1))
        self.assertEqual([f1,f2,f3,f4,f5], q.get())

        q = fb.select(Afact).order_by(Afact.num1.meta.desc())
        self.assertEqual([f5,f4,f3,f2,f1], q.get())

        q = fb.select(Afact).order_by(Afact.str2)
        self.assertEqual([f5,f4,f3,f2,f1], q.get())

        q = fb.select(Afact).order_by(Afact.str2.meta.desc())
        self.assertEqual([f1,f2,f3,f4,f5], q.get())

        q = fb.select(Afact).order_by(Afact.str1.meta.desc(), Afact.num1)
        self.assertEqual([f3,f2,f4,f1,f5], q.get())

        q = fb.select(Afact).order_by(desc(Afact.str1), Afact.num1)
        self.assertEqual([f3,f2,f4,f1,f5], q.get())

        # Adding a duplicate object to a factbase shouldn't do anything
        f6 = Afact(num1=5,str1="1",str2="1")
        fb.add(f6)
        q = fb.select(Afact).order_by(desc(Afact.str1), Afact.num1)
        self.assertEqual([f3,f2,f4,f1,f5], q.get())


    #--------------------------------------------------------------------------
    #   Test that select works with order_by for complex term
    #--------------------------------------------------------------------------
    def test_factbase_select_order_by_complex_term(self):

        class SwapField(IntegerField):
            pytocl = lambda x: 100 - x
            cltopy = lambda x: 100 - x

        class AComplex(ComplexTerm):
            swap=SwapField(index=True)
            norm=IntegerField(index=True)

        class AFact(Predicate):
            astr = StringField(index=True)
            cmplx = AComplex.Field(index=True)

        cmplx1 = AComplex(swap=99,norm=1)
        cmplx2 = AComplex(swap=98,norm=2)
        cmplx3 = AComplex(swap=97,norm=3)

        f1 = AFact(astr="aaa", cmplx=cmplx1)
        f2 = AFact(astr="bbb", cmplx=cmplx2)
        f3 = AFact(astr="ccc", cmplx=cmplx3)
        f4 = AFact(astr="ddd", cmplx=cmplx3)

        fb = FactBase(facts=[f1,f2,f3,f4], indexes = [AFact.astr, AFact.cmplx])

        q = fb.select(AFact).order_by(AFact.astr)
        self.assertEqual([f1,f2,f3,f4], q.get())

        q = fb.select(AFact).order_by(AFact.cmplx, AFact.astr)
        self.assertEqual([f3,f4,f2,f1], q.get())

        q = fb.select(AFact).where(AFact.cmplx <= ph1_).order_by(AFact.cmplx, AFact.astr)
        self.assertEqual([f3,f4,f2], q.get(cmplx2))

    #--------------------------------------------------------------------------
    #   Test that select works with order_by for complex term
    #--------------------------------------------------------------------------
    def test_factbase_select_complex_term_placeholders(self):

        class AFact(Predicate):
            astr = StringField()
            cmplx1 = (IntegerField(), IntegerField())
            cmplx2 = (IntegerField(), IntegerField())

        f1 = AFact(astr="aaa", cmplx1=(1,2), cmplx2=(1,2))
        f2 = AFact(astr="bbb", cmplx1=(1,2), cmplx2=(1,5))
        f3 = AFact(astr="ccc", cmplx1=(1,5), cmplx2=(1,5))
        f4 = AFact(astr="ddd", cmplx1=(1,4), cmplx2=(1,2))

        fb = FactBase(facts=[f1,f2,f3,f4])

        q = fb.select(AFact).where(AFact.cmplx1 == (1,2))
        self.assertEqual([f1,f2], q.get())

        q = fb.select(AFact).where(AFact.cmplx1 == ph1_)
        self.assertEqual([f1,f2], q.get((1,2)))

        q = fb.select(AFact).where(AFact.cmplx1 == AFact.cmplx2)
        self.assertEqual([f1,f3], q.get())

        # Some type mismatch failures
        with self.assertRaises(TypeError) as ctx:
            fb.select(AFact).where(AFact.cmplx1 == 1).get()

        # Fail because of type mismatch
        with self.assertRaises(TypeError) as ctx:
            q = fb.select(AFact).where(AFact.cmplx1 == (1,2,3)).get()

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(AFact).where(AFact.cmplx1 == ph1_).get((1,2,3))

    #--------------------------------------------------------------------------
    #   Test that the indexing works
    #--------------------------------------------------------------------------
    def test_factbase_select_indexing(self):
        class Afact(Predicate):
            num1=IntegerField()
            num2=IntegerField()

        fm1 = _FactMap(Afact, [Afact.num1])
        f1 = Afact(1,1)
        f2 = Afact(1,2)
        f3 = Afact(1,3)
        f4 = Afact(2,1)
        f5 = Afact(2,2)
        f6 = Afact(3,1)

        fm1.add(f1); fm1.add(f2); fm1.add(f3); fm1.add(f4); fm1.add(f5); fm1.add(f6)

        # Use a function to track the facts that are visited. This will show
        # that the first operator selects only the appropriate terms.
        facts = set()
        def track(f,a,b):
            nonlocal facts
            facts.add(f)
            return f.num2 == b

        s1 = fm1.select().where(Afact.num1 == ph1_, track)
        s2 = fm1.select().where(Afact.num1 < ph1_, track)

        self.assertTrue(set([f for f in s1.get(2,1)]), set([f4]))
        self.assertTrue(facts, set([f4,f5]))

        self.assertTrue(set([f for f in s2.get(2,2)]), set([f2]))
        self.assertTrue(facts, set([f1,f2,f3]))

    #--------------------------------------------------------------------------
    #   Test the delete
    #--------------------------------------------------------------------------
    def test_delete_over_factmap_and_factbase(self):
        class Afact(Predicate):
            num1=IntegerField()
            num2=StringField()
            str1=StringField()

        fm1 = _FactMap(Afact, [Afact.num1,Afact.str1])
        fm2 = _FactMap(Afact)
        f1 = Afact(1,1,"1")
        f3 = Afact(3,3,"3")
        f4 = Afact(4,4,"4")
        f42 = Afact(4,42,"42")
        f10 = Afact(10,10,"10")
        fm1.add(f1) ; fm2.add(f1)
        fm1.add(f3) ; fm2.add(f3)
        fm1.add(f4) ; fm2.add(f4)
        fm1.add(f42) ; fm2.add(f42)
        fm1.add(f10) ; fm2.add(f10)

        d1_all = fm1.delete()
        d1_num1 = fm2.delete().where(Afact.num1 == ph1_)
        s1_num1 = fm2.select().where(Afact.num1 == ph1_)

        self.assertEqual(d1_all.execute(), 5)
        self.assertEqual(set([f for f in s1_num1.get(4)]), set([f4,f42]))
        self.assertEqual(d1_num1.execute(4), 2)
        self.assertEqual(set([f for f in s1_num1.get(4)]), set([]))

#        return

        fb1 = FactBase(facts=[f1,f3, f4,f42,f10], indexes = [Afact.num1, Afact.num2])
        d1_num1 = fb1.delete(Afact).where(Afact.num1 == ph1_)
        s1_num1 = fb1.select(Afact).where(Afact.num1 == ph1_)
        self.assertEqual(set([f for f in s1_num1.get(4)]), set([f4,f42]))
        self.assertEqual(d1_num1.execute(4), 2)
        self.assertEqual(set([f for f in s1_num1.get(4)]), set([]))

    #--------------------------------------------------------------------------
    # Test the support for indexes of subfields
    #--------------------------------------------------------------------------
    def test_factbase_select_with_subfields(self):
        class CT(ComplexTerm):
            num1=IntegerField()
            str1=StringField()
        class Fact(Predicate):
            ct1=CT.Field()
            ct2=(IntegerField(),IntegerField())
            ct3=(IntegerField(),IntegerField())

        fb = FactBase(indexes=[Fact.ct1.num1, Fact.ct1, Fact.ct2])

        f1=Fact(CT(10,"a"),(3,4),(4,3))
        f2=Fact(CT(20,"b"),(1,2),(2,1))
        f3=Fact(CT(30,"c"),(5,2),(2,5))
        f4=Fact(CT(40,"d"),(6,1),(1,6))

        fb.add(f1); fb.add(f2); fb.add(f3); fb.add(f4);

        # Three queries that uses index
        s1 = fb.select(Fact).where(Fact.ct1.num1 <= ph1_).order_by(Fact.ct2)
        s2 = fb.select(Fact).where(Fact.ct1 == ph1_)
        s3 = fb.select(Fact).where(Fact.ct2 == ph1_)
        s4 = fb.select(Fact).where(Fact.ct3 == ph1_)

        self.assertEqual(s1.get(20), [f2,f1])
        self.assertEqual(s2.get(CT(20,"b")), [f2])
        self.assertEqual(s3.get((1,2)), [f2])
        self.assertEqual(s4.get((2,1)), [f2])

        # One query doesn't use the index
        s4 = fb.select(Fact).where(Fact.ct1.str1 == ph1_)
        self.assertEqual(s4.get("c"), [f3])

    #--------------------------------------------------------------------------
    #   Test badly formed select/delete statements where the where clause (or
    #   order by clause for select statements) refers to fields that are not
    #   part of the predicate being queried. Instead of creating an error at
    #   query time creating the error when the statement is declared can help
    #   with debugging.
    #   --------------------------------------------------------------------------
    def test_bad_factbase_select_delete_statements(self):
        class F(Predicate):
            num1=IntegerField()
            num2=IntegerField()
        class G(Predicate):
            num1=IntegerField()
            num2=IntegerField()

        f = F(1,2)
        fb = FactBase([f])

        # Making multiple calls to select where()
        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).where(F.num1 == 1).where(F.num2 == 2)
        check_errmsg("cannot specify 'where' multiple times",ctx)

        # Bad select where clauses
        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).where()
        check_errmsg("empty 'where' expression",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).where(G.num1 == 1)
        check_errmsg("'where' expression contains path 'G.num1'",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).where(F.num1 == G.num1)
        check_errmsg("'where' expression contains path 'G.num1'",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).where(F.num1 == 1, G.num1 == 1)
        check_errmsg("'where' expression contains path 'G.num1'",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).where(0)
        check_errmsg("'int' object is not callable",ctx)

        # Bad delete where clause
        with self.assertRaises(TypeError) as ctx:
            q = fb.delete(F).where(G.num1 == 1)
        check_errmsg("'where' expression contains path 'G.num1'",ctx)


        # Making multiple calls to select order_by()
        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).order_by(F.num1).order_by(F.num2)
        check_errmsg("cannot specify 'order_by' multiple times",ctx)

        # Bad select where clauses
        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).order_by()
        check_errmsg("empty 'order_by' expression",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).order_by(1)
        check_errmsg("Invalid 'order_by' expression",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).order_by(G.num1)
        check_errmsg("'order_by' expression contains path 'G.num1'",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).order_by(F.num1,G.num1)
        check_errmsg("'order_by' expression contains path 'G.num1'",ctx)

        with self.assertRaises(TypeError) as ctx:
            q = fb.select(F).order_by(F.num1,desc(G.num1))
        check_errmsg("'order_by' expression contains path 'G.num1'",ctx)


#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------

class TypeCastSignatureTestCase(unittest.TestCase):
    def setUp(self):
        class DateField(StringField):
            pytocl = lambda dt: dt.strftime("%Y%m%d")
            cltopy = lambda s: datetime.datetime.strptime(s,"%Y%m%d").date()

        class DowField(ConstantField):
            pytocl = lambda dt: calendar.day_name[dt.weekday()].lower()

        class EDate(ComplexTerm):
            idx = IntegerField()
            date = DateField()
            class Meta: name="edate"

        self.DateField = DateField
        self.DowField = DowField
        self.EDate = EDate

    #--------------------------------------------------------------------------
    # Test the signature generation for writing python functions that can be
    # called from ASP.
    # --------------------------------------------------------------------------

    def test_signature(self):

        DateField = self.DateField
        DowField = self.DowField
        EDate = self.EDate

        sig1 = TypeCastSignature(DateField)     # returns a single date
        sig2 = TypeCastSignature([DateField])   # returns a list of dates
        sig3 = TypeCastSignature(DateField, DowField)  # takes a date and returns the day or week

        sig4 = TypeCastSignature(EDate.Field,EDate.Field)    # takes an EDate and returns an EDate

        # Some bad declarations
        with self.assertRaises(TypeError) as ctx:
            sig5 = TypeCastSignature(int)
        with self.assertRaises(TypeError) as ctx:
            sig5 = TypeCastSignature(DateField, int)
        with self.assertRaises(TypeError) as ctx:
            sig5 = TypeCastSignature(DateField, [int])
        with self.assertRaises(TypeError) as ctx:
            sig5 = TypeCastSignature(DateField, [DateField, DateField])

        date1 = datetime.date(2018,1,1)
        date2 = datetime.date(2019,2,2)

        edate1 = EDate(idx=1, date=date1)
        edate2 = EDate(idx=2, date=date2)

        # Test simple output and list output

        def getdate1() : return date1
        def getdates() : return [date1, date2]

        cl_getdate1 = sig1.wrap_function(getdate1)
        cl_getdates = sig2.wrap_function(getdates)
        self.assertEqual(cl_getdate1(), String("20180101"))
        self.assertEqual(cl_getdates(), [String("20180101"), String("20190202")])

        # Use decoractor mode

        @sig3.wrap_function
        def getdow(dt) : return dt
        result = getdow(String("20180101"))
        self.assertEqual(result, Function("monday",[]))

        # Test a ComplexTerm input and output
        @sig4.wrap_function
        def getedate(indate): return indate
        self.assertEqual(getedate(edate1.raw), edate1.raw)
        self.assertEqual(getedate(edate2.raw), edate2.raw)

        # Now test the method wrapper
        class Tmp(object):
            def __init__(self,x,y):
                self._x = x
                self._y = y

            def get_pair(self):
                return [self._x, self._y]

            cl_get_pair = sig2.wrap_method(get_pair)

        t = Tmp(date1,date2)
        self.assertEqual(t.cl_get_pair(), [String("20180101"), String("20190202")])

    #--------------------------------------------------------------------------
    # Test the extended signatures with tuples
    # --------------------------------------------------------------------------

    def test_signature_with_tuples(self):
        DateField = self.DateField

        # Some complicated signatures
        sig1 = TypeCastSignature((IntegerField, DateField),(IntegerField, DateField))
        sig2 = TypeCastSignature(DateField,[(IntegerField, DateField)])

        @sig1.wrap_function
        def test_sig1(pair) : return (pair[0],pair[1])

        @sig2.wrap_function
        def test_sig2(dt): return [(1,dt),(2,dt)]

        s_raw = String("20180101")
        t1_raw = Function("",[Number(1), s_raw])
        t2_raw = Function("",[Number(2), s_raw])

#        result = test_sig1(t1_raw)
        self.assertEqual(test_sig1(t1_raw),t1_raw)
        self.assertEqual(test_sig2(s_raw),[t1_raw,t2_raw])

    #--------------------------------------------------------------------------
    # Test using function annotations and reporting better errors
    #--------------------------------------------------------------------------
    def test_get_annotations_errors(self):

        IF=IntegerField

        with self.assertRaises(TypeError) as ctx:
            def bad() -> IF : return 1
            s = _get_annotations(bad,True)
        check_errmsg("Cannot ignore", ctx)

        with self.assertRaises(TypeError) as ctx:
            def bad(a : IF, b : IF) : return 1
            s = _get_annotations(bad)
        check_errmsg("Missing function", ctx)

        with self.assertRaises(TypeError) as ctx:
            def bad(a, b) -> IF : return 1
            s = _get_annotations(bad)
        check_errmsg("Missing type cast", ctx)

        with self.assertRaises(TypeError) as ctx:
            def bad(a : IF, b) -> IF : return 1
            s = _get_annotations(bad)
        check_errmsg("Missing type cast", ctx)

    #--------------------------------------------------------------------------
    # Test the signature generation for writing python functions that can be
    # called from ASP.
    # --------------------------------------------------------------------------

    def test_make_function_asp_callable(self):

        DateField = self.DateField
        DowField = self.DowField
        EDate = self.EDate

        date1 = datetime.date(2018,1,1)
        date2 = datetime.date(2019,2,2)

        edate1 = EDate(idx=1, date=date1)
        edate2 = EDate(idx=2, date=date2)

        def getdate1() : return date1
        def getdates() : return [date1, date2]

        # Test wrapper as a normal function and specifying a signature
        cl_getdate1 = make_function_asp_callable(DateField, getdate1)
        self.assertEqual(cl_getdate1(), String("20180101"))

        cl_getdates = make_function_asp_callable([DateField], getdates)
        self.assertEqual(cl_getdates(), [String("20180101"), String("20190202")])

        # Test wrapper as a decorator and specifying a signature
        @make_function_asp_callable(DateField)
        def getdate1() : return date1
        self.assertEqual(getdate1(), String("20180101"))

        @make_function_asp_callable([DateField])
        def getdates() : return [date1, date2]
        self.assertEqual(getdates(), [String("20180101"), String("20190202")])

        @make_function_asp_callable
        def getdates2(x: DateField, y : EDate.Field) -> [DateField]:
            '''GETDATES2'''
            return [date1,date2]
        self.assertEqual(getdates2(String("20180101"), edate1.raw),
                         [String("20180101"), String("20190202")])
        self.assertEqual(getdates2.__doc__, '''GETDATES2''')

        with self.assertRaises(TypeError) as ctx:
            @make_function_asp_callable
            def getdates3(x,y): return [date1,date2]

        with self.assertRaises(TypeError) as ctx:
            @make_function_asp_callable
            def getdates4(x : DateField, y : DateField): return [date1,date2]

        # Now test the method wrapper
        class Tmp(object):
            def __init__(self,x,y):
                self._x = x
                self._y = y

            def get_pair(self):
                return [self._x, self._y]

            cl_get_pair = make_method_asp_callable([DateField], get_pair)

            @make_method_asp_callable
            def get_pair2(self) -> [DateField]:
                return [self._x, self._y]

        t = Tmp(date1,date2)
        self.assertEqual(t.cl_get_pair(), [String("20180101"), String("20190202")])
        self.assertEqual(t.get_pair2(), [String("20180101"), String("20190202")])


    def test_make_function_asp_callable_with_tuples(self):
        DateField = self.DateField

        # Some complicated signatures
        sig1 = TypeCastSignature((IntegerField, DateField),(IntegerField, DateField))
        sig2 = TypeCastSignature(DateField,[(IntegerField, DateField)])

        @make_function_asp_callable
        def test_sig1(pair : (IntegerField,DateField)) -> (IntegerField,DateField):
            return (pair[0],pair[1])

        @make_function_asp_callable
        def test_sig2(dt : DateField) -> [(IntegerField,DateField)]:
            return [(1,dt),(2,dt)]

        s_raw = String("20180101")
        t1_raw = Function("",[Number(1), s_raw])
        t2_raw = Function("",[Number(2), s_raw])

#        result = test_sig1(t1_raw)
        self.assertEqual(test_sig1(t1_raw),t1_raw)
        self.assertEqual(test_sig2(s_raw),[t1_raw,t2_raw])

    #--------------------------------------------------------------------------
    # Test that the input signature can be hashed
    # --------------------------------------------------------------------------
    def test_input_signature(self):
        DateField = self.DateField

        # Some complicated signatures
        sig1 = TypeCastSignature((IntegerField, DateField),(IntegerField, DateField))
        sig2 = TypeCastSignature(DateField,[(IntegerField, DateField)])
        sigs={}
        sigs[sig1.input_signature] = sig1
        sigs[sig2.input_signature] = sig2
        self.assertEqual(sigs[sig1.input_signature], sig1)
        self.assertEqual(sigs[sig2.input_signature], sig2)

#------------------------------------------------------------------------------
# Tests for the ContextBuilder
#------------------------------------------------------------------------------

class ContextBuilderTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test_register(self):

        SF=StringField
        IF=IntegerField
        CF=ConstantField
        # Functions to add to the context
        def add(a: IF, b: IF) -> IF: return a+b
        def mirror(val : CF) -> CF: return val

        self.assertEqual(add(1,4),5)
        self.assertEqual(mirror("aname"),"aname")

        # Test the register function as a non-decorator
        cb1=ContextBuilder()
        cb1.register(add)
        cb1.register(mirror)
        ctx1 = cb1.make_context()
        self.assertEqual(type(ctx1).__name__, "Context")
        self.assertTrue("add" in type(ctx1).__dict__)
        self.assertTrue("mirror" in type(ctx1).__dict__)

        n1=Number(1); n2=Number(2); n3=Number(3); n4=Number(4)
        c1=Function("aname")
        self.assertEqual(ctx1.add(n1,n3),n4)
        self.assertEqual(ctx1.mirror(c1),c1)

        # Test registering functions but using external signatures
        def add2(a,b): return a+b
        def mirror2(val): return val

        cb2=ContextBuilder()
        cb2.register(IF,IF,IF,add2)
        cb2.register(CF,CF,mirror2)
        ctx2 = cb2.make_context("Ctx2")
        self.assertEqual(type(ctx2).__name__, "Ctx2")
        self.assertEqual(ctx2.add2(n1,n3),n4)
        self.assertEqual(ctx2.mirror2(c1),c1)

        # Test the register function as a decorator
        cb3=ContextBuilder()

        @cb3.register
        def add2(a: IF, b: IF) -> IF: return a+b
        self.assertEqual(add2(1,2),3)

        @cb3.register(IF,IF,IF)
        def add4(a, b): return a+b
        self.assertEqual(add4(1,2),3)

        ctx3=cb3.make_context()
        self.assertEqual(ctx3.add2(n1,n2),n3)
        self.assertEqual(ctx3.add4(n1,n2),n3)


    def test_register_name(self):
        SF=StringField
        IF=IntegerField
        CF=ConstantField

        n1=Number(1); n2=Number(2); n3=Number(3); n4=Number(4)
        s1=String("ab"); s2=String("cd"); s3=String("abcd")
        c1=Function("ab",[]); c2=Function("cd",[]); c3=Function("abcd",[]);
        # Test the register_name as a decorator
        cb1=ContextBuilder()

        @cb1.register_name("addi")                 # use function annotations
        def add1(a: IF, b: IF) -> IF: return a+b   # external signature
        self.assertEqual(add1(1,2),3)

        @cb1.register_name("adds", SF,SF,SF)
        def add2(a, b): return a+b
        self.assertEqual(add2("ab","cd"),"abcd")

        # Non-decorator call - re-using a function but with a different signature
        cb1.register_name("addc", CF,CF,CF, add1)

        # Non-decorator call - setting a function with the function annotation
        cb1.register_name("addi_alt", add1)

        ctx1=cb1.make_context()
        self.assertEqual(ctx1.addi(n1,n2),n3)
        self.assertEqual(ctx1.addi_alt(n1,n2),n3)
        self.assertEqual(ctx1.adds(s1,s2),s3)
        self.assertEqual(ctx1.addc(c1,c2),c3)

        # Things that should fail
        with self.assertRaises(TypeError) as ctx:
            self.assertEqual(ctx1.addc(s1,s2),s3)

        with self.assertRaises(TypeError) as ctx:
            self.assertEqual(ctx1.addc(s1,s2),c3)

        # Fails since add2 has no function annotations
        with self.assertRaises(TypeError) as ctx:
            cb1.register_name("addo",add2)

        # Function name already assigned
        with self.assertRaises(ValueError) as ctx:
            cb1.register_name("addi",add1)

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
