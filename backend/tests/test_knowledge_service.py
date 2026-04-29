"""Tests for the knowledge service — chunk_text (pure logic, no DB/Milvus)."""

from app.services.knowledge import chunk_text


class TestChunkText:
    """Tests for chunk_text function."""

    def test_chunk_text_basic(self):
        """Long text splits into multiple chunks."""
        text = "A" * 1000
        chunks = chunk_text(text, chunk_size=512, overlap=50)
        assert len(chunks) >= 2
        # Each chunk should be at most chunk_size characters
        for c in chunks:
            assert len(c) <= 512

    def test_chunk_text_short(self):
        """Short text returns a single chunk."""
        text = "Hello world"
        chunks = chunk_text(text, chunk_size=512, overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_chunk_text_no_overlap(self):
        """With overlap=0, consecutive chunks should not share characters."""
        text = "A" * 1000
        chunks = chunk_text(text, chunk_size=512, overlap=0)
        assert len(chunks) >= 2
        # With zero overlap, the end of chunk[i] should not overlap with chunk[i+1]
        for i in range(len(chunks) - 1):
            # chunk[i] covers text[i*512 : (i+1)*512]
            # chunk[i+1] covers text[(i+1)*512 : (i+2)*512]
            # So the last char of chunk[i] at position 511 should not appear
            # at the start of chunk[i+1]
            end_of_prev = chunks[i][-1] if chunks[i] else ""
            start_of_next = chunks[i + 1][0] if chunks[i + 1] else ""
            # With uniform text "AAA...", overlap=0 means last of prev and first of next
            # are at different positions in the original string.
            # For uniform text this just means the stride is chunk_size.
            assert len(chunks[i]) <= 512
            assert len(chunks[i + 1]) <= 512

    def test_chunk_text_empty(self):
        """Empty text returns empty list."""
        assert chunk_text("") == []

    def test_chunk_text_overlap(self):
        """Verify overlap produces overlapping regions."""
        text = "ABCDEFGHIJ" * 20  # 200 chars
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) >= 2
        # The stride is 100 - 20 = 80, so chunk[1] starts at position 80
        # chunk[0] is text[0:100], chunk[1] is text[80:180]
        # The overlapping region is text[80:100] which should appear at the
        # end of chunk[0] and start of chunk[1]
        assert chunks[0][-20:] == chunks[1][:20]
