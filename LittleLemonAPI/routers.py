from rest_framework.routers import DefaultRouter, DynamicRoute, Route


class LittleLemonRouter(DefaultRouter):
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
