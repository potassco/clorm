
    ?start : [ fact* ]

    fact : function [ END ]

    function : [ NEGATE ] NAME [ args ]

    tuple : args

    args : "(" [ param ("," param)* ] ")"

    ?param : tuple
           | function
           | STRING
           | NUMBER

    END : "."
    NEGATE : "-"
    NAME : /[a-z]+[a-zA-Z0-9_]*/


    %import common.ESCAPED_STRING -> STRING
    %import common.SIGNED_NUMBER -> NUMBER
    %import common.WS
    %ignore WS

