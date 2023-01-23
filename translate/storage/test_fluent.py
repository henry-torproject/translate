#
# Copyright 2021 Jack Grigg
#
# This file is part of the Translate Toolkit.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import re
import textwrap
from io import BytesIO

from pytest import raises

from translate.storage import fluent, test_monolingual


class TestFluentUnit(test_monolingual.TestMonolingualUnit):
    UnitClass = fluent.FluentUnit


class TestFluentFile(test_monolingual.TestMonolingualStore):
    StoreClass = fluent.FluentFile

    @staticmethod
    def fluent_parse(fluent_source):
        """Helper that parses Fluent source without requiring files."""
        dummyfile = BytesIO(fluent_source.encode())
        fluent_file = fluent.FluentFile(dummyfile)
        return fluent_file

    @staticmethod
    def fluent_serialize(fluent_file):
        # The __bytes__ method on TranslationStore calls FluentFile.serialize.
        return bytes(fluent_file).decode("utf-8")

    def fluent_regen(self, fluent_source):
        """Helper that converts Fluent source to a FluentFile object and back."""
        return self.fluent_serialize(self.fluent_parse(fluent_source))

    @staticmethod
    def quick_fluent_file(unit_specs):
        """Helper to create a FluentFile populated by the FluentUnits
        parametrised in `unit_specs`.
        """
        fluent_file = fluent.FluentFile()
        for spec in unit_specs:
            fluent_file.addunit(
                fluent.FluentUnit(
                    source=spec.get("source", None),
                    unit_id=spec.get("id", None),
                    comment=spec.get("comment", None),
                    fluent_type=spec.get("type", None),
                )
            )
        return fluent_file

    @staticmethod
    def assert_units(fluent_file, expect_units):
        """Assert that the given FluentFile has the expected FluentUnits.

        :param FluentFile fluent_file: The file to test.
        :param list[dict] expect_units: A list of the expected units, specified
            by the dictionary values. The "id", "source", "type" and "comment"
            values are matched with the corresponding property. If "type" is
            missing, it will be chosen based on the "id". Otherwise, a falsey
            value is used if a value is unspecified. In addition, the "refs"
            value is matched against the placeholders property.
        """
        for unit, expect in zip(fluent_file.units, expect_units):
            unit_id = expect.get("id", None)
            assert unit_id == unit.getid()
            id_type = None
            if unit_id:
                if unit_id.startswith("-"):
                    id_type = "Term"
                else:
                    id_type = "Message"
            assert expect.get("type", id_type) == unit.fluent_type
            if unit.fluent_type.endswith("Comment"):
                assert unit.isheader()
                assert not unit.istranslatable()
            else:
                assert not unit.isheader()
                assert unit.istranslatable()
            # Order shouldn't be important.
            placeholders = {"{ " + ref_id + " }" for ref_id in expect.get("refs", [])}
            assert placeholders == set(unit.placeholders)
            assert expect.get("comment", "") == unit.getnotes()
            assert expect.get("source", None) == unit.source
            assert unit.target == unit.source
        assert len(fluent_file.units) == len(expect_units)

    def basic_test(self, fluent_source, expect_units, expect_serialize=None):
        """Assert that the given fluent source parses correctly to the expected
        FluentFile, and reserializes correctly.

        :param str fluent_source: The fluent source. Any common indent in this
            will be removed before parsing.
        :param list[dict] expect_units: The expected units in the parsed
            FluentFile (see assert_units).
        :param str expect_serialize: The expected serialization, if it would be
            different from fluent_source. Any common indent in this will be
            removed before comparing.
        """
        # Rather than requiring multiline strings start at the newline, we just
        # remove the common indent.
        fluent_source = textwrap.dedent(fluent_source)
        if expect_serialize is None:
            expect_serialize = fluent_source
        else:
            expect_serialize = textwrap.dedent(expect_serialize)

        fluent_file = self.fluent_parse(fluent_source)
        self.assert_units(fluent_file, expect_units)
        assert self.fluent_serialize(fluent_file) == expect_serialize
        if expect_serialize != fluent_source:
            # Double check that a regen of expect_serialize will give us back
            # exactly the same string.
            assert self.fluent_regen(expect_serialize) == expect_serialize

    def assert_serialize(self, fluent_file, expect_serialize):
        """Assert that the given FluentFile serializes to the given string.

        :param FluentFile fluent_file: The FluentFile to serialize.
        :param str expect_serialize: The expected result. Any common indent in
            this value will be removed before comparison.
        """
        expect_serialize = textwrap.dedent(expect_serialize)
        assert self.fluent_serialize(fluent_file) == expect_serialize

    def assert_parse_failure(self, fluent_source, error_part):
        """Assert that the given fluent source fails to parse into a
        FluentFile.

        :param str fluent_source: The fluent source. Any common indent will be
            removed before processing.
        :param str error_part: The part of the fluent_source that will be
            highlighted in the error message.
        """
        fluent_source = textwrap.dedent(fluent_source)
        error_regex = (
            r"^Parsing error for fluent source: " + error_part + r".*(\nE[0-9]+: .*)*$"
        )
        with raises(ValueError, match=error_regex):
            self.fluent_parse(fluent_source)

    def assert_serialize_failure(self, fluent_file, error_regex):
        """Assert that the given FluentFile fails to serialize.

        :param FluentFile fluent_file: The FluentFile to try and serialize.
        :param str error_regex: The expected error expression.
        """
        with raises(ValueError, match=error_regex):
            self.fluent_serialize(fluent_file)

    def test_simple_values(self):
        """Test a simple fluent Message and Term."""
        self.basic_test(
            """\
            test_me = I can code!
            """,
            [{"id": "test_me", "source": "I can code!"}],
        )
        self.basic_test(
            """\
            -my-term = Term Content
            """,
            [{"id": "-my-term", "source": "Term Content"}],
        )

    def test_with_comment(self):
        """Test a fluent Message and Term with a Comment."""
        self.basic_test(
            """\
            # A comment
            test-message = test content
            """,
            [{"id": "test-message", "source": "test content", "comment": "A comment"}],
        )
        self.basic_test(
            """\
            # A comment
            -test-term = test content
            """,
            [{"id": "-test-term", "source": "test content", "comment": "A comment"}],
        )

    def test_message_with_attributes(self):
        """Test a fluent Message with Attributes."""
        self.basic_test(
            """\
            message = test content
                .first = First attribute
                .second = Second attribute
            """,
            [
                {
                    "id": "message",
                    "source": "test content\n"
                    ".first = First attribute\n"
                    ".second = Second attribute",
                },
            ],
        )
        # Any indent is ok, but re-serializes as 4-spaces.
        self.basic_test(
            """\
            message = test content
              .first = 1
                  .second = 2
             .third = 3
            """,
            [
                {
                    "id": "message",
                    "source": "test content\n"
                    ".first = 1\n"
                    ".second = 2\n"
                    ".third = 3",
                }
            ],
            """\
            message = test content
                .first = 1
                .second = 2
                .third = 3
            """,
        )
        # With comment.
        self.basic_test(
            """\
            # A comment
            my-id = test content
                .first = First attribute
                .attr-2 = Second attribute
            """,
            [
                {
                    "id": "my-id",
                    "source": "test content\n"
                    ".first = First attribute\n"
                    ".attr-2 = Second attribute",
                    "comment": "A comment",
                },
            ],
        )
        # Message with no value, but does have attributes.
        self.basic_test(
            """\
            # No value
            my-id =
                .first = First
                .attr-2 = Second
            """,
            [
                {
                    "id": "my-id",
                    "source": ".first = First\n.attr-2 = Second",
                    "comment": "No value",
                },
            ],
        )

        # A comment between attributes is not allowed.
        self.assert_parse_failure(
            """\
            # Top comment
            -my-term = content
            # Try to comment
                .first = First
                .attr-2 = Second
            """,
            r"\.first = First",
        )

    def test_term_with_attributes(self):
        """Test a fluent Term with Attributes."""
        self.basic_test(
            """\
            # A comment
            -term = test content
                .first = First attribute
                .second = Second attribute
            """,
            [
                {
                    "id": "-term",
                    "source": "test content\n"
                    ".first = First attribute\n"
                    ".second = Second attribute",
                    "comment": "A comment",
                }
            ],
        )

        # Cannot have a term with no value, but with attributes.
        self.assert_parse_failure(
            """\
            -my-term =
                .first = First
                .attr-2 = Second
            """,
            r"-my-term =",
        )
        fluent_file = self.quick_fluent_file(
            [{"type": "Term", "source": ".attr = string", "id": "-term"}]
        )
        self.assert_serialize_failure(
            fluent_file,
            r'^Error in source of FluentUnit "-term":\n'
            r'.*Expected term "-term" to have a value \[line 1, column 1\]$',
        )

    def test_whitespace(self):
        """Test behaviour for leading and trailing whitespace."""

        # Expect leading whitespace and trailing whietspace to be dropped.
        # TODO: Do we want to try and generate warnings for this?
        def subtest_whitespace(whitespace):
            # Test leading and trailing whitespace.
            for position in ["start", "end"]:
                source = f"{whitespace}ok" if position == "start" else f"ok{whitespace}"
                # Single line Message.
                fluent_file = self.quick_fluent_file(
                    [{"type": "Message", "source": source, "id": "message"}]
                )
                self.assert_serialize(fluent_file, "message = ok\n")
                # Single line Message Attribute.
                fluent_file = self.quick_fluent_file(
                    [{"type": "Message", "source": f".a = {source}", "id": "m"}]
                )
                self.assert_serialize(
                    fluent_file,
                    """\
                    m =
                        .a = ok
                    """,
                )
                # Single line Term.
                fluent_file = self.quick_fluent_file(
                    [{"type": "Term", "source": source, "id": "-term"}]
                )
                self.assert_serialize(fluent_file, "-term = ok\n")

                # Start or end of Term's value, with attributes.
                fluent_file = self.quick_fluent_file(
                    [{"type": "Term", "source": f"{source}\n.attr = a", "id": "-term"}]
                )
                self.assert_serialize(
                    fluent_file,
                    """\
                    -term = ok
                        .attr = a
                    """,
                )

        subtest_whitespace(" ")
        subtest_whitespace("\n")
        subtest_whitespace("  ")
        subtest_whitespace(" \n ")

        # Test multiline common indent is lost. But difference in indent is
        # preserved.
        fluent_file = self.quick_fluent_file(
            [{"type": "Message", "source": " line 1\n   line 2", "id": "m"}]
        )
        self.assert_serialize(
            fluent_file,
            """\
            m =
                line 1
                  line 2
            """,
        )

        # Test that leading and trailing blank lines are lost.
        fluent_file.units[0].source = "\nline 1\nline 2"
        self.assert_serialize(
            fluent_file,
            """\
            m =
                line 1
                line 2
            """,
        )
        fluent_file.units[0].source = "  \n \nline 1\nline 2"
        self.assert_serialize(
            fluent_file,
            """\
            m =
                line 1
                line 2
            """,
        )
        fluent_file.units[0].source = "line 1\nline 2\n\n  "
        self.assert_serialize(
            fluent_file,
            """\
            m =
                line 1
                line 2
            """,
        )

        # Test that trailing spaces on lines are preserved, apart from the last
        # line, as per fluent's rules.
        fluent_file.units[0].source = "line 1   \n line 2  \nline 3   \n  "
        self.assert_serialize(
            fluent_file, "m =\n" "    line 1   \n" "     line 2  \n" "    line 3\n"
        )

    def test_empty_unit_source(self):
        """Test behaviour when we have an empty FluentUnit source."""

        def subtest_empty_unit_source(source):
            # Empty units are not serialized.
            for fluent_type, unit_id in [
                ("Message", "m2"),
                ("Term", "-term-1"),
            ]:
                fluent_file = self.quick_fluent_file(
                    [{"type": fluent_type, "source": source, "id": unit_id}]
                )
                # Empty file.
                self.assert_serialize(fluent_file, "")

                # With a previous unit and following unit.
                # Previous unit and following unit are still serialized.
                fluent_file = self.quick_fluent_file(
                    [
                        {"type": "Message", "source": "a", "id": "m1"},
                        {"type": fluent_type, "source": source, "id": unit_id},
                        {"type": "Message", "source": "b", "id": "m3"},
                    ]
                )
                self.assert_serialize(fluent_file, "m1 = a\nm3 = b\n")

            if source is None:
                return

            # A Term that has an empty value with attributes, or empty
            # attributes, simply throws because this is a syntax error within a
            # single source.
            fluent_file = self.quick_fluent_file(
                [
                    {"type": "Message", "source": "ok", "id": "message"},
                    {"type": "Term", "source": f"{source}\n.attr = ok", "id": "-term"},
                ]
            )
            self.assert_serialize_failure(
                fluent_file, r'^Error in source of FluentUnit "-term":'
            )
            # Empty Attribute for a Term
            fluent_file.units[1].source = f"ok\n.attr = {source}"
            self.assert_serialize_failure(
                fluent_file, r'^Error in source of FluentUnit "-term":'
            )

            # For a Message, an empty start is ok.
            fluent_file = self.quick_fluent_file(
                [
                    {"type": "Message", "source": "ok", "id": "message"},
                    {"type": "Message", "source": f"{source}\n.attr = ok", "id": "m"},
                ]
            )
            self.assert_serialize(
                fluent_file,
                """\
                message = ok
                m =
                    .attr = ok
                """,
            )
            # Empty attribute is not ok.
            fluent_file.units[1].source = f"ok\n.attr = {source}"
            self.assert_serialize_failure(
                fluent_file, r'^Error in source of FluentUnit "m":'
            )

        subtest_empty_unit_source(None)
        subtest_empty_unit_source("")
        subtest_empty_unit_source(" ")
        subtest_empty_unit_source("\n")
        subtest_empty_unit_source("\n ")

    def test_multiline_value(self):
        """Test multiline values for fluent Messages and Terms."""
        # Starting on the same line.
        self.basic_test(
            """\
            message = My multiline
              message
            """,
            [{"id": "message", "source": "My multiline\nmessage"}],
            """\
            message =
                My multiline
                message
            """,
        )

        # With a gap after first line.
        self.basic_test(
            """\
            message = My multiline

              gap
            """,
            [{"id": "message", "source": "My multiline\n\ngap"}],
            """\
            message =
                My multiline

                gap
            """,
        )
        # With gap after second line.
        self.basic_test(
            """\
            -term = My multiline
                  term with

                  a gap
            """,
            [{"id": "-term", "source": "My multiline\nterm with\n\na gap"}],
            """\
            -term =
                My multiline
                term with

                a gap
            """,
        )

        # Whitespace that goes beyond the common indent is preserved.
        # NOTE: The whitespace after the = is ignored.
        self.basic_test(
            """\
            -term =    Term
               lies across
              three lines
            """,
            [{"id": "-term", "source": "Term\n lies across\nthree lines"}],
            """\
            -term =
                Term
                 lies across
                three lines
            """,
        )

        # With the multiline value starting on a newline.
        self.basic_test(
            """\
            -term =
                My multiline
                term
            """,
            [{"id": "-term", "source": "My multiline\nterm"}],
        )

        # With a gap.
        self.basic_test(
            """\
            -term =
              My multiline

              gap
            """,
            [{"id": "-term", "source": "My multiline\n\ngap"}],
            """\
            -term =
                My multiline

                gap
            """,
        )
        # With a gap at the start is ignored.
        self.basic_test(
            """\
            message =

             starts with a gap
            """,
            [{"id": "message", "source": "starts with a gap"}],
            """\
            message = starts with a gap
            """,
        )

        # Whitespace at line start
        # NOTE: The whitespace for the first line is not ignored.
        self.basic_test(
            """\
            message =
                  message with
                preserved
                 whitespace
            """,
            [{"id": "message", "source": "  message with\npreserved\n whitespace"}],
        )

        # Trailing whitespace is preserved in fluent for all but the last line.
        self.basic_test(
            "message =  \n" " trailing  \n" " whitespace \n" " last line  \n",
            [{"id": "message", "source": "trailing  \nwhitespace \nlast line"}],
            "message =\n" "    trailing  \n" "    whitespace \n" "    last line\n",
        )
        # Starting on the same line, and with gap.
        self.basic_test(
            "message =   trailing  \n" " whitespace \n" "    \n" " last line  \n",
            [{"id": "message", "source": "trailing  \nwhitespace \n\nlast line"}],
            "message =\n" "    trailing  \n" "    whitespace \n" "\n" "    last line\n",
        )

    def test_multiline_message_attributes(self):
        """Test multiline Attributes for fluent Messages."""
        # Starting on the same line.
        self.basic_test(
            """\
            message =
              .attr = My multiline
             attribute
            """,
            [{"id": "message", "source": ".attr =\nMy multiline\nattribute"}],
            """\
            message =
                .attr =
                    My multiline
                    attribute
            """,
        )

        # With a gap after first line.
        self.basic_test(
            """\
            message =
             .attr = My multiline

                  gap
            """,
            [{"id": "message", "source": ".attr =\nMy multiline\n\ngap"}],
            """\
            message =
                .attr =
                    My multiline

                    gap
            """,
        )
        # With gap after second line.
        self.basic_test(
            """\
            message = My multiline
                  message with

                  a gap
                  .attr = My multiline
                    attribute with

                    a gap
            """,
            [
                {
                    "id": "message",
                    "source": "My multiline\n"
                    "message with\n"
                    "\n"
                    "a gap\n"
                    ".attr =\n"
                    "My multiline\n"
                    "attribute with\n"
                    "\n"
                    "a gap",
                },
            ],
            """\
            message =
                My multiline
                message with

                a gap
                .attr =
                    My multiline
                    attribute with

                    a gap
            """,
        )

        # Whitespace that goes beyond the common indent is preserved.
        # NOTE: The whitespace for the first line is ignored.
        self.basic_test(
            """\
            message = Message
              .attr =     Attribute
                lies across
              three lines
            """,
            [
                {
                    "id": "message",
                    "source": "Message\n"
                    ".attr =\n"
                    "Attribute\n"
                    "  lies across\n"
                    "three lines",
                },
            ],
            """\
            message = Message
                .attr =
                    Attribute
                      lies across
                    three lines
            """,
        )

        # With the multiline value starting on a newline.
        self.basic_test(
            """\
            message = Message
                .a =
                    My multiline
                    attribute
            """,
            [
                {
                    "id": "message",
                    "source": "Message\n" ".a =\n" "My multiline\n" "attribute",
                },
            ],
        )

        # With a gap.
        self.basic_test(
            """\
            message =
             Message
                .a =
              My multiline

              gap
            """,
            [
                {
                    "id": "message",
                    "source": "Message\n" ".a =\n" "My multiline\n" "\n" "gap",
                },
            ],
            """\
            message = Message
                .a =
                    My multiline

                    gap
            """,
        )
        # With a gap at the start is ignored.
        self.basic_test(
            """\
            message =
             .a =

             starts with a gap
            """,
            [{"id": "message", "source": ".a = starts with a gap"}],
            """\
            message =
                .a = starts with a gap
            """,
        )

        # Whitespace at line start
        # NOTE: The whitespace for the first line is not ignored.
        self.basic_test(
            """\
            message = Message
                .attr =
                     attribute with
                    preserved
                      whitespace
            """,
            [
                {
                    "id": "message",
                    "source": "Message\n"
                    ".attr =\n"
                    " attribute with\n"
                    "preserved\n"
                    "  whitespace",
                },
            ],
        )

        # Trailing whitespace is preserved in fluent for all but the last line.
        self.basic_test(
            "message = Message \n"
            ".attr = \n"
            " trailing  \n"
            " whitespace \n"
            " last line  \n",
            [
                {
                    "id": "message",
                    "source": "Message\n"
                    ".attr =\n"
                    "trailing  \n"
                    "whitespace \n"
                    "last line",
                },
            ],
            "message = Message\n"
            "    .attr =\n"
            "        trailing  \n"
            "        whitespace \n"
            "        last line\n",
        )
        # Starting on the same line, and with gap.
        self.basic_test(
            "message = Message\n"
            " .attr =    trailing  \n"
            " whitespace \n"
            "    \n"
            " last line  \n",
            [
                {
                    "id": "message",
                    "source": "Message\n"
                    ".attr =\n"
                    "trailing  \n"
                    "whitespace \n"
                    "\n"
                    "last line",
                },
            ],
            "message = Message\n"
            "    .attr =\n"
            "        trailing  \n"
            "        whitespace \n"
            "\n"
            "        last line\n",
        )

    def test_multiline_term_attributes(self):
        """Test multiline Attributes for fluent Terms."""
        # NOTE: Multiline attributes for fluent Terms would not usually be of
        # much use, but we still check that they behave as expected when
        # present.

        # Starting on the same line.
        self.basic_test(
            """\
            -term = val
              .attr = My multiline
             attribute
            """,
            [{"id": "-term", "source": "val\n.attr =\nMy multiline\nattribute"}],
            """\
            -term = val
                .attr =
                    My multiline
                    attribute
            """,
        )

        # With a gap after first line.
        self.basic_test(
            """\
            -term = val
             .attr = My multiline

                  gap
            """,
            [{"id": "-term", "source": "val\n.attr =\nMy multiline\n\ngap"}],
            """\
            -term = val
                .attr =
                    My multiline

                    gap
            """,
        )
        # With gap after second line.
        self.basic_test(
            """\
            -term = My multiline
                  term with

                  a gap
                  .attr = My multiline
                    attribute with

                    a gap
            """,
            [
                {
                    "id": "-term",
                    "source": "My multiline\nterm with\n\na gap\n"
                    ".attr =\nMy multiline\nattribute with\n\na gap",
                }
            ],
            """\
            -term =
                My multiline
                term with

                a gap
                .attr =
                    My multiline
                    attribute with

                    a gap
            """,
        )

        # Whitespace that goes beyond the common indent is preserved.
        # NOTE: The whitespace for the first line is ignored.
        self.basic_test(
            """\
            -term = Term
              .attr =     Attribute
                lies across
              three lines
            """,
            [
                {
                    "id": "-term",
                    "source": "Term\n"
                    ".attr =\n"
                    "Attribute\n"
                    "  lies across\n"
                    "three lines",
                }
            ],
            """\
            -term = Term
                .attr =
                    Attribute
                      lies across
                    three lines
            """,
        )

        # With the multiline value starting on a newline.
        self.basic_test(
            """\
            -term = Term
                .a =
                    My multiline
                    attribute
            """,
            [{"id": "-term", "source": "Term\n.a =\nMy multiline\nattribute"}],
        )

        # With a gap.
        self.basic_test(
            """\
            -term =
             Term
                .a =
              My multiline

              gap
            """,
            [{"id": "-term", "source": "Term\n.a =\nMy multiline\n\ngap"}],
            """\
            -term = Term
                .a =
                    My multiline

                    gap
            """,
        )
        # With a gap at the start is ignored.
        self.basic_test(
            """\
            -term = val
             .a =

             starts with a gap
            """,
            [{"id": "-term", "source": "val\n.a = starts with a gap"}],
            """\
            -term = val
                .a = starts with a gap
            """,
        )

        # Whitespace at line start
        # NOTE: The whitespace for the first line is not ignored.
        self.basic_test(
            """\
            -term = Term
                .attr =
                     attribute with
                    preserved
                      whitespace
            """,
            [
                {
                    "id": "-term",
                    "source": "Term\n"
                    ".attr =\n"
                    " attribute with\n"
                    "preserved\n"
                    "  whitespace",
                }
            ],
        )

        # Trailing whitespace is preserved in fluent for all but the last line.
        self.basic_test(
            "-term =  \n" " trailing  \n" " whitespace \n" " last line  \n",
            [{"id": "-term", "source": "trailing  \nwhitespace \nlast line"}],
            "-term =\n" "    trailing  \n" "    whitespace \n" "    last line\n",
        )
        # Starting on the same line, and with gap.
        self.basic_test(
            "-term =   trailing  \n" " whitespace \n" "    \n" " last line  \n",
            [{"id": "-term", "source": "trailing  \nwhitespace \n\nlast line"}],
            "-term =\n" "    trailing  \n" "    whitespace \n" "\n" "    last line\n",
        )

    def test_special_syntax_characters(self):
        """Test special syntax characters at the start of a line."""

        # ".", "*" and "[" cannot appear at the start of a multiline line, but
        # as a special case they can appear at the start of a value on the same
        # line without throwing a fluent syntax error. But we expect out
        # FluentFile to escape these values for consistency.
        def subtest_special_syntax_characters(char, ok_at_start):
            # Test *within* a single-line Message, Term, and Attributes.
            # Should be the same in all cases.
            middle_value = f"e{char}and more"
            self.basic_test(
                f"""\
                message = {middle_value}
                """,
                [{"id": "message", "source": middle_value}],
            )
            self.basic_test(
                f"""\
                message =
                    .a = {middle_value}
                """,
                [{"id": "message", "source": f".a = {middle_value}"}],
            )
            self.basic_test(
                f"""\
                -term = {middle_value}
                """,
                [{"id": "-term", "source": middle_value}],
            )
            self.basic_test(
                f"""\
                -term = val
                    .a = {middle_value}
                """,
                [{"id": "-term", "source": f"val\n.a = {middle_value}"}],
            )

            # Test with just the character on its own, or at the start of a
            # value.
            if ok_at_start:
                escaped_char = char
            else:
                escaped_char = f'{{ "{char}" }}'

            for value in [char, f"{char}at start"]:
                escaped_value = value.replace(char, escaped_char)
                # Test at start of a single-line Message, Term, and Attributes.
                self.basic_test(
                    f"""\
                    message = {value}
                    """,
                    [{"id": "message", "source": escaped_value}],
                    f"""\
                    message = {escaped_value}
                    """,
                )
                self.basic_test(
                    f"""\
                    message =
                        .a = {value}
                    """,
                    [{"id": "message", "source": f".a = {escaped_value}"}],
                    f"""\
                    message =
                        .a = {escaped_value}
                    """,
                )
                self.basic_test(
                    f"""\
                    -term = {value}
                    """,
                    [{"id": "-term", "source": escaped_value}],
                    f"""\
                    -term = {escaped_value}
                    """,
                )
                self.basic_test(
                    f"""\
                    -term = val
                        .a = {value}
                    """,
                    [{"id": "-term", "source": f"val\n.a = {escaped_value}"}],
                    f"""\
                    -term = val
                        .a = {escaped_value}
                    """,
                )

                # Do same with start of a multiline.
                self.basic_test(
                    f"""\
                    message = {value}
                     {middle_value}
                    """,
                    [{"id": "message", "source": f"{escaped_value}\n{middle_value}"}],
                    f"""\
                    message =
                        {escaped_value}
                        {middle_value}
                    """,
                )
                self.basic_test(
                    f"""\
                    message =
                        .a = {value}
                     {middle_value}
                    """,
                    [
                        {
                            "id": "message",
                            "source": f".a =\n{escaped_value}\n{middle_value}",
                        }
                    ],
                    f"""\
                    message =
                        .a =
                            {escaped_value}
                            {middle_value}
                    """,
                )
                self.basic_test(
                    f"""\
                    -term = {value}
                     {middle_value}
                    """,
                    [{"id": "-term", "source": f"{escaped_value}\n{middle_value}"}],
                    f"""\
                    -term =
                        {escaped_value}
                        {middle_value}
                    """,
                )
                self.basic_test(
                    f"""\
                    -term = val
                        .a = {value}
                     {middle_value}
                    """,
                    [
                        {
                            "id": "-term",
                            "source": f"val\n.a =\n{escaped_value}\n{middle_value}",
                        }
                    ],
                    f"""\
                    -term = val
                        .a =
                            {escaped_value}
                            {middle_value}
                    """,
                )

                if ok_at_start:
                    continue

                # Confirm that starting a newline with one of these characters would
                # throw an error.
                self.assert_parse_failure(
                    f"""\
                    message =
                        {value}
                    """,
                    r".*" + re.escape(value),
                )
                self.assert_parse_failure(
                    f"""\
                    message = ok
                        {value}
                    """,
                    r".*" + re.escape(value),
                )
                self.assert_parse_failure(
                    f"""\
                    -term = ok
                        {value}
                    """,
                    r".*" + re.escape(value),
                )
                self.assert_parse_failure(
                    f"""\
                    -term = ok
                      .attr =
                        {value}
                    """,
                    r".*" + re.escape(value),
                )

                for fluent_type, unit_id, source in [
                    ("Message", "message1", value),
                    ("Message", "message2", f"{middle_value}\n{value}"),
                    ("Message", "message3", f"val\n.attr = \n{value}"),
                    ("Term", "-term1", value),
                    ("Term", "-term2", f"val\n.attr =\n{value}"),
                ]:
                    fluent_file = self.quick_fluent_file(
                        [{"type": fluent_type, "source": source, "id": unit_id}]
                    )
                    self.assert_serialize_failure(
                        fluent_file,
                        f'^Error in source of FluentUnit "{unit_id}":',
                    )
                # As a special case, an Attribute can start with this and not
                # throw an exception because it starts after an "=" sign.
                fluent_file = self.quick_fluent_file(
                    [
                        {
                            "type": "Term",
                            "source": f"val\n.attr = {value}\n{middle_value}",
                            "id": "-term",
                        }
                    ]
                )
                # Note that the serializer will keep it starting on the first line,
                # even though it is a multiline value.
                self.assert_serialize(
                    fluent_file,
                    f"""\
                    -term = val
                        .attr = {value}
                            {middle_value}
                    """,
                )

        # Characters that cannot be included at the start of a block. As
        # specified in the fluent EBNF's "indented_char"
        subtest_special_syntax_characters(".", False)
        subtest_special_syntax_characters("*", False)
        subtest_special_syntax_characters("[", False)
        # Even though these are used in some syntax, they can be at the start of
        # a block:
        subtest_special_syntax_characters("]", True)
        subtest_special_syntax_characters("#", True)
        subtest_special_syntax_characters("(", True)
        subtest_special_syntax_characters(")", True)
        subtest_special_syntax_characters(":", True)
        subtest_special_syntax_characters("$", True)
        subtest_special_syntax_characters("-", True)
        subtest_special_syntax_characters(">", True)
        subtest_special_syntax_characters('"', True)
        subtest_special_syntax_characters(",", True)

    def test_multiline_message_term_comments(self):
        """Test multiline Comments for fluent Messages and Terms."""
        self.basic_test(
            """\
            # A comment
            # over two lines
            message = My Content
            """,
            [
                {
                    "id": "message",
                    "source": "My Content",
                    "comment": "A comment\nover two lines",
                }
            ],
        )
        self.basic_test(
            """\
            # A comment
            #
            # with a gap
            -term = My Content
                .attr = val
            """,
            [
                {
                    "id": "-term",
                    "source": "My Content\n.attr = val",
                    "comment": "A comment\n\nwith a gap",
                }
            ],
        )

    def test_resource_comments(self):
        """Test fluent ResourceComments."""
        self.basic_test(
            """\
            ### My resource comment
            """,
            [{"type": "ResourceComment", "comment": "My resource comment"}],
            """\
            ### My resource comment

            """,
        )
        # Does not enter the message's comment.
        self.basic_test(
            """\
            ### My resource
            ### comment
            message = value
            """,
            [
                {"type": "ResourceComment", "comment": "My resource\ncomment"},
                {"id": "message", "source": "value"},
            ],
            """\
            ### My resource
            ### comment

            message = value
            """,
        )
        # Blank line is preserved.
        self.basic_test(
            """\
            ###
            """,
            [{"type": "ResourceComment", "comment": ""}],
            """\
            ###

            """,
        )

    def test_group_comments(self):
        """Test fluent GroupComments."""
        self.basic_test(
            """\
            ## My group comment
            """,
            [{"type": "GroupComment", "comment": "My group comment"}],
            """\
            ## My group comment

            """,
        )
        # Does not enter the term's comment.
        self.basic_test(
            """\
            ## My group
            ## comment
            -term = value
            """,
            [
                {"type": "GroupComment", "comment": "My group\ncomment"},
                {"id": "-term", "source": "value"},
            ],
            """\
            ## My group
            ## comment

            -term = value
            """,
        )
        # Blank line is preserved.
        self.basic_test(
            """\
            ##
            """,
            [{"type": "GroupComment", "comment": ""}],
            """\
            ##

            """,
        )

    def test_detached_comment(self):
        """Test fluent Comments with no Message or Term."""
        self.basic_test(
            """\
            # My detached comment
            """,
            [{"type": "DetachedComment", "comment": "My detached comment"}],
            """\
            # My detached comment

            """,
        )
        # A gap is sufficient to separate a comment from a message.
        self.basic_test(
            """\
            # My detached
            # comment

            message = value
            """,
            [
                {"type": "DetachedComment", "comment": "My detached\ncomment"},
                {"id": "message", "source": "value"},
            ],
        )
        # Separates from other comments as well.
        self.basic_test(
            """\
            # My detached
            # comment

            # Another detached

            # term comment
            -term = value
            """,
            [
                {"type": "DetachedComment", "comment": "My detached\ncomment"},
                {"type": "DetachedComment", "comment": "Another detached"},
                {"id": "-term", "source": "value", "comment": "term comment"},
            ],
            """\
            # My detached
            # comment


            # Another detached

            # term comment
            -term = value
            """,
        )
        # Blank line is preserved.
        self.basic_test(
            """\
            #
            """,
            [{"type": "DetachedComment", "comment": ""}],
            """\
            #

            """,
        )

    def test_reference(self):
        """Test fluent MessageReferences, TermReferences and
        VariableReferences."""
        # Test reference to a term or message.
        self.basic_test(
            """\
            -term1 = { -term2 } and { message }!
            ref-message = { -term1 } with { message } { -term2 }
                .attribute = { -term2 } over { message }
            """,
            # The FluentUnit just uses the same text.
            # The references in the value become refs.
            # NOTE: attribute refs do not.
            [
                {
                    "id": "-term1",
                    "source": "{ -term2 } and { message }!",
                    "refs": ["-term2", "message"],
                },
                {
                    "id": "ref-message",
                    "source": "{ -term1 } with { message } { -term2 }\n"
                    ".attribute = { -term2 } over { message }",
                    "refs": ["-term1", "message", "-term2"],
                },
            ],
        )
        # TermReference with arguments.
        self.basic_test(
            """\
            message = I am { -term1(tense: "present") }
            -term = Going to { -term1(tense: "present", number: 7.5) } now
            """,
            [
                {
                    "id": "message",
                    "source": 'I am { -term1(tense: "present") }',
                    "refs": ["-term1"],
                },
                {
                    "id": "-term",
                    "source": 'Going to { -term1(tense: "present", number: 7.5) } now',
                    "refs": ["-term1"],
                },
            ],
        )
        # Test references to a message's attribute.
        self.basic_test(
            """\
            ref-message = { message.attribute }
                .attribute = { i-9.attr } over { i-9 }
            """,
            # The FluentUnit just uses the same text.
            [
                {
                    "id": "ref-message",
                    "source": "{ message.attribute }\n"
                    ".attribute = { i-9.attr } over { i-9 }",
                    "refs": ["message.attribute"],
                },
            ],
        )

        # Test reference to variable.
        self.basic_test(
            """\
            -term1 = Term with { $var }
            ref-message = { $num1 } is greater than { $num2 }
                .attribute = { $other-var } used
            """,
            # The FluentUnit just uses the same text.
            [
                # Variables used in terms do not become a ref since they are
                # locale-specific.
                {"id": "-term1", "source": "Term with { $var }", "refs": []},
                {
                    "id": "ref-message",
                    "source": "{ $num1 } is greater than { $num2 }\n"
                    ".attribute = { $other-var } used",
                    "refs": ["$num1", "$num2"],
                },
            ],
        )

        # Mix.
        self.basic_test(
            """\
            message = { $var } with { message.attr } and { -term }
            """,
            [
                {
                    "id": "message",
                    "source": "{ $var } with { message.attr } and { -term }",
                    "refs": ["$var", "message.attr", "-term"],
                }
            ],
        )

        # Repeated references are included twice only appear once in
        # refs.
        self.basic_test(
            """\
            message = { $var } with { -term0 } and { $var }
            """,
            [
                {
                    "id": "message",
                    "source": "{ $var } with { -term0 } and { $var }",
                    "refs": ["$var", "-term0"],
                }
            ],
        )

    def test_literals(self):
        """Test fluent Literals."""
        self.basic_test(
            """\
            -term = Term with number { 5 } literal and string { "s" } literal.
            message = { " " } space literal
                .attr = number { 79 }
            """,
            [
                {
                    "id": "-term",
                    "source": 'Term with number { 5 } literal and string { "s" } literal.',
                },
                {
                    "id": "message",
                    "source": '{ " " } space literal\n' + ".attr = number { 79 }",
                },
            ],
        )

    def test_selectors(self):
        """Test fluent selectors."""
        self.basic_test(
            """\
            amount =
                { $num ->
                    [one] One apple.
                   *[other] { $num } apples.
                }
            """,
            # The FluentUnit just uses the same text.
            [
                {
                    "id": "amount",
                    "source": "{ $num ->\n"
                    "    [one] One apple.\n"
                    "   *[other] { $num } apples.\n"
                    "}",
                    # Get ref from the second variant.
                    "refs": ["$num"],
                }
            ],
        )

        # Selector where the variable is not used in the branches.
        self.basic_test(
            """\
            amount =
                { $num ->
                    [one] One apple.
                   *[other] Some apples.
                }
            """,
            # The FluentUnit just uses the same text.
            [
                {
                    "id": "amount",
                    "source": "{ $num ->\n"
                    "    [one] One apple.\n"
                    "   *[other] Some apples.\n"
                    "}",
                    # Get no ref.
                    "refs": [],
                }
            ],
        )

        # On attribute, and using a Term Attribute.
        self.basic_test(
            """\
            amount = { $num ->
                [one] One apple.
                 *[other] { $num } apples.
            }
             .attr = { -term-ref.vowel-start ->
                 [yes] Have an { -term-ref }.
               *[no] Have a { -term-ref }.
             }
            """,
            # The FluentUnit just uses the same text.
            [
                {
                    "id": "amount",
                    "source": "{ $num ->\n"
                    "    [one] One apple.\n"
                    "   *[other] { $num } apples.\n"
                    "}\n"
                    ".attr =\n"
                    "{ -term-ref.vowel-start ->\n"
                    "    [yes] Have an { -term-ref }.\n"
                    "   *[no] Have a { -term-ref }.\n"
                    "}",
                    "refs": ["$num"],
                },
            ],
            """\
            amount =
                { $num ->
                    [one] One apple.
                   *[other] { $num } apples.
                }
                .attr =
                    { -term-ref.vowel-start ->
                        [yes] Have an { -term-ref }.
                       *[no] Have a { -term-ref }.
                    }
            """,
        )

        # Selector with other text.
        self.basic_test(
            """\
            amount =
                Just eat { $num ->
                    [one] an apple
                   *[other] { $num } apples
                } today.
            """,
            # The FluentUnit just uses the same text.
            [
                {
                    "id": "amount",
                    "source": "Just eat { $num ->\n"
                    "    [one] an apple\n"
                    "   *[other] { $num } apples\n"
                    "} today.",
                    "refs": ["$num"],
                }
            ],
        )

        # Sub-selector
        self.basic_test(
            """\
            sub =
                .a =
                    { $num ->
                        [zero] no apples
                       *[other]
                            { $num ->
                                [one] { $num } apple
                               *[other] { $num } apples
                            } and { $num2 ->
                                [one] { $num2 } oranges
                               *[other] { $num2 } oranges
                            }
                    }
            """,
            [
                {
                    "id": "sub",
                    "source": ".a =\n"
                    "{ $num ->\n"
                    "    [zero] no apples\n"
                    "   *[other]\n"
                    "        { $num ->\n"
                    "            [one] { $num } apple\n"
                    "           *[other] { $num } apples\n"
                    "        } and { $num2 ->\n"
                    "            [one] { $num2 } oranges\n"
                    "           *[other] { $num2 } oranges\n"
                    "        }\n"
                    "}",
                    # No refs since this is an attribute only.
                }
            ],
        )

        # Selector missing a default.
        self.assert_parse_failure(
            """\
            message = { $var ->
                [first] First
                [second] Second
            }
            """,
            r"message = { \$var ->",
        )

        fluent_file = self.quick_fluent_file(
            [
                {
                    "type": "Message",
                    "source": "{ $var ->\n[first] First\n[second] Second\n}",
                    "id": "bad",
                }
            ]
        )
        self.assert_serialize_failure(
            fluent_file,
            r'^Error in source of FluentUnit "bad":\n.* \[line 4, column 1\]$',
        )

    def test_functions(self):
        """Test fluent functions."""
        self.basic_test(
            """\
            time = Time is { DATETIME($now, hour: "numeric") }
            number = { NUMBER($var-num, minimumIntegerDigits: 4) } up
            -term =
                { NUMBER($n) ->
                    [0] -> Term0
                   *[other] -> Term
                }
            """,
            # The FluentUnit just uses the same text.
            [
                {
                    "id": "time",
                    "source": 'Time is { DATETIME($now, hour: "numeric") }',
                    "refs": ["$now"],
                },
                {
                    "id": "number",
                    "source": "{ NUMBER($var-num, minimumIntegerDigits: 4) } up",
                    "refs": ["$var-num"],
                },
                {
                    "id": "-term",
                    "source": "{ NUMBER($n) ->\n"
                    "    [0] -> Term0\n"
                    "   *[other] -> Term\n"
                    "}",
                    # No variable refs for Term.
                    "refs": [],
                },
            ],
        )

    def test_html_markup(self):
        """Test that Message and Term values can contain html markup."""
        self.basic_test(
            """\
            # The `link` is a link to the help page.
            help = visit <a data-l10n-name="link">our help page</a> for more information.
            """,
            [
                {
                    "id": "help",
                    "source": "visit "
                    '<a data-l10n-name="link">our help page</a>'
                    " for more information.",
                    "comment": "The `link` is a link to the help page.",
                }
            ],
        )

    def test_parse_errors(self):
        """Test that errors are extracted when parsing."""
        self.assert_parse_failure(
            """\
            message = hello
            # break
            .floating-attribute = yellow
            """,
            r"\.floating-attribute = yellow",
        )
        self.assert_parse_failure(
            """\
            message = { -ref
            """,
            r"message = { -ref",
        )

    @staticmethod
    def test_unit_ids():
        """Test that setting valid ids is ok, and invalid ids are blocked."""
        # Test valid ids.
        for fluent_type, unit_id in [
            ("Term", "-id"),
            ("Message", "i0"),
            ("Term", "-i9_8-h"),
        ]:
            unit = fluent.FluentUnit(
                source="ok", unit_id=unit_id, fluent_type=fluent_type
            )
            unit.setid(unit_id + "a")
            assert unit.getid() == unit_id + "a"
        # Test invalid ids.
        ok_id_dict = {"Message": "i", "Term": "-i"}
        for fluent_type, unit_id in [
            ("Term", "id"),
            ("Term", "id.a"),
            ("Term", "-id.a"),
            ("Term", "--id"),
            ("Message", "-id"),
            ("Message", "id.a"),
            ("Message", "a@"),
            ("Message", "0id"),
        ]:
            with raises(ValueError, match=r"^Invalid id "):
                fluent.FluentUnit(
                    source="test", unit_id=unit_id, fluent_type=fluent_type
                )
            ok_id = ok_id_dict.get(fluent_type)
            unit = fluent.FluentUnit(
                source="test", unit_id=ok_id, fluent_type=fluent_type
            )
            with raises(ValueError, match=r"^Invalid id "):
                unit.setid(unit_id)
            assert unit.getid() == ok_id

    def test_serialize_errors(self):
        """Test that errors are extracted when serializing."""
        fluent_file = self.quick_fluent_file(
            [
                {"type": "Message", "source": "fine", "id": "ok"},
                {"type": "Message", "source": "tmp", "id": "message-id"},
            ]
        )
        # Fluent syntax errors are not allowed.
        for source, line, column in [
            # Open placeable without closing.
            ("{", 1, 2),
            # Invalid id.
            ("includes { -b@d-term }", 1, 14),
            # Closing placeable without opening.
            ("ok\n.bad = open } bracket", 2, 13),
            # Invalid number literal.
            ("ok\n.ok = value\n  .bad = { .5 }\n.attr = value", 3, 12),
        ]:
            fluent_file.units[1].source = source
            self.assert_serialize_failure(
                fluent_file,
                r'^Error in source of FluentUnit "message-id":\n.* '
                f"\\[line {line}, column {column}\\]$",
            )

    def test_several_entries(self):
        """Test when we have several fluent Entries."""
        self.basic_test(
            """\
            # My license
            #
            # for this file.


            ### NOTE: Please be careful!


            ## This group is special 🍄.

            # Term to use
            -term-1 =
                { $possessive ->
                   *[no] Elephant
                    [yes] Elephant's
                }
                .vowel-start = yes
            # Variables:
            #   $var (string) - Some variable
            message-1 =
                Please select { $var } to continue.

                Thanks.
            message-2 = New Window 🙂
                .title = Opens a new window
                .accesskey = N
            # Watch out for this one.
            message-3 =
                .title = This { -term-1 } is great
                .alt =
                    { -term-1.vowel-start ->
                        [yes] An { -term-1(possessive: "yes") } tail.
                       *[no] A { -term-1(possessive: "yes") } tail.
                    }

            ##

            # Another message
            final-message = done!
            """,
            [
                {"type": "DetachedComment", "comment": "My license\n\nfor this file."},
                {"type": "ResourceComment", "comment": "NOTE: Please be careful!"},
                {"type": "GroupComment", "comment": "This group is special 🍄."},
                {
                    "id": "-term-1",
                    "source": "{ $possessive ->\n"
                    "   *[no] Elephant\n"
                    "    [yes] Elephant's\n"
                    "}\n"
                    ".vowel-start = yes",
                    "comment": "Term to use",
                },
                {
                    "id": "message-1",
                    "source": "Please select { $var } to continue.\n\nThanks.",
                    "comment": "Variables:\n  $var (string) - Some variable",
                    "refs": ["$var"],
                },
                {
                    "id": "message-2",
                    "source": "New Window 🙂\n"
                    ".title = Opens a new window\n"
                    ".accesskey = N",
                },
                {
                    "id": "message-3",
                    "source": ".title = This { -term-1 } is great\n"
                    ".alt =\n"
                    "{ -term-1.vowel-start ->\n"
                    '    [yes] An { -term-1(possessive: "yes") } tail.\n'
                    '   *[no] A { -term-1(possessive: "yes") } tail.\n'
                    "}",
                    "comment": "Watch out for this one.",
                },
                {"type": "GroupComment", "comment": ""},
                {
                    "id": "final-message",
                    "source": "done!",
                    "comment": "Another message",
                },
            ],
        )
