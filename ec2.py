from math import log
from ipaddress import ip_network

import boto3


def split_net_across_zones(net, region, subnets=4, b3_session=None):
    """
    Split a network into subnets across availability zones.

    Args:
        net: Network to be split. Will be passed to Python's 'ipaddress'
            module, so must be in a format accepted by it. Standard CIDR
            notation ('192.168.1.0/24') is valid.
        region: AWS region, string.
        subnets: Number of subnets the network should be split into. Must be
            a power of 2. If not specified it will default to 4 because 3 is
            the minimum number for high availability.
        b3_session: Boto3 Session object. If passed to the function, boto3
            clients and resources will be based off it, otherwise the
            default session will be used.

    Returns:
        A list of dictionaries mapping subnets to region. Example:
            [{'cidr': '192.168.1.0/25',
              'az': 'eu-west-1a'},
             {'cidr': '192.168.1.128/25',
              'az': eu-west-1b'}]
        It will try to cover all zones and cycle back to the first one if
        more subnets are specified than available zones
    """
    # Check that subnets is a power of 2
    if not (not subnets & (subnets - 1) and subnets and type(subnets) is int):
        raise ValueError('Number of subnets must be a power of 2')
    if b3_session:
        ec2 = b3_session.client('ec2', region_name=region)
    else:
        ec2 = boto3.client('ec2', region_name=region)
    azs = list()
    for az in ec2.describe_availability_zones()['AvailabilityZones']:
        azs.append(az['ZoneName'])
    snets = list(ip_network(net).subnets(prefixlen_diff=int(log(subnets, 2))))
    net_split = list()
    for index, subnet in enumerate(snets):
        az = azs[index % len(azs)]
        net_split.append({
            "cidr": subnet.with_prefixlen,
            "az": az})

    return net_split
