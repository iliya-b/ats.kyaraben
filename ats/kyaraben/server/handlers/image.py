
from aiohttp import web

from ats.util.db import sql


class ImageHandler:
    def setup_routes(self, app):
        router = app.router
        router.add_route('GET', '/images', self.list)

    async def list(self, request):
        request['slog'].debug('request: image list')

        rows = await sql(request, """
                         SELECT image, android_version
                           FROM images
                         """)

        response_js = {
            'images': [
                {
                    'image': row[0],
                    'android_version': row[1],
                } for row in rows
            ]
        }

        return web.json_response(response_js)
