def test_ensure_ui_loads(client):
    """The ui is rendered in javascript... so the response is always 200
    even if the openapi schema is malformed

    We could render the javacript using something like requests-html

    from requests_html import HTML
    html = HTML(html=r.data.decode())
    html.render()
    print(html.html)
    """

    r = client.get("/docs", allow_redirects=True)
    assert r.status_code == 200
    r = client.get("/redoc", allow_redirects=True)
    assert r.status_code == 200

    # redirect /ui to /redoc
    r = client.get("/ui", allow_redirects=True)
    assert r.status_code == 200
    assert r.url.endswith("/redoc")
