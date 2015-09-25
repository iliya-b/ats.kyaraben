
from ats.kyaraben.model.android import AndroidVM
from ats.kyaraben.model.project import Project
from ats.kyaraben.model.apk import APK
from ats.kyaraben.model.camera import Camera
from ats.util.db import sql


async def is_task_obsolete(app, *, avm_id=None, project_id=None, apk_id=None, camera_id=None, **kw):
    # don't check for avm_command because it has no status=DELETED
    if avm_id and await AndroidVM.is_deleted(app, avm_id=avm_id):
        return True
    if project_id and await Project.is_deleted(app, project_id=project_id):
        return True
    if apk_id and await APK.is_deleted(app, apk_id=apk_id):
        return True
    if camera_id and await Camera.is_deleted(app, camera_id=camera_id):
        return True
    return False


async def set_status_error(app, log, *, reason, message):
    command_id = message.get('command_id')
    apk_id = message.get('apk_id')
    camera_id = message.get('camera_id')
    project_id = message.get('project_id')
    avm_id = message.get('avm_id')

    if command_id:
        await sql(app, """
            UPDATE avm_commands
               SET status = 'ERROR',
                   status_ts = transaction_timestamp(),
                   status_reason = %s
             WHERE command_id = %s
             """, [reason, command_id])
    elif apk_id:
        await sql(app, """
            UPDATE project_apks
               SET status = 'ERROR',
                   status_ts = transaction_timestamp(),
                   status_reason = %s
             WHERE apk_id = %s
             """, [reason, command_id])
    elif camera_id:
        await sql(app, """
            UPDATE project_camera
               SET status = 'ERROR',
                   status_ts = transaction_timestamp(),
                   status_reason = %s
             WHERE camera_id = %s
             """, [reason, camera_id])
    elif avm_id:
        await sql(app, """
            UPDATE avms
               SET status = 'ERROR',
                   status_ts = transaction_timestamp(),
                   status_reason = %s
             WHERE avm_id = %s
             """, [reason, avm_id])
    elif project_id:
        await sql(app, """
            UPDATE projects
               SET status = 'ERROR',
                   status_ts = transaction_timestamp(),
                   status_reason = %s
             WHERE project_id = %s
             """, [reason, project_id])
