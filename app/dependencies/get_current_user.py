from typing import Annotated

from core.security import get_current_user

from fastapi import Depends

CurrentUserDep = Annotated[dict, Depends(get_current_user)]
