from dst_wiki_db.parser import parse_page


def test_parse_page_extracts_infobox_fields_and_images():
    text = """{{Character Infobox
|image ds=Wilson.png
|image dst=Wilson Original Portrait.png
|health ds=150
|hunger dst=150
|spawnCode dst="wilson"
}}
'''Wilson Percival Higgsbury''' is a playable [[character]].
[[Category:Characters]]
"""

    parsed = parse_page("Wilson", text)

    assert parsed.kind == "character"
    assert parsed.summary.startswith("Wilson Percival Higgsbury")
    assert parsed.infoboxes[0].name == "Character Infobox"
    assert parsed.attributes["health ds"] == "150"
    assert parsed.attributes["spawnCode dst"] == '"wilson"'
    assert [image.name for image in parsed.images] == [
        "Wilson.png",
        "Wilson Original Portrait.png",
    ]
    assert parsed.images[0].role == "image ds"
    assert parsed.categories == ["Characters"]
    assert parsed.links == ["character"]


def test_parse_page_classifies_boss_from_category():
    text = """{{Mob Infobox
|image=Deerclops.png
|health=2000
|damage=75
|attack period=3
}}
'''Deerclops''' is a giant.
[[Category:Bosses]]
[[Category:Mobs]]
"""

    parsed = parse_page("Deerclops", text)

    assert parsed.kind == "boss"
    assert parsed.attributes["damage"] == "75"
    assert parsed.categories == ["Bosses", "Mobs"]


def test_parse_page_prefers_infobox_type_over_loose_categories():
    text = """{{Mob Infobox
|image=Abigail.png
|health=150
}}
'''Abigail''' is a mob.
[[Category:Characters]]
[[Category:Mobs]]
"""

    parsed = parse_page("Abigail", text)

    assert parsed.kind == "mob"
