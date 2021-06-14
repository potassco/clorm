#show.
#script(python)

from clorm.clingo import Control,Symbol
from clorm import Predicate, ConstantField, IntegerField, simple_predicate, desc
from clorm import ph1_

from clorm import Predicate, ComplexTerm, StringField

class Location(ComplexTerm):
    city = StringField
    country = StringField

class Booking(Predicate):
    date=StringField
    location=Location.Field

Booking_alt=simple_predicate("booking",2)

bk=Booking(date="2018-12-31", location=Location(city="Sydney",country="Australia"))

bk_alt=Booking_alt(raw=bk.raw)

print("{} : {}".format(bk_alt[1], type(bk_alt[1])))
assert type(bk_alt[1]) == Symbol
#end.
