import re


def alphanum(string):
    """Remove non-alphanumeric characters

    Deletes all characters that are not a letter or number from a given
    string and capitalizes the letter following said character.

    For example, "my_subnet_in_eu-west-1a!" becomes "mySubnetInEuWest1a".

    Main use could be Logical IDs in CloudFormation

    Args:
        string: string to transform

    Returns:
        string
    """
    m = re.search('[\W_]', string)
    while m is not None:
        if m.start() == 0:
            string = string[1:]
        elif m.start() == len(string) - 1:
            string = string[:-1]
        else:
            string = string[:m.start()] + string[m.end():].capitalize()
        m = re.search('[\W_]', string)

    return string
