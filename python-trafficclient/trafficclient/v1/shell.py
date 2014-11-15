
import argparse
import os
import copy
import sys
from trafficclient import utils
from trafficclient import exceptions

if os.name == 'nt':
    import msvcrt
else:
    msvcrt = None
    
from trafficclient import exc
from trafficclient.common import utils
import trafficclient.v1

@utils.arg('--instance',
     default=None,
     metavar='<instance>',
     help="Instance ID (see 'nova list').")
@utils.arg('--band',
     metavar='<band>',
     help="the network band of the instance")
@utils.arg('--prio',
    default=None,
    metavar='<prio>',
    help="the priority of this traffic controll.")
def do_create(cs, args):
    
    if not args.band:
        raise exceptions.CommandError("you need to specify a band ")
    if not args.instance:
        raise exceptions.CommandError('you need to specify a instance ID')
    cs.traffic.create(args.instance, args.band)

@utils.arg('--instance',
    default=None,
    metavar='<instance>',
    help="The ID of the instance to delete.")
def do_delete(cs, args):
    cs.traffic.delete(cs, args)

def do_list(cs, args):
    id_col = 'ID'
    columns = [id_col, 'Name', 'Status', 'Networks']
    utils.print_list(cs.traffic.list(cs, args), columns,
                     sortby_index=1)

@utils.arg('--instance',
    default=None,
    metavar='<instance>',
    help="The ID of the instance to delete.")
def do_show(cs, args):
    cs.traffic.show(cs, args)

