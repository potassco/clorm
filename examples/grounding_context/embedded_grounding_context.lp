% -----------------------------------------------------------------------------
% This example shows how to use the Clorm ContextBuilder to specify a set of
% Python functions for the clingo grounding context. It highlists the
% flexibility of using ContextBuilder. For example, Python annotations can be
% used to specify a type conversion signature, and the same function can be
% re-used with a different name and different type conversion signature.
% -----------------------------------------------------------------------------

f(@addi(1,4)).
g(@addi_alt(2,4)).
h(@adds("ab","cd")).

#script(python).

from clorm import IntegerField,StringField,ContextBuilder

# Convenient aliases
IF=IntegerField
SF=StringField
cb=ContextBuilder()

# Register the "addi" function and register a type conversion signature to add
# two numbers.
@cb.register
def addi(a : IF, b : IF) -> IF : return a+b

# Register a function but use a different name for the clingo context
# "addi_alt".
@cb.register_name("addi_alt")
def add2(a : IF, b : IF) -> IF : return a+b

# Register the previously defined add2 function with the name "adds" and use it
# to concatanate strings.
cb.register_name("adds", SF, SF, SF, addi)

ctx=cb.make_context()

def main(prg):
  prg.ground([("base",[])],context=ctx)
  prg.solve()

#end.
