
import os
import shutil
import pkg_resources
import tempfile

from ats.kyaraben.process import aiorun


def docker_env(env=None):
    if env is None:
        env = {}
    ret = {
        **env,
        'PATH': os.environ.get('PATH'),
        'DOCKER_HOST': os.environ['KYARABEN_DOCKER_HOST'],
        'DOCKER_TLS_VERIFY': os.environ['KYARABEN_DOCKER_TLS_VERIFY'],
    }
    if not ret.get('DOCKER_TLS_VERIFY'):
        del ret['DOCKER_TLS_VERIFY']
    return ret


async def cmd_docker(*args, log):
    ret = await aiorun('docker',
                       *args,
                       log=log,
                       env=docker_env())
    return ret


async def cmd_docker_exec(*args, log, stdin_bytes=None):
    ret = await aiorun('docker', 'exec',
                       *args,
                       log=log,
                       stdin_bytes=stdin_bytes,
                       env=docker_env())
    return ret


async def cmd_docker_run(*args, log, stdin_bytes=None):
    ret = await aiorun('docker', 'run',
                       *args,
                       log=log,
                       stdin_bytes=stdin_bytes,
                       env=docker_env())
    return ret

async def cmd_docker_cp(*, log, from_container, from_file,
                        to_container, to_file, tempdir):
    local_dir = tempfile.mkdtemp(dir=tempdir)
    local_file = os.path.join(local_dir, 'file')
    await cmd_docker('cp', '{}:{}'.format(from_container, from_file), local_file, log=log)
    await cmd_docker('cp', local_file, '{}:{}'.format(to_container, to_file), log=log)
    shutil.rmtree(local_dir)


async def cmd_docker_inspect(*args, log):
    ret = await aiorun('docker', 'inspect',
                       *args,
                       log=log,
                       env=docker_env())
    return ret


async def cmd_docker_compose(*args, log, envvars=None):
    template_dir = pkg_resources.resource_filename('ats.kyaraben.templates', 'docker')

    ret = await aiorun('docker-compose',
                       *args,
                       log=log,
                       cwd=template_dir,
                       env=docker_env(envvars))
    return ret
