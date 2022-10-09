r"""Generate tuple mapping overloads.

the problem solved by this script is that of there's no way in current
pep-484 typing to unpack \*args: _T into Tuple[_T].  pep-646 is the first
pep to provide this, but it doesn't work for the actual Tuple class
and also mypy does not have support for pep-646 as of yet.  Better pep-646
support would allow us to use a TypeVarTuple with Unpack, but TypeVarTuple
does not have support for sequence operations like ``__getitem__`` and
iteration; there's also no way for TypeVarTuple to be translated back to a
Tuple which does have those things without a combinatoric hardcoding approach
to each length of tuple.

So here, the script creates a map from `*args` to a Tuple directly using a
combinatoric generated code approach.

copied from sqlalchemy

"""
from __future__ import annotations

import importlib
import itertools
import os
import re
import shutil
import sys
import textwrap
from argparse import ArgumentParser
from pathlib import Path
from tempfile import NamedTemporaryFile

is_posix = os.name == "posix"


sys.path.append(str(Path(__file__).parent.parent))


def process_module(modname: str, filename: str) -> str:

    # use tempfile in same path as the module, or at least in the
    # current working directory, so that black / zimports use
    # local pyproject.toml
    with NamedTemporaryFile(
        mode="w", delete=False, suffix=".py", dir=Path(filename).parent
    ) as buf, open(filename) as orig_py:
        indent = ""
        in_block = False
        current_fnname = given_fnname = None
        for line in orig_py:
            m = re.match(r"^( *)# START OVERLOADED FUNCTIONS (.*)$", line)
            if m:
                config_ = m.group(2).split(";")
                assert len(config_) == 6
                indent = m.group(1)
                given_fnname = current_fnname = config_[0]
                if current_fnname.startswith("self."):
                    use_self = True
                    current_fnname = current_fnname.split(".")[1]
                else:
                    use_self = False

                return_type = config_[1]
                start_index = int(config_[2])
                end_index = int(config_[3])
                generic_ = config_[4]  # _Tx is argument of generic_ like Type[_T1]
                product = bool(
                    config_[5] == "Y"
                )  # whether product of generic and non-generic arguments should be created

                sys.stderr.write(
                    f"Generating {start_index}-{end_index} overloads "
                    f"attributes for "
                    f"class {'self.' if use_self else ''}{current_fnname} "
                    f"-> {return_type}\n"
                )
                in_block = True
                buf.write(line)
                buf.write(
                    "\n    # code within this block is "
                    "**programmatically, \n"
                    "    # statically generated** by"
                    f" {os.path.basename(__file__)}\n\n"
                )

                if generic_:
                    arg_template = ["__ent{0}: " + generic_ + "[_T{0}]"]
                else:
                    arg_template = ["__ent{0}: _T{0}"]
                if product:
                    arg_template.append("__ent{0}: _T{0}")
                for num_args in range(start_index, end_index + 1):
                    typevars = ", ".join(f"_T{i}" for i in range(num_args))
                    # for a single argument we return just a scalar instead of a tuple
                    return_type_arg = typevars if num_args == 1 else f"Tuple[{typevars}]"

                    for combination in itertools.product(arg_template, repeat=num_args):
                        entities = ", ".join(
                            arg_t.format(i) for i, arg_t in enumerate(combination, 0)
                        )
                        buf.write(
                            textwrap.indent(
                                f"""@overload
def {current_fnname}(
    {'self, ' if use_self else ''}{entities}
) -> '{return_type.format(return_type_arg)}':
    ...

""",
                                indent,
                            )
                        )

            if in_block and line.startswith(f"{indent}# END OVERLOADED FUNCTIONS {given_fnname}"):
                in_block = False

            if not in_block:
                buf.write(line)
    return buf.name


def run_module(modname, stdout):

    sys.stderr.write(f"importing module {modname}\n")
    mod = importlib.import_module(modname)
    filename = destination_path = mod.__file__
    assert filename is not None

    tempfile = process_module(modname, filename)

    ignore_output = stdout

    # console_scripts(
    #     str(tempfile),
    #     {"entrypoint": "zimports"},
    #     ignore_output=ignore_output,
    # )

    # console_scripts(
    #     str(tempfile),
    #     {"entrypoint": "black"},
    #     ignore_output=ignore_output,
    # )

    if stdout:
        with open(tempfile) as tf:
            print(tf.read())
        os.unlink(tempfile)
    else:
        sys.stderr.write(f"Writing {destination_path}...\n")
        shutil.move(tempfile, destination_path)


def main(args):
    for modname in entries:
        if args.module in {"all", modname}:
            run_module(modname, args.stdout)


entries = ["clorm.orm.factbase", "clorm.orm._queryimpl"]

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--module",
        choices=entries + ["all"],
        default="all",
        help="Which file to generate. Default is to regenerate all files",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Write to stdout instead of saving to file",
    )
    args = parser.parse_args()
    main(args)
