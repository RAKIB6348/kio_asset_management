# -*- coding: utf-8 -*-

from . import controllers
from . import models


def post_init_hook(env):
    env['kio.asset.unit']._init_migrate_maintenance_to_repair()
    env['kio.asset.unit'].action_sync_assignment_statuses()
