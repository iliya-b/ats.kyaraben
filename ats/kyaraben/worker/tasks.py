
import datetime
import os
import tempfile
import uuid
import re

from ats.kyaraben.model.android import AndroidVM
from ats.kyaraben.model.apk import APK
from ats.kyaraben.model.camera import Camera
from ats.kyaraben.model.campaign import Campaign
from ats.kyaraben.model.command import Command
from ats.kyaraben.model.project import Project
from ats.kyaraben.model.testsource import Testsource
from ats.kyaraben.docker import cmd_docker_exec, cmd_docker, cmd_docker_cp, cmd_docker_run
from ats.kyaraben.password import generate_password
from ats.kyaraben.process import quoted_cmdline, ProcessError
from ats.util.db import sql

from .amqp.admin import AMQPRestError
from .amqp.queues import create_event_queues, delete_event_queues
from .compose import player_up, player_down, project_up, project_down
from .openstack.exceptions import AVMNotFoundError


class TaskDelay(Exception):
    pass


def new_stack_name(stack_prefix, userid, avm_id):
    """
    Return the proposed stack name to use during a create operation.
    It can be truncated by heat; therefore it must not be used to derive
    a stack name from avm_id. The actual stack name is stored in the DB.
    """
    # Not sure which is the limit for a stack name.
    if stack_prefix:
        return '{}-{}-{}'.format(stack_prefix, userid, avm_id)
    else:
        return '{}-{}'.format(userid, avm_id)


def adb_container(avm_id):
    return '{}_adb'.format(avm_id)


def prj_container(project_id):
    return '{}_prjdata'.format(project_id)


async def project_container_create(app, log, *, userid, project_id):
    project = await Project.get(app, project_id=project_id, userid=userid)
    if not project:
        raise Exception('Project %s not found, or no permission for user %s' % (project_id, userid))

    await project.set_status(app, 'CREATING')

    await project_up(project_id)

    await project.set_status(app, 'READY')

    log.info('project READY', project_id=project_id)


async def project_container_delete(app, log, *, userid, project_id):
    project = await Project.get(app, project_id=project_id, userid=userid)
    if not project:
        raise Exception('Project %s not found, or no permission for user %s' % (project_id, userid))

    if (await project.is_active(app)):
        raise Exception('cannot delete project with active vms or campaigns')

    await project_down(project_id=project_id)

    log.info('deleting project', project_id=project_id)
    await project.set_status(app, 'DELETED')


async def camera_upload(app, log, *, userid, project_id, camera_id, filename, tmppath):
    project = await Project.get(app, project_id=project_id, userid=userid)
    if not project:
        raise Exception('Project %s not found, or no permission for user %s' % (project_id, userid))

    camera = await Camera.get(app, camera_id=camera_id, project_id=project_id, userid=userid)

    log.info('uploading file', filename=filename)

    with open(tmppath, 'rb') as fin:
        # XXX should buffer or use docker cp
        stdin_bytes = fin.read()

    await cmd_docker_exec('-i', prj_container(project_id),
                          '/root/video_create.sh',
                          filename,
                          await app.camera_path(camera_id=camera_id),
                          log=log,
                          stdin_bytes=stdin_bytes)

    await camera.set_status(app, 'READY')

    log.info('removing temp file', filename=filename)
    os.unlink(tmppath)


async def apk_upload(app, log, *, userid, project_id, apk_id, filename, tmppath):
    project = await Project.get(app, project_id=project_id, userid=userid)
    if not project:
        raise Exception('Project %s not found, or no permission for user %s' % (project_id, userid))

    apk = await APK.get(app, apk_id=apk_id, project_id=project_id, userid=userid)

    log.info('uploading file', filename=filename)

    apk_path = await app.apk_path(apk_id=apk_id)

    await cmd_docker('cp', tmppath, '{}:{}'.format(prj_container(project_id), apk_path), log=log)

    # make it readable to the other containers
    await cmd_docker_exec(prj_container(project_id), 'chmod', '644', apk_path, log=log)

    await apk.set_status(app, 'READY')

    log.info('removing temp file', filename=filename, tmppath=tmppath)
    os.unlink(tmppath)


async def camera_delete(app, log, *, userid, project_id, camera_id):
    project = await Project.get(app, project_id=project_id, userid=userid)
    if not project:
        raise Exception('Project %s not found, or no permission for user %s' % (project_id, userid))

    camera = await Camera.get(app, camera_id=camera_id, project_id=project_id, userid=userid)

    log.info('deleting file', camera_id=camera_id)

    await cmd_docker_exec(prj_container(project_id),
                          'rm', '-f', await app.camera_path(camera_id=camera_id), log=log)

    await camera.set_status(app, 'DELETED')


async def apk_delete(app, log, *, userid, project_id, apk_id):
    project = await Project.get(app, project_id=project_id, userid=userid)
    if not project:
        raise Exception('Project %s not found, or no permission for user %s' % (project_id, userid))

    apk = await APK.get(app, apk_id=apk_id, project_id=project_id, userid=userid)

    log.info('deleting apk', apk_id=apk_id)

    await cmd_docker_exec(prj_container(project_id),
                          'rm', '-f', await app.apk_path(apk_id=apk_id), log=log)

    await sql(app, """
              UPDATE testsources
                 SET apk_id = NULL
               WHERE apk_id = %s
              """, [apk_id])

    await apk.set_status(app, 'DELETED')


async def avm_amqp_config_create(app, log, *, userid, avm_id, amqp_user, amqp_password):
    avm = await AndroidVM.get(app, avm_id=avm_id, userid=userid)
    if not avm:
        raise Exception('AVM %s not found, or no permission for user %s' % (avm_id, userid))

    await create_event_queues(app, log, avm_id=avm_id)

    try:
        await app.amqp_admin.create_user(amqp_user, amqp_password)
    except AMQPRestError:
        log.exception('could not create AMQP user')
        raise

    try:
        await app.amqp_admin.set_user_permissions('/', amqp_user, avm_id)
    except AMQPRestError:
        log.exception('could not assign AMQP permissions')
        raise


async def avm_amqp_config_delete(app, log, *, userid, avm_id):
    avm = await AndroidVM.get(app, avm_id=avm_id, userid=userid)
    if not avm:
        raise Exception('User %s has no permission for avm %s' % (userid, avm_id))

    await delete_event_queues(app, log, avm_id=avm_id)

    try:
        await app.amqp_admin.delete_user(avm_id)
    except AMQPRestError as exc:
        if exc.args[0] == '404 (NOT_FOUND): "Not Found"\n':
            log.warning('AMQP user %s already removed', avm_id)
        else:
            log.error('Could not remove AMQP user %s (%s)', avm_id, exc)
            raise


async def avm_create(app, log, *, userid, image, project_id, avm_id, hwconfig, vnc_secret):
    avm = await AndroidVM.get(app, avm_id=avm_id, userid=userid)
    if not avm:
        raise Exception('User %s has no permission for avm %s' % (userid, avm_id))

    await avm.set_status(app, 'CREATING')

    amqp_user = avm_id
    amqp_password = generate_password(32)

    await avm_amqp_config_create(app, log,
                                 userid=userid,
                                 avm_id=avm_id,
                                 amqp_user=amqp_user,
                                 amqp_password=amqp_password)

    stack_prefix = app.config['orchestration']['stackprefix']

    stack_name = new_stack_name(stack_prefix, userid, avm_id)

    await avm.update_stack_name(app, stack_name=stack_name)

    row = await sql(app, """
            SELECT system_image, data_image
              FROM images
             WHERE image = %s""", [image])

    system_image = row[0].system_image
    data_image = row[0].data_image

    stack = await app.heat.stack_create(
        stack_name=stack_name,
        stack_params={
            'system_image': system_image,
            'data_image': data_image,
            # floating_net is only used by developer stack templates
            'floating_net': app.config['openstack']['floating_net'],
        },
        template=app.config['openstack']['template'],
        log=log)

    rows = await sql(app, """
                     SELECT android_version::TEXT AS android_version
                       FROM images
                      WHERE image = %s
                     """, [image])

    # TODO check for missing image

    android_version = rows[0].android_version

    await app.task_broker.publish('avm_containers_create', {
        'project_id': project_id,
        'avm_id': avm_id,
        'hwconfig': hwconfig,
        'amqp_user': amqp_user,
        'amqp_password': amqp_password,
        'android_version': android_version,
        'stack_name': stack_name,
        'stack_id': stack['id'],
        'userid': userid,
        'vnc_secret': vnc_secret,
    }, log=log)


async def avm_containers_create(app, log, *, userid, project_id, avm_id,
                                amqp_user, amqp_password, hwconfig,
                                stack_name, stack_id, android_version, vnc_secret):
    avm = await AndroidVM.get(app, avm_id=avm_id, userid=userid)
    if not avm:
        raise Exception('User %s has no permission for avm %s' % (userid, avm_id))

    stack_output = await app.heat.stack_output(stack_name=stack_name,
                                               stack_id=stack_id, log=log)

    if not stack_output:
        raise TaskDelay('stack_output for %s not ready' % stack_name)

    instance_ip = stack_output['instance_ip']

    if not instance_ip:
        raise TaskDelay('stack_output for %s not ready' % stack_name)

    amqp_host = app.config['amqp']['hostname']

    await player_up(project_id=project_id,
                    avm_id=avm_id,
                    instance_ip=instance_ip,
                    hwconfig=hwconfig,
                    amqp_host=amqp_host,
                    amqp_user=amqp_user,
                    amqp_password=amqp_password,
                    vnc_secret=vnc_secret,
                    android_version=android_version)

    await avm.start_billing(app)

    await avm.set_status(app, 'READY')


async def avm_delete(app, log, *, userid, avm_id, stack_name):
    avm = await AndroidVM.get(app, avm_id=avm_id, userid=userid)
    if not avm:
        raise Exception('User %s has no permission for avm %s' % (userid, avm_id))

    project_id = await avm.get_project_id(app)

    await player_down(avm_id=avm_id, project_id=project_id)

    await avm.stop_billing(app)

    await avm_amqp_config_delete(app, log,
                                 userid=userid,
                                 avm_id=avm_id)

    try:
        await app.heat.stack_delete(stack_name=stack_name, log=log)
    except AVMNotFoundError:
        log.warning('stack already removed', stack_name=stack_name)

    await avm.set_status(app, 'DELETED')


async def apk_install(app, log, *, userid, project_id, avm_id, apk_id, command_id):
    avm = await AndroidVM.get(app, avm_id=avm_id, userid=userid)
    if not avm:
        raise Exception('User %s has no permission for avm %s' % (userid, avm_id))

    log.info('installing APK', avm_id=avm_id, apk_id=apk_id)

    apk = await APK.get(app,
                        apk_id=apk_id,
                        project_id=project_id,
                        userid=userid)

    package_name = await apk.get_package_name(app)

    unquoted_command = ['adb', 'install', '-r', await app.apk_path(apk_id=apk_id)]

    quoted_command = quoted_cmdline(*unquoted_command)
    ts_begin = datetime.datetime.now()

    cmd = Command(command_id=command_id)
    await cmd.set_status(app, 'RUNNING')

    await sql(app, """
        UPDATE avm_commands
           SET command = %s,
               ts_begin = %s
         WHERE avm_id = %s
               AND command_id = %s
        """, [quoted_command, ts_begin, avm_id, command_id])

    # force uninstall, in case of changed signature, etc.
    try:
        await cmd_docker_exec(adb_container(avm_id), 'adb', 'shell', 'pm', 'uninstall', package_name, log=log)
    except ProcessError:
        pass

    await cmd_docker_exec(adb_container(avm_id),
                          'adb', 'shell', 'settings', 'put', 'global', 'install_non_market_apps', '1', log=log)

    await cmd_docker_exec(adb_container(avm_id),
                          'adb', 'shell', 'settings', 'put', 'global', 'package_verifier_enable', '0', log=log)

    proc = await cmd_docker_exec(adb_container(avm_id), *unquoted_command, log=log)

    ts_end = datetime.datetime.now()

    await sql(app, """
        UPDATE avm_commands
           SET ts_end = %s,
               proc_returncode = %s,
               proc_stdout = %s,
               proc_stderr = %s
         WHERE avm_id = %s
               AND command_id = %s
        """, [ts_end, proc.status, proc.out, proc.err, avm_id, command_id])

    if 'Success' not in proc.out:
        raise Exception('install failed')

    await cmd.set_status(app, 'READY')

    log.info('APK installed', avm_id=avm_id, apk_id=apk_id)


async def avm_monkey(app, log, *, userid, avm_id, command_id, packages, event_count, throttle):
    avm = await AndroidVM.get(app, avm_id=avm_id, userid=userid)
    if not avm:
        raise Exception('User %s has no permission for avm %s' % (userid, avm_id))

    log.info('monkey', avm_id=avm_id, packages=packages,
             event_count=event_count, throttle=throttle)

    unquoted_command = ['adb', 'shell', 'monkey']

    for package in packages:
        unquoted_command.extend(['-p', package])

    if throttle:
        unquoted_command.extend(['--throttle', str(throttle)])

    unquoted_command.append(str(event_count))

    quoted_command = quoted_cmdline(*unquoted_command)
    ts_begin = datetime.datetime.now()

    cmd = Command(command_id=command_id)
    await cmd.set_status(app, 'RUNNING')

    await sql(app, """
        UPDATE avm_commands
           SET command = %s,
               ts_begin = %s
         WHERE avm_id = %s
               AND command_id = %s
        """, [quoted_command, ts_begin, avm_id, command_id])

    proc = await cmd_docker_exec(adb_container(avm_id), *unquoted_command, log=log)

    ts_end = datetime.datetime.now()

    await sql(app, """
        UPDATE avm_commands
           SET ts_end = %s,
               proc_returncode = %s,
               proc_stdout = %s,
               proc_stderr = %s
         WHERE avm_id = %s
               AND command_id = %s
        """, [ts_end, proc.status, proc.out, proc.err, avm_id, command_id])

    await cmd.set_status(app, 'READY')

    log.info('monkey finished', status=proc.status)


async def avm_test_run(app, log, *, userid, avm_id, package, command_id):
    avm = await AndroidVM.get(app, avm_id=avm_id, userid=userid)
    if not avm:
        raise Exception('User %s has no permission for avm %s' % (userid, avm_id))

    log.info('test run', avm_id=avm_id)

    unquoted_command = ['adb', 'shell', 'am', 'instrument', '-r', '-w', package]

    quoted_command = quoted_cmdline(*unquoted_command)
    ts_begin = datetime.datetime.now()

    cmd = Command(command_id=command_id)
    await cmd.set_status(app, 'RUNNING')

    await sql(app, """
        UPDATE avm_commands
           SET command = %s,
               ts_begin = %s
         WHERE avm_id = %s
               AND command_id = %s
        """, [quoted_command, ts_begin, avm_id, command_id])

    proc = await cmd_docker_exec(adb_container(avm_id), *unquoted_command, log=log)

    ts_end = datetime.datetime.now()

    await sql(app, """
        UPDATE avm_commands
           SET ts_end = %s,
               proc_returncode = %s,
               proc_stdout = %s,
               proc_stderr = %s
         WHERE avm_id = %s
               AND command_id = %s
        """, [ts_end, proc.status, proc.out, proc.err, avm_id, command_id])

    await cmd.set_status(app, 'READY')

    log.info('test run finished', status=proc.status)


async def campaign_run(app, log, *, userid, project_id, campaign_id):
    project = await Project.get(app, project_id=project_id, userid=userid)
    if not project:
        raise Exception('User %s has no permission for project %s' % (userid, project_id))

    campaign = await Campaign.get(app, campaign_id=campaign_id, project_id=project_id, userid=userid)
    if not campaign:
        raise Exception('Campaign not found: %s' % campaign_id)

    await campaign.set_status(app, 'RUNNING')

    # create task for each image

    for row in await sql(app, """
            SELECT testruns.testrun_id,
                   testruns.image,
                   testruns.hwconfig,
                   ARRAY_AGG(apk_id::text ORDER BY install_order) AS apk_ids,
                   ARRAY_AGG(package) AS packages
              FROM testruns
              JOIN testrun_apks ON testruns.testrun_id=testrun_apks.testrun_id
         LEFT JOIN testrun_packages ON testruns.testrun_id=testrun_packages.testrun_id
             WHERE campaign_id = %s
          GROUP BY testruns.testrun_id
          ORDER BY testruns.testrun_id""", [campaign_id]):

        testrun_id = row.testrun_id
        image = row.image
        hwconfig = row.hwconfig
        apk_ids = row.apk_ids
        packages = [pkg for pkg in set(row.packages) if pkg is not None]

        await app.task_broker.publish('campaign_avm_create', {
            'userid': userid,
            'project_id': project_id,
            'campaign_id': campaign_id,
            'testrun_id': testrun_id,
            'image': image,
            'hwconfig': hwconfig,
            'apk_ids': apk_ids,
            'packages': packages
        }, log=log)


async def campaign_avm_create(app, log, *, userid, project_id, campaign_id,
                              testrun_id, image, hwconfig, apk_ids, packages):
    project = await Project.get(app, project_id=project_id, userid=userid)
    if not project:
        raise Exception('User %s has no permission for project %s' % (userid, project_id))

    campaign = await Campaign.get(app, campaign_id=campaign_id, project_id=project_id, userid=userid)
    if not campaign:
        raise Exception('Campaign not found: %s' % campaign_id)

    avm_id = uuid.uuid1().hex

    log = log.bind(avm_id=avm_id)

    vnc_secret = generate_password(128, password_chars='01234567890abcdef')

    vm_per_user = app.config['quota']['vm_async_max']

    async_current = (await AndroidVM.count(app, uid_owner=userid))['async_current']

    if vm_per_user and async_current >= vm_per_user:
        raise TaskDelay('Async vm quota reached (%d), waiting for a slot' % async_current)

    await AndroidVM.insert(app,
                           avm_id=avm_id,
                           avm_name=None,
                           userid=userid,
                           project_id=project.project_id,
                           image=image,
                           hwconfig=hwconfig,
                           testrun_id=testrun_id,
                           vnc_secret=vnc_secret)

    avm = await AndroidVM.get(app, avm_id=avm_id, userid=userid)
    if not avm:
        raise Exception('User %s has no permission for avm %s' % (userid, avm_id))

    await avm.set_status(app, 'CREATING')

    amqp_user = avm_id
    amqp_password = generate_password(32)

    await avm_amqp_config_create(app, log,
                                 userid=userid,
                                 avm_id=avm_id,
                                 amqp_user=amqp_user,
                                 amqp_password=amqp_password)

    stack_prefix = app.config['orchestration']['stackprefix']

    stack_name = new_stack_name(stack_prefix, userid, avm_id)

    await avm.update_stack_name(app, stack_name=stack_name)

    row = await sql(app, """
            SELECT system_image, data_image
              FROM images
             WHERE image = %s""", [image])

    system_image = row[0].system_image
    data_image = row[0].data_image

    stack = await app.heat.stack_create(
        stack_name=stack_name,
        stack_params={
            'system_image': system_image,
            'data_image': data_image,
            # floating_net is only used by developer stack templates
            'floating_net': app.config['openstack']['floating_net'],
        },
        template=app.config['openstack']['template'],
        log=log)

    rows = await sql(app, """
                     SELECT android_version::TEXT AS android_version
                       FROM images
                      WHERE image = %s
                     """, [image])

    # TODO check for missing image

    android_version = rows[0][0]

    await app.task_broker.publish('campaign_containers_create', {
        'userid': userid,
        'project_id': project_id,
        'campaign_id': campaign_id,
        'testrun_id': testrun_id,
        'avm_id': avm_id,
        'hwconfig': hwconfig,
        'amqp_user': amqp_user,
        'amqp_password': amqp_password,
        'android_version': android_version,
        'stack_name': stack_name,
        'stack_id': stack['id'],
        'apk_ids': apk_ids,
        'packages': packages,
        'vnc_secret': vnc_secret
    }, log=log)


async def campaign_containers_create(app, log, *, userid, project_id, campaign_id,
                                     testrun_id, avm_id, hwconfig, amqp_user, amqp_password,
                                     android_version, stack_name, stack_id, apk_ids, packages,
                                     vnc_secret):
    avm = await AndroidVM.get(app, avm_id=avm_id, userid=userid)
    if not avm:
        raise Exception('User %s has no permission for avm %s' % (userid, avm_id))

    stack_output = await app.heat.stack_output(stack_name=stack_name,
                                               stack_id=stack_id, log=log)

    if not stack_output:
        raise TaskDelay('stack_output for %s not ready' % stack_name)

    instance_ip = stack_output['instance_ip']

    if not instance_ip:
        raise TaskDelay('stack_output for %s not ready' % stack_name)

    amqp_host = app.config['amqp']['hostname']

    await player_up(project_id=project_id,
                    avm_id=avm_id,
                    instance_ip=instance_ip,
                    hwconfig=hwconfig,
                    amqp_host=amqp_host,
                    amqp_user=amqp_user,
                    amqp_password=amqp_password,
                    vnc_secret=vnc_secret,
                    android_version=android_version)

    await avm.start_billing(app)

    await avm.set_status(app, 'READY')

    await app.task_broker.publish('campaign_runtest', {
        'userid': userid,
        'project_id': project_id,
        'campaign_id': campaign_id,
        'avm_id': avm_id,
        'stack_name': stack_name,
        'apk_ids': apk_ids,
        'testrun_id': testrun_id,
        'packages': packages,
    }, log=log)


async def campaign_runtest(app, log, *, userid, project_id, campaign_id,
                           avm_id, stack_name, apk_ids, testrun_id, packages):
    campaign = await Campaign.get(app, campaign_id=campaign_id, project_id=project_id, userid=userid)
    if not campaign:
        raise Exception('Campaign not found: %s' % campaign_id)

    avm = await AndroidVM.get(app, avm_id=avm_id, userid=userid)
    if not avm:
        raise Exception('User %s has no permission for avm %s' % (userid, avm_id))

    try:
        proc = await cmd_docker_exec(adb_container(avm.avm_id),
                                     'adb', 'shell', 'getprop', 'dev.bootcomplete', log=log)
        if proc.out != '1':
            raise TaskDelay('dev.bootcomplete != 1 for %s' % stack_name)
    except ProcessError:
        raise TaskDelay('dev.bootcomplete not responding for %s' % stack_name)

    for apk_id in apk_ids:
        command_id = uuid.uuid1().hex

        ts_request = datetime.datetime.now()

        await sql(app, """
            INSERT INTO avm_commands (
                avm_id, command_id, ts_request
            ) VALUES (%s, %s, %s)
            """, [avm.avm_id, command_id, ts_request])

        await sql(app, """
            UPDATE testrun_apks
               SET command_id = %s
             WHERE testrun_id = %s
                   AND apk_id = %s
            """, [command_id, testrun_id, apk_id])

        log.info('installing APK', apk_id=apk_id)

        unquoted_command = ['adb', 'install', '-r', await app.apk_path(apk_id=apk_id)]

        quoted_command = quoted_cmdline(*unquoted_command)
        ts_begin = datetime.datetime.now()

        cmd = Command(command_id=command_id)
        await cmd.set_status(app, 'RUNNING')

        await sql(app, """
            UPDATE avm_commands
            SET command = %s,
                ts_begin = %s
            WHERE avm_id = %s
                AND command_id = %s
            """, [quoted_command, ts_begin, avm_id, command_id])

        proc = await cmd_docker_exec(adb_container(avm_id), *unquoted_command, log=log)

        ts_end = datetime.datetime.now()

        await sql(app, """
            UPDATE avm_commands
            SET ts_end = %s,
                proc_returncode = %s,
                proc_stdout = %s,
                proc_stderr = %s
            WHERE avm_id = %s
                AND command_id = %s
            """, [ts_end, proc.status, proc.out, proc.err, avm_id, command_id])

        if 'Success' not in proc.out:
            raise Exception('install failed')

        await cmd.set_status(app, 'READY')

        log.info('APK installed', apk_id=apk_id)

    if not len(packages):
        packages = await campaign_get_packages(app, avm_id, log)
        for package in packages:
            await sql(app, """
                      INSERT INTO testrun_packages (
                          testrun_id, package
                      ) VALUES (%s, %s)
                      """, [testrun_id, package])

    for package in packages:
        log.info('test run', package=package)
        command_id = uuid.uuid1().hex
        ts_request = datetime.datetime.now()

        await sql(app, """
            INSERT INTO avm_commands (
                avm_id, command_id, ts_request
            ) VALUES (%s, %s, %s)
            """, [avm.avm_id, command_id, ts_request])

        await sql(app, """
            UPDATE testrun_packages
               SET command_id = %s
             WHERE testrun_id = %s
                   AND package = %s
            """, [command_id, testrun_id, package])

        unquoted_command = ['adb', 'shell', 'am', 'instrument', '-r', '-w', package]

        quoted_command = quoted_cmdline(*unquoted_command)
        ts_begin = datetime.datetime.now()

        cmd = Command(command_id=command_id)
        await cmd.set_status(app, 'RUNNING')

        await sql(app, """
            UPDATE avm_commands
            SET command = %s,
                ts_begin = %s
            WHERE avm_id = %s
                AND command_id = %s
            """, [quoted_command, ts_begin, avm_id, command_id])

        proc = await cmd_docker_exec(adb_container(avm_id), *unquoted_command, log=log)

        ts_end = datetime.datetime.now()

        await sql(app, """
            UPDATE avm_commands
            SET ts_end = %s,
                proc_returncode = %s,
                proc_stdout = %s,
                proc_stderr = %s
            WHERE avm_id = %s
                AND command_id = %s
            """, [ts_end, proc.status, proc.out, proc.err, avm_id, command_id])

        await cmd.set_status(app, 'READY')

        log.info('test run finished', status=proc.status)

    log.info('deleting avm')

    project_id = await avm.get_project_id(app)

    await player_down(avm_id=avm_id, project_id=project_id)

    await avm.stop_billing(app)

    await avm_amqp_config_delete(app, log,
                                 userid=userid,
                                 avm_id=avm_id)

    try:
        await app.heat.stack_delete(stack_name=stack_name, log=log)
    except AVMNotFoundError:
        log.warning('stack already removed', stack_name=stack_name)

    await avm.set_status(app, 'DELETED')

    if list((await campaign.command_statuses(app)).keys()) == ['READY']:
        await campaign.set_status(app, 'READY')


async def testsource_compile(app, log, *, userid, project_id, testsource_id):
    project = await Project.get(app, project_id=project_id, userid=userid)
    if not project:
        raise Exception('User %s has no permission for project %s' % (userid, project_id))

    testsource = await Testsource.get(app,
                                      testsource_id=testsource_id,
                                      project_id=project.project_id,
                                      userid=userid)

    apk_id = await testsource.apk_id(app)
    content = await testsource.content(app)

    apk = await APK.get(app,
                        apk_id=apk_id,
                        project_id=project.project_id,
                        userid=userid)

    if not apk:
        raise Exception('APK not found: %s' % apk_id)

    await apk.set_status(app, 'COMPILING DSL')

    dslcc_container = uuid.uuid1().hex

    try:
        await cmd_docker_run('--name', dslcc_container, '-i', '--restart=no', 'aic.dslcc',
                             'scripts/compile.sh',
                             log=log,
                             stdin_bytes=content.encode('utf8'))
    except ProcessError as exc:
        await apk.set_status(app, 'ERROR', reason=exc.proc.err)
        await cmd_docker('rm', '-f', dslcc_container, log=log)
        return

    log.info('dslcc: {}'.format(dslcc_container))

    dslcc_output = '/home/developer/com.zenika.aicdsl/DslFiles/Testing.java'
    testcc_output = '/home/developer/signed.apk'

    with tempfile.NamedTemporaryFile() as testing_java:
        await cmd_docker('cp', '{}:{}'.format(dslcc_container, dslcc_output), testing_java.name, log=log)
        with open(testing_java.name) as fin:
            testing_java_content = fin.read()

        await apk.set_status(app, 'COMPILING JAVA')

        testcc_container = uuid.uuid1().hex

        try:
            proc = await cmd_docker_run('--name', testcc_container, '-i', '--restart=no', 'aic.testcc',
                                        '/home/developer/scripts/compile.sh',
                                        log=log,
                                        stdin_bytes=testing_java_content.encode('utf8'))
        except ProcessError as exc:
            await apk.set_status(app, 'ERROR', reason=exc.proc.err)
            await cmd_docker('rm', '-f', dslcc_container, log=log)
            await cmd_docker('rm', '-f', testcc_container, log=log)
            return

        package_name = proc.out_lines[-1]

    tempdir = app.config['media']['tempdir']

    await cmd_docker('rm', '-f', dslcc_container, log=log)

    await cmd_docker_cp(from_container=testcc_container,
                        from_file=testcc_output,
                        to_container='{}_prjdata'.format(project_id),
                        to_file=await app.apk_path(apk_id=apk_id),
                        tempdir=tempdir,
                        log=log)

    await apk.set_package_name(app, package_name)

    await cmd_docker('rm', '-f', testcc_container, log=log)

    await apk.set_status(app, 'READY')


async def campaign_get_packages(app, avm_id, log):
    log.info('getting list of instrumented packages', avm_id=avm_id)

    unquoted_command = ['adb', 'shell', 'pm', 'list', 'instrumentation']

    proc = await cmd_docker_exec(adb_container(avm_id), *unquoted_command, log=log)

    _re_parse_instrumentation = re.compile('instrumentation:(?P<package>.*) \(target=(?P<target>.*)\)')

    packages = []
    for line in proc.out_lines:
        m = _re_parse_instrumentation.match(line)
        if not m:
            raise Exception('Cannot parse instrumentation package: %s' % line)
        if m.group('package') != 'com.example.android.apis/.app.LocalSampleInstrumentation':
            packages.append(m.group('package'))

    log.info('packages listed', avm_id=avm_id)

    return packages


async def campaign_delete(app, log, *, userid, project_id, campaign_id):

    campaign = await Campaign.get(app, campaign_id=campaign_id, project_id=project_id, userid=userid)

    for row in await sql(app, """
            SELECT avm_id, stack_name
              FROM campaign_resources
             WHERE campaign_id = %s""", [campaign_id]):
        avm_id = row.avm_id
        stack_name = row.stack_name

        avm = await AndroidVM.get(app, avm_id=avm_id, userid=userid)
        if avm:
            await app.task_broker.publish('avm_delete', {
                'userid': userid,
                'avm_id': avm_id,
                'stack_name': stack_name,
            }, log=log)
            await avm.set_status(app, status='DELETING')

    await campaign.set_status(app, status='DELETED')
