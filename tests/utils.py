def join_url(*args):
    return "/".join(s.strip("/") for s in args)


def api_url(*args):
    return join_url("/api/v1", *args)
