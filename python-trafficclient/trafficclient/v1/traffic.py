##
#test the openstack
#
import copy
import errno
import json
import os
import urllib

from trafficclient.common import base
from trafficclient.common import utils

UPDATE_PARAMS = ('name', 'disk_format', 'container_format', 'min_disk',
                 'min_ram', 'owner', 'size', 'is_public', 'protected',
                 'location', 'checksum', 'copy_from', 'properties',
                 #NOTE(bcwaldon: an attempt to update 'deleted' will be
                 # ignored, but we need to support it for backwards-
                 # compatibility with the legacy client library
                 'deleted')

CREATE_PARAMS = UPDATE_PARAMS + ('id',)

DEFAULT_PAGE_SIZE = 20


class Traffic(base.Resource):
    def __repr__(self):
        return "<Traffic %s>" % self._info

    def update(self, **fields):
        self.manager.update(self, **fields)

    def delete(self):
        return self.manager.delete(self)

    def data(self, **kwargs):
        return self.manager.data(self, **kwargs)


class TrafficManager(base.Manager):
    resource_class = Traffic

    def _traffic_meta_from_headers(self, headers):
        meta = {'properties': {}}
        for key, value in headers.iteritems():
            if key.startswith('x-image-meta-property-'):
                _key = key[22:]
                meta['properties'][_key] = value
            elif key.startswith('x-image-meta-'):
                _key = key[13:]
                meta[_key] = value

        for key in ['is_public', 'protected', 'deleted']:
            if key in meta:
                meta[key] = utils.string_to_bool(meta[key])

        return self._format_image_meta_for_user(meta)

    def _image_meta_to_headers(self, fields):
        headers = {}
        fields_copy = copy.deepcopy(fields)
        for key, value in fields_copy.pop('properties', {}).iteritems():
            headers['x-image-meta-property-%s' % key] = str(value)
        for key, value in fields_copy.iteritems():
            headers['x-image-meta-%s' % key] = str(value)
        return headers

    @staticmethod
    def _format_traffic_meta_for_user(meta):
        for key in ['size', 'min_ram', 'min_disk']:
            if key in meta:
                try:
                    meta[key] = int(meta[key])
                except ValueError:
                    pass
        return meta

    def get(self, image_id):
        """Get the metadata for a specific image.

        :param image: image object or id to look up
        :rtype: :class:`Image`
        """
        resp, body = self.api.client.raw_request('HEAD', '/v1/images/%s' % image_id)
        meta = self._image_meta_from_headers(dict(resp.getheaders()))
        return Traffic(self, meta)

    def data(self, image, do_checksum=True):
        """Get the raw data for a specific image.

        :param image: image object or id to look up
        :param do_checksum: Enable/disable checksum validation
        :rtype: iterable containing image data
        """
        image_id = base.getid(image)
        resp, body = self.api.client.raw_request('GET', '/v1/images/%s' % image_id)
        checksum = resp.getheader('x-image-meta-checksum', None)
        if do_checksum and checksum is not None:
            return utils.integrity_iter(body, checksum)
        else:
            return body

    def _get_file_size(self, obj):
        """Analyze file-like object and attempt to determine its size.

        :param obj: file-like object, typically redirected from stdin.
        :retval The file's size or None if it cannot be determined.
        """
        # For large images, we need to supply the size of the
        # image file. See LP Bugs #827660 and #845788.
        if hasattr(obj, 'seek') and hasattr(obj, 'tell'):
            try:
                obj.seek(0, os.SEEK_END)
                obj_size = obj.tell()
                obj.seek(0)
                return obj_size
            except IOError, e:
                if e.errno == errno.ESPIPE:
                    # Illegal seek. This means the user is trying
                    # to pipe image data to the client, e.g.
                    # echo testdata | bin/glance add blah..., or
                    # that stdin is empty, or that a file-like
                    # object which doesn't support 'seek/tell' has
                    # been supplied.
                    return None
                else:
                    raise
        else:
            # Cannot determine size of input image
            return None

    def create(self, instance_id, band, prio=1):
        qparams = {}
        qparams['instance_id'] = instance_id
        qparams['band'] = band
        qparams['prio'] = prio
        
        resp, body_iter = self.api.client.post('/traffic/create', body=qparams)
        return body_iter

    def delete(self, instance_id): 
        """Delete an image."""
        qparams = {}
        qparams['instance_id'] = instance_id
        self.api.client.post("/traffic/delete", body=qparams)
        
    def list(self, *args):
        url = '/traffic/list'
        return self._list(url, 'traffics')
    
    def show(self, instance_id):
        qparams = {}
        qparams['instance_id'] = instance_id
        resp, body = self.api.client.post('/traffic/show', body=qparams)
        return body

    
    def update(self, image, **kwargs):
        """Update an image

        TODO(bcwaldon): document accepted params
        """
        image_data = kwargs.pop('data', None)
        if image_data is not None:
            image_size = self._get_file_size(image_data)
            if image_size is not None:
                kwargs.setdefault('size', image_size)

        hdrs = {}
        try:
            purge_props = 'true' if kwargs.pop('purge_props') else 'false'
        except KeyError:
            pass
        else:
            hdrs['x-glance-registry-purge-props'] = purge_props

        fields = {}
        for field in kwargs:
            if field in UPDATE_PARAMS:
                fields[field] = kwargs[field]
            else:
                msg = 'update() got an unexpected keyword argument \'%s\''
                raise TypeError(msg % field)

        copy_from = fields.pop('copy_from', None)
        hdrs.update(self._image_meta_to_headers(fields))
        if copy_from is not None:
            hdrs['x-glance-api-copy-from'] = copy_from

        url = '/v1/images/%s' % base.getid(image)
        resp, body_iter = self.api.client.raw_request(
                'PUT', url, headers=hdrs, body=image_data)
        body = json.loads(''.join([c for c in body_iter]))
        return Traffic(self, self._format_image_meta_for_user(body['image']))
