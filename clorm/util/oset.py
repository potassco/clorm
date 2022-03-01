# -----------------------------------------------------------------------------
# Using collections.OrderedDict to implement an OrderedSet (i.e., insertion
# ordered set).
# ------------------------------------------------------------------------------

from collections import OrderedDict

# ------------------------------------------------------------------------------
#
# ------------------------------------------------------------------------------

class OrderedSet(object):
    def __init__(self,iterable=[]):
        self._dict=OrderedDict([(elem,True) for elem in iterable])

    def add(self,elem):
        self._dict[elem]=True

    def remove(self,elem):
        del self._dict[elem]

    def discard(self,elem):
        self._dict.pop(elem,None)

    def pop(self,last=True):
        return self._dict.popitem(last)[0]

    def clear(self):
        self._dict.clear()

    def copy(self):
        tmp = OrderedSet()
        tmp._dict = self._dict.copy()
        return tmp

    #--------------------------------------------------------------------------
    # Boolean set functions
    #--------------------------------------------------------------------------
    def isdisjoint(self,other):
        for elem in self._dict:
            if elem in other: return False
        for elem in other:
            if elem in self._dict: return False
        return True

    def issubset(self,other):
        for elem in self._dict:
            if elem not in other: return False
        return True

    def issuperset(self,other):
        for elem in other:
            if elem not in self._dict: return False
        return True

    # Since __eq__ will return False for two OrderedSets with same elements but
    # a different order so provide a separate function.
    def isequal(self,other):
        if not isinstance(other, self.__class__): return NotImplemented
        if len(self) != len(other): return False
        for elem in self._dict.keys():
            if elem not in other._dict: return False
        return True

    #--------------------------------------------------------------------------
    # Set operations
    #--------------------------------------------------------------------------
    def union(self,*others):
        tmp=self.copy()
        for other in others:
            if isinstance(other, self.__class__):
                tmp._dict.update(other._dict)
            else:
                tmp._dict.update({key:True for key in other})
        return tmp

    def intersection(self,*others):
        tmp = self.copy()
        if not others: return tmp
        tmp2=set(self._dict.keys()).intersection(*others)
        for key in self._dict.keys():
            if key not in tmp2: tmp._dict.pop(key,None)
        return tmp

    def difference(self,*others):
        tmp = self.copy()
        if not others: return tmp
        tmp2 = set()
        tmp2.update(*others)
        for key in tmp2: tmp._dict.pop(key,None)
        return tmp

    def symmetric_difference(self,other):
        tmp = set(self._dict.keys())
        tmp.intersection_update(other)
        tmp2 = self.union(other)
        for key in tmp: del tmp2._dict[key]
        return tmp2

    def update(self,*others):
        for other in others:
            if isinstance(other, self.__class__):
                self._dict.update(other._dict)
            else:
                self._dict.update({key:True for key in other})

    def intersection_update(self,*others):
        if not others: return
        tmp = set(self._dict.keys())
        tmp2=set(tmp).intersection(*others)
        for key in tmp:
            if key not in tmp2: del self._dict[key]

    def difference_update(self,*others):
        if not others: return
        tmp2 = set()
        tmp2.update(*others)
        for key in tmp2: self._dict.pop(key,None)

    def symmetric_difference_update(self, other):
        tmp = set(self._dict.keys())
        tmp.intersection_update(other)
        self.update(other)
        for key in tmp: del self._dict[key]


    #--------------------------------------------------------------------------
    # Special functions to support set and container operations
    #--------------------------------------------------------------------------

    def __contains__(self, elem):
        """Implemement set 'in' operator."""
        return elem in self._dict

    def __bool__(self):
        """Implemement set bool operator."""
        return bool(self._dict)

    def __len__(self):
        return len(self._dict)

    def __iter__(self):
        for k,v in self._dict.items():
            yield k

    def __eq__(self, other):
        # Not sure why this shouldn't raise a TypeError for set but I want the
        # behaviour to be consistent with standard set.
        """Overloaded boolean operator."""
        if isinstance(other, self.__class__):
            return self._dict == other._dict
        elif isinstance(other, set):
            if len(self) != len(other): return False
            if not self.issubset(other): return False
            return self.issuperset(other)
        return NotImplemented

    def __lt__(self,other):
        """Implemement set < operator."""
        if not isinstance(other, self.__class__) and \
           not isinstance(other, set): return NotImplemented
        return self <= other and self != other

    def __le__(self,other):
        """Implemement set <= operator."""
        if not isinstance(other, self.__class__) and \
           not isinstance(other, set): return NotImplemented
        return self.issubset(other)

    def __gt__(self,other):
        """Implemement set > operator."""
        if not isinstance(other, self.__class__) and \
           not isinstance(other, set): return NotImplemented
        return self >= other and self != other

    def __ge__(self,other):
        """Implemement set >= operator."""
        if not isinstance(other, self.__class__) and \
           not isinstance(other, set): return NotImplemented
        return self.issuperset(other)

    def __or__(self,other):
        """Implemement set | operator."""
        return self.union(other)

    def __and__(self,other):
        """Implemement set & operator."""
        return self.intersection(other)

    def __sub__(self,other):
        """Implemement set - operator."""
        return self.difference(other)

    def __xor__(self,other):
        """Implemement set ^ operator."""
        return self.symmetric_difference(other)

    def __ior__(self,other):
        """Implemement set |= operator."""
        self.update(other)
        return self

    def __iand__(self,other):
        """Implemement set &= operator."""
        self.intersection_update(other)
        return self

    def __isub__(self,other):
        """Implemement set -= operator."""
        self.difference_update(other)
        return self

    def __ixor__(self,other):
        """Implemement set ^= operator."""
        self.symmetric_difference_update(other)
        return self

    #--------------------------------------------------------------------------
    # String representation
    #--------------------------------------------------------------------------

    def __str__(self):
        if not self: return "set()"
        return "{" + ", ".join([repr(e) for e in self]) + "}"

    def __repr__(self):
        if not self: return "{}()".format(type(self).__name__)
        return self.__str__()

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError('Cannot run modules')
