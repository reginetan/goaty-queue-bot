def is_admin(user):
    return any(role.permissions.administrator for role in user.roles)

def has_queue_permission(user):
    return is_admin(user) or user.guild_permissions.manage_messages

def check_permissions(ctx):
    if not has_queue_permission(ctx.author):
        raise commands.MissingPermissions(["manage_messages"])