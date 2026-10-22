import re
import unittest

import ui


class StreamPainterTests(unittest.TestCase):
    def test_flush_preserves_unmatched_inline_markers(self):
        for text in ("word*", "word**", "word`", "unfinished *italic"):
            with self.subTest(text=text):
                painter = ui.StreamPainter()
                rendered = painter.feed(text) + painter.flush()
                plain = re.sub(r"\x1b\[[0-9;]*m", "", rendered)
                self.assertIn(text, plain)

    def test_flush_keeps_closed_inline_markdown_styled(self):
        painter = ui.StreamPainter()
        rendered = painter.feed("**bold**") + painter.flush()
        self.assertNotIn("**", rendered)
        self.assertIn("bold", rendered)


if __name__ == "__main__":
    unittest.main()
