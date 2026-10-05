from handlers.general import labeler as general_labeler
from handlers.moder import labeler as moder_labeler
from handlers.admin import labeler as admin_labeler
from handlers.owner import labeler as owner_labeler
from handlers.events import labeler as events_labeler
from handlers.security import labeler as security_labeler
from handlers.callbacks import labeler as callbacks_labeler

labelers = [
    callbacks_labeler,
    events_labeler,
    general_labeler,
    moder_labeler,
    admin_labeler,
    owner_labeler,
    security_labeler
]

__all__ = ["labelers"]
