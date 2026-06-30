# Re-export everything so that crm/urls.py (which uses `views.function_name`) works unchanged.
from crm.views.common import *  # noqa: F401,F403
from crm.views.companies import *  # noqa: F401,F403
from crm.views.rounds import *  # noqa: F401,F403
from crm.views.investors import *  # noqa: F401,F403
from crm.views.colaboradores import *  # noqa: F401,F403
from crm.views.ma import *  # noqa: F401,F403
from crm.views.colaboraciones import *  # noqa: F401,F403
from crm.views.inbox import *  # noqa: F401,F403
from crm.views.reports import *  # noqa: F401,F403
from crm.views.admin_views import *  # noqa: F401,F403
from crm.views.docs import *  # noqa: F401,F403
from crm.views.contacts import *  # noqa: F401,F403
