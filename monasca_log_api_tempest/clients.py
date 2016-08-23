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

from tempest import clients

from monasca_log_api_tempest.services import log_api_client
from monasca_log_api_tempest.services import log_search_client


class Manager(clients.Manager):
    def __init__(self, credentials=None, service=None):
        super(Manager, self).__init__(credentials, service)
        self.log_api_client = log_api_client.LogApiClient(
            self.auth_provider,
            'logs_v2',
            None
        )
        self.log_search_client = log_search_client.LogsSearchClient(
            self.auth_provider,
            'logs-search',
            None
        )
