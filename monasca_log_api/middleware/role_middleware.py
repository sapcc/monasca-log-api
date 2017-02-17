# Copyright 2015 FUJITSU LIMITED
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_config import cfg
from oslo_log import log
from oslo_middleware import base as om
from webob import response

CONF = cfg.CONF
LOG = log.getLogger(__name__)

role_m_opts = [
    cfg.ListOpt(name='path',
                default='/',
                help='List of paths where middleware applies to'),
    cfg.ListOpt(name='default_roles',
                default=None,
                help='List of roles allowed to enter api'),
    cfg.ListOpt(name='agent_roles',
                default=None,
                help=('List of roles, that if set, mean that request '
                      'comes from agent, thus is authorized in the same '
                      'time'))
]
role_m_group = cfg.OptGroup(name='roles_middleware', title='roles_middleware')

CONF.register_group(role_m_group)
CONF.register_opts(role_m_opts, role_m_group)

_X_IDENTITY_STATUS = 'X-Identity-Status'
_X_ROLES = 'X-Roles'
_X_MONASCA_LOG_AGENT = 'X-MONASCA-LOG-AGENT'
_CONFIRMED_STATUS = 'Confirmed'


def _ensure_lower_roles(roles):
    if not roles:
        return []
    return [role.strip().lower() for role in roles]


def _intersect(a, b):
    return list(set(a) & set(b))


class RoleMiddleware(om.ConfigurableMiddleware):
    """Authorization middleware for X-Roles header.

    RoleMiddleware is responsible for authorizing user's
    access against **X-Roles** header. Middleware
    expects authentication to be completed (i.e. keystone middleware
    has been already called).

    If tenant is authenticated and authorized middleware
    exits silently (that is considered a success). Otherwise
    middleware produces JSON response according to following schema

    .. code-block:: json

        {
          'title': u'Unauthorized',
          'message': explanation (str)
        }

    Configuration example

    .. code-block:: cfg

        [roles_middleware]
        path = /v2.0/log
        default_roles = monasca-user
        agent_roles = monasca-log-agent

    Configuration explained:

    * path (list) - path (or list of paths) middleware should be applied
    * agent_roles (list) - list of roles that identifies tenant as an agent
    * default_roles (list) - list of roles that should be authorized

    Note:
        Being an agent means that tenant is automatically authorized.
    Note:
        Middleware works only for configured paths and for all
        requests apart from HTTP method **OPTIONS**.

    """

    def __init__(self, application, conf=None):
        super(RoleMiddleware, self).__init__(application, conf)
        middleware = CONF.roles_middleware

        self._path = middleware.path
        self._default_roles = _ensure_lower_roles(middleware.default_roles)
        self._agent_roles = _ensure_lower_roles(middleware.agent_roles)

        LOG.debug('RolesMiddleware initialized for paths=%s', self._path)

    def process_request(self, req):
        if not self._can_apply_middleware(req):
            LOG.debug('%s skipped in role middleware', req.path)
            return None

        is_authenticated = self._is_authenticated(req)
        is_authorized, is_agent = self._is_authorized(req)
        tenant_id = req.headers.get('X-Tenant-Id')

        req.environ[_X_MONASCA_LOG_AGENT] = is_agent

        LOG.debug('%s is authenticated=%s, authorized=%s, log_agent=%s',
                  tenant_id, is_authenticated, is_authorized, is_agent)

        if is_authenticated and is_authorized:
            LOG.debug('%s has been authenticated and authorized', tenant_id)
            return  # do return nothing to enter API internal

        # whoops
        if is_authorized:
            explanation = u'Failed to authenticate request for %s' % tenant_id
        else:
            explanation = (u'Tenant %s is missing a required role to access '
                           u'this service' % tenant_id)

        if explanation is not None:
            LOG.error(explanation)
            json_body = {u'title': u'Unauthorized', u'message': explanation}
            return response.Response(status=401,
                                     json_body=json_body,
                                     content_type='application/json')

    def _is_authorized(self, req):
        headers = req.headers
        roles = headers.get(_X_ROLES)

        if not roles:
            LOG.warning('Couldn\'t locate %s header,or it was empty', _X_ROLES)
            return False, False
        else:
            roles = _ensure_lower_roles(roles.split(','))

        is_agent = len(_intersect(roles, self._agent_roles)) > 0
        is_authorized = (len(_intersect(roles, self._default_roles)) > 0 or
                         is_agent)

        return is_authorized, is_agent

    def _is_authenticated(self, req):
        headers = req.headers
        if _X_IDENTITY_STATUS in headers:
            status = req.headers.get(_X_IDENTITY_STATUS)
            return _CONFIRMED_STATUS == status
        return False

    def _can_apply_middleware(self, req):
        path = req.path
        method = req.method

        if method == 'OPTIONS':
            return False

        if self._path:
            for p in self._path:
                if path.startswith(p):
                    return True
        return False  # if no configured paths, or nothing matches
