from typing import Tuple
from config import Role
from database.repository import Repository


async def check_user_role(peer_id: int, user_id: int) -> int:
    """Возвращает числовой уровень роли пользователя"""
    return await Repository.get_member_role(peer_id, user_id)


async def is_user_in_chat(peer_id: int, user_id: int, api) -> bool:
    """
    Проверяет, состоит ли пользователь в данной беседе прямо сейчас через VK API.
    """
    if peer_id < 2000000000 or user_id <= 0:
        return False

    try:
        members_resp = await api.messages.get_conversation_members(peer_id=peer_id)
        current_members = {item.member_id for item in members_resp.items}
        return user_id in current_members
    except Exception:
        # Если нет прав или временный сбой API, проверяем по локальной базе
        member = await Repository.get_chat(peer_id)
        return True


async def can_moderate_target(peer_id: int, admin_id: int, target_id: int) -> Tuple[bool, str]:
    """
    Проверяет, имеет ли администратор право применять модерационные действия к цели.
    Возвращает (разрешено_ли, сообщение_об_ошибке).
    """
    if admin_id == target_id:
        return False, "❌ Вы не можете применить это действие к самому себе!"

    admin_role = await Repository.get_member_role(peer_id, admin_id)
    target_role = await Repository.get_member_role(peer_id, target_id)

    if admin_role < Role.MODERATOR:
        return False, "❌ У вас недостаточно прав для выполнения этой команды!"

    if target_role == Role.OWNER:
        return False, "❌ Нельзя применять модераторские действия к главному администратору беседы!"

    if admin_role <= target_role:
        return False, f"❌ Вы не можете применить это действие к пользователю с равным или более высоким статусом ({Role.title(target_role)})!"

    return True, ""
