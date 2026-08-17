from importlib.resources import files


def test_gui_web_bundle_contains_required_assets():
    root = files("sonus.gui").joinpath("web")

    for name in (
        "index.html",
        "styles.css",
        "app.js",
        "assets/wh-1000xm6-black.svg",
        "assets/PretendardVariable.woff2",
        "assets/lucide.svg",
        "assets/LUCIDE-LICENSE.txt",
    ):
        assert root.joinpath(name).is_file(), name

    html = root.joinpath("index.html").read_text(encoding="utf-8")
    assert "qrc:///qtwebchannel/qwebchannel.js" in html
    assert "설정 변경 전 확인" in html
    assert "assets/lucide.svg#" in html
    assert '<button class="nav-link active" data-view="status"><svg' in html
    assert ">01</span>상태" not in html
    assert "wh-1000xm6-black.png" not in html

    illustration = root.joinpath("assets/wh-1000xm6-black.svg").read_text(
        encoding="utf-8"
    )
    assert '<svg xmlns="http://www.w3.org/2000/svg"' in illustration
    assert "<image" not in illustration
