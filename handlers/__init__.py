from handlers.general import labeler as general_labeler
from handlers.moder import labeler as moder_labeler
from handlers.admin import labeler as admin_labeler
from handlers.owner import labeler as owner_labeler
from handlers.events import labeler as events_labeler

labelers = [
    events_labeler,
    general_labeler,
    moder_labeler,
    admin_labeler,
    owner_labeler
]

__all__ = ["labelers"]
