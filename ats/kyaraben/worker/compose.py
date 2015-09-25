
import structlog

from ats.kyaraben.docker import cmd_docker_compose


async def project_up(project_id):
    log = structlog.get_logger()
    log.info('creating project container', project_id=project_id)

    await cmd_docker_compose(
        '-f', 'run-project.yml',
        '--project-name', 'project-%s' % project_id,
        'up', '--no-color', '--no-build', '-d',
        log=log,
        envvars={'AIC_PROJECT_PREFIX': project_id + '_'})


async def project_down(project_id):
    log = structlog.get_logger()
    log.info('removing project container', project_id=project_id)

    await cmd_docker_compose(
        '-f', 'run-project.yml',
        '--project-name', 'project-%s' % project_id,
        'kill',
        log=log,
        envvars={'AIC_PROJECT_PREFIX': project_id + '_'})

    await cmd_docker_compose(
        '-f', 'run-project.yml',
        '--project-name', 'project-%s' % project_id,
        'down', '-v',
        log=log,
        envvars={'AIC_PROJECT_PREFIX': project_id + '_'})


async def player_up(*, project_id, avm_id, instance_ip, hwconfig,
                    amqp_host, amqp_user, amqp_password, android_version, vnc_secret):
    log = structlog.get_logger()
    log.debug('creating player containers', avm_id=avm_id)

    hc = hwconfig

    envvars = {
        'AIC_AVM_PREFIX': avm_id + '_',
        'AIC_PROJECT_PREFIX': project_id + '_',
        'AIC_PLAYER_VM_ID': avm_id,
        'AIC_PLAYER_VM_HOST': instance_ip,
        'AIC_PLAYER_AMQP_HOST': amqp_host,
        'AIC_PLAYER_AMQP_USERNAME': amqp_user,
        'AIC_PLAYER_AMQP_PASSWORD': amqp_password,
        'AIC_PLAYER_WIDTH': str(hc['width']),
        'AIC_PLAYER_HEIGHT': str(hc['height']),
        'AIC_PLAYER_MAX_DIMENSION': str(max(int(hc['width']), int(hc['height']))),
        'AIC_PLAYER_DPI': str(hc['dpi']),
        'AIC_PLAYER_VNC_SECRET': vnc_secret,
        'AIC_PLAYER_ENABLE_SENSORS': str(hc['enable_sensors']),
        'AIC_PLAYER_ENABLE_BATTERY': str(hc['enable_battery']),
        'AIC_PLAYER_ENABLE_GPS': str(hc['enable_gps']),
        'AIC_PLAYER_ENABLE_CAMERA': str(hc['enable_camera']),
        'AIC_PLAYER_ENABLE_RECORD': str(hc['enable_record']),
        'AIC_PLAYER_ENABLE_GSM': str(hc['enable_gsm']),
        'AIC_PLAYER_ENABLE_NFC': str(hc['enable_nfc']),
        'AIC_PLAYER_ANDROID_VERSION': android_version,
        'AIC_PLAYER_PATH_RECORD': '/data/avm/log/',
    }

    await cmd_docker_compose(
        '-f', 'run-player.yml',
        '--project-name', 'avm-%s' % avm_id,
        'up', '--no-color', '--no-build', '-d',
        log=log,
        envvars=envvars)


async def player_down(*, avm_id, project_id):
    log = structlog.get_logger()
    log.debug('Removing containers', avm_id=avm_id)

    envvars = {
        'AIC_AVM_PREFIX': avm_id + '_',
        'AIC_PROJECT_PREFIX': project_id + '_',
    }

    await cmd_docker_compose(
        '-f', 'run-player.yml',
        '--project-name', 'avm-%s' % avm_id,
        'kill',
        log=log,
        envvars=envvars)

    await cmd_docker_compose(
        '-f', 'run-player.yml',
        '--project-name', 'avm-%s' % avm_id,
        'down', '-v',
        log=log,
        envvars=envvars)
