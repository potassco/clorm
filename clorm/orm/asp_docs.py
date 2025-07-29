# -----------------------------------------------------------------------------
# Functions to support the generation of ASP documentation for Clorm Predicate
# sub-classes. 
# ------------------------------------------------------------------------------

from __future__ import annotations


def _trim_docstring(docstring):
    if not docstring:
        return ""
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxsize
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxsize:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return "\n".join(trimmed)


def _endstrip(string):
    if not string:
        return
    nl = string[-1] == "\n"
    tmp = string.rstrip()
    return tmp + "\n" if nl else tmp


def _format_docstring(docstring, output):
    if not docstring:
        return
    tmp = _trim_docstring(docstring)
    tmpstr = "".join(_endstrip("%     " + l) for l in tmp.splitlines(True))
    if tmpstr:
        print("% Description:", file=output)
        print(tmpstr, file=output)


def _maxwidth(lines):
    return max([len(l) for l in lines])


def _format_commented(fm: FactMap, out: TextIO) -> None:
    pm: PredicateDefn = fm.predicate.meta
    docstring = _trim_docstring(fm.predicate.__doc__) if fm.predicate.__doc__ else ""
    indent = "    "
    if pm.arity == 0:
        lines = ["Unary predicate signature:", indent + pm.name]
    else:

        def build_signature(p: Type[Predicate]) -> str:
            args = []
            for pp in p:
                complex = pp.meta.field.complex
                args.append(
                    cast(str, pp._pathseq[1]) if not complex else build_signature(complex)
                )
            return f"{p.meta.name}({','.join(args)})"

        lines = ["Predicate signature:", indent + build_signature(fm.predicate)]
    if docstring:
        lines.append("Description:")
        for l in docstring.splitlines():
            lines.append(indent + l)
    bar = "-" * _maxwidth(lines)
    lines.insert(0, bar)
    lines.append(bar)
    for l in lines:
        tmp = l.rstrip()
        if tmp:
            print("% {}".format(tmp), file=out)
        else:
            print("%", file=out)
    return




# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError("Cannot run modules")
