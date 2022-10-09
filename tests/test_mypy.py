import re
import unittest
from pathlib import Path

import clorm


def eq_(a, b, msg=None):
    """Assert a == b, with repr messaging on failure."""
    assert a == b, msg or "%r != %r" % (a, b)


__all__ = ["MypyTestCase"]


def mypy_installed():
    try:
        import mypy
    except ModuleNotFoundError:
        return False
    return True


@unittest.skipIf(not mypy_installed(), reason="Test can just we executed if mypy is installed")
class MypyTestCase(unittest.TestCase):
    """TestCase for running a file with mypy and validate the revealed type by mypy"""

    def mypy_runner(self, cachedir):
        from mypy import api

        def run(path):
            args = ["--cache-dir", cachedir]
            args.append(path)
            return api.run(args)

        return run

    def test_files(self):
        """test wether revealed types by mypy are equal to expected type"""
        # based on sqlalchemy
        path = Path("tests", "test_mypy_query.py")
        expected_messages = []

        mypy_runner = self.mypy_runner(str(Path(clorm.__file__).parent.parent / ".mypy_cache"))
        filename = path.name
        expected_re = re.compile(r"\s*# EXPECTED(_MYPY)?(_RE)?(_TYPE)?: (.+)")
        with open(path) as file_:
            current_assert_messages = []
            for num, line in enumerate(file_, 1):
                m = expected_re.match(line)
                if m:
                    is_mypy = bool(m.group(1))
                    is_re = bool(m.group(2))
                    is_type = bool(m.group(3))

                    expected_msg = re.sub(r"# noqa[:]? ?.*", "", m.group(4))
                    if is_type:
                        if not is_re:
                            # the goal here is that we can cut-and-paste
                            # from vscode -> pylance into the
                            # EXPECTED_TYPE: line, then the test suite will
                            # validate that line against what mypy produces
                            expected_msg = re.sub(
                                r"([\[\]])",
                                lambda m: rf"\{m.group(0)}",
                                expected_msg,
                            )

                            # note making sure preceding text matches
                            # with a dot, so that an expect for "Select"
                            # does not match "TypedSelect"
                            expected_msg = re.sub(
                                r"([\w_]+)",
                                lambda m: rf"(?:.*\.)?{m.group(1)}\*?",
                                expected_msg,
                            )

                            expected_msg = re.sub("List", "builtins.list", expected_msg)

                            expected_msg = re.sub(
                                r"(int|str|float|bool)",
                                lambda m: rf"builtins.{m.group(0)}\*?",
                                expected_msg,
                            )
                            # expected_msg = re.sub(
                            #     r"(Sequence|Tuple|List|Union)",
                            #     lambda m: fr"typing.{m.group(0)}\*?",
                            #     expected_msg,
                            # )

                        is_mypy = is_re = True
                        expected_msg = f'Revealed type is "{expected_msg}"'
                    current_assert_messages.append((is_mypy, is_re, expected_msg.strip()))
                elif current_assert_messages:
                    expected_messages.extend(
                        (num, is_mypy, is_re, expected_msg)
                        for (
                            is_mypy,
                            is_re,
                            expected_msg,
                        ) in current_assert_messages
                    )
                    current_assert_messages[:] = []

        result = mypy_runner(str(path))

        if expected_messages:
            eq_(result[2], 1, msg=result)

            output = []

            raw_lines = result[0].split("\n")
            while raw_lines:
                e = raw_lines.pop(0)
                if re.match(r".+\.py:\d+: error: .*", e):
                    output.append(("error", e))
                elif re.match(r".+\.py:\d+: note: +(?:Possible overload|def ).*", e):
                    while raw_lines:
                        ol = raw_lines.pop(0)
                        if not re.match(r".+\.py:\d+: note: +def \[.*", ol):
                            break
                elif re.match(r".+\.py:\d+: note: .*(?:perhaps|suggestion)", e, re.I):
                    pass
                elif re.match(r".+\.py:\d+: note: .*", e):
                    output.append(("note", e))

            for num, is_mypy, is_re, msg in expected_messages:
                msg = msg.replace("'", '"')
                prefix = "[SQLAlchemy Mypy plugin] " if not is_mypy else ""
                for idx, (typ, errmsg) in enumerate(output):
                    if is_re:
                        if re.match(
                            rf".*{filename}\:{num}\: {typ}\: {prefix}{msg}",  # noqa: E501
                            errmsg,
                        ):
                            break
                    elif f"{filename}:{num}: {typ}: {prefix}{msg}" in errmsg.replace("'", '"'):
                        break
                else:
                    continue
                del output[idx]

            if output:
                print(f"{len(output)} messages from mypy were not consumed:")
                print("\n".join(msg for _, msg in output))
                assert False, "errors and/or notes remain, see stdout"

        else:
            if result[2] != 0:
                print(result[0])

            eq_(result[2], 0, msg=result)
