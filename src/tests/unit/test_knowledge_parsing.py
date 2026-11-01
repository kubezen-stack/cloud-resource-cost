from app.services.knowledge_base import Chunk, load_catalog, parse_markdown

DOC = """# Databases

Intro text about databases.

## Sizing
Pick by memory.

## Backups
Keep seven days.
"""


def test_parse_markdown_splits_intro_and_sections():
    chunks = parse_markdown("db.md", DOC)

    assert [c.heading for c in chunks] == ["Databases", "Databases / Sizing", "Databases / Backups"]
    assert chunks[0].content == "Intro text about databases."
    assert chunks[1].content == "Pick by memory."
    assert all(c.source == "db.md" for c in chunks)


def test_empty_sections_are_skipped():
    chunks = parse_markdown("x.md", "# T\n\n## Empty\n\n## Full\ntext\n")
    assert [c.heading for c in chunks] == ["T / Full"]


def test_hash_changes_with_content():
    a = Chunk("f.md", "H", "one")
    b = Chunk("f.md", "H", "two")
    assert a.content_hash != b.content_hash
    assert a.content_hash == Chunk("f.md", "H", "one").content_hash


def test_real_catalog_is_well_formed():
    chunks = load_catalog()

    assert len(chunks) >= 30
    assert len({(c.source, c.heading) for c in chunks}) == len(chunks)
    assert all(c.content.strip() for c in chunks)
    assert {c.source for c in chunks} >= {"ec2-instance-families.md", "rds-databases.md"}
