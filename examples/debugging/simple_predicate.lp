   bid(dave,chair,8). bid(morri,chair,10). bid(michael,chair,12).
   bid(dave,car,80). bid(morri,car,70).
   bid(michael,truck,100).

   num_bids(I,C) :- C = #count{ P,B : bid(P,I,B) }, bid(_,I,_).
   max_num_bids(I) :- num_bids(I,C), #false : num_bids(_,C2), C2 > C.
   max_bid(P,I,B) :- bid(P,I,B), max_num_bids(I), #false : bid(_,I,B2), B2 > B.

#show.
#script(python).

from clorm.clingo import Control
from clorm import Predicate, ConstantField, IntegerField, simple_predicate, desc
from clorm import ph1_

class Max_Bid(Predicate):
    bidder=ConstantField
    item=ConstantField
    price=IntegerField

NB=simple_predicate("num_bids",2)

#--------------------------------------------------------------------------
# main
#--------------------------------------------------------------------------

# Print the model
def on_model(model):
    fb = model.facts(atoms=True)

    # Print the important parts
    max_bid = fb.select(Max_Bid).get_unique()
    print("-------------------")
    print("Highest bid for item with the most bids\n")
    print("Bidder: {}".format(max_bid.bidder))
    print("Item: {}".format(max_bid.item))
    print("Price: ${}".format(max_bid.price))

    # Now print some debugging information
    print("\n-------------------")
    q=fb.select(NB).order_by(desc(NB[1]))
    for nb in q.get():
        print("{}".format(nb))
    print("-------------------")

def main(ctrl_):
    # For better integration with Clorm wrap the clingo.Control object with a
    ctrl = Control(control_=ctrl_, unifier=[Max_Bid,NB])


    # Add the instance data and ground the ASP program
    ctrl.ground([("base",[])])

    ctrl.solve(on_model=on_model)

#end.
