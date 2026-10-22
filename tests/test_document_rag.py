import unittest
from array import array

import document_rag


class DocumentRetrievalTests(unittest.TestCase):
    def test_retrieval_ranks_relevant_pdf_pages_and_formats_citations(self):
        chunks = document_rag.chunk_document(
            "physics.pdf",
            "[Page 1]\nVoltage is 12 volts and resistance is 4 ohms.\n\n"
            "[Page 2]\nThe solar system contains eight planets.",
        )
        selected = document_rag.retrieve(
            "What voltage and resistance does the resistor have?",
            chunks,
        )
        self.assertEqual([(chunk.name, chunk.page) for chunk in selected], [("physics.pdf", 1)])
        self.assertIn("Source: physics.pdf, Page 1", document_rag.format_context(selected))
        self.assertIn("12 volts", document_rag.format_context(selected))
        self.assertNotIn("planets", document_rag.format_context(selected))

    def test_text_chunks_overlap_and_retrieval_is_bounded(self):
        source = " ".join(f"topic{index}" for index in range(1000))
        chunks = document_rag.chunk_document("notes.txt", source)
        self.assertGreater(len(chunks), 1)
        self.assertLessEqual(
            len(document_rag.format_context(document_rag.retrieve(
                "topic999", chunks, max_chars=250
            ))),
            500,
        )

    def test_local_index_persists_for_follow_up_but_isolated_by_chat(self):
        index = document_rag.LocalDocumentIndex()
        index.add("chat-a", "formula.txt", "Ohm law: voltage is 12 V and resistance is 4 ohms.")
        self.assertEqual(
            len(index.retrieve("chat-a", "What is the resistance?")),
            1,
        )
        self.assertEqual(index.retrieve("chat-b", "What is the resistance?"), [])

    def test_first_lines_preserves_original_lines_and_is_chat_scoped(self):
        index = document_rag.LocalDocumentIndex()
        source = "[Page 1]\nICSE CLASS 10 PHYSICS\n\nMoment = Force × distance\n"
        index.add("chat-a", "formula.pdf", source)

        self.assertEqual(
            index.first_lines("chat-a", 4),
            [("formula.pdf", "[Page 1]\nICSE CLASS 10 PHYSICS\n\nMoment = Force × distance")],
        )
        self.assertEqual(index.first_lines("chat-b", 4), [])

    def test_first_lines_rejects_invalid_counts(self):
        index = document_rag.LocalDocumentIndex()
        index.add("chat-a", "notes.txt", "First line")
        for count in (0, -1, True, 1.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                index.first_lines("chat-a", count)

    def test_query_without_terms_uses_first_available_chunks(self):
        chunks = document_rag.chunk_document("notes.txt", "Alpha details.\n\nBeta details.")
        selected = document_rag.retrieve("the and is", chunks, limit=1)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].text, "Alpha details. Beta details.")

    def test_semantic_retrieval_prefers_embedding_similarity_over_keyword_overlap(self):
        lexical_match = document_rag.DocumentChunk(
            "notes.txt", None, "The word nebula appears here.", ("nebula",),
            array("f", [0, 1]).tobytes(),
        )
        semantic_match = document_rag.DocumentChunk(
            "notes.txt", None, "A cloud of interstellar dust.", ("interstellar",),
            array("f", [1, 0]).tobytes(),
        )
        selected = document_rag.retrieve(
            "nebula", [lexical_match, semantic_match], query_embedding=[1, 0]
        )
        self.assertEqual(selected[0].text, "A cloud of interstellar dust.")

    def test_document_index_stores_embeddings_and_reports_availability(self):
        index = document_rag.LocalDocumentIndex()
        index.add("chat-a", "notes.txt", "A cloud of interstellar dust.", [[1, 0]])
        self.assertTrue(index.has_embeddings("chat-a"))
        self.assertEqual(
            index.retrieve("chat-a", "nebula", query_embedding=[1, 0])[0].text,
            "A cloud of interstellar dust.",
        )
        self.assertFalse(index.has_embeddings("chat-b"))


if __name__ == "__main__":
    unittest.main()
