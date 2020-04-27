from math import log
from ipaddress import ip_network

import boto3


def launch_ami_like_instance(
    ami_id, model_id, count=1, copy_tags={}, b3_session=None, **kwargs
):
    """
    Start a new instance from the specified AMI, copying the settings
    (instance type, subnet, security groups, etc.) of another instance.

    Args:
        ami_id: ID of AMI to use for the new instance
        model_id: launch new instances in this one's likeness
        count: number of instances to start
        copy_tags: dictionary, optional.
            {
                'CopyTags': True|False,
                'SetTags': [
                    {
                        'Key': 'string',
                        'Value': 'string'
                    }
                ]
            }
            If CopyTags is True, tags present on model instance will
            also be set on the new ones. Tags present in SetTags will
            also be set. Tags from SetTags will overwrite the ones
            coppied from the model instance if they have the same key.
            If the parameter receives any other values in the
            dictionary, it will ignore them.
        b3_session: Boto3 Session object. If passed to the function, boto3
            clients and resources will be based off it, otherwise the
            default session will be used.
        kwargs: any additional parameters will be passed to the boto3
            function ec2.create_instances() directly. Primary use would
            probably be to specify ClientToken or PrivateIpAddress.
            See https://boto3.readthedocs.io/en/latest/reference/services/
                ec2.html#EC2.ServiceResource.create_instances
            and https://docs.aws.amazon.com/AWSEC2/latest/APIReference/
                Run_Instance_Idempotency.html
            The following parameters can't be used in kwargs:
                ImageId
                InstanceType
                KeyName
                MaxCount
                MinCount
                Monitoring
                SecurityGroupIds
                SubnetId
                EbsOptimized
                IamInstanceProfile

    Returns:
        list of instance IDs that are being created
    """
    if b3_session:
        ec2 = b3_session.resource("ec2")
    else:
        ec2 = boto3.resource("ec2")
    ec2_model = ec2.Instance(model_id)
    # Copy tags
    if "SetTags" in copy_tags:
        tags_to_set = copy_tags["SetTags"]
        tag_keys_to_set = [tag["Key"] for tag in copy_tags["SetTags"]]
        tags_to_copy = [
            tag for tag in ec2_model.tags if tag["Key"] not in tag_keys_to_set
        ]
    else:
        tags_to_set = []
        tags_to_copy = ec2_model.tags
    if copy_tags["CopyTags"]:
        tag_spec = [{"Tags": tags_to_copy + tags_to_set}]
    else:
        tag_spec = [{"Tags": tags_to_set}]
    tag_spec[0]["ResourceType"] = "instance"
    # Not coppied, can be passed on through kwargs
    #   DisableApiTermination
    #   InstanceInitiatedShutdownBehavior
    #   NetworkInterfaces
    #   InstanceMarketOptions
    #   CreditSpecification
    #   CpuOptions
    instance_role = {}
    if ec2_model.iam_instance_profile is not None:
        instance_role["Arn"] = ec2_model.iam_instance_profile["Arn"]
        # instance_role['Name'] = ec2_model.iam_instance_profile['Arn'][
        #         ec2_model.iam_instance_profile['Arn'].rfind('/') + 1:]
    new_instances = ec2.create_instances(
        ImageId=ami_id,
        InstanceType=ec2_model.instance_type,
        KeyName=ec2_model.key_pair.key_name,
        MaxCount=count,
        MinCount=count,
        Monitoring={"Enabled": ec2_model.monitoring["State"] == "enabled"},
        SecurityGroupIds=[gid["GroupId"] for gid in ec2_model.security_groups],
        SubnetId=ec2_model.subnet_id,
        EbsOptimized=ec2_model.ebs_optimized,
        IamInstanceProfile=instance_role,
        TagSpecifications=tag_spec,
        **kwargs
    )
    return new_instances


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
        raise ValueError("Number of subnets must be a power of 2")
    if b3_session:
        ec2 = b3_session.client("ec2", region_name=region)
    else:
        ec2 = boto3.client("ec2", region_name=region)
    azs = list()
    for az in ec2.describe_availability_zones()["AvailabilityZones"]:
        azs.append(az["ZoneName"])
    snets = list(ip_network(net).subnets(prefixlen_diff=int(log(subnets, 2))))
    net_split = list()
    for index, subnet in enumerate(snets):
        az = azs[index % len(azs)]
        net_split.append({"cidr": subnet.with_prefixlen, "az": az})

    return net_split
