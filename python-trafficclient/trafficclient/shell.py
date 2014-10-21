"""
command line , interface to traffic api
"""

import argparse
import logging
import re
import sys

from keystoneclient.v2_0 import client as ksclient

import trafficclient
from trafficclient import exc
from trafficclient.common import utils

class OpenstackTrafficShell(object):
    
    def get_base_parser(self):
        parser = argparse.ArgumentParser(
                 prog = 'traffic',
                 description = __doc__.strip(),
                 epilog = 'See "traffic help COMMAND"'
                          'for help on a special help .',
                 add_help = False,
                 formatter_class = HelpFormatter,
        )
        
        parser.add_argument('-h', '--help',
                            action = 'store_true',
                            help = argparse.SUPPRESS,)
        parser.add_argument('-d', '--debug',
                            default = bool(utils.env('TRAFFICCLIENT_DEBUG')),
                            action = 'store_true',
                            help = 'Defaults to env[TRAFFICCLIENT_DEBUG]')
        
        parser.add_argument('-v', '--verbase',
                            default = False, action='store_true',
                            help = 'Print more verbase output')
        
        parser.add_argument('--timeout',
            default=600,
            help='Number of seconds to wait for a response')
        
        parser.add_argument('-H', '--host',
            metavar='ADDRESS',
            help='DEPRECATED! Send a fully-formed endpoint using '
                 '--os-traffic-url instead.')

        #NOTE(bcwaldon): DEPRECATED
        parser.add_argument('-p', '--port',
            dest='port',
            metavar='PORT',
            type=int,
            default=9898,
            help='DEPRECATED! Send a fully-formed endpoint using '
                 '--os-traffic-url instead.')
        
        parser.add_argument('--os-username',
            default=utils.env('OS_USERNAME'),
            help='Defaults to env[OS_USERNAME]')

        parser.add_argument('--os_username',
            help=argparse.SUPPRESS)

        #NOTE(bcwaldon): DEPRECATED
        parser.add_argument('-I',
            dest='os_username',
            help='DEPRECATED! Use --os-username.')

        parser.add_argument('--os-password',
            default=utils.env('OS_PASSWORD'),
            help='Defaults to env[OS_PASSWORD]')

        parser.add_argument('--os_password',
            help=argparse.SUPPRESS)
        
        parser.add_argument('--os-tenant-id',
            default=utils.env('OS_TENANT_ID'),
            help='Defaults to env[OS_TENANT_ID]')

        parser.add_argument('--os_tenant_id',
            help=argparse.SUPPRESS)
        parser.add_argument('--os-tenant-name',
            default=utils.env('OS_TENANT_NAME'),
            help='Defaults to env[OS_TENANT_NAME]')

        parser.add_argument('--os_tenant_name',
            help=argparse.SUPPRESS)

        #NOTE(bcwaldon): DEPRECATED
        parser.add_argument('-T',
            dest='os_tenant_name',
            help='DEPRECATED! Use --os-tenant-name.')

        parser.add_argument('--os-auth-url',
            default=utils.env('OS_AUTH_URL'),
            help='Defaults to env[OS_AUTH_URL]')

        parser.add_argument('--os_auth_url',
            help=argparse.SUPPRESS)
        
        parser.add_argument('-N',
            dest='os_auth_url',
            help='DEPRECATED! Use --os-auth-url.')

        parser.add_argument('--os-region-name',
            default=utils.env('OS_REGION_NAME'),
            help='Defaults to env[OS_REGION_NAME]')

        parser.add_argument('--os_region_name',
            help=argparse.SUPPRESS)

        #NOTE(bcwaldon): DEPRECATED
        parser.add_argument('-R',
            dest='os_region_name',
            help='DEPRECATED! Use --os-region-name.')

        parser.add_argument('--os-auth-token',
            default=utils.env('OS_AUTH_TOKEN'),
            help='Defaults to env[OS_AUTH_TOKEN]')

        parser.add_argument('--os_auth_token',
            help=argparse.SUPPRESS)        
        
        parser.add_argument('-A', '--auth_token',
            dest='os_auth_token',
            help='DEPRECATED! Use --os-auth-token.')

        parser.add_argument('--os-traffic-url',
            default=utils.env('OS_TRAFFIC_URL'),
            help='Defaults to env[OS_TRAFFIC_URL]')

        parser.add_argument('--os_traffic_url',
            help=argparse.SUPPRESS)

        #NOTE(bcwaldon): DEPRECATED
        parser.add_argument('-U', '--url',
            dest='os_traffic_url',
            help='DEPRECATED! Use --os-traffic-url.')

        parser.add_argument('--os-traffic-api-version',
            default=utils.env('OS_TRAFFIC_API_VERSION', default='1'),
            help='Defaults to env[OS_TRAFFIC_API_VERSION] or 1')

        parser.add_argument('--os_traffic_api_version',
            help=argparse.SUPPRESS)

        parser.add_argument('--os-service-type',
            default=utils.env('OS_SERVICE_TYPE'),
            help='Defaults to env[OS_SERVICE_TYPE]')

        parser.add_argument('--os_service_type',
            help=argparse.SUPPRESS)

        parser.add_argument('--os-endpoint-type',
            default=utils.env('OS_ENDPOINT_TYPE'),
            help='Defaults to env[OS_ENDPOINT_TYPE]')

        parser.add_argument('--os_endpoint_type',
            help=argparse.SUPPRESS)

        parser.add_argument('-S', '--os_auth_strategy',
            help='DEPRECATED! This option is completely ignored.')

        return parser
    
    def get_subcommand_parser(self, version):
        parser = self.get_base_parser()
        self.subcommands = {}

        subparsers = parser.add_subparsers(metavar='<subcommand>')
        submodule = utils.import_versioned_module(version, 'shell')
        self._find_actions(subparsers, submodule)
        self._find_actions(subparsers, self)

        return parser
    
    def _find_actions(self, subparsers, actions_module):
        for attr in (a for a in dir(actions_module) if a.startswith('do_')):
            # I prefer to be hypen-separated instead of underscores.
            command = attr[3:].replace('_', '-')
            callback = getattr(actions_module, attr)
            desc = callback.__doc__ or ''
            help = desc.strip().split('\n')[0]
            arguments = getattr(callback, 'arguments', [])

            subparser = subparsers.add_parser(command,
                help=help,
                description=desc,
                add_help=False,
                formatter_class=HelpFormatter
            )
            subparser.add_argument('-h', '--help',
                action='help',
                help=argparse.SUPPRESS,
            )
            self.subcommands[command] = subparser
            for (args, kwargs) in arguments:
                subparser.add_argument(*args, **kwargs)
            subparser.set_defaults(func=callback)
            
    def _strip_version(self, endpoint):
        """Strip a version from the last component of an endpoint if present"""

        # Get rid of trailing '/' if present
        if endpoint.endswith('/'):
            endpoint = endpoint[:-1]
        url_bits = endpoint.split('/')
        # regex to match 'v1' or 'v2.0' etc
        if re.match('v\d+\.?\d*', url_bits[-1]):
            endpoint = '/'.join(url_bits[:-1])
        return endpoint

    def _get_ksclient(self, **kwargs):
        """Get an endpoint and auth token from Keystone.

        :param username: name of user
        :param password: user's password
        :param tenant_id: unique identifier of tenant
        :param tenant_name: name of tenant
        :param auth_url: endpoint to authenticate against
        """
        return ksclient.Client(username=kwargs.get('username'),
                               password=kwargs.get('password'),
                               tenant_id=kwargs.get('tenant_id'),
                               tenant_name=kwargs.get('tenant_name'),
                               auth_url=kwargs.get('auth_url'),
                               insecure=kwargs.get('insecure'))

    def _get_endpoint(self, client, **kwargs):
        """Get an endpoint using the provided keystone client."""
        endpoint = client.service_catalog.url_for(
                service_type=kwargs.get('service_type') or 'traffic',
                endpoint_type=kwargs.get('endpoint_type') or 'publicURL')
        return self._strip_version(endpoint)

    def _get_traffic_url(self, args):
        """Translate the available url-related options into a single string.

        Return the endpoint that should be used to talk to Glance if a
        clear decision can be made. Otherwise, return None.
        """
        if args.os_traffic_url:
            return args.os_traffic_url
        elif args.host:
            scheme = 'https' if args.use_ssl else 'http'
            return '%s://%s:%s/' % (scheme, args.host, args.port)
        else:
            return None

    def main(self, argv):
        # Parse args once to find version
        parser = self.get_base_parser()
        (options, args) = parser.parse_known_args(argv)

        # build available subcommands based on version
        api_version = options.os_traffic_api_version
        subcommand_parser = self.get_subcommand_parser(api_version)
        self.parser = subcommand_parser

        # Handle top-level --help/-h before attempting to parse
        # a command off the command line
        if options.help or not argv:
            self.do_help(options)
            return 0

        # Parse args again and call whatever callback was selected
        args = subcommand_parser.parse_args(argv)

        # Short-circuit and deal with help command right away.
        if args.func == self.do_help:
            self.do_help(args)
            return 0

        LOG = logging.getLogger('glanceclient')
        LOG.addHandler(logging.StreamHandler())
        LOG.setLevel(logging.DEBUG if args.debug else logging.INFO)

        traffic_url = self._get_traffic_url(args)
        auth_reqd = (utils.is_authentication_required(args.func) and
                     not (args.os_auth_token and traffic_url))

        if not auth_reqd:
            endpoint = traffic_url
            token = args.os_auth_token
        else:
            if not args.os_username:
                raise exc.CommandError("You must provide a username via"
                        " either --os-username or env[OS_USERNAME]")

            if not args.os_password:
                raise exc.CommandError("You must provide a password via"
                        " either --os-password or env[OS_PASSWORD]")

            if not (args.os_tenant_id or args.os_tenant_name):
                raise exc.CommandError("You must provide a tenant_id via"
                        " either --os-tenant-id or via env[OS_TENANT_ID]")

            if not args.os_auth_url:
                raise exc.CommandError("You must provide an auth url via"
                        " either --os-auth-url or via env[OS_AUTH_URL]")
            kwargs = {
                'username': args.os_username,
                'password': args.os_password,
                'tenant_id': args.os_tenant_id,
                'tenant_name': args.os_tenant_name,
                'auth_url': args.os_auth_url,
                'service_type': args.os_service_type,
                'endpoint_type': args.os_endpoint_type,
                'insecure': args.insecure
            }
            _ksclient = self._get_ksclient(**kwargs)
            token = args.os_auth_token or _ksclient.auth_token

            endpoint = args.os_traffic_url or \
                    self._get_endpoint(_ksclient, **kwargs)

        kwargs = {
            'token': token,
            'insecure': args.insecure,
            'timeout': args.timeout,
            'ca_file': args.ca_file,
            'cert_file': args.cert_file,
            'key_file': args.key_file,
            'ssl_compression': args.ssl_compression
        }

        client = trafficclient.Client(api_version, endpoint, **kwargs)

        try:
            args.func(client, args)
        except exc.Unauthorized:
            raise exc.CommandError("Invalid OpenStack Identity credentials.")

    @utils.arg('command', metavar='<subcommand>', nargs='?',
               help='Display help for <subcommand>')
    def do_help(self, args):
        """
        Display help about this program or one of its subcommands.
        """
        if getattr(args, 'command', None):
            if args.command in self.subcommands:
                self.subcommands[args.command].print_help()
            else:
                raise exc.CommandError("'%s' is not a valid subcommand" %
                                       args.command)
        else:
            self.parser.print_help()


class HelpFormatter(argparse.HelpFormatter):
    def start_section(self, heading):
        # Title-case the headings
        heading = '%s%s' % (heading[0].upper(), heading[1:])
        super(HelpFormatter, self).start_section(heading)


def main():
    try:
        OpenstackTrafficShell().main(sys.argv[1:])

    except Exception, e:
        print >> sys.stderr, e
        sys.exit(1)


        
