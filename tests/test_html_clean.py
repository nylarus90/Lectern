from lectern.render.html_clean import anchor_name, normalize, strip_tags

SRC = """<html><head><title>Kap 1</title><style>p{color:red}</style></head><body>
<section id="s1"><h1>Titel</h1><p style="display:none">geheim</p>
<p>Hallo <mark>Welt</mark>!</p>
<figure><svg viewBox="0 0 10 10"><image xlink:href="img/cover.jpg"/></svg>
<figcaption>Bild 1</figcaption></figure>
<p><a href="kap2.xhtml#z">weiter</a><br/>Ende</body></html>"""


def test_normalize_maps_html5_and_resolves_resources():
    body, title = normalize(
        SRC,
        anchor_prefix="c0",
        resolve_src=lambda s: "RES:" + s,
        resolve_href=lambda h: "#HREF:" + h,
    )
    assert title == "Kap 1"
    assert "geheim" not in body, "display:none content must be dropped"
    assert "color:red" not in body, "<style> subtree must be dropped"
    assert '<a name="c0__s1"></a>' in body, "id must become a navigable anchor"
    assert "<div" in body and "<section" not in body, "section must map to div"
    assert '<img src="RES:img/cover.jpg" />' in body, "SVG cover must become <img>"
    assert '<a href="#HREF:kap2.xhtml#z">' in body
    assert body.count("<br />") == 1
    assert body.count("<div") == body.count("</div>"), "tags must balance"


def test_unclosed_tags_are_repaired():
    body, _ = normalize("<p>eins<p>zwei<b>fett", anchor_prefix="c1")
    assert body.count("<p>") == body.count("</p>")
    assert body.endswith("</b></p>") or body.endswith("</p>")


def test_image_without_resource_falls_back_to_alt_text():
    body, _ = normalize(
        '<p><img src="fehlt.png" alt="Ein Diagramm"/></p>',
        anchor_prefix="c0",
        resolve_src=lambda s: "",
    )
    assert "Ein Diagramm" in body and "<img" not in body


def test_strip_tags_and_anchor_name():
    # Tags collapse to a space so that "<p>a</p><p>b</p>" never becomes "ab".
    assert strip_tags("<p>Hallo   <b>Welt</b></p><p>Zwei</p>") == "Hallo Welt Zwei"
    assert strip_tags("Tom&amp;Jerry") == "Tom&Jerry"
    assert anchor_name("c3", "a b/c") == "c3__a_b_c"
    assert anchor_name("c3") == "c3"
