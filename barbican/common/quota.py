# Copyright (c) 2015 Cisco Systems
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from oslo_config import cfg
from oslo_log import log as logging

from barbican.common import exception
from barbican.common import hrefs
from barbican.model import repositories as repo


LOG = logging.getLogger(__name__)
UNLIMITED_VALUE = -1


quota_opt_group = cfg.OptGroup(name='quotas',
                               title='Quota Options')

quota_opts = [
    cfg.IntOpt('quota_secrets',
               default=-1,
               help='Number of secrets allowed per project'),
    cfg.IntOpt('quota_orders',
               default=-1,
               help='Number of orders allowed per project'),
    cfg.IntOpt('quota_containers',
               default=-1,
               help='Number of containers allowed per project'),
    cfg.IntOpt('quota_transport_keys',
               default=-1,
               help='Number of transport keys allowed per project'),
    cfg.IntOpt('quota_consumers',
               default=-1,
               help='Number of consumers allowed per project'),
]

CONF = cfg.CONF
CONF.register_group(quota_opt_group)
CONF.register_opts(quota_opts, group=quota_opt_group)


class QuotaDriver(object):
    """Driver to enforce quotas and obtain quota information."""

    def __init__(self):
        self.repo = repo.get_project_quotas_repository()

    def _get_resources(self):
        """List of resources that can be constrained by a quota"""
        return ['secrets', 'orders', 'containers', 'transport_keys',
                'consumers']

    def _get_defaults(self):
        """Return list of default quotas"""
        quotas = {
            'secrets': CONF.quotas.quota_secrets,
            'orders': CONF.quotas.quota_orders,
            'containers': CONF.quotas.quota_containers,
            'transport_keys': CONF.quotas.quota_transport_keys,
            'consumers': CONF.quotas.quota_consumers
        }
        return quotas

    def _extract_project_quotas(self, project_quotas_model):
        """Convert project quotas model to Python dict

        :param project_quotas_model: Model containing quota information
        :return: Python dict containing quota information
        """
        resp_quotas = {}
        for resource in self._get_resources():
            resp_quotas[resource] = getattr(project_quotas_model, resource)
        return resp_quotas

    def _compute_effective_quotas(self, configured_quotas):
        """Merge configured and default quota information

        When a quota value is not set, use the default value
        :param configured_quotas: configured quota values
        :return: effective quotas
        """
        default_quotas = self._get_defaults()
        resp_quotas = dict(configured_quotas)
        for resource, quota in resp_quotas.iteritems():
            if quota is None:
                resp_quotas[resource] = default_quotas[resource]
        return resp_quotas

    def _is_unlimited_value(self, v):
        """A helper method to check for unlimited value."""
        return v is not None and v <= UNLIMITED_VALUE

    def set_project_quotas(self, project_id, parsed_project_quotas):
        """Create a new database entry, or update existing one

        :param project_id: ID of project whose quotas are to be set
        :param parsed_project_quotas: quota values to save in database
        :return: None
        """
        session = self.repo.get_session()
        self.repo.create_or_update_by_project_id(
            project_id, parsed_project_quotas, session=session)
        session.commit()

    def get_project_quotas(self, project_id):
        """Retrieve configured quota information from database

        :param project_id: ID of project for whose value are wanted
        :return: the values
        """
        session = self.repo.get_session()
        try:
            retrieved_project_quotas =\
                self.repo.get_by_project_id(project_id, session=session)
        except exception.NotFound:
            return None
        resp_quotas = self._extract_project_quotas(retrieved_project_quotas)
        resp = {'project_quotas': resp_quotas}
        return resp

    def get_project_quotas_list(self, offset_arg=None, limit_arg=None):
        """Return a dict and list of all configured quota information

        :return: a dict and list of a page of quota config info
        """
        session = self.repo.get_session()
        retrieved_project_quotas, offset, limit, total =\
            self.repo.get_by_create_date(session=session,
                                         offset_arg=offset_arg,
                                         limit_arg=limit_arg,
                                         suppress_exception=True)
        resp_quotas = []
        for quotas in retrieved_project_quotas:
            list_item = {'project_id': quotas.project_id,
                         'project_quotas':
                             self._extract_project_quotas(quotas)}
            resp_quotas.append(list_item)
        resp = {'project_quotas': resp_quotas}
        resp_overall = hrefs.add_nav_hrefs(
            'project_quotas', offset, limit, total, resp)
        resp_overall.update({'total': total})
        return resp_overall

    def delete_project_quotas(self, project_id):
        """Remove configured quota information from database

        :param project_id: ID of project whose quota config will be deleted
        :raises NotFound: if project has no configured values
        :return: None
        """
        session = self.repo.get_session()
        self.repo.delete_by_project_id(project_id,
                                       session=session)

    def get_quotas(self, project_id):
        """Get the effective quotas for a project

        Effective quotas are based on both configured and default values
        :param project_id: ID of project for which to get effective quotas
        :return: dict of effective quota values
        """
        session = self.repo.get_session()
        try:
            retrieved_project_quotas =\
                self.repo.get_by_project_id(project_id,
                                            session=session)
        except exception.NotFound:
            resp_quotas = self._get_defaults()
        else:
            resp_quotas = self._compute_effective_quotas(
                self._extract_project_quotas(retrieved_project_quotas))
        resp = {'quotas': resp_quotas}
        return resp


class QuotaEnforcer(object):
    """Checks quotas limits and current resource usage levels"""
    def __init__(self, resource_type):
        self.resource_type = resource_type

    def enforce(self, project):
        """This is a dummy implementation for developing the API"""
        # TODO(dave) implement
        if project.id is None:  # dummy logic, dummy code
            raise exception.QuotaReached(project_id=project.external_id,
                                         resource_type=self.resource_type,
                                         count=0)
