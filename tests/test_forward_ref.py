import importlib.util
import inspect
import secrets
import sys
import tempfile
import textwrap
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType

from clingo import Number, String

__all__ = [
    "ForwardRefTestCase",
]


def _extract_source_code_from_function(function):
    if function.__code__.co_argcount:
        raise RuntimeError(f"function {function.__qualname__} cannot have any arguments")

    code_lines = ""
    body_started = False
    for line in textwrap.dedent(inspect.getsource(function)).split("\n"):
        if line.startswith("def "):
            body_started = True
            continue
        elif body_started:
            code_lines += f"{line}\n"

    return textwrap.dedent(code_lines)


def _create_module_file(code, tmp_path, name):
    name = f"{name}_{secrets.token_hex(5)}"
    path = Path(tmp_path, f"{name}.py")
    path.write_text(code)
    return name, str(path)


def create_module(tmp_path, method_name):
    def run(source_code_or_function):
        """
        Create module object, execute it and return

        :param source_code_or_function string or function with body as a source code for created module

        """
        if isinstance(source_code_or_function, FunctionType):
            source_code = _extract_source_code_from_function(source_code_or_function)
        else:
            source_code = source_code_or_function

        module_name, filename = _create_module_file(source_code, tmp_path, method_name)

        spec = importlib.util.spec_from_file_location(module_name, filename, loader=None)
        sys.modules[module_name] = module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return run


class ForwardRefTestCase(unittest.TestCase):
    def setUp(self):
        @contextmanager
        def f(source_code_or_function):
            with tempfile.TemporaryDirectory() as tmp_path:
                yield create_module(tmp_path, self._testMethodName)(source_code_or_function)

        self._create_module = f

    def test_postponed_annotations(self):
        code = """
from __future__ import annotations
from clorm import Predicate

class P1(Predicate):
    a: int
    b: str
"""
        with self._create_module(code) as module:
            p = module.P1(a=3, b="42")
            self.assertEqual(str(p), 'p1(3,"42")')

    def test_postponed_annotations_inner_class_basic(self):
        code = """
from __future__ import annotations
from clorm import Predicate

class Outer(Predicate):
    class Inner(Predicate):
        a: int
    b: Inner
"""
        with self._create_module(code) as module:
            inner = module.Outer.Inner(a=3)
            outer = module.Outer(b=inner)
            self.assertEqual(str(outer), "outer(inner(3))")

    def test_postponed_annotations_inner_class_complex(self):
        """Test a complex case with inner classes across different bases classes.

        Note: I think the internal implementation functionality of this test is already covered
        by other tests, but adding this for peace of mind.

        """
        code = """
from __future__ import annotations
from clorm import Predicate

class Outer(Predicate):
    class Inner(Predicate):
        a: int
    b: Inner

class NonPredicate:
    class Inner(Predicate):
        a: Outer
        b: Outer.Inner
"""
        with self._create_module(code) as module:
            inner = module.Outer.Inner(a=3)
            outer = module.Outer(b=inner)
            npinner = module.NonPredicate.Inner(a=outer, b=inner)
            self.assertEqual(str(npinner), "inner(outer(inner(3)),inner(3))")

    def test_postponed_annotations_complex(self):
        code = """
from __future__ import annotations
from clorm import Predicate
from typing import Union

class P1(Predicate):
    a: int
    b: str

class P2(Predicate):
    a: int

class P3(Predicate):
    a: 'Union[P1, P2]'
"""
        with self._create_module(code) as module:
            p = module.P3(a=module.P1(a=3, b="42"))
            self.assertEqual(str(p), 'p3(p1(3,"42"))')
            p = module.P3(a=module.P2(a=42))
            self.assertEqual(str(p), "p3(p2(42))")

    def test_postponed_annotations_complex2(self):
        code = """
from __future__ import annotations
from clorm import Predicate
from typing import Union

class P1(Predicate):
    a: int
    b: str

class P2(Predicate):
    a: int

class P3(Predicate):
    a: P1 | P2
"""
        if sys.version_info >= (3, 10):
            with self._create_module(code) as module:
                p = module.P3(a=module.P1(a=3, b="42"))
                self.assertEqual(str(p), 'p3(p1(3,"42"))')
                p = module.P3(a=module.P2(a=42))
                self.assertEqual(str(p), "p3(p2(42))")

    def test_postponed_annotations_complex3(self):
        code = """
from __future__ import annotations
from clorm import Predicate
from typing import Union

class P1(Predicate):
    a: int
    b: str

class P2(Predicate):
    a: int

class P3(Predicate):
    a: 'P1 | P2'
"""
        if sys.version_info >= (3, 10):
            with self._create_module(code) as module:
                p = module.P3(a=module.P1(a=3, b="42"))
                self.assertEqual(str(p), 'p3(p1(3,"42"))')
                p = module.P3(a=module.P2(a=42))
                self.assertEqual(str(p), "p3(p2(42))")

    def test_postponed_annotations_tuple1(self):
        code = """
from __future__ import annotations
from clorm import Predicate

class P(Predicate):
    a: tuple[int, str]
"""
        if sys.version_info >= (3, 10):
            with self._create_module(code) as module:
                p = module.P(a=(123, "Hello"))
                self.assertEqual(str(p), 'p((123,"Hello"))')

    def test_postponed_annotations_tuple1(self):
        code = """
from __future__ import annotations
from clorm import Predicate
from typing import Tuple

class P(Predicate):
    a: Tuple[int, str]
"""
        with self._create_module(code) as module:
            p = module.P(a=(123, "Hello"))
            self.assertEqual(str(p), 'p((123,"Hello"))')

    def test_postponed_annotations_nonglobal1(self):
        code = """
from __future__ import annotations
from clorm import Predicate, ConstantField, field
from typing import Union

def define_predicates():


    class P1(Predicate):
        a1: str = field(ConstantField)
        a: int
        b: str

    class P2(Predicate):
        a: Union[int, P1]

    return P1, P2

XP1, XP2 = define_predicates()

"""
        with self._create_module(code) as module:
            p1 = module.XP1(a1="c", a=3, b="42")
            self.assertEqual(str(p1), 'p1(c,3,"42")')
            p2 = module.XP2(a=p1)
            self.assertEqual(str(p2), 'p2(p1(c,3,"42"))')

    def test_postponed_annotations_nonglobal2(self):
        code = """
from __future__ import annotations
from clorm import Predicate, ConstantField, field
from typing import Union

def define_predicates():


    class P1(Predicate):
        a1: str = field(ConstantField)
        a: int
        b: str

    def define_complex():
        class P2(Predicate):
            a: Union[int, P1]
        return P2

    return P1, define_complex()

XP1, XP2 = define_predicates()

"""
        with self._create_module(code) as module:
            p1 = module.XP1(a1="c", a=3, b="42")
            self.assertEqual(str(p1), 'p1(c,3,"42")')
            p2 = module.XP2(a=p1)
            self.assertEqual(str(p2), 'p2(p1(c,3,"42"))')

    def test_postponed_annotations_headlist(self):
        code = """
from __future__ import annotations
from typing import Tuple
from clorm import Predicate, HeadList

class P(Predicate):
    x: HeadList[Tuple[int,str]]
"""
        with self._create_module(code) as module:
            p = module.P(x=((1, "a"), (2, "b")))
            self.assertEqual(str(p), 'p(((1,"a"),((2,"b"),())))')

    def test_postponed_annotations_flatlist(self):
        code = """
from __future__ import annotations
from typing import Tuple
from clorm import Predicate

class P(Predicate):
    x: Tuple[Tuple[int,str], ...]
"""
        with self._create_module(code) as module:
            p = module.P(x=((1, "a"), (2, "b")))
            self.assertEqual(str(p), 'p(((1,"a"),(2,"b")))')

    def test_forward_ref(self):
        def module_():
            from typing import ForwardRef

            from clorm import Predicate

            class A(Predicate):
                a: int

            ARef = ForwardRef("A")

            class B(Predicate):
                a: ARef

        with self._create_module(module_) as module:
            b = module.B(a=module.A(a=42))
            self.assertEqual(str(b), "b(a(42))")

    def test_forward_ref_list(self):
        def module_():
            from typing import ForwardRef

            from clorm import HeadList, Predicate

            class A(Predicate):
                a: int

            ARef = ForwardRef("A")

            class B(Predicate):
                a: HeadList[ARef]

        with self._create_module(module_) as module:
            b = module.B(a=[module.A(a=41), module.A(a=42)])
            self.assertEqual(str(b), "b((a(41),(a(42),())))")

    def test_forward_ref_asp_callable(self):
        code = """
from __future__ import annotations
from clorm import Predicate, make_function_asp_callable, make_method_asp_callable

class P1(Predicate):
    a: int
    b: str

@make_function_asp_callable
def f(a: int, b: str) -> P1:
    return P1(a,b)

class Context:
    @make_method_asp_callable
    def f(self, a: int, b: str) -> P1:
        return P1(a,b)
"""
        with self._create_module(code) as module:
            p = module.f(Number(2), String("2"))
            self.assertEqual(str(p), 'p1(2,"2")')
            ctx = module.Context()
            p = ctx.f(Number(2), String("2"))
            self.assertEqual(str(p), 'p1(2,"2")')
