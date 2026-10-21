from rest_framework.routers import DefaultRouter, DynamicRoute, Route


class LittleLemonRouter(DefaultRouter):
    """DefaultRouter whose routes accept an optional trailing slash.

    With APPEND_SLASH = False a slash-less path must match the route regex
    itself, otherwise it 404s (and Django raises a 500 for a slash-less POST
    while DEBUG is on). Making the slash optional in the regex lets one
    pattern serve both /path and /path/.
    """

    include_format_suffixes = False

    routes = [
        Route(
            url=r"^{prefix}/?$",
            mapping={"get": "list", "post": "create"},
            name="{basename}-list",
            detail=False,
            initkwargs={"suffix": "List"},
        ),
        DynamicRoute(
            url=r"^{prefix}/{url_path}/?$",
            name="{basename}-{url_name}",
            detail=False,
            initkwargs={},
        ),
        Route(
            url=r"^{prefix}/{lookup}/?$",
            mapping={
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            },
            name="{basename}-detail",
            detail=True,
            initkwargs={"suffix": "Instance"},
        ),
    ]
