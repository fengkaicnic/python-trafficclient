# Copyright 2012 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Base utilities to build API operation managers and objects on top of.
"""

import copy
import contextlib
import hashlib
import os
from trafficclient import exceptions
from trafficclient import utils

# Python 2.4 compat
try:
    all
except NameError:
    def all(iterable):
        return True not in (not x for x in iterable)


def getid(obj):
    """
    Abstracts the common pattern of allowing both an object or an object's ID
    (UUID) as a parameter when dealing with relationships.
    """
    try:
        return obj.id
    except AttributeError:
        return obj


class Manager(object):
    """
    Managers interact with a particular type of API (servers, flavors, images,
    etc.) and provide CRUD operations for them.
    """
    resource_class = None

    def __init__(self, api):
        self.api = api

    def _list(self, url, response_key, obj_class=None, body=None):
        if body:
            _resp, body = self.api.client.post(url, body=body)
        else:
            _resp, body = self.api.client.get(url)

        if obj_class is None:
            obj_class = self.resource_class

        data = body[response_key]
        # NOTE(ja): keystone returns values as list as {'values': [ ... ]}
        #           unlike other services which just return the list...
        if isinstance(data, dict):
            try:
                data = data['values']
            except KeyError:
                pass

        with self.completion_cache('human_id', obj_class, mode="w"):
            with self.completion_cache('uuid', obj_class, mode="w"):
                return [obj_class(self, res, loaded=True)
                        for res in data if res]
                
    @contextlib.contextmanager
    def completion_cache(self, cache_type, obj_class, mode):
        """
        The completion cache store items that can be used for bash
        autocompletion, like UUIDs or human-friendly IDs.

        A resource listing will clear and repopulate the cache.

        A resource create will append to the cache.

        Delete is not handled because listings are assumed to be performed
        often enough to keep the cache reasonably up-to-date.
        """
        base_dir = utils.env('NOVACLIENT_UUID_CACHE_DIR',
                             default="~/.novaclient")

        # NOTE(sirp): Keep separate UUID caches for each username + endpoint
        # pair
        username = utils.env('OS_USERNAME', 'NOVA_USERNAME')
        url = utils.env('OS_URL', 'NOVA_URL')
        uniqifier = hashlib.md5(username + url).hexdigest()

        cache_dir = os.path.expanduser(os.path.join(base_dir, uniqifier))

        try:
            os.makedirs(cache_dir, 0755)
        except OSError:
            # NOTE(kiall): This is typicaly either permission denied while
            #              attempting to create the directory, or the directory
            #              already exists. Either way, don't fail.
            pass

        resource = obj_class.__name__.lower()
        filename = "%s-%s-cache" % (resource, cache_type.replace('_', '-'))
        path = os.path.join(cache_dir, filename)

        cache_attr = "_%s_cache" % cache_type

        try:
            setattr(self, cache_attr, open(path, mode))
        except IOError:
            # NOTE(kiall): This is typicaly a permission denied while
            #              attempting to write the cache file.
            pass

        try:
            yield
        finally:
            cache = getattr(self, cache_attr, None)
            if cache:
                cache.close()
                delattr(self, cache_attr)

    def write_to_completion_cache(self, cache_type, val):
        cache = getattr(self, "_%s_cache" % cache_type, None)
        if cache:
            cache.write("%s\n" % val)


    def _delete(self, url):
        self.api.raw_request('DELETE', url)

    def _update(self, url, body, response_key=None):
        resp, body = self.api.json_request('PUT', url, body=body)
        # PUT requests may not return a body
        if body:
            return self.resource_class(self, body[response_key])


class Resource(object):
    """
    A resource represents a particular instance of an object (tenant, user,
    etc). This is pretty much just a bag for attributes.

    :param manager: Manager object
    :param info: dictionary representing resource attributes
    :param loaded: prevent lazy-loading if set to True
    """
    def __init__(self, manager, info, loaded=False):
        self.manager = manager
        self._info = info
        self._add_details(info)
        self._loaded = loaded

    def _add_details(self, info):
        for (k, v) in info.iteritems():
            setattr(self, k, v)

    def __getattr__(self, k):
        if k not in self.__dict__:
            #NOTE(bcwaldon): disallow lazy-loading if already loaded once
            if not self.is_loaded():
                self.get()
                return self.__getattr__(k)

            raise AttributeError(k)
        else:
            return self.__dict__[k]

    def __repr__(self):
        reprkeys = sorted(k for k in self.__dict__.keys() if k[0] != '_' and
                                                                k != 'manager')
        info = ", ".join("%s=%s" % (k, getattr(self, k)) for k in reprkeys)
        return "<%s %s>" % (self.__class__.__name__, info)

    def get(self):
        # set_loaded() first ... so if we have to bail, we know we tried.
        self.set_loaded(True)
        if not hasattr(self.manager, 'get'):
            return

        new = self.manager.get(self.id)
        if new:
            self._add_details(new._info)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if hasattr(self, 'id') and hasattr(other, 'id'):
            return self.id == other.id
        return self._info == other._info

    def is_loaded(self):
        return self._loaded

    def set_loaded(self, val):
        self._loaded = val

    def to_dict(self):
        return copy.deepcopy(self._info)
