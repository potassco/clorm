
f(@addi(1,4)).
g(@addi_alt(2,4)).
h(@adds("ab","cd")).

#script(python).

from clorm import IntegerField,StringField,ContextBuilder

IF=IntegerField
SF=StringField
cb=ContextBuilder()

@cb.register
def addi(a : IF, b : IF) -> IF : return a+b

@cb.register_name("addi_alt")
def add2(a : IF, b : IF) -> IF : return a+b

cb.register_name("adds", SF, SF, SF, addi)

ctx=cb.make_context()

def main(prg):
  prg.ground([("base",[])],context=ctx)
  prg.solve()

#end.
