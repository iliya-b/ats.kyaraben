
from http import HTTPStatus
import json
import pkg_resources
import re

from .exceptions import AVMNotFoundError, AVMCreationError, AVMImageNotFoundError


header_json_content = ('Content-Type', 'application/json')

HEAT = 'heat-api'

GET = 'get'
POST = 'post'
DELETE = 'delete'


def status_message(status):
    try:
        return '{}: {}'.format(status, HTTPStatus(status).description)
    except ValueError:
        return 'HTTP Status {}'.format(status)


def check_image_could_not_be_found(error):
    if not error:
        error = {}
    message = error.get('message', '')
    # checking 'type' == 'ResourceNotAvailable' is not enough
    return re.search('The Image (.*) could not be found', message)


def output_dict(outputs):
    ret = {}
    for output in outputs:
        ret[output['output_key']] = output['output_value']
    return ret


class HeatClient:
    def __init__(self, openstack, config):
        self.openstack = openstack
        self.config = config

    async def stack_output(self, stack_name, stack_id, log):
        """
        Retrieves output parameters from an existing stack.
        If output parameters are not available, return None.

        returns:
            dictionary of {output_key: output_value...}
        """
        r = await self.openstack(HEAT, GET, ['stacks', stack_name, stack_id])

        js = await r.json()

        stack = js['stack']

        if 'outputs' in stack:
            log.debug('Got stack output', outputs=stack['outputs'])
            return output_dict(stack['outputs'])

        return None

    template_re = re.compile('^[a-zA-Z0-9_\.\-]+$')

    async def stack_create(self, stack_name, stack_params, log, template='android.yml'):
        if not self.template_re.match(template):
            raise ValueError('Invalid template name "%s": must be %s' % (
                template,
                self.template_re.pattern)
            )

        template = pkg_resources.resource_string('ats.kyaraben.templates.openstack', template).decode('utf8')

        response_js = {
            'stack_name': stack_name,
            'template': template,
            'parameters': stack_params,
        }

        log.info('Creating stack', stack_name=stack_name)

        r = await self.openstack(HEAT, POST, ['stacks'],
                                 data=json.dumps(response_js),
                                 headers=[header_json_content])

        js = await r.json()

        if r.status != HTTPStatus.CREATED:
            log.error('Stack creation error', body=js)
            if check_image_could_not_be_found(js.get('error')):
                raise AVMImageNotFoundError
            raise AVMCreationError

        # TODO: test error cases (malformed template etc)

        return js['stack']

    async def lookup_stack_id(self, stack_name, log):
        r = await self.openstack(HEAT, GET, ['stacks', stack_name])

        if r.status == HTTPStatus.NOT_FOUND:
            raise AVMNotFoundError('Stack %s not found' % stack_name)

        if r.status != HTTPStatus.OK:
            text = await r.text()
            log.warning('Error from heat', error=text)
            raise Exception(status_message(r.status))

        js = await r.json()

        return js['stack']['id']

    async def stack_delete(self, stack_name, log):
        log.info('Removing stack', stack_name=stack_name)

        stack_id = await self.lookup_stack_id(stack_name=stack_name, log=log)

        r = await self.openstack(HEAT, DELETE, ['stacks', stack_name, stack_id])
        r.close()

        if r.status == HTTPStatus.NOT_FOUND:
            raise AVMNotFoundError('Stack %s not found' % stack_name)

        if r.status == HTTPStatus.CONFLICT:
            # when does this happen?
            log.warning('Heat returned CONFLICT', stack_name=stack_name)
            raise Exception(status_message(r.status))

        if r.status != HTTPStatus.NO_CONTENT:
            text = await r.text()
            log.warning('Error from heat', error=text)
            raise Exception(status_message(r.status))
