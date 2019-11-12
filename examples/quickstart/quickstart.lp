%----------------------------------------------------------------------------------
% Domain encoding for a simple scheduling problem. Drivers need to make
% deliveries.  Every driver has a fixed base cost and every delivery has a
% cost. We also need deliveries within a time limit.
% ----------------------------------------------------------------------------------


time(1..4).

1 { assignment(I, D, T) : driver(D), time(T) } 1 :- item(I).
:- assignment(I1, D, T), assignment(I2, D, T), I1 != I2.

working_driver(D) :- assignment(_,D,_).

#minimize { 1@2,D : working_driver(D) }.
#minimize { T@1,D : assignment(_,D,T) }.
